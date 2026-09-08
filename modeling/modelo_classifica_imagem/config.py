"""Configurações da classificação de cobertura do solo. Mude aqui, não dentro do step."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# raiz de data-extraction/, dois níveis acima de modeling/modelo_classifica_imagem/
RAIZ_PROJETO = BASE_DIR.parent.parent

ENV_PATH = RAIZ_PROJETO / ".env"

# --- Entrada -----------------------------------------------------------
# GeoTIFFs + metadata.json gerados por extract/imagens_satelite/step1.
RAW_DIR = RAIZ_PROJETO / "data" / "raw" / "imagens_satelite"

# --- Rótulos de referência ---------------------------------------------
LABELS_DIR = RAIZ_PROJETO / "data" / "raw" / "labels"

# --- Saída ---------------------------------------------------------------
PROCESSED_DIR = RAIZ_PROJETO / "data" / "silver" / "cobertura_solo"
OVERLAYS_DIR = RAIZ_PROJETO / "data" / "raw" / "imagens_satelite_overlay"

# --- Parâmetros do treino -------------------------------------------------
# Ano usado pra rotular (WorldCover + malha viária) e treinar o classificador; os anos
# restantes da série (config em extract/imagens_satelite) são só classificados, não treinados.
REFERENCE_YEAR = 2024
ROAD_BUFFER_M = 4          # largura da via rasterizada a partir do eixo do OpenStreetMap
N_SAMPLES_PER_CLASS = 3000  # pixels de treino amostrados por classe
TEST_SIZE = 0.25
RANDOM_STATE = 42

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
