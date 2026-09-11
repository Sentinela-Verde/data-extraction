# %% [markdown]
# # NB03 — Aplicação temporal
# Reconstrói o mesmo Random Forest e aplica de 2017 a 2026.

# %%
import sys, os, json
from pathlib import Path
import pandas as pd
import ee

PROJECT_ROOT = Path.cwd()
while not (PROJECT_ROOT / "config").exists() and PROJECT_ROOT != PROJECT_ROOT.parent:
    PROJECT_ROOT = PROJECT_ROOT.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from config.config import *
from common import init_ee, s2_composite
init_ee()

catalogo = catalogo_dataframe()
validos = catalogo[catalogo.coordinates_valid].copy()
meta_path = MODELS_DIR / "random_forest_metadata.json"
if not meta_path.exists():
    raise FileNotFoundError("Execute NB02 antes de NB03.")
meta = json.loads(meta_path.read_text(encoding="utf-8"))

def treinar_modelo():
    geoms = [ee.Geometry.Point([float(r.longitude), float(r.latitude)]).buffer(RAIO_ANALISE)
             for _, r in validos.iterrows()]
    area = ee.FeatureCollection([ee.Feature(g) for g in geoms]).geometry()
    img, _ = s2_composite(area, ANO_MAPBIOMAS)
    mb = ee.ImageCollection(COLECAO_MAPBIOMAS).filter(
        ee.Filter.eq("collection_id", 10)).filter(
        ee.Filter.eq("version", "v1")).first().select(f"classification_{ANO_MAPBIOMAS}")
    v = mb.remap(CLASSES_MAPBIOMAS["Vegetação"], [1]*len(CLASSES_MAPBIOMAS["Vegetação"]), 0).eq(1)
    b = mb.remap(CLASSES_MAPBIOMAS["Construído"], [1]*len(CLASSES_MAPBIOMAS["Construído"]), 0).eq(1)
    w = mb.remap(CLASSES_MAPBIOMAS["Água"], [1]*len(CLASSES_MAPBIOMAS["Água"]), 0).eq(1)
    lab = ee.Image(0).rename("classe").where(b,1).where(w,2).updateMask(v.Or(b).Or(w))
    samples = img.select(meta["bandas"]).addBands(lab).stratifiedSample(
        numPoints=meta["pontos_por_classe"], classBand="classe", region=area,
        scale=ESCALA_S2, classValues=[0,1,2],
        classPoints=[meta["pontos_por_classe"]]*3, seed=meta["seed"],
        geometries=False, tileScale=4)
    samples = samples.randomColumn("random", meta["seed"])
    train = samples.filter(ee.Filter.lt("random", meta["percentual_treino"]))
    return ee.Classifier.smileRandomForest(
        numberOfTrees=meta["num_arvores"], seed=meta["seed"]
    ).train(features=train, classProperty="classe", inputProperties=meta["bandas"])

classificador = treinar_modelo()

# %%
linhas = []
for _, r in validos.iterrows():
    geom = ee.Geometry.Point([float(r.longitude), float(r.latitude)]).buffer(RAIO_ANALISE)
    for ano in range(ANO_INICIO, ANO_FIM+1):
        img, n = s2_composite(geom, ano)
        n = int(n.getInfo())
        if n == 0:
            continue
        pred = img.select(BANDAS_ML).classify(classificador)
        hist = pred.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=geom, scale=ESCALA_S2, maxPixels=1e9, tileScale=4
        ).get("classification")
        h = hist.getInfo() or {}
        total = sum(float(v) for v in h.values()) or 1.0
        for classe, nome in [(0,"Vegetação"),(1,"Construído"),(2,"Água")]:
            area_pct = 100.0 * float(h.get(str(classe), 0)) / total
            linhas.append({
                "facility_id": r.facility_id,
                "facility_name": r.facility_name,
                "state_region": r.state_region,
                "ano": ano,
                "classe": nome,
                "percentual": area_pct,
                "imagens_s2": n,
                "ano_parcial": ano == ANO_FIM,
            })

serie = pd.DataFrame(linhas)
serie.to_csv(PROCESSED_DIR / "cobertura_temporal_20_datacenters.csv", index=False, encoding="utf-8")
display(serie.head(30))
print("NB03 concluído.")
