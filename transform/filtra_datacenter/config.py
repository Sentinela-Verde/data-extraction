"""Configurações do filtro de data centers. Mude aqui, não dentro do step."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# raiz de data-extraction/, dois níveis acima de transform/filtra_datacenter/
RAIZ_PROJETO = BASE_DIR.parent.parent

# --- Entrada -----------------------------------------------------------
# Saída de extract/scraping_datacentermap/ (ver README da raiz desse repo).
INPUT_CSV = RAIZ_PROJETO / "data" / "raw" / "outputs_extraction" / "datacentermap_datacenters.csv"

# --- Saída ---------------------------------------------------------------
# Consumida por modeling/modelo_grupo_controle/ e extract/imagens_satelite/.
OUTPUT_DIR = RAIZ_PROJETO / "data" / "silver"
OUTPUT_CSV = OUTPUT_DIR / "datacenter_filtrado.csv"

# --- Critérios do filtro ---------------------------------------------------
# Ver célula "Definição do Range de dados do facility" do notebook original:
# considera-se uma janela móvel de 4 anos ao redor da abertura do data center
# (ano0, ano+1, ano-1, ano-2, ano-3), por isso os limites abaixo.
STATUS_ATIVO = 1        # datacenter em operação (coluna `status` do datacentermap)
STAGE_ALVO = 2          # coluna `stage` do datacentermap (facility já construído/operacional)
ANO_OPERACIONAL_MIN = 2017  # exclui: amostra ficaria muito distante do período de estudo
ANO_OPERACIONAL_MAX = 2025  # exclui: precisa sobrar pelo menos 2026 como ano de referência pós-obra
TIPO_LISTAGEM_ALVO = 'Facility' # coluna `tipo_listagem` do datacentermap (exclui: "Campus", "Multi-Tenant Building")

# Colunas mantidas no CSV final (identificação + porte, sem os campos de
# certificação/segurança que não são usados nas etapas seguintes).
COLUNAS_FINAIS = [
    "nome_datacenter", "endereco", "cidade", "latitude", "longitude", "tags", 
    "mw_construido", "whitespace_construido_m", 
    "ano_operacional", "tipo_construcao",
]

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
