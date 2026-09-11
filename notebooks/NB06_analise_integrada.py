# %% [markdown]
# # NB06 — Análise integrada Sentinela Verde
# Controle espacial + múltiplas dimensões + índice multidimensional.
#
# O índice final é uma ferramenta de síntese, não uma prova causal.

# %%
import sys, os, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path.cwd()
while not (PROJECT_ROOT / "config").exists() and PROJECT_ROOT != PROJECT_ROOT.parent:
    PROJECT_ROOT = PROJECT_ROOT.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from config.config import *
from common import compute_periods

catalogo = pd.read_csv(PROCESSED_DIR / "data_centers_catalogo.csv")
serie = pd.read_csv(PROCESSED_DIR / "cobertura_temporal_20_datacenters.csv")
mf_path = RESULTS_DIR / "cruzamento_multifonte_anual_aneis.csv"
mf = pd.read_csv(mf_path) if mf_path.exists() else pd.DataFrame()
energy = pd.read_csv(RESULTS_DIR / "energia_agua_datacenters.csv")

# %%
# Função robusta para calcular Pré/Pós e diferença relativa DC - Controle.
def period_average(df, years, col, ring):
    x=df[df.ano.isin(years) & (df.anel==ring)][col]
    return x.mean() if not x.empty else np.nan

integrated=[]
for _, row in catalogo[catalogo.coordinates_valid].iterrows():
    periods=compute_periods(row)
    if not periods or mf.empty:
        continue
    rec={"facility_id":row.facility_id,"facility_name":row.facility_name,"state_region":row.state_region}
    for metric in ["ndvi","ndwi","ndbi","viirs_ntl","lst_k"]:
        pre=period_average(mf,periods["pre"],metric,"0_5km")
        post=period_average(mf,periods["post"],metric,"0_5km")
        cpre=period_average(mf,periods["pre"],metric,"5_10km_controle")
        cpost=period_average(mf,periods["post"],metric,"5_10km_controle")
        rec[f"{metric}_pre"]=pre; rec[f"{metric}_post"]=post
        rec[f"{metric}_delta_dc"]=post-pre
        rec[f"{metric}_delta_controle"]=cpost-cpre
        rec[f"{metric}_efeito_relativo"]=(post-pre)-(cpost-cpre)
    integrated.append(rec)

integrated=pd.DataFrame(integrated)
integrated=integrated.merge(energy[["facility_id","capacity_mw","it_load_mw","pue","wue",
                                     "water_usage_m3_year","energia_total_estimada_mwh_ano",
                                     "agua_estimada_m3_ano","energia_status","agua_status"]],
                            on="facility_id",how="left")

# %%
# Transformação territorial do RF.
rf=serie.pivot_table(index=["facility_id","ano"],columns="classe",values="percentual").reset_index()
rf=rf.merge(catalogo[["facility_id","construction_start_year","operational_year","opening_year"]],on="facility_id",how="left")
rf_rows=[]
for fid,g in rf.groupby("facility_id"):
    rowcat=catalogo[catalogo.facility_id==fid].iloc[0]
    p=compute_periods(rowcat)
    if not p: continue
    pre=g[g.ano.isin(p["pre"])]
    post=g[g.ano.isin(p["post"])]
    if pre.empty or post.empty: continue
    for c in ["Vegetação","Construído","Água"]:
        pass
    dv=post["Vegetação"].mean()-pre["Vegetação"].mean()
    db=post["Construído"].mean()-pre["Construído"].mean()
    dw=post["Água"].mean()-pre["Água"].mean()
    rf_rows.append({"facility_id":fid,"delta_vegetacao_pp":dv,"delta_construido_pp":db,
                    "delta_agua_pp":dw,"transformacao_territorial":np.nansum(np.abs([dv,db,dw]))})
rf_delta=pd.DataFrame(rf_rows)

# %%
# Normalização 0-1 somente entre sites disponíveis, sem pesos arbitrários.
# Para variáveis onde aumento representa maior transformação, usamos valor absoluto.
def minmax(s):
    s=pd.to_numeric(s,errors="coerce")
    if s.notna().sum()<2 or s.max()==s.min():
        return pd.Series(np.nan,index=s.index)
    return (s-s.min())/(s.max()-s.min())

