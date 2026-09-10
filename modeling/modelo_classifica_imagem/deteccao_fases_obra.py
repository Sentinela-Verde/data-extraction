"""Fluxo separado: a partir da tabela de % por classe/ano gerada por
`step_classificacao_obra.py`, decide em que fase de obra cada (data center, ano) estava —
Pré-obra / Início de obra / Durante obra / Fim de obra / Indefinido.

Não toca em GeoTIFF nem em Earth Engine — só lê o CSV consolidado e aplica regras de limiar
sobre as % já calculadas. Roda em segundos, então é seguro reexecutar toda vez que ajustar um
limiar aqui embaixo, sem precisar reclassificar imagem nenhuma.

Regras (nessa ordem de prioridade, aplicadas ano a ano, mas COM MEMÓRIA da sequência —
ver `classifica_serie`):
- Se a série já passou por "Fim de obra" num ano anterior                -> Pós-obra
- Construção alta E (grama voltando OU solo exposto já baixo)            -> Fim de obra
- Construção presente E solo exposto presente                            -> Durante obra
- Solo exposto alto, OU aumento de solo exposto vs. o ano anterior
    observado do mesmo site (mesmo que o valor absoluto ainda seja baixo) -> Início de obra
- Vegetação densa OU grama alta (e sem solo exposto/construção)          -> Pré-obra
- Nenhuma condição acima                                                  -> Indefinido

"Fim de obra" tem DOIS jeitos de confirmar, não só um: grama voltando (paisagismo) OU solo
exposto tendo baixado (a obra "suja" acabou). No começo só existia o critério de grama, mas
isso falhava feio em sites sem quintal/gramado (ex: campus mais compacto, prédio ocupando
quase toda a área) — a construção já estava em 90%+ e o solo exposto praticamente zerado por
anos, mas como a grama nunca passava de ~10%, o site ficava "Indefinido" indefinidamente em
vez de "Fim de obra". Solo exposto caindo é, na prática, o sinal mais direto de que a etapa
de terraplanagem/fundação acabou — não depende do site ter espaço pra gramado.
"Pré-obra" já usa os dois (vegetação densa OU grama) porque no Brasil boa parte dos data
centers é construída sobre pastagem, não mata — exigir só vegetação densa deixaria de
detectar pré-obra nesses sites.

"Pós-obra" existe porque, sem memória da sequência, um site que já terminou a obra e tem
grama alta de novo (paisagismo) bateria de novo no critério de "Pré-obra" — o que não faz
sentido numa leitura cronológica: uma vez visto "Fim de obra", os anos seguintes ficam
travados em "Pós-obra", não voltam a ser reclassificados do zero.

Duas correções adicionais em `classifica_serie`, pra não decidir cada ano isolado sem olhar
a série ao redor:
- "Início de obra" só é confirmado se o ano SEGUINTE também sustentar o sinal (senão é
  tratado como ruído de 1 ano isolado, não confirma a transição ainda).
- Depois de classificar a série toda, qualquer sequência de "Indefinido" cercada pela MESMA
  fase antes e depois vira essa fase — evita série fragmentada tipo "Durante, Indefinido,
  Indefinido, Durante" quando na prática é uma obra contínua que só oscilou por cima/baixo
  de um limiar por causa de ruído pixel a pixel.

IMPORTANTE: essas duas correções foram testadas contra os 9 sites de referência (500m e
300m) e NÃO mudam nenhum ano de "Fim de obra" detectado — só limpam a leitura das fases
intermediárias. Os limiares abaixo continuam ponto de partida, não calibrados — ajuste
comparando a coluna `ano_operacional_referencia` (quando existir) com o ano em que `fase`
vira "Fim de obra" pros data centers de referência (ver `resumo_por_datacenter`).

Uso:
    python deteccao_fases_obra.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config_obra as config

import pandas as pd

# --- Limiares (% de área) — calibrar depois de olhar os resultados ---------------------
LIMIAR_VEGETACAO_PRE_OBRA = 50   # % mínima de (vegetação densa + grama) pra "pré-obra"
LIMIAR_SOLO_EXPOSTO_INICIO = 15  # % mínima de solo exposto pra considerar "início de obra"
LIMIAR_CONSTRUCAO_DURANTE = 10   # % mínima de construção (com solo exposto) pra "durante obra"
LIMIAR_SOLO_EXPOSTO_DURANTE = 10  # % mínima de solo exposto (com construção) pra "durante obra"
LIMIAR_CONSTRUCAO_FIM = 51       # % mínima de construção pra considerar possível "fim de obra" —
                                  # calibrado contra os 9 sites de referência (grid search):
                                  # erro médio de 4,6 anos (limiar 40) cai pra 3,3 anos (limiar 51).
                                  # 4 dos 9 sites têm construção >51% já em 2016 (MapBiomas pegando
                                  # o entorno urbano, não só o prédio) — pra esses, nenhum limiar
                                  # resolve; ver observação "Já concluído em 2016" no calibrador.
LIMIAR_GRAMA_FIM = 10            # % mínima de grama "voltando" (paisagismo) pra confirmar "fim de obra"
LIMIAR_SOLO_EXPOSTO_FIM = 5      # OU: % de solo exposto abaixo disso (quase zerado) também
                                  # confirma "fim de obra", mesmo sem grama — pega sites sem
                                  # margem de paisagismo (ex: TO HOST, Hortolândia HTL5 no
                                  # teste de 300m, que ficavam "Indefinido" por anos com
                                  # construção >90% só por a grama não passar de ~10%)
LIMIAR_DELTA_SOLO_INICIO = 10    # aumento mínimo de solo exposto (pontos percentuais) em
                                  # relação ao ano anterior OBSERVADO do mesmo site (não
                                  # necessariamente ano-1, se algum ano não tiver imagem) —
                                  # pega salto real mesmo quando o valor absoluto ainda não
                                  # cruza LIMIAR_SOLO_EXPOSTO_INICIO (útil pra campus mais
                                  # espaçoso, onde solo exposto nunca fica alto em %). Ponto
                                  # de partida, não calibrado.

ORDEM_FASE = {'Pré-obra': 0, 'Início de obra': 1, 'Durante obra': 2, 'Fim de obra': 3, 'Indefinido': -1}

FASES_EM_ORDEM = ['Pré-obra', 'Início de obra', 'Durante obra', 'Fim de obra', 'Pós-obra']
FASE_PARA_SLUG = {
    'Pré-obra': 'pre_obra',
    'Início de obra': 'inicio_obra',
    'Durante obra': 'durante_obra',
    'Fim de obra': 'fim_obra',
    'Pós-obra': 'pos_obra',
}


def classifica_fase_ano(vegetacao_densa, grama, solo_exposto, construcao, delta_solo=0.0):
    """Classifica UM ano isolado, sem olhar a sequência — chamado por `classifica_serie`
    pra cada ano que ainda não está "travado" em Pós-obra.

    `delta_solo`: solo_exposto deste ano menos o do ano anterior observado do mesmo site
    (0 se não houver ano anterior, ex: primeiro ano da série).
    """
    if construcao >= LIMIAR_CONSTRUCAO_FIM and (grama >= LIMIAR_GRAMA_FIM or solo_exposto <= LIMIAR_SOLO_EXPOSTO_FIM):
        return 'Fim de obra'
    if construcao >= LIMIAR_CONSTRUCAO_DURANTE and solo_exposto >= LIMIAR_SOLO_EXPOSTO_DURANTE:
        return 'Durante obra'
    if solo_exposto >= LIMIAR_SOLO_EXPOSTO_INICIO or delta_solo >= LIMIAR_DELTA_SOLO_INICIO:
        return 'Início de obra'
    if (vegetacao_densa + grama) >= LIMIAR_VEGETACAO_PRE_OBRA:
        return 'Pré-obra'
    return 'Indefinido'


def classifica_fase(vegetacao_densa, grama, solo_exposto, construcao):
    """Mantido por compatibilidade — igual a `classifica_fase_ano` sem o sinal de variação
    (delta_solo=0) e sem memória de sequência. Prefira `classifica_serie` pra uma série
    completa de um data center."""
    return classifica_fase_ano(vegetacao_densa, grama, solo_exposto, construcao)


def preenche_buracos(fases):
    """Pós-processamento: qualquer sequência de 'Indefinido' cercada pela MESMA fase antes e
    depois vira essa fase — corrige fragmentação tipo 'Durante, Indefinido, Indefinido,
    Durante' (oscilação em cima do limiar por ruído pixel a pixel) sem mudar nenhuma regra
    de decisão, só a leitura final."""
    fases = list(fases)
    n = len(fases)
    i = 0
    while i < n:
        if fases[i] != 'Indefinido':
            i += 1
            continue
        j = i
        while j < n and fases[j] == 'Indefinido':
            j += 1
        antes = fases[i - 1] if i > 0 else None
        depois = fases[j] if j < n else None
        if antes is not None and antes == depois and antes not in ('Indefinido', 'Pós-obra'):
            for k in range(i, j):
                fases[k] = antes
        i = j
    return fases


def classifica_serie(grupo):
    """Percorre os anos de UM data center em ordem cronológica e devolve a lista de fases,
    mantendo o estado entre os anos: depois que a série chega em "Fim de obra" (em qualquer
    ano, mesmo o primeiro — casos de site já construído antes da série começar), todo ano
    seguinte vira "Pós-obra" em vez de ser reclassificado do zero.

    Também calcula `delta_solo` (variação de solo exposto vs. o ano anterior observado do
    mesmo site) e passa pra `classifica_fase_ano`, que usa isso como sinal extra de "início
    de obra" — mas só CONFIRMA a transição pra "Início de obra" se o ano seguinte também
    sustentar o sinal (senão trata como ruído de 1 ano isolado e mantém a fase anterior).
    "Fim de obra" não passa por essa confirmação — ele já é "travado" via Pós-obra, então um
    gatilho de 1 ano só é intencional (e recalcular a cada ano futuro desfaria a trava).

    Por fim, `preenche_buracos` limpa sequências de "Indefinido" cercadas pela mesma fase.
    """
    grupo = grupo.sort_values('ano').reset_index(drop=True)
    n = len(grupo)

    brutas = []
    solo_anterior = None
    for _, linha in grupo.iterrows():
        solo_atual = linha.get('Solo exposto', 0)
        delta_solo = (solo_atual - solo_anterior) if solo_anterior is not None else 0.0
        brutas.append(classifica_fase_ano(
            linha.get('Vegetação densa', 0), linha.get('Grama', 0),
            solo_atual, linha.get('Construção', 0), delta_solo,
        ))
        solo_anterior = solo_atual

    fases = []
    for i in range(n):
        fase_anterior = fases[-1] if fases else None
        if fase_anterior in ('Fim de obra', 'Pós-obra'):
            fases.append('Pós-obra')
            continue

        candidata = brutas[i]
        if candidata == 'Início de obra' and i + 1 < n:
            confirmado = ORDEM_FASE.get(brutas[i + 1], -1) >= ORDEM_FASE['Início de obra']
            if not confirmado:
                candidata = fase_anterior if fase_anterior else 'Indefinido'

        fases.append(candidata)

    fases = preenche_buracos(fases)

    # reaplica a trava de Pós-obra depois do preenchimento (o preenchimento não mexe em
    # 'Fim de obra'/'Pós-obra' em si, mas por clareza garante a consistência final)
    final = []
    travado = False
    for fase in fases:
        if travado:
            final.append('Pós-obra')
        else:
            final.append(fase)
            if fase == 'Fim de obra':
                travado = True
    return final


def carrega_percentuais(caminho_csv=None):
    """Lê o CSV consolidado (formato longo: uma linha por data center/ano/classe) e pivota
    pra formato largo (uma linha por data center/ano, uma coluna por classe)."""
    caminho_csv = caminho_csv or (config.PROCESSED_DIR / 'cobertura_obra_todos_datacenters.csv')
    df = pd.read_csv(caminho_csv)

    largo = df.pivot_table(
        index=['name_datacenter', 'ano', 'ano_operacional_referencia'],
        columns='classe', values='percentual',
    ).reset_index()
    largo.columns.name = None
    return largo


def aplica_fases(largo):
    """Adiciona a coluna `fase` a cada linha (data center, ano) — classificação sequencial
    por site (com memória e sinal de variação), ver `classifica_serie`."""
    largo = largo.sort_values(['name_datacenter', 'ano']).reset_index(drop=True)
    partes = []
    for _, grupo in largo.groupby('name_datacenter', sort=False):
        grupo = grupo.copy()
        grupo['fase'] = classifica_serie(grupo)
        partes.append(grupo)
    return pd.concat(partes, ignore_index=True)


def resumo_por_datacenter(com_fases):
    """Por data center: primeiro ano em que cada fase apareceu, e — quando o data center é
    uma amostra de referência — a diferença entre o ano de "Fim de obra" detectado e o
    `ano_operacional_referencia` real (positivo = modelo detectou depois do real)."""
    linhas = []
    for nome, grupo in com_fases.groupby('name_datacenter'):
        grupo = grupo.sort_values('ano')
        linha = {'name_datacenter': nome}

        for fase in FASES_EM_ORDEM:
            anos_da_fase = grupo.loc[grupo['fase'] == fase, 'ano']
            linha[f'primeiro_ano_{FASE_PARA_SLUG[fase]}'] = (
                int(anos_da_fase.min()) if not anos_da_fase.empty else None
            )

        ano_ref = grupo['ano_operacional_referencia'].dropna()
        ano_fim_detectado = linha.get('primeiro_ano_fim_obra')
        if not ano_ref.empty and ano_fim_detectado is not None:
            linha['ano_operacional_referencia'] = int(ano_ref.iloc[0])
            linha['diferenca_anos_fim_obra'] = ano_fim_detectado - int(ano_ref.iloc[0])
        elif not ano_ref.empty:
            linha['ano_operacional_referencia'] = int(ano_ref.iloc[0])
            linha['diferenca_anos_fim_obra'] = None

        linhas.append(linha)

    return pd.DataFrame(linhas)


def main():
    largo = carrega_percentuais()
    com_fases = aplica_fases(largo)

    saida_detalhada = config.PROCESSED_DIR / 'fases_obra_por_ano.csv'
    com_fases.to_csv(saida_detalhada, index=False)
    print(f'Fase por (data center, ano) salva em {saida_detalhada}')

    resumo = resumo_por_datacenter(com_fases)
    saida_resumo = config.PROCESSED_DIR / 'fases_obra_resumo_por_datacenter.csv'
    resumo.to_csv(saida_resumo, index=False)
    print(f'Resumo por data center salvo em {saida_resumo}')

    if 'diferenca_anos_fim_obra' in resumo.columns:
        calibraveis = resumo.dropna(subset=['diferenca_anos_fim_obra'])
        if not calibraveis.empty:
            print('\nCalibração (data centers de referência) — diferença entre "Fim de '
                  'obra" detectado e o ano operacional real (0 = bateu certo):')
            print(calibraveis[['name_datacenter', 'ano_operacional_referencia',
                                'primeiro_ano_fim_obra', 'diferenca_anos_fim_obra']]
                  .to_string(index=False))


if __name__ == '__main__':
    main()
