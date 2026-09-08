"""Índices espectrais usados como features na classificação (`classification.py`, Step 2).

ATENÇÃO: este arquivo não fazia parte do código migrado de `notebooks_antigos/` — o notebook
original (`step2_classificacao_imagens.ipynb`) já importava `from src.indices import
load_features`, mas o módulo `indices.py` em si nunca chegou a ser trazido pra este repositório.
As fórmulas abaixo são as fórmulas padrão de sensoriamento remoto pra cada índice (as mesmas
citadas no docstring do notebook: NDVI, NDWI, NDBI, EVI, SAVI, BSI, MNDWI, IBI, NDMI) — mas
como o original não está disponível pra comparar, vale conferir se batem com o que foi usado
pra treinar/validar os modelos já existentes antes de reusar em produção.

Bandas Sentinel-2 exportadas pelo Step 1 (`extraction.py`), sempre nessa ordem:
B2 (azul), B3 (verde), B4 (vermelho), B8 (NIR), B11 (SWIR1), B12 (SWIR2).
"""
import numpy as np
import rasterio

L_SAVI = 0.5  # fator de ajuste de brilho do solo (Huete, 1988) — 0.5 é o valor mais comum

INDICE_NOMES = ['NDVI', 'NDWI', 'NDBI', 'EVI', 'SAVI', 'BSI', 'MNDWI', 'IBI', 'NDMI']


def _safe_div(numerador, denominador):
    """Divisão que devolve 0 (em vez de inf/NaN) onde o denominador é 0."""
    with np.errstate(divide='ignore', invalid='ignore'):
        resultado = np.true_divide(numerador, denominador)
    resultado[~np.isfinite(resultado)] = 0.0
    return resultado


def compute_indices(bandas: dict) -> dict:
    """Calcula os índices espectrais a partir de um dicionário {nome_da_banda: array}.

    `bandas` precisa ter, no mínimo, as chaves B2, B3, B4, B8, B11 (B12 não é usado por
    nenhum índice abaixo, mas continua indo pro feature_stack como banda crua).
    """
    blue, green, red, nir, swir1 = bandas['B2'], bandas['B3'], bandas['B4'], bandas['B8'], bandas['B11']

    ndvi = _safe_div(nir - red, nir + red)
    ndwi = _safe_div(green - nir, green + nir)
    ndbi = _safe_div(swir1 - nir, swir1 + nir)
    evi = 2.5 * _safe_div(nir - red, nir + 6 * red - 7.5 * blue + 1)
    savi = _safe_div(nir - red, nir + red + L_SAVI) * (1 + L_SAVI)
    bsi = _safe_div((swir1 + red) - (nir + blue), (swir1 + red) + (nir + blue))
    mndwi = _safe_div(green - swir1, green + swir1)
    ibi = _safe_div(ndbi - (savi + mndwi) / 2, ndbi + (savi + mndwi) / 2)
    ndmi = _safe_div(nir - swir1, nir + swir1)

    return {
        'NDVI': ndvi, 'NDWI': ndwi, 'NDBI': ndbi, 'EVI': evi, 'SAVI': savi,
        'BSI': bsi, 'MNDWI': mndwi, 'IBI': ibi, 'NDMI': ndmi,
    }


def load_features(tif_path, band_names):
    """Lê um GeoTIFF Sentinel-2 e devolve (feature_stack, nodata_mask).

    feature_stack: array (n_bands_cruas + n_indices, H, W) — as bandas cruas na ordem de
    `band_names`, seguidas dos índices espectrais (`INDICE_NOMES`), nessa ordem.
    nodata_mask: array booleano (H, W), True onde o pixel não tem dado válido (todas as
    bandas cruas zeradas — como os GeoTIFFs são recortados num buffer quadrado ao redor do
    ponto, sempre sobra alguma borda fora da região exportada pelo Earth Engine).
    """
    with rasterio.open(tif_path) as src:
        raw = src.read()  # (n_bands, H, W), na ordem de band_names

    bandas = {nome: raw[i] for i, nome in enumerate(band_names)}
    nodata_mask = np.all(raw == 0, axis=0)

    indices = compute_indices(bandas)
    indices_stack = np.stack([indices[nome] for nome in INDICE_NOMES], axis=0)

    feature_stack = np.concatenate([raw, indices_stack], axis=0)
    return feature_stack, nodata_mask


def nomes_features(band_names):
    """Nomes de cada camada de `feature_stack`, na mesma ordem — útil pra rotular
    importância de features."""
    return list(band_names) + INDICE_NOMES