for c in ["transformacao_territorial","viirs_ntl_efeito_relativo","lst_k_efeito_relativo",
          "ndvi_efeito_relativo","ndbi_efeito_relativo"]:
    if c in integrated.columns:
        integrated[c+"_abs"]=integrated[c].abs()

final=rf_delta.merge(integrated,on="facility_id",how="left",suffixes=("","_multi"))

components=[]
for c in ["dim_ambiental","dim_urbanizacao","energia_escala_norm","agua_escala_norm"]:
    if c in final.columns:
        components.append(c)
# Pesos iguais entre dimensões disponíveis. Não há conversão de MW para vegetação,
# nem de m³ para temperatura: cada dimensão é normalizada antes da síntese.
final["indice_multidimensional"]=final[components].mean(axis=1,skipna=True) if components else np.nan
final["rank_integrado"]=final["indice_multidimensional"].rank(method="min",ascending=False).astype("Int64")

# %%
# Indicadores por dimensão.
# Primeiro normalizamos as variáveis comparáveis; energia/água permanecem como
# indicadores de pressão/escala, sem misturar unidades físicas diretamente.
dim_vars = {
    "dim_ambiental": ["ndvi_efeito_relativo_abs","lst_k_efeito_relativo_abs"],
    "dim_urbanizacao": ["transformacao_territorial","viirs_ntl_efeito_relativo_abs",
                        "ndbi_efeito_relativo_abs"],
}
for dim, cols in dim_vars.items():
    norms=[]
    for c in cols:
        if c in final.columns:
            n=minmax(final[c])
            norms.append(n)
    final[dim] = pd.concat(norms,axis=1).mean(axis=1,skipna=True) if norms else np.nan

if "energia_total_estimada_mwh_ano" in final.columns:
    final["energia_escala_norm"] = minmax(final["energia_total_estimada_mwh_ano"])
if "agua_estimada_m3_ano" in final.columns:
    final["agua_escala_norm"] = minmax(final["agua_estimada_m3_ano"])

final.to_csv(RESULTS_DIR / "perfil_integrado_datacenters.csv",index=False,encoding="utf-8")
final.sort_values("indice_multidimensional",ascending=False).to_csv(
    RESULTS_DIR / "ranking_integrado_sentinela_verde.csv",index=False,encoding="utf-8"
)
final.to_csv(RESULTS_DIR / "ranking_integrado_sentinela_verde.csv",index=False,encoding="utf-8")

# %%
# Correlações exploratórias, sem afirmar causalidade.
numeric_cols=[c for c in [
    "transformacao_territorial","viirs_ntl_efeito_relativo","lst_k_efeito_relativo",
    "ndvi_efeito_relativo","ndbi_efeito_relativo","capacity_mw",
    "it_load_mw","energia_total_estimada_mwh_ano","agua_estimada_m3_ano"
] if c in final.columns]
corr=final[numeric_cols].corr(method="spearman")
corr.to_csv(RESULTS_DIR / "correlacoes_spearman_integradas.csv",encoding="utf-8")

# %%
report={
    "projeto":"Sentinela Verde",
    "data_centers_cadastrados":int(catalogo.facility_id.nunique()),
    "data_centers_com_coordenadas":int(catalogo.coordinates_valid.sum()),
    "fontes_principais":[
        "Sentinel-2 SR Harmonized","MapBiomas Collection 10","VIIRS VNP46A2",
        "Landsat 8/9 Collection 2 Level 2","Dynamic World","ERA5-Land",
        "JRC Global Surface Water","WorldPop","ANA","ANEEL","ONS","IBGE","OSM"
    ],
    "controle":"anel externo 5–10 km; efeito relativo = ΔDC - ΔControle",
    "indice":"média dos componentes normalizados disponíveis; pesos iguais; síntese exploratória",
    "causalidade":"Não causal. Os resultados indicam transformação territorial e associação temporal/multifonte.",
    "observacoes":[
        "VIIRS é proxy de atividade/luz noturna, não consumo direto de energia.",
        "LST é temperatura da superfície, não temperatura do ar.",
        "Energia/água calculadas por PUE/WUE são estimativas quando não informadas diretamente.",
        "Arquivos locais ANA/ANEEL/ONS/IBGE/OSM são opcionais e nunca são inventados.",
        "2026 é ano parcial e deve ser tratado como tal."
    ]
}
(RESULTS_DIR/"relatorio_nb06.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(final.sort_values("indice_multidimensional",ascending=False).head(20))
print("NB06 concluído.")
