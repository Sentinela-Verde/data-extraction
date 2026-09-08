"""Step 2 — rotulagem, treino (Random Forest + rede neural) e classificação da série temporal.

Para cada data center com GeoTIFFs em `data/raw/imagens_satelite/` (gerados por
`extract/imagens_satelite/step1`):
1. Exporta rótulos de referência pro ano de `config.REFERENCE_YEAR` (ESA WorldCover +
   malha viária do OpenStreetMap).
2. Treina um Random Forest e uma rede neural densa a partir de pixels amostrados desses
   rótulos, usando bandas cruas + índices espectrais (`indices.load_features`) como features.
3. Classifica todos os anos da série (`meta['year_list']`) com os dois modelos e calcula
   % de área por classe/ano.
4. Salva a série de cobertura em CSV e as máscaras de classificação sobrepostas ao RGB.

A lógica reutilizável vive em `classification.py` (rotulagem, treino, classificação, plots) e
`indices.py` (`load_features`) — este script só orquestra, um data center por vez.

Uso:
    python step2_classificacao_imagens.py                      # roda para todos os data centers com metadata.json em data/raw/imagens_satelite/
    python step2_classificacao_imagens.py --datacenter "Ascenty - Jundiai JDI2"   # roda só para um data center

Precisa de:
- `EE_PROJECT` no `.env` da raiz do repo (usado só pra exportar o rótulo WorldCover).
"""
import argparse
import glob
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
from classification import (
    CLASS_NAMES,
    build_label_raster, classify_image, compute_class_percentages,
    export_worldcover_labels, extract_training_samples, get_road_mask,
    load_metadata, plot_mask_overlay, plot_timeseries, remap_worldcover, tif_path,
    train_neural_network, train_random_forest,
)
from indices import load_features

import ee
import pandas as pd
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split


def inicializa_earth_engine():
    load_dotenv(config.ENV_PATH)
    ee_project = os.environ.get("EE_PROJECT")
    if not ee_project:
        raise RuntimeError(
            f"Defina a variável de ambiente EE_PROJECT em {config.ENV_PATH} com o ID do seu "
            "projeto no Google Cloud (veja .env.example na raiz do repo)."
        )
    ee.Initialize(project=ee_project)


def lista_datacenters_disponiveis():
    """Um data center por `<nome_datacenter>_metadata.json` encontrado em data/raw/imagens_satelite/."""
    padrao = str(config.RAW_DIR / "*_metadata.json")
    return sorted(Path(p).name.removesuffix("_metadata.json") for p in glob.glob(padrao))


def classifica_datacenter(name_datacenter: str) -> pd.DataFrame:
    print(f"\n=== {name_datacenter} ===")

    meta = load_metadata(name_datacenter, str(config.RAW_DIR))
    band_names = meta["bands"]
    ref_tif = tif_path(name_datacenter, config.REFERENCE_YEAR, str(config.RAW_DIR))
    if not os.path.exists(ref_tif):
        print(f"  [aviso] ano de referência {config.REFERENCE_YEAR} não encontrado, pulando data center.")
        return pd.DataFrame()

    # --- Rótulos de referência (WorldCover + vias) ---
    label_path = export_worldcover_labels(meta, str(config.LABELS_DIR))
    remapped = remap_worldcover(label_path)
    road_mask = get_road_mask(ref_tif, buffer_m=config.ROAD_BUFFER_M)
    labels = build_label_raster(remapped, road_mask)

    # --- Treino ---
    feature_stack, nodata_mask = load_features(ref_tif, band_names)
    X, y = extract_training_samples(
        feature_stack, labels, nodata_mask, n_samples_per_class=config.N_SAMPLES_PER_CLASS,
    )
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, stratify=y, random_state=config.RANDOM_STATE,
    )
    rf_model = train_random_forest(X_train, y_train, X_test, y_test)
    nn_model, scaler = train_neural_network(X_train, y_train, X_test, y_test)

    # --- Classifica toda a série temporal ---
    rows = []
    for year in meta["year_list"]:
        path = tif_path(name_datacenter, year, str(config.RAW_DIR))
        if not os.path.exists(path):
            print(f"  [{year}] arquivo não encontrado, pulei.")
            continue

        fstack, nmask = load_features(path, band_names)
        classified_rf = classify_image(fstack, nmask, rf_model)
        classified_nn = classify_image(fstack, nmask, nn_model, scaler)

        pct_rf = compute_class_percentages(classified_rf)
        pct_nn = compute_class_percentages(classified_nn)

        for classe in CLASS_NAMES:
            rows.append({"name_datacenter": name_datacenter, "ano": year, "classe": classe,
                         "modelo": "Random Forest", "percentual": pct_rf[classe]["percentual"],
                         "area_km2": pct_rf[classe]["area_km2"]})
            rows.append({"name_datacenter": name_datacenter, "ano": year, "classe": classe,
                         "modelo": "Rede Neural", "percentual": pct_nn[classe]["percentual"],
                         "area_km2": pct_nn[classe]["area_km2"]})

        plot_mask_overlay(
            fstack, classified_rf, titulo=f"{name_datacenter} {year} - Random Forest", alpha=0.5,
            salvar_em=str(config.OVERLAYS_DIR / f"{name_datacenter}_{year}_overlay.jpg"),
            mostrar=False,
        )
        print(f"  [{year}] classificado.")

    df = pd.DataFrame(rows)

    plot_timeseries(
        df, name_datacenter, modelo="Random Forest",
        salvar_em=str(config.PROCESSED_DIR / f"{name_datacenter}_evolucao.png"), mostrar=False,
    )
    df.to_csv(config.PROCESSED_DIR / f"{name_datacenter}_cobertura_por_ano.csv", index=False)
    return df


def main(datacenter: str = None):
    inicializa_earth_engine()

    alvos = [datacenter] if datacenter else lista_datacenters_disponiveis()
    if not alvos:
        print(f"Nenhum *_metadata.json encontrado em {config.RAW_DIR} — rode extract/imagens_satelite antes.")
        return

    todos = [classifica_datacenter(nome) for nome in alvos]
    consolidado = pd.concat([df for df in todos if not df.empty], ignore_index=True)

    saida = config.PROCESSED_DIR / "cobertura_todos_datacenters.csv"
    consolidado.to_csv(saida, index=False)
    print(f"\n{consolidado['name_datacenter'].nunique()} data centers classificados. Consolidado em {saida}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datacenter", default=None, help="roda só para esse nome_datacenter (padrão: todos)")
    args = parser.parse_args()
    main(datacenter=args.datacenter)
