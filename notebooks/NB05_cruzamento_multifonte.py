# %% [markdown]
# # NB05 — Cruzamento multifonte
# VIIRS, LST Landsat, Dynamic World, ERA5-Land, JRC Water, WorldPop e arquivos
# locais opcionais de IBGE/ANA/ANEEL/ONS/OSM.
#
# Fontes externas não entram no Random Forest. Elas entram na interpretação.

# %%
import sys, os, json, math
from pathlib import Path
import pandas as pd
import numpy as np
import ee

PROJECT_ROOT = Path.cwd()
while not (PROJECT_ROOT / "config").exists() and PROJECT_ROOT != PROJECT_ROOT.parent:
    PROJECT_ROOT = PROJECT_ROOT.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from config.config import *
from common import init_ee, rings, s2_composite
init_ee()

catalogo = pd.read_csv(PROCESSED_DIR / "data_centers_catalogo.csv")
validos = catalogo[catalogo.coordinates_valid].copy()

# %%
def mask_landsat(image):
    qa = image.select("QA_PIXEL")
    mask = (qa.bitwiseAnd(1 << 1).eq(0)
            .And(qa.bitwiseAnd(1 << 2).eq(0))
            .And(qa.bitwiseAnd(1 << 3).eq(0))
            .And(qa.bitwiseAnd(1 << 4).eq(0))
            .And(qa.bitwiseAnd(1 << 5).eq(0)))
    return image.updateMask(mask).copyProperties(image, image.propertyNames())

def lst_collection(geometry, year):
    start = ee.Date(f"{year}-{MES_DIA_INICIO}")
    end = ee.Date(f"{year}-{MES_DIA_FIM}")
    l8 = ee.ImageCollection(COLECAO_L8).filterBounds(geometry).filterDate(start,end).filter(
        ee.Filter.eq("PROCESSING_LEVEL","L2SP")).filter(ee.Filter.lte("CLOUD_COVER",40))
    l9 = ee.ImageCollection(COLECAO_L9).filterBounds(geometry).filterDate(start,end).filter(
        ee.Filter.eq("PROCESSING_LEVEL","L2SP")).filter(ee.Filter.lte("CLOUD_COVER",40))
    return l8.merge(l9).map(mask_landsat).map(
        lambda im: im.select("ST_B10").multiply(0.00341802).add(149).rename("LST_K")
    )

def viirs_image(geometry, year):
    col = (ee.ImageCollection(COLECAO_VIIRS).filterBounds(geometry)
           .filterDate(f"{year}-{MES_DIA_INICIO}", f"{year}-{MES_DIA_FIM}")
           .select([BANDA_VIIRS]))
    return col.mean().rename("NTL"), col.size()

def dynamic_world(geometry, year):
    col = (ee.ImageCollection(COLECAO_DYNAMIC_WORLD).filterBounds(geometry)
           .filterDate(f"{year}-{MES_DIA_INICIO}", f"{year}-{MES_DIA_FIM}"))
    label = col.select("label").mode()
    # DW: 0 water, 1 trees, 2 grass, 3 flooded_vegetation, 4 crops,
    # 5 shrub_and_scrub, 6 built, 7 bare, 8 snow_and_ice.
    veg = label.gte(1).And(label.lte(5))
    built = label.eq(6)
    water = label.eq(0)
    grouped = ee.Image(0).rename("dw_group").where(built,1).where(water,2)
    grouped = grouped.where(veg,0)
    return grouped, col.size()

def reduce_mean(image, geom, scale):
    value = image.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geom, scale=scale,
        maxPixels=1e9, tileScale=4
    ).getInfo()
    if not value:
        return np.nan
    return list(value.values())[0]

