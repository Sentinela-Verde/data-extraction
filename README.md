# SENTINELA VERDE — versão final VS Code + Google Colab

## O que foi ajustado
- Período temporal padronizado em **2017–2026**.
- Random Forest continua usando somente Sentinel-2 + NDVI/NDWI/NDBI.
- MapBiomas Collection 10/2023 permanece como referência dos rótulos.
- Avaliação do RF: matriz de confusão, acurácia global, Kappa e importância.
- Análise Pré/Durante/Pós por Data Center.
- Controle espacial: anel externo **5–10 km**.
- Efeito relativo: **ΔDC − ΔControle**.
- VIIRS VNP46A2: luz noturna.
- Landsat 8/9 L2: temperatura da superfície (LST).
- Dynamic World: validação/referência independente de cobertura do solo.
- ERA5-Land: contexto climático.
- JRC Global Surface Water e WorldPop: contexto ambiental/populacional.
- ANA, ANEEL, ONS, IBGE e OSM: entradas locais opcionais.
- Energia/água: distinguidas entre informadas e estimadas.
- Ranking por dimensões e índice multidimensional exploratório.
- 2026 marcado como ano parcial.
- Nenhuma coordenada faltante é inventada.

## Ordem
NB01 → NB02 → NB03 → NB04 → NB05 → NB06 → dashboard

## VS Code
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python scripts/run_pipeline.py
streamlit run dashboard.py
```

## Google Colab
Envie/abra esta pasta no Drive, instale requirements e execute os mesmos seis notebooks.
O pacote também contém notebooks `.ipynb` equivalentes.

## Fontes locais opcionais
Os arquivos em `data/external/` são templates. Só produzem indicadores quando preenchidos com
dados reais. O pipeline não inventa ANA/ANEEL/ONS/IBGE/OSM.

## Interpretação metodológica
O resultado é de transformação territorial/ambiental e associação temporal/multifonte.
Não deve ser apresentado como causalidade automática.
