import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/"data"/"results"
st.set_page_config(page_title="Sentinela Verde",page_icon="🌱",layout="wide")
st.title("🌱 Sentinela Verde")
st.caption("Transformação territorial e evidências ambientais/urbanas em torno de Data Centers.")

path=RESULTS/"perfil_integrado_datacenters.csv"
if not path.exists():
    st.error("Execute NB01 → NB06 primeiro.")
    st.stop()

df=pd.read_csv(path)
states=["Todos"]+sorted(df.state_region.dropna().astype(str).unique())
state=st.sidebar.selectbox("Estado",states)
if state!="Todos": df=df[df.state_region.astype(str)==state]

st.metric("Data Centers analisados",len(df))
cols=st.columns(3)
with cols[0]:
    st.metric("Maior índice integrado", round(df.indice_multidimensional.max(),3) if df.indice_multidimensional.notna().any() else "n/d")
with cols[1]:
    st.metric("Maior transformação territorial", round(df.transformacao_territorial.max(),2) if df.transformacao_territorial.notna().any() else "n/d")
with cols[2]:
    st.metric("Com coordenadas",len(df))

st.subheader("Ranking integrado")
show=[c for c in ["rank_integrado","facility_id","facility_name","state_region",
                  "indice_multidimensional","transformacao_territorial",
                  "viirs_ntl_efeito_relativo","lst_k_efeito_relativo",
                  "ndvi_efeito_relativo","ndbi_efeito_relativo",
                  "capacity_mw","energia_total_estimada_mwh_ano","agua_estimada_m3_ano"] if c in df.columns]
st.dataframe(df.sort_values("indice_multidimensional",ascending=False)[show],use_container_width=True)

st.subheader("Interpretação")
st.write(
"""O índice é uma síntese exploratória. O pipeline não afirma que o Data Center causou
cada mudança observada. O resultado deve ser interpretado como evidência temporal e
multifonte, reforçada pelo contraste com o anel de controle de 5–10 km."""
)
