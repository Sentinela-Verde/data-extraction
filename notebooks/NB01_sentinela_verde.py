# %% [markdown]
# # NB01 — Sentinela Verde: preparação
# Catálogo, áreas, Sentinel-2, índices espectrais e validação de coordenadas.

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
from common import init_ee, s2_composite

init_ee()
catalogo = catalogo_dataframe()
print(f"Data Centers cadastrados: {len(catalogo)}")
print(f"Com coordenadas válidas: {int(catalogo.coordinates_valid.sum())}")
print(f"Pendentes de coordenadas: {int((~catalogo.coordinates_valid).sum())}")

# %%
catalogo.to_csv(PROCESSED_DIR / "data_centers_catalogo.csv", index=False, encoding="utf-8")
catalogo[~catalogo.coordinates_valid].to_csv(
    RESULTS_DIR / "datacenters_pendentes_coordenadas.csv", index=False, encoding="utf-8"
)

# %%
validos = catalogo[catalogo.coordinates_valid].copy()
features = []
for _, r in validos.iterrows():
    geom = ee.Geometry.Point([float(r.longitude), float(r.latitude)])
    features.append(ee.Feature(geom.buffer(RAIO_ANALISE), {
        "facility_id": r.facility_id,
        "facility_name": r.facility_name,
        "state_region": r.state_region,
    }))
areas_datacenters = ee.FeatureCollection(features)

# %%
# Teste visual maior: círculo de 5 km ao redor do ponto de São Paulo.
ponto_teste = ee.Geometry.Point([-46.6333, -23.5505])
area_teste = ponto_teste.buffer(5000)
Map = geemap.Map()
Map.set_center(-46.6333, -23.5505, 10)
Map.add_layer(area_teste, {"color": "red"}, "Área de teste — 5 km")
Map.add_layer(ponto_teste, {"color": "yellow"}, "Ponto de teste")
display(Map)

# %%
# Diagnóstico da série Sentinel-2 por Data Center e ano.
linhas = []
for _, r in validos.iterrows():
    geom = ee.Geometry.Point([float(r.longitude), float(r.latitude)]).buffer(RAIO_ANALISE)
    for ano in range(ANO_INICIO, ANO_FIM + 1):
        _, n = s2_composite(geom, ano)
        linhas.append({
            "facility_id": r.facility_id,
            "ano": ano,
            "imagens_s2": int(n.getInfo()),
            "ano_parcial": bool(ano == ANO_FIM),
        })
cobertura = pd.DataFrame(linhas)
cobertura.to_csv(PROCESSED_DIR / "cobertura_sentinel2_nb01.csv", index=False, encoding="utf-8")
display(cobertura.head(20))

print("NB01 concluído.")
