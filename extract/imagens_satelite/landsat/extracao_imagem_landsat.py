"""Step 1 — extração da série temporal Landsat via Google Earth Engine.
 
Equivalente ao script Sentinel-2, mas usando Landsat Collection 2 Level 2 (Surface
Reflectance), combinando Landsat 8 e Landsat 9. Reaproveitável do mesmo jeito: basta
chamar `extract_datacenter_timeseries_landsat` para cada ponto (data center, sítio de
controle, etc.).
 
Principais diferenças em relação ao Sentinel-2:
- Coleções: 'LANDSAT/LC08/C02/T1_L2' + 'LANDSAT/LC09/C02/T1_L2' (mescladas com `.merge`).
- Bandas óticas SR precisam de fator de escala (multiply 0.0000275, add -0.2) para virar
  refletância de superfície (0-1).
- Máscara de nuvem usa a banda `QA_PIXEL` (bits: dilated cloud, cirrus, cloud, cloud
  shadow), em vez da `QA60` do Sentinel-2.
- Filtro de nuvem por cena usa a propriedade `CLOUD_COVER` (não `CLOUDY_PIXEL_PERCENTAGE`).
- Resolução nativa das bandas óticas é 30m (vs 10m/20m do Sentinel-2).
 
Para manter `tif_to_rgb`/`export_rgb_jpgs` funcionando sem alteração, as bandas são
exportadas na mesma ordem "espectral" usada no script Sentinel-2 (azul, verde, vermelho,
NIR, SWIR1, SWIR2):
    Sentinel-2: B2, B3, B4, B8, B11, B12
    Landsat:    SR_B2, SR_B3, SR_B4, SR_B5, SR_B6, SR_B7
"""
import json
import os
 
import ee
import geemap
import numpy as np
import rasterio
 
DEFAULT_BANDS = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
 
# Valor por padrão só usado se a função for chamada sem `out_dir` explícito.
RAW_DIR = 'data/raw'
 
 
def mask_scale_landsat(image):
    """Aplica máscara de nuvem/sombra/cirrus (via QA_PIXEL) e o fator de escala das
    bandas óticas de refletância de superfície (Collection 2 Level 2).
 
    Args:
        image (ee.Image): Uma imagem Landsat C2 L2 (LC08 ou LC09).
 
    Returns:
        ee.Image: Imagem com bandas SR_* já em refletância (0-1) e mascarada.
    """
    qa = image.select('QA_PIXEL')
 
    # Bits da QA_PIXEL (Collection 2): 1=dilated cloud, 2=cirrus, 3=cloud, 4=cloud shadow.
    dilated_cloud_bit_mask = 1 << 1
    cirrus_bit_mask = 1 << 2
    cloud_bit_mask = 1 << 3
    cloud_shadow_bit_mask = 1 << 4
 
    mask = (
        qa.bitwiseAnd(dilated_cloud_bit_mask)
        .eq(0)
        .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
        .And(qa.bitwiseAnd(cloud_bit_mask).eq(0))
        .And(qa.bitwiseAnd(cloud_shadow_bit_mask).eq(0))
    )
 
    # Fator de escala oficial das bandas SR_* da Collection 2 Level 2.
    optical_bands = image.select('SR_B.').multiply(0.0000275).add(-0.2)
 
    return image.addBands(optical_bands, None, True).updateMask(mask)
 
 
