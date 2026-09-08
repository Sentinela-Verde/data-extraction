# modelo_classifica_imagem — classificação de cobertura do solo

Rotula, treina e classifica a série temporal de imagens de satélite baixada por
[`extract/imagens_satelite`](../../extract/imagens_satelite/README.md), transformando cada
GeoTIFF Sentinel-2 num % de área por classe de cobertura do solo. É a fonte das variáveis
de satélite (`prop_vegetacao_densa`, `prop_construida_urbana`, etc.) usadas em
[`modeling/modelo_impacto`](../modelo_impacto/README.md).

## Classes

| Classe | Cor | Origem no rótulo |
|---|---|---|
| Vegetação | verde | ESA WorldCover (classes 10,20,30,40,95,100) |
| Água | azul | ESA WorldCover (classes 80,90) |
| Construção | vermelho | ESA WorldCover (classe 50) |
| Estrada | cinza | malha viária OpenStreetMap (sobrepõe WorldCover) |
| Outro | amarelo | ESA WorldCover (classes 60,70 — solo exposto/outro) |

## Pipeline (por data center)

1. **Rótulo de referência** — exporta o [ESA WorldCover v200](https://esa-worldcover.org/)
   pro ano de `config.REFERENCE_YEAR` (padrão: 2024) na mesma região do GeoTIFF, remapeia
   pras 5 classes do projeto, e sobrepõe a malha viária do OpenStreetMap (via `osmnx`) —
   a classe "Estrada" tem prioridade sobre o que o WorldCover disser embaixo dela.
2. **Features** — cada pixel vira um vetor com as 6 bandas cruas do Sentinel-2 (`B2,B3,B4,
   B8,B11,B12`) + 9 índices espectrais (NDVI, NDWI, NDBI, EVI, SAVI, BSI, MNDWI, IBI, NDMI —
   ver `indices.py`).
3. **Treino** — amostra `config.N_SAMPLES_PER_CLASS` pixels por classe do rótulo do ano de
   referência e treina dois modelos: um Random Forest e uma rede neural densa (Keras).
4. **Classificação** — aplica os dois modelos em **todos** os anos disponíveis da série
   (`metadata.json` do Step 1), não só no ano de referência.
5. **Agregação** — calcula % de área e área em km² por classe/ano/modelo.

## Como rodar

```bash
cd data-extraction/modeling/modelo_classifica_imagem
pip install -r requirements.txt
python step2_classificacao_imagens.py                      # todos os data centers com metadata.json
python step2_classificacao_imagens.py --datacenter dc_123   # só um
```

Precisa de `EE_PROJECT` no `.env` da raiz (usado só pra exportar o rótulo WorldCover — a
classificação em si roda localmente, sem Earth Engine).

## Arquivos

- `classification.py` — funções reutilizáveis: exportar/remapear rótulos, treinar,
  classificar, agregar, plotar. Chamado pelo step, não roda sozinho.
- `indices.py` — cálculo dos índices espectrais (`load_features`). **Reconstruído durante a
  reorganização deste repositório** — o notebook original já importava esse módulo, mas o
  arquivo em si não estava entre o código migrado. As fórmulas usadas são as fórmulas padrão
  de sensoriamento remoto para cada índice; vale conferir se batem com o que foi de fato
  usado pra treinar os modelos já existentes antes de usar isso em produção (ver comentário
  no topo do arquivo).
- `step2_classificacao_imagens.py` — orquestra: acha todos os `*_metadata.json` em
  `data/raw/imagens_satelite/`, roda o pipeline pra cada data center, salva e consolida.

## Saídas

- `data/silver/cobertura_solo/<nome_datacenter>_cobertura_por_ano.csv` — % de área e área em
  km² por classe, ano e modelo (Random Forest / Rede Neural), um arquivo por data center.
- `data/silver/cobertura_solo/cobertura_todos_datacenters.csv` — os CSVs acima empilhados.
  É essa tabela que alimenta o painel consolidado de `modeling/modelo_impacto`.
- `data/silver/cobertura_solo/<nome_datacenter>_evolucao.png` — gráfico da evolução do % de
  área por classe ao longo dos anos (modelo Random Forest).
- `data/raw/imagens_satelite_overlay/<nome_datacenter>_<ano>_overlay.jpg` — composição RGB com
  a máscara de classificação sobreposta (semi-transparente), pra conferência visual de cada
  ano classificado.
- `data/raw/labels/<nome_datacenter>_worldcover.tif` — rótulo WorldCover exportado (cache
  intermediário, reaproveitável entre execuções).

## Limitações conhecidas

- O treino usa só o ano de referência como rótulo — o WorldCover não tem uma versão
  histórica confiável pra todos os anos da série 2016-2026, então os demais anos são
  classificados com o modelo treinado num único ano (2024). Mudanças de cobertura muito
  anteriores a 2024 dependem do modelo generalizar bem, não de um rótulo daquele ano
  específico.
- `indices.py` foi reconstruído (ver acima) — mesma ressalva.
