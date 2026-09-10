"""Config do fluxo PARALELO de teste com imagem menor (300m x 300m, em vez dos 500m x 500m
de `config_obra.py`) — ver docstring de `extract/imagens_satelite/landsat/extraction_landsat_300m.py`
pro porquê.

Mesma estrutura de `config_obra.py`, só que todo caminho de saída tem sufixo `_300m`, pra não
encostar em nada do fluxo de 500m — dá pra rodar os dois e comparar os resultados sem um
sobrescrever o outro.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RAIZ_PROJETO = BASE_DIR.parent.parent

ENV_PATH = RAIZ_PROJETO / ".env"

# --- Entrada -------------------------------------------------------------
# GeoTIFFs Landsat (300m) + metadata.json gerados por
# extract/imagens_satelite/landsat/extraction_landsat_300m.py.
RAW_DIR = RAIZ_PROJETO / "data" / "raw" / "imagens_satelite_landsat_300m"

REFERENCIA_CSV = RAIZ_PROJETO / "data" / "silver" / "datacenters_referencia.csv"

# --- Saída -----------------------------------------------------------------
PROCESSED_DIR = RAIZ_PROJETO / "data" / "silver" / "cobertura_obra_300m"
OVERLAYS_DIR = RAIZ_PROJETO / "data" / "raw" / "imagens_satelite_landsat_300m_overlay"
MODEL_PATH = RAIZ_PROJETO / "data" / "models" / "rf_obra_landsat_300m.joblib"

USAR_MAPBIOMAS = True
MAPBIOMAS_LABELS_DIR = RAIZ_PROJETO / "data" / "raw" / "labels_mapbiomas_300m"

# --- Limiares dos rótulos-semente ------------------------------------------
# Ponto de partida = os mesmos valores já calibrados no fluxo de 500m. Como a caixa é menor
# (menos pixel de contexto por imagem), pode precisar recalibrar de novo — não assuma que o
# que funcionou pra 500m vale igual aqui.
NDVI_VEGETACAO_DENSA = 0.6
SAVI_VEGETACAO_DENSA = 0.5
NDVI_GRAMA_MIN = 0.35
NDVI_NAO_VEGETACAO = 0.2
NDBI_CONSTRUCAO = 0.0
BSI_SOLO_EXPOSTO = 0.1
REDNESS_SOLO_EXPOSTO = 0.03

# --- Parâmetros de treino ----------------------------------------------------
N_SAMPLES_PER_CLASS = 3000   # com só 9 sites x 11 anos x ~100px (300m/30m)², provavelmente
                              # nem chega nesse teto pra toda classe — balancear_amostras já
                              # lida com isso sozinho (usa o que tiver disponível).
TEST_SIZE = 0.25
RANDOM_STATE = 42

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
MAPBIOMAS_LABELS_DIR.mkdir(parents=True, exist_ok=True)
