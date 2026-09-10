"""Converte os GeoTIFFs extraídos pelo `extraction_landsat.py` em JPGs (RGB) para
inspeção visual rápida.

Pasta de entrada: data/raw/imagens_satelite_landsat  (mesma usada como OUT_DIR em
`extraction_landsat.py`)
Pasta de saída:   data/raw/imagens_satelite_landsat_jpg  (irmã da pasta de entrada,
mesmo nome + sufixo "_jpg")

Como rodar (de qualquer diretório, os caminhos são resolvidos a partir da raiz do
projeto):
    python extract/imagens_satelite/landsat/converte_tif_para_jpg.py
"""
from pathlib import Path

from extracao_imagem_landsat import export_rgb_jpgs

ROOT_DIR = Path(__file__).resolve().parents[3]

TIF_DIR = ROOT_DIR / 'data/raw/imagens_satelite_landsat'
JPG_DIR = TIF_DIR.parent / f'{TIF_DIR.name}_jpg'

export_rgb_jpgs(pasta_entrada=str(TIF_DIR), pasta_saida=str(JPG_DIR))

print(f'\nJPGs salvos em: {JPG_DIR}')
