# data-extraction — camada de coleta de dados

Ponto de entrada pra várias coletas independentes (scraping, API, etc.), cada
uma na sua pasta dentro de `extract/`, com dois pontos em comum: onde guardam
o dado bruto (`data/raw/`) e onde entregam o resultado final
(`data/raw/outputs_extraction/`).

```
data-extraction/
├── extract/
│   ├── scraping_datacentermap/    # coleta: scraping do datacentermap.com
│   │   └── README.md              #   -> como rodar, estrutura interna, colunas do CSV
│   └── bigquery_ibge/             # coleta: Base dos Dados / IBGE (BigQuery)
│       └── README.md              #   -> como rodar, autenticação, colunas do CSV
├── data/
│   ├── raw/                       # dado bruto de todas as coletas, uma pasta por fonte
│   │   ├── datacentermap/
│   │   │   ├── pais/
│   │   │   ├── regioes/
│   │   │   └── datacenters/
│   │   └── outputs_extraction/    # CSVs finais de todas as coletas
│   │       ├── datacentermap_datacenters.csv
│   │       └── ibge_municipios.csv
│   ├── silver/                    # dado tratado/normalizado (ainda vazio)
│   └── gold/                      # dado pronto pra consumo final (ainda vazio)
├── transform/                     # transformação raw -> silver/gold (ainda vazio)
├── modeling/                      # modelagem (ainda vazio)
└── analytics/                     # análises/consumo final (ainda vazio)
```

## Convenção pras coletas

Cada coleta é uma pasta própria dentro de `extract/` (`scraping_datacentermap/`,
`bigquery_ibge/`, ...) com seu próprio código, `config.py` e (se precisar)
`requirements.txt` — sem compartilhar código entre coletas. O que é
compartilhado é só a **saída**, guardada fora de `extract/`, em `data/raw/`:

- **`data/raw/<fonte>/...`** — dado bruto extraído por aquela coleta, o mais
  próximo possível do que a fonte devolveu (só convertido de HTML/resposta de
  API pra JSON pequeno). Também funciona como cache incremental: se o item já
  está lá com status `ok`, a coleta não busca de novo.
- **`data/raw/outputs_extraction/<fonte>_<algo>.csv`** — o(s) CSV(s) finais e
  prontos pra uso de cada coleta, já limpos/mesclados. É o que outra etapa
  (`transform/`, `modeling/`, `analytics/`) deveria consumir.

CSVs intermediários que só interessam a uma coleta (ex.:
`extract/scraping_datacentermap/output/regioes.csv`) ficam dentro da própria
pasta da coleta, não em `data/raw/`.

## Coletas

| Pasta | Fonte | Status | Saída em `data/raw/outputs_extraction/` |
|---|---|---|---|
| `extract/scraping_datacentermap/` | datacentermap.com (Selenium) | pronta — [README](extract/scraping_datacentermap/README.md) | `datacentermap_datacenters.csv` |
| `extract/bigquery_ibge/` | Base dos Dados / IBGE (BigQuery) | pronta — [README](extract/bigquery_ibge/README.md) | `ibge_municipios.csv` |

Cada pasta de coleta tem seu próprio README com o "como rodar" específico.
