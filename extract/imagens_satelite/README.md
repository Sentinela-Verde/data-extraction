# imagens_satelite — extração da série temporal Sentinel-2

Coleta a matéria-prima do resto do pipeline: para cada data center (e, futuramente, cada
ponto de controle) filtrado em [`transform/filtra_datacenter`](../../transform/filtra_datacenter/README.md),
baixa via Google Earth Engine um GeoTIFF Sentinel-2 por ano, cobrindo toda a série
2016-2026. É uma das coletas dentro de `data-extraction/extract/` — ver o
[README da raiz](../../README.md) pra como as coletas se encaixam.

Diferente das outras coletas (`scraping_datacentermap`, `bigquery_ibge`), aqui o dado bruto
não é tabular — é imagem — mas o princípio é o mesmo: `extraction.py` guarda as funções
reutilizáveis, `config.py` guarda os caminhos e parâmetros, e `step1_extracao_imagens_satelite.py`
é o script que de fato roda.

## Como funciona

Para cada data center (`nome_datacenter`, `latitude`, `longitude`) e cada ano de
`config.YEAR_LIST`:

1. Filtra a coleção `COPERNICUS/S2_SR_HARMONIZED` pela janela de meses
   `config.MONTH_START`–`config.MONTH_END` (maio-julho — período historicamente mais
   livre de nuvens no Sudeste/Centro-Oeste/Sul) e por `CLOUDY_PIXEL_PERCENTAGE <
   config.CLOUD_PCT`.
2. Mascara nuvem e cirrus pixel a pixel (`mask_s2_clouds`, usando a banda `QA60`).
3. Tira a mediana temporal das imagens que sobraram e recorta num buffer de
   `config.BUFFER_M` (3km de raio → ~6km x 6km) ao redor do ponto.
4. Exporta um GeoTIFF com as bandas `config.DEFAULT_BANDS` (`B2,B3,B4,B8,B11,B12`) —
   RGB + infravermelho próximo + dois SWIR — na resolução `config.SCALE` (10m/pixel).

Ao final, salva um `<nome_datacenter>_metadata.json` por data center com os parâmetros usados
(bandas, buffer, escala, CRS) — reaproveitado por
[`modeling/modelo_classifica_imagem`](../../modeling/modelo_classifica_imagem/README.md) pra
saber como interpretar cada GeoTIFF sem precisar repetir esses parâmetros.

`nome_datacenter` (a coluna `nome_datacenter` de `datacenter_filtrado.csv`) é o identificador
usado em todo o pipeline pra partir daqui — não tem mais um `id_datacenter` separado. Como o
nome vira literalmente o nome dos arquivos gerados (`<nome_datacenter>_<ano>.tif`, etc.), ele
precisa ser único entre os data centers filtrados e não conter `/` ou `\`.

## Como rodar

Autenticação (só na primeira vez nesta máquina):

```bash
cd data-extraction/extract/imagens_satelite
pip install -r requirements.txt
python -c "import ee; ee.Authenticate()"   # abre o fluxo de login do Earth Engine no navegador
```

Defina `EE_PROJECT` no `.env` da raiz do repo (projeto do Google Cloud usado pra
autenticar/cotas do Earth Engine — ver `.env.example`).

Rodar a extração:

```bash
python step1_extracao_imagens_satelite.py
```

Isso baixa um GeoTIFF por (data center, ano) e gera as composições RGB em JPG pra
conferência visual. Pra só regenerar os JPGs a partir de `.tif` já baixados (sem gastar
cota do Earth Engine):

```bash
python step1_extracao_imagens_satelite.py --so-jpgs
```

A extração é **incremental por execução do Earth Engine**, mas não pula automaticamente
o que já foi baixado (diferente do cache de `scraping_datacentermap`) — rodar de novo
sempre baixa tudo. Se quiser reprocessar só alguns data centers, edite temporariamente
`config.DATACENTERS_CSV` pra apontar pra um CSV com só as linhas desejadas, ou filtre
`df_datacenters` dentro de `main()`.

## Saídas (`data/raw/imagens_satelite/`)

- `<nome_datacenter>_<ano>.tif` — um GeoTIFF por (data center, ano), bandas na ordem
  `B2,B3,B4,B8,B11,B12`.
- `<nome_datacenter>_metadata.json` — parâmetros da extração (`lat`, `lon`, `year_list`,
  `bands`, `buffer_m`, `scale`, `crs`), consumido pelo step de classificação.
- `data/raw/imagens_satelite_jpg/<nome_datacenter>_<ano>.jpg` — composição RGB de cada
  GeoTIFF, só pra inspeção visual (não é lido por nenhum step seguinte).

## Quem consome essa saída

[`modeling/modelo_classifica_imagem`](../../modeling/modelo_classifica_imagem/README.md) lê os
GeoTIFFs e o `metadata.json` pra rotular, treinar e classificar a cobertura do solo de cada
ano da série.
