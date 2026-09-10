"""Exemplo — roda a extração Landsat para vários pontos de um DataFrame.
 
Espera um CSV/DataFrame com (pelo menos) as colunas:
    name_datacenter, lat, lon
 
Equivalente ao que o `step1_extracao_imagens_satelite.py` original faz lendo
`data/silver/datacenter_filtrado.csv` e chamando `extract_datacenter_timeseries` uma vez
por linha — aqui é a mesma ideia, só que pro Landsat.
"""
import os
from pathlib import Path
 
import ee
import pandas as pd
from dotenv import load_dotenv
 
from extracao_imagem_landsat import extract_datacenter_timeseries_landsat
 
# --- Carrega o .env pro ambiente do processo ---
# Este script fica em <raiz>/extract/imagens_satelite/landsat/, então subimos 3 níveis
# para chegar na raiz do projeto (data-extraction), onde está o .env.
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / '.env'
load_dotenv(ENV_PATH)
 
# --- Autenticação/inicialização do Earth Engine (uma vez por sessão) ---
# Na primeira vez, `ee.Authenticate()` abre um fluxo de login no navegador.
# O projeto vem da variável de ambiente PROJECT_ID (ID do projeto no Google Cloud
# com a API do Earth Engine habilitada), lida do .env acima.
ee.Authenticate()
PROJECT_ID = os.environ.get('PROJECT_ID')
if not PROJECT_ID:
    raise RuntimeError(
        f"PROJECT_ID não encontrado em {ENV_PATH}. Confira se o arquivo existe e "
        "tem a linha PROJECT_ID=seu-projeto-aqui."
    )
ee.Initialize(project=PROJECT_ID)
 
# --- Carrega o DataFrame com os pontos ---
# Teste inicial: só os data centers de referência (ano_operacional conhecido), usados pra
# calibrar os limiares do modelo (ver modeling/modelo_classifica_imagem/config_obra.py) —
# não a base filtrada inteira. Ver extract/imagens_satelite/landsat/README.md.
CSV_PATH = ROOT_DIR / 'data/silver/datacenters_referencia.csv'
df = pd.read_csv(CSV_PATH, sep=';')

# Base filtrada inteira (rodar só depois de validar/calibrar com a amostra de referência):
# CSV_PATH = ROOT_DIR / 'data/silver/datacentermap_datacenters_filtered_low.csv'
# df = pd.read_csv(CSV_PATH, sep=';')

# Exemplo alternativo, sem CSV:
# df = pd.DataFrame({
#     'name_datacenter': ['dc_01', 'dc_02', 'dc_03'],
#     'lat': [-23.5505, -22.9068, -19.9167],
#     'lon': [-46.6333, -43.1729, -43.9345],
# })

YEAR_LIST = [2016, 2017,2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
OUT_DIR = ROOT_DIR / 'data/raw/imagens_satelite_landsat'
 
# --- Loop: uma extração por linha do DataFrame ---
metadata_paths = []
erros = []
 
for _, row in df.iterrows():
    name = row['nome_datacenter']
    lat = row['latitude']
    lon = row['longitude']
 
    print(f'\n=== Extraindo {name} (lat={lat}, lon={lon}) ===')
 
    try:
        metadata_path = extract_datacenter_timeseries_landsat(
            name_datacenter=name,
            lat=lat,
            lon=lon,
            year_list=YEAR_LIST,
            out_dir=OUT_DIR,
            # buffer_m=250 e scale=30 já são o default -> imagem de 500m x 500m.
        )
        metadata_paths.append(metadata_path)
    except Exception as e:
        # Um ponto com erro (ex: sem cena Landsat limpa no período) não derruba o loop
        # inteiro — só registra e segue pros próximos.
        print(f'[{name}] ERRO: {e}')
        erros.append((name, str(e)))
 
# --- Resumo final ---
print(f'\n{len(metadata_paths)}/{len(df)} pontos extraídos com sucesso.')
if erros:
    print(f'{len(erros)} pontos falharam:')
    for name, msg in erros:
        print(f'  - {name}: {msg}')
 