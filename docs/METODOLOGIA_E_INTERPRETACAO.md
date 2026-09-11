# Metodologia e interpretação

## Pergunta central
O pipeline procura responder: **o que mudou no território, quando mudou, em que intensidade e como a mudança se relaciona com água, energia, urbanização, população e condições ambientais?**

## O que o Random Forest faz
Classifica pixels em Vegetação, Construído/Não vegetado e Água. Usa apenas Sentinel-2 e índices espectrais. MapBiomas fornece os rótulos de referência de 2023.

## O que as fontes externas fazem
VIIRS, Landsat/LST, Dynamic World, ERA5-Land, JRC, WorldPop, ANA, ANEEL, ONS, IBGE e OSM são usados para **cruzamento e interpretação**, não como rótulos adicionais do Random Forest.

## Controle espacial
Para cada Data Center:
- área analisada: 0–5 km;
- anel de controle: 5–10 km;
- efeito relativo: `(Pós − Pré)_DC − (Pós − Pré)_Controle`.

Isso reduz a dependência de uma comparação simples antes/depois, mas não transforma o estudo automaticamente em desenho causal.

## Energia e água
- consumo direto: somente quando houver dado real e fonte identificada;
- energia estimada: `IT Load × PUE × 8760`;
- água estimada por WUE: `Energia IT (MWh) × WUE (L/kWh)`, numericamente equivalente a m³/ano;
- capacidade MW não é tratada como consumo observado.

## Limitações
- coordenadas ausentes continuam ausentes;
- 2026 é ano parcial;
- OSM/ANA/ANEEL/IBGE/ONS podem exigir arquivos externos atualizados;
- VIIRS é proxy de luminosidade noturna, não consumo elétrico;
- LST é temperatura da superfície;
- correlações são exploratórias;
- o índice integrado é uma síntese, não uma prova de causalidade.
