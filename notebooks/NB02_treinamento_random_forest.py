# %% [markdown]
# # NB02 — Treinamento Random Forest
# Sentinel-2 + NDVI/NDWI/NDBI; MapBiomas 2023 apenas como referência de rótulos.

# %%
import sys, os, json
from pathlib import Path
import pandas as pd
import ee
import geemap

PROJECT_ROOT = Path.cwd()
while not (PROJECT_ROOT / "config").exists() and PROJECT_ROOT != PROJECT_ROOT.parent:
    PROJECT_ROOT = PROJECT_ROOT.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from config.config import *
from common import init_ee, s2_composite, mask_s2, add_indices
init_ee()

catalogo = catalogo_dataframe()
validos = catalogo[catalogo.coordinates_valid].copy()
if validos.empty:
    raise RuntimeError("Nenhum Data Center possui coordenadas válidas.")

geoms = [ee.Geometry.Point([float(r.longitude), float(r.latitude)]).buffer(RAIO_ANALISE)
         for _, r in validos.iterrows()]
area_treinamento = ee.FeatureCollection([ee.Feature(g) for g in geoms]).geometry()

# %%
imagem_base, n_img = s2_composite(area_treinamento, ANO_MAPBIOMAS)
imagem_ml = imagem_base.select(BANDAS_ML)

mapbiomas = ee.ImageCollection(COLECAO_MAPBIOMAS).filter(
    ee.Filter.eq("collection_id", 10)
).filter(ee.Filter.eq("version", "v1")).first().select(f"classification_{ANO_MAPBIOMAS}")

# Classe 0 = vegetação; 1 = construído/não vegetado; 2 = água.
v = mapbiomas.remap(CLASSES_MAPBIOMAS["Vegetação"], [1]*len(CLASSES_MAPBIOMAS["Vegetação"]), 0).eq(1)
b = mapbiomas.remap(CLASSES_MAPBIOMAS["Construído"], [1]*len(CLASSES_MAPBIOMAS["Construído"]), 0).eq(1)
w = mapbiomas.remap(CLASSES_MAPBIOMAS["Água"], [1]*len(CLASSES_MAPBIOMAS["Água"]), 0).eq(1)
rotulos = ee.Image(0).rename("classe").where(b, 1).where(w, 2).updateMask(v.Or(b).Or(w))

# %%
# Amostragem estratificada: mesma quantidade alvo por classe.
amostras_pixels = imagem_ml.addBands(rotulos).stratifiedSample(
    numPoints=PONTOS_POR_CLASSE,
    classBand="classe",
    region=area_treinamento,
    scale=ESCALA_S2,
    classValues=[0,1,2],
    classPoints=[PONTOS_POR_CLASSE]*3,
    seed=SEED,
    geometries=False,
    tileScale=4,
)
amostras_pixels = amostras_pixels.randomColumn("random", SEED)
amostras_treino = amostras_pixels.filter(ee.Filter.lt("random", PERCENTUAL_TREINO))
amostras_teste = amostras_pixels.filter(ee.Filter.gte("random", PERCENTUAL_TREINO))

print("Total:", amostras_pixels.size().getInfo())
print("Treino:", amostras_treino.size().getInfo())
print("Teste:", amostras_teste.size().getInfo())

# %%
classificador = ee.Classifier.smileRandomForest(
    numberOfTrees=NUM_ARVORES,
    seed=SEED
).train(
    features=amostras_treino,
    classProperty="classe",
    inputProperties=BANDAS_ML,
)

avaliacao = amostras_teste.classify(classificador)
matriz = avaliacao.errorMatrix("classe", "classification")
acuracia_global = float(matriz.accuracy().getInfo())
kappa = float(matriz.kappa().getInfo())
print("Matriz de confusão:")
print(matriz.getInfo())
print(f"Acurácia global: {acuracia_global:.4f}")
print(f"Kappa: {kappa:.4f}")

# %%
explicacao = classificador.explain().getInfo()
importancia = explicacao.get("importance", {})
importance_df = pd.DataFrame(
    [{"variavel": k, "importancia": v} for k, v in importancia.items()]
).sort_values("importancia", ascending=False)
importance_df.to_csv(MODELS_DIR / "random_forest_importancia_variaveis.csv", index=False)

metadata = {
    "modelo": "Random Forest",
    "colecao_sentinel2": COLECAO_S2,
    "colecao_referencia": COLECAO_MAPBIOMAS,
    "ano_referencia": ANO_MAPBIOMAS,
    "bandas": BANDAS_ML,
    "classes": {"0":"Vegetação","1":"Construído / não vegetado","2":"Água"},
    "num_arvores": NUM_ARVORES,
    "seed": SEED,
    "pontos_por_classe": PONTOS_POR_CLASSE,
    "percentual_treino": PERCENTUAL_TREINO,
    "total_amostras": int(amostras_pixels.size().getInfo()),
    "amostras_treino": int(amostras_treino.size().getInfo()),
    "amostras_teste": int(amostras_teste.size().getInfo()),
    "acuracia_global": acuracia_global,
    "kappa": kappa,
    "importancia_variaveis": importancia,
}
(MODELS_DIR / "random_forest_metadata.json").write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
)

# %%
classificada = imagem_ml.classify(classificador)
Map = geemap.Map()
Map.center_object(area_treinamento, 7)
Map.add_layer(imagem_base, {"bands":["B4","B3","B2"],"min":0,"max":0.3}, "Sentinel-2 RGB 2023")
Map.add_layer(classificada, {"min":0,"max":2}, "Random Forest 2023")
Map.add_layer(ee.FeatureCollection([ee.Feature(g) for g in geoms]),
              {"color":"red"}, "Áreas de treinamento")
display(Map)

print("NB02 concluído.")
