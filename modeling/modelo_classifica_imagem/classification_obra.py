"""Classificação de cobertura em 4 classes (vegetação densa, grama/vegetação rasteira, solo
exposto, construção) a partir dos GeoTIFFs Landsat — pensada como insumo pra, depois,
detectar fases de obra (pré-obra / início / durante / fim) a partir da série temporal de %
por classe.

Vegetação densa vs. grama é a distinção mais frágil das quatro — sem informação de textura
(que a 30m nem daria pra calcular direito), o critério é NDVI alto + dossel fechado (SAVI
próximo do NDVI) pra densa, e NDVI moderado (ou NDVI alto mas SAVI mais baixo, indicando solo
"vazando" por baixo do gramado) pra grama. Calibre os limiares `NDVI_VEGETACAO_DENSA`/
`SAVI_VEGETACAO_DENSA`/`NDVI_GRAMA_MIN` olhando exemplos conhecidos antes de confiar cegamente
nisso.

Diferença chave em relação a `classification.py` (Step 2 original, 5 classes): lá o rótulo
de treino vem do ESA WorldCover, um retrato ESTÁTICO (~2020/2021) do mundo. Usar WorldCover
pra rotular todos os anos da série de um site que está mudando de vegetação pra construção
invalidaria o próprio rótulo na maioria dos anos — o rótulo de um único ano não vale pros
outros.

Aqui o rótulo vem de limiares em índices espectrais (NDVI, NDBI, BSI) calculados a partir
das próprias bandas de cada imagem — fisicamente aterrado, sem depender de rótulo externo
desatualizado. Só os pixels em que o índice é inequívoco viram "rótulo-semente"; os pixels
na zona cinzenta (o par mais parecido no visível: solo exposto vs. construção) ficam sem
rótulo e são resolvidos pelo Random Forest, treinado nos casos óbvios pooled de TODAS as
imagens disponíveis (todos os data centers, todos os anos) — não existe aqui um "ano de
referência" confiável por site, como no Step 2 original.

Este módulo é propositalmente independente de `classification.py`/`indices.py`: eles puxam
earthengine-api, geemap, osmnx e tensorflow (usados só pelo pipeline Sentinel+WorldCover),
que não fazem falta aqui — só rasterio, numpy, scikit-learn e matplotlib.

As bandas cruas seguem a mesma ordem espectral usada tanto no Sentinel-2 quanto no Landsat
(azul, verde, vermelho, NIR, SWIR1, SWIR2 — ver docstring de
`extract/imagens_satelite/landsat/extracao_imagem_landsat.py`), então os índices são
calculados por POSIÇÃO na pilha de bandas, não pelo nome literal da banda (SR_B2 vs B2) —
funciona pros dois sensores sem alteração.

IMPORTANTE: os limiares em `config_obra.py` são um ponto de partida de literatura, não um
valor calibrado — ajuste comparando com um data center cuja data real de início/fim de obra
você já conhece (ver docstring de `seed_labels_from_indices`).
"""
import json
import os

import matplotlib
matplotlib.use('Agg')  # roda como script batch, sem mostrar figura na tela — só salva em
# arquivo (mostrar=False nos plots). Sem isso o matplotlib escolhe o backend TkAgg por
# padrão no Windows, que gera erro de thread do Tkinter ("main thread is not in main loop")
# ao criar/fechar muitas figuras em sequência e derruba o script no meio do loop.

import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

CLASS_NAMES_OBRA = ['Vegetação densa', 'Grama', 'Solo exposto', 'Construção']
CLASS_COLORS_OBRA = ['#1b5e20', '#8bc34a', '#c9a66b', '#e74c3c']

VEGETACAO_DENSA, GRAMA, SOLO_EXPOSTO, CONSTRUCAO = 0, 1, 2, 3
SEM_DADO = 255  # nodata E "sem rótulo-semente confiável" (zona cinzenta) — fica fora do treino


def load_metadata(name_datacenter, out_dir):
    """Lê o metadata.json gerado pela extração Landsat (bandas, buffer, escala, CRS etc.)."""
    path = os.path.join(out_dir, f'{name_datacenter}_metadata.json')
    with open(path) as f:
        return json.load(f)


