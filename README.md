# Pipeline de dados do Sentinela Verde

Repositório com todas as etapas do processamento de dados do projeto, da
coleta bruta até o dado pronto pra análise: **extração → transformação →
modelagem → analytics**. Cada etapa é uma pasta própria na raiz, e o dado
percorre as camadas em `data/` (`raw` → `silver` → `gold`) conforme passa por
elas.

```
data-extraction/
├── extract/                       # ETAPA 1: coleta de dado bruto
│   ├── scraping_datacentermap/    # coleta: scraping do datacentermap.com
│   │   └── README.md              #   -> como rodar, estrutura interna, colunas do CSV
│   └── bigquery_ibge/             # coleta: Base dos Dados / IBGE (BigQuery)
│       └── README.md              #   -> como rodar, autenticação, colunas do CSV
├── transform/                     # ETAPA 2: raw -> silver/gold (ainda vazio)
├── modeling/                      # ETAPA 3: modelagem sobre o dado tratado (ainda vazio)
├── analytics/                     # ETAPA 4: análises/consumo final (ainda vazio)
└── data/                          # dado em trânsito entre as etapas
    ├── raw/                       # dado bruto de todas as coletas, uma pasta por fonte
    │   ├── datacentermap/
    │   │   ├── pais/
    │   │   ├── regioes/
    │   │   └── datacenters/
    │   └── outputs_extraction/    # CSVs finais de todas as coletas (saída da etapa extract)
    │       ├── datacentermap_datacenters.csv
    │       └── ibge_municipios.csv
    ├── silver/                    # dado tratado/normalizado (saída da etapa transform, ainda vazio)
    └── gold/                      # dado pronto pra consumo final (saída da modelagem/analytics, ainda vazio)
```

## Etapas do pipeline

1. **`extract/`** — coletas independentes (scraping, API, etc.), cada uma na
   sua própria pasta. Detalhes na seção [Coletas](#coletas) abaixo.
2. **`transform/`** — limpeza, normalização e merge do que está em
   `data/raw/` pra produzir `data/silver/`. Ainda vazio.
3. **`modeling/`** — modelagem (estatística/ML) em cima do dado de
   `data/silver/`. Ainda vazio.
4. **`analytics/`** — análises e artefatos de consumo final, a partir de
   `data/silver/` e/ou `data/gold/`. Ainda vazio.

À medida que `transform/`, `modeling/` e `analytics/` ganharem conteúdo, cada
uma passa a ter seu próprio README com o "como rodar" específico, do mesmo
jeito que as pastas de coleta já têm.

## Convenção pras coletas (`extract/`)

Cada coleta é uma pasta própria dentro de `extract/` (`scraping_datacentermap/`,
`bigquery_ibge/`, ...) com seu próprio código, `config.py` e (se precisar)
`requirements.txt` — sem compartilhar código entre coletas. O que é
compartilhado é só a **saída**, guardada fora de `extract/`, em `data/raw/`:

- **`data/raw/<fonte>/...`** — dado bruto extraído por aquela coleta, o mais
  próximo possível do que a fonte devolveu (só convertido de HTML/resposta de
  API pra JSON pequeno). Também funciona como cache incremental: se o item já
  está lá com status `ok`, a coleta não busca de novo.
- **`data/raw/outputs_extraction/<fonte>_<algo>.csv`** — o(s) CSV(s) finais e
  prontos pra uso de cada coleta, já limpos/mesclados. É o que a etapa
  `transform/` deveria consumir.

CSVs intermediários que só interessam a uma coleta (ex.:
`extract/scraping_datacentermap/output/regioes.csv`) ficam dentro da própria
pasta da coleta, não em `data/raw/`.

## Coletas

| Pasta | Fonte | Status | Saída em `data/raw/outputs_extraction/` |
|---|---|---|---|
| `extract/scraping_datacentermap/` | datacentermap.com (Selenium) | pronta — [README](extract/scraping_datacentermap/README.md) | `datacentermap_datacenters.csv` |
| `extract/bigquery_ibge/` | Base dos Dados / IBGE (BigQuery) | pronta — [README](extract/bigquery_ibge/README.md) | `ibge_municipios.csv` |

Cada pasta de coleta tem seu próprio README com o "como rodar" específico.
