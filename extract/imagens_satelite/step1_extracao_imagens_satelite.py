"""Step 1 — extração da série temporal Sentinel-2 via Google Earth Engine.

Para cada data center em `data/silver/datacenter_filtrado.csv` (saída de
`transform/filtra_datacenter/`), exporta um GeoTIFF por ano (`config.YEAR_LIST`) num
buffer ao redor do ponto (lat/lon), com um `metadata.json` por data center — e gera as
composições RGB em JPG da série, pra inspeção visual rápida.

A lógica reutilizável (`mask_s2_clouds`, `extract_datacenter_timeseries`, `export_rgb_jpgs`)
vive em `extraction.py` — este script só orquestra: lê a lista de pontos, chama a extração
pra cada um, e gera os JPGs no final.

Uso:
    python step1_extracao_imagens_satelite.py
    python step1_extracao_imagens_satelite.py --so-jpgs   # só regenera os JPGs a partir dos .tif já baixados

Precisa de:
- `EE_PROJECT` no `.env` da raiz do repo — projeto do Google Cloud usado pra autenticar
  no Earth Engine.
- Autenticação feita uma vez com `ee.Authenticate()` (ver comentário em `main()`).
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
from extraction import export_rgb_jpgs, extract_datacenter_timeseries

import ee
import pandas as pd
from dotenv import load_dotenv


def inicializa_earth_engine():
    load_dotenv(config.ENV_PATH)
    ee_project = os.environ.get("EE_PROJECT")
    if not ee_project:
        raise RuntimeError(
            f"Defina a variável de ambiente EE_PROJECT em {config.ENV_PATH} com o ID do seu "
            "projeto no Google Cloud (veja .env.example na raiz do repo)."
        )
    # Primeira vez rodando nesta máquina: descomente a linha abaixo, rode uma vez e
    # siga o fluxo de autenticação que abre no navegador/terminal.
    # ee.Authenticate()
    ee.Initialize(project=ee_project)


def main(so_jpgs: bool = False):
    if not so_jpgs:
        inicializa_earth_engine()

        df_datacenters = pd.read_csv(config.DATACENTERS_CSV, sep=";", encoding="utf-8-sig")
        print(f"{len(df_datacenters)} data centers em {config.DATACENTERS_CSV}")

        for _, row in df_datacenters[["nome_datacenter", "latitude", "longitude"]].iterrows():
            extract_datacenter_timeseries(
                name_datacenter=row["nome_datacenter"],
                lat=row["latitude"],
                lon=row["longitude"],
                year_list=config.YEAR_LIST,
                month_start=config.MONTH_START,
                month_end=config.MONTH_END,
                cloud_pct=config.CLOUD_PCT,
                buffer_m=config.BUFFER_M,
                scale=config.SCALE,
                out_dir=str(config.RAW_DIR),
            )

    export_rgb_jpgs(pasta_entrada=str(config.RAW_DIR), pasta_saida=str(config.JPG_DIR))
    print(f"\nJPGs de conferência em {config.JPG_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--so-jpgs", action="store_true",
        help="pula o Earth Engine e só regenera os JPGs a partir dos .tif já baixados em data/raw/",
    )
    args = parser.parse_args()
    main(so_jpgs=args.so_jpgs)
