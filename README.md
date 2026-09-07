# scraping_v2 — camada de coleta de dados

Ponto de entrada pra várias coletas independentes (scraping, API, etc.), cada
uma na sua pasta, com dois pontos em comum: onde guardam o dado bruto
(`raw_data/`) e onde entregam o resultado final (`outputs/`).

```
scraping_v2/
├── scraping_datacentermap/    # coleta: scraping do datacentermap.com
│   └── README.md              #   -> como rodar, estrutura interna, colunas do CSV
├── api_ibge/                  # coleta: API do IBGE (planejada)
├── raw_data/                  # dado bruto de todas as coletas, uma pasta por fonte
│   └── datacentermap/
│       ├── pais/
│       ├── regioes/
│       └── datacenters/
└── outputs/                   # CSVs finais de todas as coletas
    └── datacentermap_datacenters.csv
```

## Convenção pras coletas

Cada coleta é uma pasta própria (`scraping_datacentermap/`, `api_ibge/`, ...)
com seu próprio código, `config.py` e (se precisar) `requirements.txt` — sem
compartilhar código entre coletas. O que é compartilhado é só a **saída**:

- **`raw_data/<fonte>/...`** — dado bruto extraído por aquela coleta, o mais
  próximo possível do que a fonte devolveu (só convertido de HTML/resposta de
  API pra JSON pequeno). Também funciona como cache incremental: se o item já
  está lá com status `ok`, a coleta não busca de novo.
- **`outputs/<fonte>_<algo>.csv`** — o(s) CSV(s) finais e prontos pra uso de
  cada coleta, já limpos/mesclados. É o que outra etapa (join, análise,
  dashboard) deveria consumir.

CSVs intermediários que só interessam a uma coleta (ex.:
`scraping_datacentermap/output/regioes.csv`) ficam dentro da própria pasta da
coleta, não em `raw_data/` nem em `outputs/`.

## Coletas

| Pasta | Fonte | Status | Saída em `outputs/` |
|---|---|---|---|
| `scraping_datacentermap/` | datacentermap.com (Selenium) | pronta — [README](scraping_datacentermap/README.md) | `datacentermap_datacenters.csv` |
| `api_ibge/` | API do IBGE | planejada | `ibge_cidades.csv` |

Cada pasta de coleta tem seu próprio README com o "como rodar" específico.