def tif_path(name_datacenter, year, out_dir):
    return os.path.join(out_dir, f'{name_datacenter}_{year}.tif')


def _safe_div(numerador, denominador):
    """Divisão que devolve 0 (em vez de inf/NaN) onde o denominador é 0."""
    with np.errstate(divide='ignore', invalid='ignore'):
        resultado = np.true_divide(numerador, denominador)
    resultado[~np.isfinite(resultado)] = 0.0
    return resultado


L_SAVI = 0.5  # fator de ajuste de brilho do solo (Huete, 1988) — 0.5 é o valor mais comum


def compute_indices_obra(raw_bands):
    """NDVI, NDBI, BSI, SAVI e REDNESS a partir de uma pilha de bandas cruas (n_bands, H, W),
    nas 4 primeiras posições azul, verde, vermelho, NIR e na 5ª SWIR1 — mesma ordem exportada
    tanto pelo Sentinel-2 quanto pelo Landsat, então funciona pros dois sem mudar nada.

    SAVI existe só pra ajudar a separar vegetação densa de grama: SAVI corrige o NDVI pelo
    brilho do solo por baixo — num gramado (dossel não fecha 100%) o solo "vaza" mais e o
    SAVI fica mais baixo que o NDVI; numa vegetação densa (dossel fechado) os dois ficam
    parecidos.

    REDNESS existe pra ajudar a separar solo exposto de construção — solo brasileiro
    (principalmente Latossolo/"terra roxa") é avermelhado por óxido de ferro, o que dá um
    vermelho mais alto que o verde na banda visível. Não é infalível sozinho (telha
    cerâmica tem cor parecida, e a cor do solo varia por região), por isso entra só como
    mais uma feature pro Random Forest ponderar, não como regra rígida.
    """
    blue, green, red, nir, swir1 = raw_bands[0], raw_bands[1], raw_bands[2], raw_bands[3], raw_bands[4]

    ndvi = _safe_div(nir - red, nir + red)
    ndbi = _safe_div(swir1 - nir, swir1 + nir)
    bsi = _safe_div((swir1 + red) - (nir + blue), (swir1 + red) + (nir + blue))
    savi = _safe_div(nir - red, nir + red + L_SAVI) * (1 + L_SAVI)
    redness = _safe_div(red - green, red + green)

    return {'NDVI': ndvi, 'NDBI': ndbi, 'BSI': bsi, 'SAVI': savi, 'REDNESS': redness}


def build_feature_stack_obra(caminho_tif):
    """Lê um GeoTIFF e devolve (feature_stack, nodata_mask, indices).

    feature_stack: bandas cruas + [NDVI, NDBI, BSI, SAVI, REDNESS] empilhadas — (n_bands+5,
    H, W). nodata_mask: True onde o pixel não tem dado válido (todas as bandas cruas
    zeradas, como nos GeoTIFFs recortados no buffer quadrado ao redor do ponto).
    indices: dict com os arrays separados, pra rotulagem por limiar.
    """
    with rasterio.open(caminho_tif) as src:
        raw = src.read()

    nodata_mask = np.all(raw == 0, axis=0)
    indices = compute_indices_obra(raw)
    indices_stack = np.stack(
        [indices['NDVI'], indices['NDBI'], indices['BSI'], indices['SAVI'], indices['REDNESS']],
        axis=0,
    )
    feature_stack = np.concatenate([raw, indices_stack], axis=0)
    return feature_stack, nodata_mask, indices


