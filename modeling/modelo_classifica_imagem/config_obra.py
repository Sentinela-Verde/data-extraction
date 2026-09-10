"""Configurações da classificação de obra (vegetação densa / grama / solo exposto /
construção). Mude aqui, não dentro do step.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# raiz de data-extraction/, dois níveis acima de modeling/modelo_classifica_imagem/
RAIZ_PROJETO = BASE_DIR.parent.parent

ENV_PATH = RAIZ_PROJETO / ".env"  # usado só se USAR_MAPBIOMAS=True (precisa de PROJECT_ID)

# --- Entrada -------------------------------------------------------------
# GeoTIFFs Landsat + metadata.json gerados por extract/imagens_satelite/landsat.
RAW_DIR = RAIZ_PROJETO / "data" / "raw" / "imagens_satelite_landsat"

# Data centers de referência (ano_operacional conhecido) — usados só pra marcar o ano
# operacional no gráfico de evolução (calibração visual), não pro treino.
REFERENCIA_CSV = RAIZ_PROJETO / "data" / "silver" / "datacenters_referencia.csv"

# --- Saída -----------------------------------------------------------------
PROCESSED_DIR = RAIZ_PROJETO / "data" / "silver" / "cobertura_obra"
OVERLAYS_DIR = RAIZ_PROJETO / "data" / "raw" / "imagens_satelite_landsat_overlay"
MODEL_PATH = RAIZ_PROJETO / "data" / "models" / "rf_obra_landsat.joblib"

# Cache dos rótulos MapBiomas exportados (um GeoTIFF por data center/ano) — ver
# labels_mapbiomas.py. USAR_MAPBIOMAS=False volta a treinar só com o rótulo-semente
# espectral (precisa de EE_PROJECT no .env pra exportar; ver extract/imagens_satelite/landsat).
USAR_MAPBIOMAS = True
MAPBIOMAS_LABELS_DIR = RAIZ_PROJETO / "data" / "raw" / "labels_mapbiomas"

# --- Limiares dos rótulos-semente ------------------------------------------
# Ponto de partida (valores típicos de literatura de sensoriamento remoto), NÃO calibrado.
# Calibrar depois comparando a série de um data center cuja data real de início/fim de obra
# você já conhece — ver docstring de `classification_obra.seed_labels_from_indices`.
NDVI_VEGETACAO_DENSA = 0.6   # NDVI acima disso, com SAVI alto -> vegetação densa
SAVI_VEGETACAO_DENSA = 0.5   # SAVI acima disso (dossel fechado) -> confirma vegetação densa
NDVI_GRAMA_MIN = 0.35        # NDVI acima disso (mas não densa) -> grama/vegetação rasteira
NDVI_NAO_VEGETACAO = 0.2     # NDVI abaixo disso -> candidato a solo exposto/construção
NDBI_CONSTRUCAO = 0.0        # NDBI acima disso (e não-vegetação) -> construção
BSI_SOLO_EXPOSTO = 0.1       # BSI acima disso (e não-vegetação, não-construção) -> solo exposto
REDNESS_SOLO_EXPOSTO = 0.03  # (R-G)/(R+G) acima disso -> confirma solo exposto (avermelhado);
                              # filtra superfície clara/cinza que também tem BSI alto, mas não
                              # resolve telha cerâmica (também avermelhada) nem varia por região

# --- Parâmetros de treino ----------------------------------------------------
N_SAMPLES_PER_CLASS = 3000   # pixels de treino amostrados por classe (pool de todos os DCs/anos)
TEST_SIZE = 0.25
RANDOM_STATE = 42

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
MAPBIOMAS_LABELS_DIR.mkdir(parents=True, exist_ok=True)