# %%
# Série anual multifonte por anéis.
records = []
for _, r in validos.iterrows():
    p = ee.Geometry.Point([float(r.longitude), float(r.latitude)])
    rs = rings(p)
    for ano in range(ANO_INICIO, ANO_FIM+1):
        # Sentinel spectral metrics
        s2, ns2 = s2_composite(rs["0_5km"], ano)
        ns2 = int(ns2.getInfo())
        if ns2 > 0:
            for ring_name in ["0_500m","500m_1km","1_3km","3_5km","0_5km","5_10km_controle"]:
                geom = rs[ring_name]
                vals = s2.select(["NDVI","NDWI","NDBI"]).reduceRegion(
                    ee.Reducer.mean(), geom, ESCALA_S2, maxPixels=1e9, tileScale=4
                ).getInfo() or {}
                records.append({
                    "facility_id":r.facility_id,"ano":ano,"anel":ring_name,
                    "ndvi":vals.get("NDVI"),"ndwi":vals.get("NDWI"),"ndbi":vals.get("NDBI"),
                    "s2_imagens":ns2
                })
        # VIIRS
        ntl, nviirs = viirs_image(rs["0_5km"], ano)
        nviirs = int(nviirs.getInfo())
        if nviirs > 0:
            for ring_name in ["0_500m","500m_1km","1_3km","3_5km","0_5km","5_10km_controle"]:
                records[-1 if False else 0:0] = []  # no-op to keep cell deterministic
                records.append({
                    "facility_id":r.facility_id,"ano":ano,"anel":ring_name,
                    "ndvi":np.nan,"ndwi":np.nan,"ndbi":np.nan,
                    "s2_imagens":ns2,"viirs_ntl":reduce_mean(ntl, rs[ring_name], 500),
                    "viirs_imagens":nviirs
                })
        # LST
        lc = lst_collection(rs["0_5km"], ano)
        nlst = int(lc.size().getInfo())
        if nlst > 0:
            lst = lc.mean()
            for ring_name in ["0_500m","500m_1km","1_3km","3_5km","0_5km","5_10km_controle"]:
                records.append({
                    "facility_id":r.facility_id,"ano":ano,"anel":ring_name,
                    "lst_k":reduce_mean(lst, rs[ring_name], ESCALA_LST),
                    "lst_imagens":nlst
                })
        # Dynamic World (validation/reference, not RF training)
        dw, ndw = dynamic_world(rs["0_5km"], ano)
        ndw = int(ndw.getInfo())
        if ndw > 0:
            for ring_name in ["0_500m","500m_1km","1_3km","3_5km","0_5km","5_10km_controle"]:
                hist = dw.reduceRegion(
                    ee.Reducer.frequencyHistogram(), rs[ring_name], 10,
                    maxPixels=1e9, tileScale=4
                ).getInfo() or {}
                h = hist.get("dw_group", {})
                total = sum(float(v) for v in h.values()) or 1
                records.append({
                    "facility_id":r.facility_id,"ano":ano,"anel":ring_name,
                    "dw_vegetacao_pct":100*float(h.get("0",0))/total,
                    "dw_construido_pct":100*float(h.get("1",0))/total,
                    "dw_agua_pct":100*float(h.get("2",0))/total,
                    "dw_imagens":ndw
                })

# %%
mf = pd.DataFrame(records)
# Multiple rows per facility/year/ring exist by source; aggregate source columns.
keys = ["facility_id","ano","anel"]
agg = mf.groupby(keys, dropna=False).mean(numeric_only=True).reset_index()
agg = agg.merge(catalogo[["facility_id","facility_name","state_region","city","construction_start_year",
                           "operational_year","opening_year","capacity_mw","it_load_mw","pue","wue",
                           "water_usage_m3_year"]], on="facility_id", how="left")
agg.to_csv(RESULTS_DIR / "cruzamento_multifonte_anual_aneis.csv", index=False, encoding="utf-8")

# %%
# JRC water occurrence + WorldPop + ERA5: one current/historical contextual snapshot per site.
context=[]
for _, r in validos.iterrows():
    p=ee.Geometry.Point([float(r.longitude),float(r.latitude)])
    area=p.buffer(RAIO_ANALISE)
    water=ee.Image(COLECAO_GSW).select("occurrence")
    wp=ee.ImageCollection(COLECAO_WORLDPOP).filterDate("2020-01-01","2022-01-01").mosaic()
    era5=ee.ImageCollection(COLECAO_ERA5).filterDate("2021-05-01","2021-08-01").select(
        ["temperature_2m","total_precipitation_sum"]).mean()
    wr=water.reduceRegion(ee.Reducer.mean(),area,30,maxPixels=1e9,tileScale=4).getInfo() or {}
    pr=wp.reduceRegion(ee.Reducer.sum(),area,100,maxPixels=1e9,tileScale=4).getInfo() or {}
    er=era5.reduceRegion(ee.Reducer.mean(),area,11000,maxPixels=1e9,tileScale=4).getInfo() or {}
    context.append({
        "facility_id":r.facility_id,
        "jrc_water_occurrence_mean_pct":wr.get("occurrence"),
        "worldpop_population_approx":pr.get("population"),
        "era5_temperature_2m_k":er.get("temperature_2m"),
        "era5_precipitation_m":er.get("total_precipitation_sum"),
    })
context_df=pd.DataFrame(context)
context_df.to_csv(RESULTS_DIR / "indicadores_ambientais_contextuais.csv",index=False,encoding="utf-8")

# %%
# Optional local sources. Expected CSV schemas are documented in templates.
def optional_points(filename):
    path = EXTERNAL_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"Não foi possível ler {path}: {exc}")
        return pd.DataFrame()

ana = optional_points("ana/outorgas.csv")
aneel = optional_points("aneel/infraestrutura.csv")
ons = optional_points("ons/contexto_estado_ano.csv")
osm = optional_points("osm/infraestrutura.csv")
ibge = optional_points("ibge/setores_2022.csv")

for name,df in [("ANA",ana),("ANEEL",aneel),("ONS",ons),("OSM",osm),("IBGE",ibge)]:
    if df.empty:
        print(f"{name}: arquivo opcional não encontrado; análise mantida sem inventar dados.")

# Se houver dados já pré-agregados por facility_id, mescla diretamente.
for name,df in [("ana",ana),("aneel",aneel),("ons",ons),("osm",osm),("ibge",ibge)]:
    if not df.empty and "facility_id" in df.columns:
        out = RESULTS_DIR / f"indicadores_{name}.csv"
        df.to_csv(out,index=False,encoding="utf-8")

print("NB05 concluído.")