def seed_labels_from_indices(
    indices, nodata_mask,
    ndvi_vegetacao_densa=0.6, savi_vegetacao_densa=0.5, ndvi_grama_min=0.35,
    ndvi_nao_vegetacao=0.2, ndbi_construcao=0.0, bsi_solo_exposto=0.1,
    redness_solo_exposto=0.03,
):
    """Rotula com limiar só os pixels "óbvios" — o resto fica SEM_DADO, pra não ensinar o
    modelo com um palpite ruim bem nas zonas mais difíceis (solo exposto vs. construção, e
    vegetação densa vs. grama — os dois pares mais parecidos entre si). O Random Forest
    treinado nesses casos óbvios é quem resolve a zona cinzenta depois, na classificação de
    fato.

    Regras (nessa ordem):
    - NDVI > ndvi_vegetacao_densa e SAVI > savi_vegetacao_densa
        (dossel fechado, solo não "vaza" por baixo)         -> Vegetação densa
    - NDVI > ndvi_grama_min (mas não bateu a regra acima:
        NDVI moderado, ou NDVI alto com SAVI baixo — solo
        vazando por baixo do gramado)                       -> Grama
    - NDVI < ndvi_nao_vegetacao (não é vegetação) e:
        - NDBI > ndbi_construcao                            -> Construção
        - NDBI <= ndbi_construcao e BSI > bsi_solo_exposto
            e REDNESS > redness_solo_exposto (avermelhado,
            como solo brasileiro típico — filtra telhado
            claro/cinza que também tem BSI alto)             -> Solo exposto
    - qualquer outro caso (zona cinzenta, incl. NDVI entre
        ndvi_nao_vegetacao e ndvi_grama_min)                -> SEM_DADO

    A exigência de REDNESS ajuda a não confundir superfície clara/cinza (que também tem BSI
    alto) com solo exposto, mas não resolve tudo sozinha: telha cerâmica também é
    avermelhada, e a cor do solo varia por região do Brasil — por isso REDNESS também vai
    pro feature_stack como mais uma banda pro Random Forest, não só pro rótulo-semente.

    Calibração: rode isso num data center cujo início/fim de obra real você já sabe, plote
    `plot_mask_overlay_obra` pros anos-chave e veja se o rótulo-semente bate com o que você
    vê a olho nu no RGB. Se não bater, ajuste os limiares aqui (ex: baixar
    `ndvi_vegetacao_densa`/`savi_vegetacao_densa` se vegetação claramente densa está caindo
    em "Grama", subir `bsi_solo_exposto` se telhado claro está sendo confundido com solo
    exposto, ou baixar `redness_solo_exposto` se solo real da região está ficando de fora
    por não ser tão avermelhado quanto o Latossolo do Sudeste).
    """
    ndvi, ndbi, bsi, savi, redness = (
        indices['NDVI'], indices['NDBI'], indices['BSI'], indices['SAVI'], indices['REDNESS'],
    )
    labels = np.full(ndvi.shape, SEM_DADO, dtype=np.uint8)

    densa = (ndvi > ndvi_vegetacao_densa) & (savi > savi_vegetacao_densa)
    labels[densa] = VEGETACAO_DENSA
    labels[~densa & (ndvi > ndvi_grama_min)] = GRAMA

    nao_vegetacao = ndvi < ndvi_nao_vegetacao
    labels[nao_vegetacao & (ndbi > ndbi_construcao)] = CONSTRUCAO
    labels[
        nao_vegetacao & (ndbi <= ndbi_construcao)
        & (bsi > bsi_solo_exposto) & (redness > redness_solo_exposto)
    ] = SOLO_EXPOSTO

    labels[nodata_mask] = SEM_DADO
    return labels


def extract_seed_samples(feature_stack, seed_labels):
    """Achata a imagem e devolve só os pixels com rótulo-semente (exclui SEM_DADO) — sem
    amostrar/balancear ainda, isso é feito depois, juntando pixels de várias imagens (ver
    `balancear_amostras`), porque uma imagem sozinha (poucas dezenas de pixels no Landsat)
    tem amostra de menos pra treinar sozinha."""
    n_bands = feature_stack.shape[0]
    flat_features = feature_stack.reshape(n_bands, -1).T
    flat_labels = seed_labels.ravel()

    valido = flat_labels != SEM_DADO
    return flat_features[valido], flat_labels[valido]


def balancear_amostras(X, y, n_por_classe=3000, seed=42):
    """Amostra até `n_por_classe` pixels de cada classe (pool de várias imagens), pra
    treino balanceado."""
    rng = np.random.default_rng(seed)
    X_list, y_list = [], []
    for cls in np.unique(y):
        idx = np.where(y == cls)[0]
        n = min(n_por_classe, len(idx))
        chosen = rng.choice(idx, size=n, replace=False)
        X_list.append(X[chosen])
        y_list.append(y[chosen])

    X_bal, y_bal = np.concatenate(X_list), np.concatenate(y_list)
    print(f'Amostras de treino: {X_bal.shape[0]} pixels')
    for cls in np.unique(y_bal):
        print(f'  {CLASS_NAMES_OBRA[cls]}: {(y_bal == cls).sum()} amostras')
    return X_bal, y_bal


