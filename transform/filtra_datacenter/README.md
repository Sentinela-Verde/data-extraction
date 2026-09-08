# filtra_datacenter — raw → silver dos data centers

Primeiro passo da etapa `transform/`: pega o CSV bruto do
[`extract/scraping_datacentermap`](../../extract/scraping_datacentermap/README.md)
e filtra só os data centers que servem pro estudo de impacto — ver o
[README da raiz](../../README.md) pra como essa etapa se encaixa no pipeline.

## Critério de elegibilidade

Um data center entra no estudo se:

- **`status == 1`** — está ativo (não descontinuado/planejado).
- **`stage == 2`** — já foi construído (não é só projeto anunciado).
- **`tipo_listagem == 'Facility'`** — exclui listagens de "Campus" e
  "Multi-Tenant Building" (que agregam vários facilities e distorceriam a
  unidade de observação do estudo).
- **`ano_operacional`** entre **2018 e 2024** (exclusive nas pontas — ver
  `config.ANO_OPERACIONAL_MIN`/`MAX`; linhas sem `ano_operacional` preenchido
  também caem fora, já que `NaN` nunca satisfaz uma comparação `>`/`<`).

O motivo da janela de anos: o modelo de impacto (`modeling/modelo_impacto/`)
mede o efeito numa janela móvel ao redor do ano de abertura (ano-3 até
ano+2). Um data center que abriu antes de 2018 ou depois de 2024 não deixaria
sobrar anos suficientes de série de satélite (2016-2026) dos dois lados da
abertura.

## Como rodar

```bash
cd data-extraction/transform/filtra_datacenter
python step1_filtra_dados.py
```

- **Entrada:** `../../data/raw/outputs_extraction/datacentermap_datacenters.csv`
- **Saída:** `../../data/silver/datacenter_filtrado.csv` (mesmo separador `;`),
  com as colunas de identificação e porte (`nome_datacenter`, `endereco`,
  `cidade`, `latitude`, `longitude`, `tags`, `mw_construido`,
  `whitespace_construido_m`, `ano_operacional`, `tipo_construcao`). Não tem
  mais `id_datacenter`/`estado` — `nome_datacenter` é o identificador usado em
  todo o pipeline a partir daqui (precisa ser único entre os data centers
  filtrados).

## Quem consome essa saída

- `modeling/modelo_grupo_controle/` — pareia cada data center filtrado (por
  `nome_datacenter`) com um grupo de controle.
- `extract/imagens_satelite/` — usa `nome_datacenter`/`latitude`/`longitude`
  como lista de pontos a extrair do Google Earth Engine.
