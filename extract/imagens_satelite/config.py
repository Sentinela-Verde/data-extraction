"""Configurações da extração de imagens de satélite. Mude aqui, não dentro do step."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# raiz de data-extraction/, dois níveis acima de extract/imagens_satelite/
RAIZ_PROJETO = BASE_DIR.parent.parent

FONTE = "imagens_satelite"  # nome dessa coleta, usado na pasta de dado bruto

# --- Entrada -----------------------------------------------------------
# Saída de transform/filtra_datacenter/ (nome_datacenter, latitude, longitude, ...).
DATACENTERS_CSV = RAIZ_PROJETO / "data" / "silver" / "datacenter_filtrado.csv"

# --- Earth Engine -----------------------------------------------------------
# Projeto do Google Cloud usado pra autenticar no Earth Engine — vem do .env
# na raiz do repo (ver .env.example). Nunca comitar o .env.
ENV_PATH = RAIZ_PROJETO / ".env"

# --- Saída (dado bruto = cache) ---------------------------------------------
# Um GeoTIFF por (data center, ano) + um metadata.json por data center,
# compartilhado entre coletores em data/raw/<fonte>/.
RAW_DIR = RAIZ_PROJETO / "data" / "raw" / FONTE
JPG_DIR = RAIZ_PROJETO / "data" / "raw" / f"{FONTE}_jpg"  # composições RGB, só pra inspeção visual

# --- Parâmetros da extração --------------------------------------------
# Série cobrindo alguns anos antes e depois da janela de abertura aceita em
# transform/filtra_datacenter (2018-2024) — dá margem pra nível/tendência
# pré-obra e para os horizontes pós-obra usados em modeling/modelo_impacto/.
YEAR_LIST = list(range(2016, 2027))  # 2016..2026
MONTH_START = "05-01"   # início da janela de meses considerada em cada ano (seca no SE/CO/S)
MONTH_END = "07-30"     # fim da janela — período historicamente mais livre de nuvens
CLOUD_PCT = 5           # % máxima de cobertura de nuvem por granule (CLOUDY_PIXEL_PERCENTAGE)
BUFFER_M = 3000         # raio do buffer ao redor do ponto -> ~6km x 6km de região exportada
SCALE = 10              # resolução espacial da exportação, em metros/pixel

RAW_DIR.mkdir(parents=True, exist_ok=True)
JPG_DIR.mkdir(parents=True, exist_ok=True)
