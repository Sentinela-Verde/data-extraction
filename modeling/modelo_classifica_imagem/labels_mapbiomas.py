"""Exporta e cacheia rótulos MapBiomas pra usar como semente de treino em
`classification_obra.py`, no lugar (ou além) do limiar espectral — sobretudo pra
solo exposto/construção, que é onde o limiar espectral mais erra.

Por que MapBiomas e não ESA WorldCover (usado em `classification.py`, Step 2 original):
WorldCover é um retrato ESTÁTICO (~2020/2021) do mundo — inválido pra rotular todos os anos
de um site que está mudando de vegetação pra construção. O MapBiomas classifica o Brasil
ANO A ANO desde 1985 (`projects/mapbiomas-public/assets/brazil/lulc/v1`, banda
`classification`, propriedade `year`), resolvendo exatamente esse problema — o rótulo de
2018 é o mapa de 2018, não uma foto de outro ano forçada a servir pra ele.

Limitações honestas:
- Só cobre até `ULTIMO_ANO_DISPONIVEL` — anos depois disso (2025/2026 na sua série) não têm
  MapBiomas ainda; o treino cai de volta pro rótulo-semente espectral
  (`classification_obra.seed_labels_from_indices`) só pra esses anos.
- 30m de resolução (igual ao Landsat), então erro de borda/pixel misto do MapBiomas se
  soma ao seu próprio recorte — não é um "gabarito perfeito", é uma segunda opinião melhor
  que threshold cru.
- Os códigos de classe abaixo são da legenda da Coleção 9 (ago/2024) — a legenda é mantida
  estável entre coleções, mas vale conferir contra a coleção que estiver rodando se os
  resultados vierem estranhos: https://brasil.mapbiomas.org/codigos-de-legenda/
"""
import os

import ee
import geemap
import numpy as np
import rasterio

from classification_obra import CONSTRUCAO, GRAMA, SEM_DADO, SOLO_EXPOSTO, VEGETACAO_DENSA

MAPBIOMAS_COLLECTION = 'projects/mapbiomas-public/assets/brazil/lulc/v1'
ULTIMO_ANO_DISPONIVEL = 2024  # cobertura do dataset vai até 2024 (checar no catálogo do GEE)

# Códigos da legenda MapBiomas Coleção 9 -> classes do projeto.
CODIGOS_VEGETACAO_DENSA = {1, 3, 4, 5, 6, 49}    # Floresta (formação florestal/savânica/
                                                   # mangue/alagável/restinga arbórea)
CODIGOS_GRAMA = {12, 15}                          # Formação Campestre + Pastagem
CODIGOS_CONSTRUCAO = {24}                         # Área Urbanizada
CODIGOS_SOLO_EXPOSTO = {23, 25, 30}               # Praia/Duna/Areal + Outras Áreas não
                                                   # Vegetadas + Mineração
# Tudo mais (água, agricultura, silvicultura etc.) fica SEM_DADO — não é um dos 4 casos que
# esse projeto classifica, então não vira semente nem positiva nem negativa.


def mapbiomas_disponivel(ano):
    return ano <= ULTIMO_ANO_DISPONIVEL


def mapbiomas_label_path(name_datacenter, ano, out_dir):
    return os.path.join(out_dir, f'{name_datacenter}_{ano}_mapbiomas.tif')


def exporta_label_mapbiomas(meta, ano, out_dir):
    """Exporta (ou reaproveita, se já em cache) o raster MapBiomas do ano/região de um data
    center, alinhado ao mesmo buffer/escala do GeoTIFF Landsat — pra ficar pixel-a-pixel
    comparável com `build_feature_stack_obra`."""
    os.makedirs(out_dir, exist_ok=True)
    caminho = mapbiomas_label_path(meta['name_datacenter'], ano, out_dir)
    if os.path.exists(caminho):
        return caminho

    colecao = (
        ee.ImageCollection(MAPBIOMAS_COLLECTION)
        .filter(ee.Filter.eq('year', ano))
        .sort('collection_id', False)  # pega a coleção/reprocessamento mais recente pro ano
    )
    imagem = ee.Image(colecao.first()).select('classification')

    center_point = ee.Geometry.Point([meta['lon'], meta['lat']])
    region = center_point.buffer(meta['buffer_m']).bounds()

    geemap.ee_export_image(
        imagem, filename=caminho, scale=meta['scale'], region=region, file_per_band=False,
    )
    return caminho


def carrega_seed_mapbiomas(caminho_tif, nodata_mask):
    """Lê o raster MapBiomas já exportado e remapeia pros 4 códigos internos do projeto
    (0-3), com SEM_DADO pra qualquer classe fora do mapeamento (água, agricultura etc.) ou
    nodata."""
    with rasterio.open(caminho_tif) as src:
        raw = src.read(1)

    labels = np.full(raw.shape, SEM_DADO, dtype=np.uint8)
    for codigo in CODIGOS_VEGETACAO_DENSA:
        labels[raw == codigo] = VEGETACAO_DENSA
    for codigo in CODIGOS_GRAMA:
        labels[raw == codigo] = GRAMA
    for codigo in CODIGOS_CONSTRUCAO:
        labels[raw == codigo] = CONSTRUCAO
    for codigo in CODIGOS_SOLO_EXPOSTO:
        labels[raw == codigo] = SOLO_EXPOSTO

    labels[nodata_mask] = SEM_DADO
    return labels


def seed_labels_hibrido(meta, ano, feature_stack, nodata_mask, indices, labels_dir, seed_espectral_fn):
    """Combina MapBiomas (quando disponível) com o rótulo-semente espectral: usa MapBiomas
    como fonte principal (rótulo real, não heurística) e preenche com o espectral só onde o
    MapBiomas não tem opinião (classe fora do mapeamento, ex: água/agricultura) ou onde o
    ano não tem MapBiomas ainda (2025/2026).

    `seed_espectral_fn`: função que devolve o rótulo espectral (normalmente
    `functools.partial(seed_labels_from_indices, **limiares)`), chamada com (indices,
    nodata_mask).
    """
    seed_espectral = seed_espectral_fn(indices, nodata_mask)

    if not mapbiomas_disponivel(ano):
        return seed_espectral, 'espectral (MapBiomas indisponível pra esse ano)'

    caminho_mb = exporta_label_mapbiomas(meta, ano, labels_dir)
    seed_mb = carrega_seed_mapbiomas(caminho_mb, nodata_mask)

    combinado = np.where(seed_mb != SEM_DADO, seed_mb, seed_espectral)
    return combinado, 'MapBiomas + espectral (preenchimento)'
