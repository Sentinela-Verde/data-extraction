"""Step 2 — Estágio 2: aprender o efeito da chegada do data center.

Implementa o Estágio 2 descrito em `proposta_projeto.md`: a partir do porte do data
center e do contexto/tendência pré-obra da região (Estágio 1, consolidado em
`data/silver/consolidado_impacto_modelo.csv`), aprende **o quanto a chegada do data center
muda cada variável, além do que já era esperado pela tendência regional** — medido nos
horizontes 0 (ano de abertura), +1 e +2, sempre comparado com o ano anterior à abertura.

Pipeline:
1. Recalcula `delta_*` (variação vs. ano-base pré-obra) para cada área (`comum.calcula_deltas`).
2. Extrai nível e tendência pré-obra por área (features fixas, item 5 do guia de estrutura).
3. Monta o alvo do modelo: **efeito líquido** (`delta_tratamento - delta_controle`) por par e
   horizonte (`config.HORIZONTES_ALVO`).
4. Treina um Random Forest raso por variável de interesse (`config.VARS_MODELO`), valida com
   **Leave-One-DC-Out** (proposta, item 6 / guia, item 9) e compara com uma baseline ingênua
   (prever a média).
5. Treina o modelo final com todos os dados, reporta importância das features, e expõe
   `prever_impacto()` pra prever o efeito de um data center hipotético.

**Limitação conhecida (proposta, item 7):** com poucos pares tratamento/controle
disponíveis hoje, a amostra é pequena para qualquer modelo de ML — por isso o modelo é
raso (`config.RF_MAX_DEPTH`) e a validação Leave-One-DC-Out serve para medir honestamente
se o modelo generaliza melhor que simplesmente prever a média, não para produzir uma
métrica de "produção".

Uso:
    python step2_estagio2_modelo_efeito.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
from comum import calcula_deltas, calcula_tendencia

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

pd.set_option("display.float_format", "{:.4f}".format)
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

FEATURES_NUM = None  # preenchido em main(), depende das colunas de tendência calculadas
FEATURES_CAT = config.COLS_CONTEXTO_CAT


def monta_features_tendencia(df: pd.DataFrame, baseline_map: pd.DataFrame) -> pd.DataFrame:
    """`nivel_pre_<var>` (valor no ano-base) e `tendencia_pre_<var>` (inclinação da reta
    ajustada nos anos pré-obra), por área — não mudam entre horizontes da mesma área."""
    registros = []
    for site_id, g in df.groupby("site_id"):
        g_pre = g[g["ano_relativo_ao_inicio_obra"] < 0].sort_values("ano_relativo_ao_inicio_obra")
        linha = {"site_id": site_id}
        for var in config.VARS_ALVO:
            linha[f"nivel_pre_{var}"] = baseline_map.loc[site_id, var] if site_id in baseline_map.index else np.nan
            linha[f"tendencia_pre_{var}"] = calcula_tendencia(
                g_pre["ano_relativo_ao_inicio_obra"].values, g_pre[var].values,
            )
        registros.append(linha)
    return pd.DataFrame(registros).set_index("site_id")


def monta_features_estaticas(df: pd.DataFrame) -> pd.DataFrame:
    """Porte do data center + contexto regional — primeira linha de cada área (não muda
    entre horizontes)."""
    primeira_linha_por_site = df.groupby("site_id").first()
    cols = config.COLS_PORTE + config.COLS_CONTEXTO_NUM + config.COLS_CONTEXTO_CAT
    features = primeira_linha_por_site[cols].copy()
    for c in config.COLS_CONTEXTO_CAT:
        features[c] = features[c].fillna("desconhecido")
    return features


def monta_alvo(df: pd.DataFrame) -> pd.DataFrame:
    """efeito_liquido_<var> = delta_tratamento - delta_controle, só nos horizontes-alvo."""
    registros = []
    for par in df["pareado_com"].dropna().unique():
        grupo = df[df["pareado_com"] == par]
        trat = grupo[grupo["tipo"] == "tratamento"].set_index("ano_relativo_ao_inicio_obra")
        ctrl = grupo[grupo["tipo"] == "controle"].set_index("ano_relativo_ao_inicio_obra")
        if trat.empty:
            continue

        site_tratado = trat["site_id"].iloc[0]
        horizontes_comuns = trat.index.intersection(ctrl.index)
        for h in config.HORIZONTES_ALVO:
            if h not in horizontes_comuns:
                continue
            linha = {"site_id": site_tratado, "horizonte": h}
            for var in config.VARS_ALVO:
                dcol = f"delta_{var}"
                linha[f"efeito_liquido_{var}"] = trat.loc[h, dcol] - ctrl.loc[h, dcol]
            registros.append(linha)
    return pd.DataFrame(registros)


def monta_modelo(preprocessador):
    return Pipeline([
        ("preprocessa", preprocessador),
        ("modelo", RandomForestRegressor(
            n_estimators=config.RF_N_ESTIMATORS, max_depth=config.RF_MAX_DEPTH,
            min_samples_leaf=config.RF_MIN_SAMPLES_LEAF, random_state=config.RANDOM_STATE,
        )),
    ])


def roda_leave_one_dc_out(treino: pd.DataFrame, preprocessador) -> pd.DataFrame:
    """Compara o erro do modelo (removendo uma área inteira por vez do treino) com uma
    baseline ingênua que só prevê a média do treino, sem usar nenhuma feature."""
    resultados = []
    for var in config.VARS_MODELO:
        target_col = f"efeito_liquido_{var}"
        dados_var = treino.dropna(subset=[target_col]).reset_index(drop=True)
        X = dados_var[FEATURES_NUM + FEATURES_CAT]
        y = dados_var[target_col]
        sites = dados_var["site_id"]

        preds = np.full(len(dados_var), np.nan)
        preds_baseline = np.full(len(dados_var), np.nan)
        for site_out in sites.unique():
            treino_mask = sites != site_out
            teste_mask = ~treino_mask
            if treino_mask.sum() < 5:
                continue
            modelo = monta_modelo(preprocessador)
            modelo.fit(X[treino_mask], y[treino_mask])
            preds[teste_mask.values] = modelo.predict(X[teste_mask])
            preds_baseline[teste_mask.values] = y[treino_mask].mean()

        validos = ~np.isnan(preds)
        mae_modelo = mean_absolute_error(y[validos], preds[validos])
        mae_baseline = mean_absolute_error(y[validos], preds_baseline[validos])
        resultados.append({
            "variavel": var, "n_amostras": int(validos.sum()),
            "mae_modelo": mae_modelo, "mae_baseline_media": mae_baseline,
            "melhora_vs_baseline_%": 100 * (1 - mae_modelo / mae_baseline),
        })
    return pd.DataFrame(resultados)


def treina_modelos_finais(treino: pd.DataFrame, preprocessador):
    """Treina (com todos os dados) um modelo por variável de `config.VARS_MODELO` e devolve
    os modelos + a importância de cada feature."""
    modelos, importancias = {}, {}
    for var in config.VARS_MODELO:
        target_col = f"efeito_liquido_{var}"
        dados_var = treino.dropna(subset=[target_col]).reset_index(drop=True)
        X = dados_var[FEATURES_NUM + FEATURES_CAT]
        y = dados_var[target_col]

        modelo = monta_modelo(preprocessador)
        modelo.fit(X, y)
        modelos[var] = modelo

        nomes_cat = (
            modelo.named_steps["preprocessa"].named_transformers_["cat"]
            .named_steps["onehot"].get_feature_names_out(FEATURES_CAT)
        )
        nomes_features = FEATURES_NUM + list(nomes_cat)
        importancias[var] = pd.Series(
            modelo.named_steps["modelo"].feature_importances_, index=nomes_features,
        ).sort_values(ascending=False)

    return modelos, importancias


def prever_impacto(modelos: dict, features_dict: dict, horizonte: int, variavel: str) -> float:
    """features_dict: dicionário com as chaves de FEATURES_NUM (exceto 'horizonte') e
    FEATURES_CAT que você conseguir preencher — o que faltar é imputado automaticamente
    (mediana / categoria "desconhecido" aprendida no treino).
    horizonte: um dos valores em config.HORIZONTES_ALVO.
    variavel: uma das config.VARS_MODELO.
    """
    linha = {c: features_dict.get(c, np.nan) for c in FEATURES_NUM + FEATURES_CAT}
    linha["horizonte"] = horizonte
    X_novo = pd.DataFrame([linha])[FEATURES_NUM + FEATURES_CAT]
    return modelos[variavel].predict(X_novo)[0]


def main():
    global FEATURES_NUM

    df = pd.read_csv(config.CONSOLIDADO_CSV)
    df, baseline_map = calcula_deltas(df, config.VARS_ALVO)

    features_tendencia = monta_features_tendencia(df, baseline_map)
    features_estaticas = monta_features_estaticas(df)
    features_site = features_estaticas.join(features_tendencia)
    print(f"features_site: {features_site.shape[0]} áreas x {features_site.shape[1]} features")

    alvo_df = monta_alvo(df)
    print(f"{alvo_df.shape[0]} linhas (áreas tratadas x horizontes {config.HORIZONTES_ALVO} disponíveis)")

    treino = alvo_df.merge(features_site, left_on="site_id", right_index=True, how="left")

    FEATURES_NUM = config.COLS_PORTE + config.COLS_CONTEXTO_NUM + list(features_tendencia.columns) + ["horizonte"]
    preprocessador = ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), FEATURES_NUM),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="desconhecido")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]), FEATURES_CAT),
    ])

    resultados_validacao = roda_leave_one_dc_out(treino, preprocessador)
    print("\nValidação Leave-One-DC-Out (vs. baseline ingênua = prever a média):")
    print(resultados_validacao.round(4).to_string(index=False))
    resultados_validacao.to_csv(config.OUTPUT_DIR / "validacao_leave_one_dc_out.csv", index=False)

    modelos_finais, importancias = treina_modelos_finais(treino, preprocessador)

    fig, axes = plt.subplots(1, len(config.VARS_MODELO), figsize=(15, 4))
    for ax, var in zip(axes, config.VARS_MODELO):
        top = importancias[var].head(8).sort_values()
        ax.barh(top.index, top.values, color="tab:red")
        ax.set_title(var)
    fig.suptitle("Importância das features (top 8) por variável-alvo")
    fig.tight_layout()
    fig.savefig(config.FIGURAS_DIR / "importancia_features_estagio2.png", dpi=150)
    plt.close(fig)

    modelos_dir = config.OUTPUT_DIR / "modelos"
    modelos_dir.mkdir(parents=True, exist_ok=True)
    for var, modelo in modelos_finais.items():
        joblib.dump(modelo, modelos_dir / f"modelo_efeito_{var}.joblib")
    print(f"\nModelos finais salvos em {modelos_dir}")

    # Exemplo: data center hipotético de 10 MW, 2 prédios, na Mata Atlântica
    print("\nExemplo — prever_impacto(mw=10, 2 prédios, Mata Atlântica):")
    for h in config.HORIZONTES_ALVO:
        valor = prever_impacto(
            modelos_finais,
            {"mw_construido_total": 10, "n_predios_no_campus": 2, "bioma": "Mata Atlantica"},
            horizonte=h, variavel="prop_vegetacao_densa",
        )
        print(f"  horizonte +{h}: efeito líquido previsto em prop_vegetacao_densa = {valor:.4f}")


if __name__ == "__main__":
    main()