def train_random_forest_obra(X_train, y_train, X_test, y_test):
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=20, n_jobs=-1,
        random_state=42, class_weight='balanced',
    )
    rf.fit(X_train, y_train)
    print(classification_report(
        y_test, rf.predict(X_test), target_names=CLASS_NAMES_OBRA, zero_division=0,
    ))
    return rf


def classify_image(feature_stack, nodata_mask, model):
    """Aplica o modelo treinado pixel a pixel na imagem inteira."""
    n_bands, h, w = feature_stack.shape
    flat = feature_stack.reshape(n_bands, -1).T
    pred = model.predict(flat)
    classified = pred.reshape(h, w).astype(np.uint8)
    classified[nodata_mask] = SEM_DADO
    return classified


def compute_class_percentages_obra(classified):
    """% de área (pixels) por classe, ignorando nodata."""
    valid = classified[classified != SEM_DADO]
    total = valid.size
    return {
        name: round(100 * (valid == cls).sum() / total, 2) if total else 0
        for cls, name in enumerate(CLASS_NAMES_OBRA)
    }


def plot_timeseries_obra(df, name_datacenter, salvar_em=None, mostrar=True, ano_operacional=None):
    """Plota a evolução do % de área por classe ao longo dos anos, pra um data center.

    `ano_operacional`: se esse data center for uma amostra de referência (ver
    `config_obra.REFERENCIA_CSV`), desenha uma linha vertical nesse ano — dá pra conferir a
    olho nu se o "fim de obra" que o modelo sugere (construção alta + vegetação voltando)
    bate com o ano real em que o site entrou em operação.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    for classe, cor in zip(CLASS_NAMES_OBRA, CLASS_COLORS_OBRA):
        dados = df[df['classe'] == classe]
        ax.plot(dados['ano'], dados['percentual'], marker='o', label=classe, color=cor)

    if ano_operacional:
        ax.axvline(ano_operacional, color='black', linestyle='--', alpha=0.6,
                   label=f'Ano operacional (referência): {ano_operacional}')

    ax.set_title(f'Evolução vegetação densa/grama/solo/construção — {name_datacenter}')
    ax.set_xlabel('Ano')
    ax.set_ylabel('% da área')
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()

    if salvar_em:
        plt.savefig(salvar_em, dpi=150, bbox_inches='tight')
        print(f'Salvo: {salvar_em}')
    if mostrar:
        plt.show()
    else:
        plt.close(fig)


def plot_mask_overlay_obra(feature_stack, classified, titulo='', alpha=0.5, salvar_em=None, mostrar=True):
    """Sobrepõe a máscara de classificação (semi-transparente) à composição RGB do site —
    útil pra conferir a olho nu se o rótulo-semente/classificação fazem sentido (ver
    docstring de `seed_labels_from_indices` sobre calibração)."""
    red, green, blue = feature_stack[2], feature_stack[1], feature_stack[0]
    rgb = np.clip(np.dstack([red, green, blue]) / 0.3, 0, 1)

    cmap = mcolors.ListedColormap(CLASS_COLORS_OBRA)
    norm = mcolors.BoundaryNorm(list(range(len(CLASS_NAMES_OBRA) + 1)), cmap.N)
    mask = np.ma.masked_where(classified == SEM_DADO, classified)

    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(rgb)
    ax.imshow(mask, cmap=cmap, norm=norm, alpha=alpha)
    ax.set_title(titulo)
    ax.axis('off')

    patches = [
        mpatches.Patch(color=CLASS_COLORS_OBRA[i], label=CLASS_NAMES_OBRA[i])
        for i in range(len(CLASS_NAMES_OBRA))
    ]
    ax.legend(handles=patches, loc='upper right', bbox_to_anchor=(1.3, 1))

    if salvar_em:
        plt.savefig(salvar_em, dpi=150, bbox_inches='tight')
        print(f'Salvo: {salvar_em}')
    if mostrar:
        plt.show()
    else:
        plt.close(fig)
