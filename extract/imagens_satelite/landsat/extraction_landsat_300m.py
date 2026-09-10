"""Teste paralelo: mesma amostra de referência, mesmos anos, mas imagem MENOR
(buffer_m=150 -> 300m x 300m, em vez dos 500m x 500m padrão de `extraction_landsat.py`).

Existe pra testar uma hipótese que apareceu na calibração do modelo de 500m: pra vários
sites, a % de "Construção" nunca cai de um valor alto em NENHUM ano da série (ver
observação "Possível área já urbanizada" no Calibrador de Obra) — hipótese é que a caixa de
500m está pegando o entorno urbano já construído (via, terreno vizinho), não só o prédio do
data center. Uma caixa menor, mais colada no prédio, deveria reduzir essa contaminação — mas
também sobra menos pixel de contexto e a imagem fica mais sensível a erro de
georreferenciamento do ponto. Esse script só existe pra comparar os dois, não substitui o de
500m.

Grava numa pasta separada (`data/raw/imagens_satelite_landsat_300m`) — não sobrescreve nada
do fluxo de 500m. Ver `config_obra_300m.py`/`step_classificacao_obra_300m.py`/
`deteccao_fases_obra_300m.py` pro resto do fluxo paralelo.
"""
import os
from pathlib import Path

import ee
import pandas as pd
from dotenv import load_dotenv

from extracao_imagem_landsat import extract_datacenter_timeseries_landsat

# --- Carrega o .env pro ambiente do processo ---
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / '.env'
load_dotenv(ENV_PATH)

# --- Autenticação/inicialização do Earth Engine (uma vez por sessão) ---
ee.Authenticate()
PROJECT_ID = os.environ.get('PROJECT_ID')
if not PROJECT_ID:
    raise RuntimeError(
        f"PROJECT_ID não encontrado em {ENV_PATH}. Confira se o arquivo existe e "
        "tem a linha PROJECT_ID=seu-projeto-aqui."
    )
ee.Initialize(project=PROJECT_ID)

# --- Mesma amostra de referência do fluxo de 500m ---
CSV_PATH = ROOT_DIR / 'data/silver/datacenters_referencia.csv'
df = pd.read_csv(CSV_PATH, sep=';')

YEAR_LIST = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
BUFFER_M = 150  # raio -> quadrado de 2*150 = 300m de lado (era 250 -> 500m)
OUT_DIR = ROOT_DIR / 'data/raw/imagens_satelite_landsat_300m'

# --- Loop: uma extração por linha do DataFrame ---
metadata_paths = []
erros = []

for _, row in df.iterrows():
    name = row['nome_datacenter']
    lat = row['latitude']
    lon = row['longitude']

    print(f'\n=== Extraindo {name} (lat={lat}, lon={lon}), buffer {BUFFER_M*2}m ===')

    try:
        metadata_path = extract_datacenter_timeseries_landsat(
            name_datacenter=name,
            lat=lat,
            lon=lon,
            year_list=YEAR_LIST,
            buffer_m=BUFFER_M,
            out_dir=OUT_DIR,
        )
        metadata_paths.append(metadata_path)
    except Exception as e:
        print(f'[{name}] ERRO: {e}')
        erros.append((name, str(e)))

# --- Resumo final ---
print(f'\n{len(metadata_paths)}/{len(df)} pontos extraídos com sucesso.')
if erros:
    print(f'{len(erros)} pontos falharam:')
    for name, msg in erros:
        print(f'  - {name}: {msg}')