def extract_datacenter_timeseries_landsat(
    name_datacenter,
    lat,
    lon,
    year_list,
    month_start='04-01',
    month_end='08-30',
    cloud_pct=10,
    buffer_m=250,
    scale=30,
    bands=None,
    out_dir=RAW_DIR,
):
    """Extrai, para cada ano de `year_list`, um compósito Landsat (média, Landsat 8+9)
    em torno de (lat, lon), exporta um GeoTIFF por ano em `out_dir` e salva um
    `metadata.json` com os parâmetros usados.
 
    Com os defaults (buffer_m=250, scale=30) a imagem exportada cobre uma área de
    ~500m x 500m (o `.buffer(buffer_m).bounds()` de um círculo de raio 250m já é um
    quadrado de 500m de lado), o que a 30m de resolução dá em torno de 16x16 a 17x17 pixels.
 
    Args:
        name_datacenter (str): Nome usado no nome dos arquivos exportados.
        lat, lon (float): Coordenadas do ponto central.
        year_list (list[int]): Anos para os quais gerar um compósito.
        month_start, month_end (str): Janela de datas dentro do ano, formato 'MM-DD'.
        cloud_pct (float): Filtro de `CLOUD_COVER` (% de nuvem na cena inteira) aplicado
            antes do compósito. Default 10% — mais rígido que os 20% originais, compensado
            pela janela de datas mais larga (mai-jul → abr-ago) pra ainda sobrar cena o
            suficiente sem deixar passar muita nuvem. Ajuste conforme a disponibilidade de
            cenas na sua região/período.
        buffer_m (float): Raio (m) do buffer ao redor do ponto; o bounds() do buffer vira
            um quadrado de lado 2*buffer_m. Default 250 -> quadrado de 500m.
        scale (float): Resolução (m/pixel) da exportação. Default 30 (resolução nativa
            das bandas óticas do Landsat).
        bands (list[str] | None): Bandas a exportar. Default DEFAULT_BANDS.
        out_dir (str): Diretório de saída dos GeoTIFFs e do metadata.json.
    """
    bands = bands or DEFAULT_BANDS
    os.makedirs(out_dir, exist_ok=True)
 
    for year in year_list:
        l8 = (
            ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
            .filterDate(f'{year}-{month_start}', f'{year}-{month_end}')
            .filter(ee.Filter.lt('CLOUD_COVER', cloud_pct))
        )
        l9 = (
            ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
            .filterDate(f'{year}-{month_start}', f'{year}-{month_end}')
            .filter(ee.Filter.lt('CLOUD_COVER', cloud_pct))
        )
 
        dataset = l8.merge(l9).map(mask_scale_landsat)

        # Se nenhuma cena passou no filtro de data/nuvem, `dataset.mean()` vira uma imagem
        # totalmente mascarada (sem erro nenhum) e o geemap exporta isso como um GeoTIFF
        # zerado (preto) — melhor falhar aqui com uma mensagem clara do que exportar lixo
        # silenciosamente. Custa uma chamada síncrona a mais (`.size().getInfo()`), mas só
        # roda uma vez por ano/site.
        n_cenas = dataset.size().getInfo()
        if n_cenas == 0:
            raise RuntimeError(
                f'Nenhuma cena Landsat 8/9 encontrada para {name_datacenter} em {year} '
                f'(janela {month_start} a {month_end}, CLOUD_COVER < {cloud_pct}%). '
                'Aumente cloud_pct ou amplie month_start/month_end.'
            )
 
        # Quadrado de 2*buffer_m de lado ao redor do ponto central (default: 500m x 500m).
        center_point = ee.Geometry.Point([lon, lat])
        region = center_point.buffer(buffer_m).bounds()
 
        # --- Preparar a imagem final para exportação ---
        image_to_export = dataset.mean().select(bands)
 
        # --- Baixar direto para a máquina local ---
        geemap.ee_export_image(
            image_to_export,
            filename=os.path.join(out_dir, f'{name_datacenter}_{year}.tif'),
            scale=scale,
            region=region,
            file_per_band=False,
        )
 
        print(f'[{name_datacenter} {year}] Download concluído.')
 
    # --- Salva os metadados usados, pra reaproveitar depois na classificação ---
    metadata = {
        'name_datacenter': name_datacenter,
        'lat': lat,
        'lon': lon,
        'year_list': year_list,
        'bands': bands,
        'buffer_m': buffer_m,
        'image_size_m': buffer_m * 2,
        'scale': scale,
        'crs': 'EPSG:4326',
        'sensor': 'Landsat 8/9 C2 L2 (SR)',
    }
    metadata_path = os.path.join(out_dir, f'{name_datacenter}_metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
 
    print(f'\nMetadados salvos em {metadata_path}')
    return metadata_path
 
 
def tif_to_rgb(tif_path, red_index=3, green_index=2, blue_index=1, vis_max=0.3):
    """Lê um GeoTIFF Landsat (bandas na ordem SR_B2,SR_B3,SR_B4,SR_B5,SR_B6,SR_B7) e
    devolve um array RGB (H, W, 3) já normalizado (clip 0-1) para plot com matplotlib."""
    with rasterio.open(tif_path) as src:
        # Bandas na ordem exportada: SR_B2(azul),SR_B3(verde),SR_B4(vermelho),SR_B5(NIR),
        # SR_B6(SWIR1),SR_B7(SWIR2). Para RGB "natural": vermelho=SR_B4, verde=SR_B3,
        # azul=SR_B2 -> mesmos índices default usados no script Sentinel-2.
        red = src.read(red_index)
        green = src.read(green_index)
        blue = src.read(blue_index)
 
    rgb = np.dstack([red, green, blue])
    return np.clip(rgb / vis_max, 0, 1)
 
 
def export_rgb_jpgs(pasta_entrada=RAW_DIR, pasta_saida='imagens_jpg'):
    """Converte todos os GeoTIFFs de `pasta_entrada` em composições RGB salvas como JPG em
    `pasta_saida`, para inspeção visual rápida da série temporal."""
    import matplotlib.pyplot as plt
 
    os.makedirs(pasta_saida, exist_ok=True)
 
    for nome_arquivo in sorted(os.listdir(pasta_entrada)):
        if not nome_arquivo.endswith('.tif'):
            continue
 
        path = os.path.join(pasta_entrada, nome_arquivo)
        rgb = tif_to_rgb(path)
 
        nome_saida = os.path.splitext(nome_arquivo)[0] + '.jpg'
        path_saida = os.path.join(pasta_saida, nome_saida)
 
        plt.figure(figsize=(8, 8))
        plt.imshow(rgb)
        plt.title(nome_arquivo)
        plt.axis('off')
        plt.savefig(path_saida, dpi=150, bbox_inches='tight')
        plt.close()
 
        print(f'Salvo: {path_saida}')
 