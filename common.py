"""Funções compartilhadas do Sentinela Verde."""
from pathlib import Path
import json
import ee
import pandas as pd
import numpy as np

from config.config import (
    PROJECT_ID, ANO_INICIO, ANO_FIM, MES_DIA_INICIO, MES_DIA_FIM,
    MAX_CLOUD_PERCENT, RAIO_ANALISE, RAIO_CONTROLE_EXTERNO,
    COLECAO_S2, COLECAO_MAPBIOMAS, ANO_MAPBIOMAS, BANDAS_S2,
    INDICES_SPECTRAIS, BANDAS_ML, COLECAO_VIIRS, BANDA_VIIRS,
    COLECAO_L8, COLECAO_L9, COLECAO_DYNAMIC_WORLD,
    COLECAO_ERA5, COLECAO_GSW, COLECAO_WORLDPOP,
    ESCALA_S2, ESCALA_LST, PROCESSED_DIR, MODELS_DIR, RESULTS_DIR
)

def init_ee(project_id=PROJECT_ID, authenticate=True):
    try:
        ee.Initialize(project=project_id)
    except Exception:
        if not authenticate:
            raise
        ee.Authenticate()
        ee.Initialize(project=project_id)
    return True

def mask_s2(image):
    scl = image.select("SCL")
    good = (scl.neq(3).And(scl.neq(8)).And(scl.neq(9))
              .And(scl.neq(10)).And(scl.neq(11)))
    return image.updateMask(good).divide(10000).copyProperties(image, image.propertyNames())

def add_indices(image):
    ndvi = image.normalizedDifference(["B8","B4"]).rename("NDVI")
    ndwi = image.normalizedDifference(["B3","B8"]).rename("NDWI")
    ndbi = image.normalizedDifference(["B11","B8"]).rename("NDBI")
    return image.addBands([ndvi, ndwi, ndbi])

def s2_composite(geometry, year):
    start = ee.Date(f"{year}-{MES_DIA_INICIO}")
    end = ee.Date(f"{year}-{MES_DIA_FIM}")
    col = (ee.ImageCollection(COLECAO_S2)
           .filterBounds(geometry)
           .filterDate(start, end)
           .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PERCENT))
           .map(mask_s2)
           .map(add_indices))
    return col.median().clip(geometry), col.size()

def rings(point):
    p = ee.Geometry(point)
    r500 = p.buffer(500)
    r1k = p.buffer(1000)
    r3k = p.buffer(3000)
    r5k = p.buffer(5000)
    r10k = p.buffer(RAIO_CONTROLE_EXTERNO)
    return {
        "0_500m": r500,
        "500m_1km": r1k.difference(r500, 1),
        "1_3km": r3k.difference(r1k, 1),
        "3_5km": r5k.difference(r3k, 1),
        "0_5km": r5k,
        "5_10km_controle": r10k.difference(r5k, 1),
    }

def mapbiomas_image():
    return ee.ImageCollection(COLECAO_MAPBIOMAS).filter(
        ee.Filter.eq("collection_id", 10)
    ).filter(ee.Filter.eq("version", "v1")).first().select(f"classification_{ANO_MAPBIOMAS}")

def labels_for_geometry(geometry):
    mb = mapbiomas_image()
    img = ee.Image(0).rename("classe").clip(geometry)
    img = img.where(mb.remap(CLASSES_MAPBIOMAS["Vegetação"], [0]*len(CLASSES_MAPBIOMAS["Vegetação"]), -1).eq(0), 0)
    # Rebuild cleanly with explicit class masks to avoid remap ambiguity.
    v = mb.remap(CLASSES_MAPBIOMAS["Vegetação"], [1]*len(CLASSES_MAPBIOMAS["Vegetação"]), 0).eq(1)
    b = mb.remap(CLASSES_MAPBIOMAS["Construído"], [1]*len(CLASSES_MAPBIOMAS["Construído"]), 0).eq(1)
    w = mb.remap(CLASSES_MAPBIOMAS["Água"], [1]*len(CLASSES_MAPBIOMAS["Água"]), 0).eq(1)
    out = ee.Image(0).rename("classe").where(v, 0).where(b, 1).where(w, 2)
    valid = v.Or(b).Or(w)
    return out.updateMask(valid).clip(geometry)

# Imported lazily to keep this module self-contained.
from config.config import CLASSES_MAPBIOMAS

def compute_periods(row):
    construction = row.get("construction_start_year")
    operation = row.get("operational_year")
    opening = row.get("opening_year")
    if pd.isna(operation):
        operation = opening
    construction = None if pd.isna(construction) else int(construction)
    operation = None if pd.isna(operation) else int(operation)
    if construction is None and operation is not None:
        construction = operation - 1
    if construction is None:
        return None
    if operation is None:
        operation = ANO_FIM
    pre = list(range(max(ANO_INICIO, construction-3), max(ANO_INICIO, construction)))
    during = list(range(max(ANO_INICIO, construction), min(ANO_FIM, operation)+1))
    post = list(range(min(ANO_FIM+1, operation+1), ANO_FIM+1))
    return {"pre": pre, "during": during, "post": post}

def numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def safe_delta(df, pre_col, post_col):
    return pd.to_numeric(df[post_col], errors="coerce") - pd.to_numeric(df[pre_col], errors="coerce")

def write_json(path, obj):
    path = Path(path)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
