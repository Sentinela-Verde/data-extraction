"""Step 1 — filtra os data centers do datacentermap para os que entram no estudo.

Lê o CSV bruto de `extract/scraping_datacentermap` (`data/raw/outputs_extraction/
datacentermap_datacenters.csv`) e aplica os critérios de elegibilidade descritos
em `config.py`: datacenter ativo, já construído (`stage`), com ano de operação
dentro da janela de estudo (2018-2024, pra sobrar pelo menos 3 anos de série de
satélite antes e depois da abertura).

Uso:
    python step1_filtra_dados.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import pandas as pd


def filtra_datacenters(df: pd.DataFrame) -> pd.DataFrame:
    mask_ativo = df["status"] == config.STATUS_ATIVO
    mask_ano_min = df["ano_operacional"] > config.ANO_OPERACIONAL_MIN
    mask_ano_max = df["ano_operacional"] < config.ANO_OPERACIONAL_MAX
    mask_stage = df["stage"] == config.STAGE_ALVO
    masK_listagem = df['tipo_listagem'] == config.TIPO_LISTAGEM_ALVO

    df_filtrado = df[mask_ativo & mask_ano_min & mask_ano_max & mask_stage & masK_listagem]
    df_filtrado = df_filtrado.reset_index(drop=True)
    df_filtrado["ano_operacional"] = df_filtrado["ano_operacional"].astype(int)
    return df_filtrado[config.COLUNAS_FINAIS]


def main():
    df = pd.read_csv(config.INPUT_CSV, sep=";", encoding="utf-8-sig", low_memory=False)
    print(f"Lidos {len(df)} data centers de {config.INPUT_CSV}")

    df_filtrado = filtra_datacenters(df)
    print(f"{len(df_filtrado)} data centers passaram no filtro (de {len(df)})")

    df_filtrado.to_csv(config.OUTPUT_CSV, sep=";", index=False, encoding="utf-8")
    print(f"Salvo em {config.OUTPUT_CSV}")


if __name__ == "__main__":
    main()
