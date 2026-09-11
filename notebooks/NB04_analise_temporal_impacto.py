# %% [markdown]
# # NB04 — Análise temporal Pré/Durante/Pós + energia/água

# %%
import sys, os, json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

PROJECT_ROOT = Path.cwd()
while not (PROJECT_ROOT / "config").exists() and PROJECT_ROOT != PROJECT_ROOT.parent:
    PROJECT_ROOT = PROJECT_ROOT.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from config.config import *
from common import compute_periods

serie = pd.read_csv(PROCESSED_DIR / "cobertura_temporal_20_datacenters.csv")
catalogo = pd.read_csv(PROCESSED_DIR / "data_centers_catalogo.csv")

# %%
registros = []
for _, row in catalogo.iterrows():
    periodos = compute_periods(row)
    if not periodos:
        continue
    for periodo, anos in periodos.items():
        if not anos:
            continue
        sub = serie[(serie.facility_id == row.facility_id) & serie.ano.isin(anos)]
        if sub.empty:
            continue
        for classe in ["Vegetação","Construído","Água"]:
            vals = sub[sub.classe == classe].percentual
            registros.append({
                "facility_id": row.facility_id,
                "facility_name": row.facility_name,
                "state_region": row.state_region,
                "periodo": periodo,
                "anos_periodo": ",".join(map(str, anos)),
                "classe": classe,
                "percentual_medio": vals.mean() if not vals.empty else np.nan,
                "n_anos": int(vals.notna().sum()),
            })
periodos_df = pd.DataFrame(registros)
periodos_df.to_csv(RESULTS_DIR / "analise_temporal_por_periodo.csv", index=False, encoding="utf-8")

# %%
wide = periodos_df.pivot_table(
    index=["facility_id","facility_name","state_region"],
    columns=["periodo","classe"], values="percentual_medio"
).reset_index()

def getv(r, p, c):
    try: return r[(p,c)]
    except Exception: return np.nan

rows=[]
for _, r in wide.iterrows():
    dv = getv(r,"post","Vegetação") - getv(r,"pre","Vegetação")
    db = getv(r,"post","Construído") - getv(r,"pre","Construído")
    dw = getv(r,"post","Água") - getv(r,"pre","Água")
    rows.append({
        "facility_id": r.facility_id,
        "facility_name": r.facility_name,
        "state_region": r.state_region,
        "delta_vegetacao_pp": dv,
        "delta_construido_pp": db,
        "delta_agua_pp": dw,
        "transformacao_territorial": np.nansum(np.abs([dv,db,dw])),
    })
ranking = pd.DataFrame(rows).sort_values("transformacao_territorial", ascending=False)
ranking["rank"] = range(1, len(ranking)+1)
ranking.to_csv(RESULTS_DIR / "ranking_transformacao_territorial.csv", index=False, encoding="utf-8")

# %%
energy = catalogo.copy()
energy["energia_it_estimada_mwh_ano"] = energy["it_load_mw"] * 8760
energy["energia_total_estimada_mwh_ano"] = energy["energia_it_estimada_mwh_ano"] * energy["pue"]
energy["agua_estimada_m3_ano"] = energy["energia_it_estimada_mwh_ano"] * energy["wue"]
energy["energia_status"] = np.where(
    energy.energia_total_estimada_mwh_ano.notna(), "Estimado por IT Load × PUE",
    np.where(energy.capacity_mw.notna(), "Somente capacidade disponível", "Sem dado energético")
)
energy["agua_status"] = np.where(
    energy.water_usage_m3_year.notna(), "Informado no cadastro",
    np.where(energy.agua_estimada_m3_ano.notna(), "Estimado por WUE", "Sem dado hídrico")
)
energy.to_csv(RESULTS_DIR / "energia_agua_datacenters.csv", index=False, encoding="utf-8")

perfil = ranking.merge(
    energy[["facility_id","capacity_mw","it_load_mw","pue","wue","water_usage_m3_year",
            "energia_it_estimada_mwh_ano","energia_total_estimada_mwh_ano","energia_status",
            "agua_estimada_m3_ano","agua_status"]],
    on="facility_id", how="left"
)
perfil.to_csv(RESULTS_DIR / "perfil_impacto_territorial_energia_agua.csv", index=False, encoding="utf-8")

# %%
relatorio = {
    "projeto":"Sentinela Verde",
    "data_centers_cadastrados": int(catalogo.facility_id.nunique()),
    "data_centers_com_serie": int(serie.facility_id.nunique()),
    "periodos":["Pré","Durante","Pós"],
    "observacao":"O ranking territorial é descritivo/exploratório; energia e água estimadas não são medições diretas."
}
(RESULTS_DIR / "relatorio_nb04.json").write_text(json.dumps(relatorio,ensure_ascii=False,indent=2),encoding="utf-8")
print("NB04 concluído.")
