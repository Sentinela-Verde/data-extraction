# notebooks_antigos — arquivo temporário

Notebooks originais, mantidos aqui só de referência enquanto o conteúdo
equivalente é migrado para código (`.py`) nas pastas correspondentes de
`extract/`, `transform/` e `modeling/`. **Esta pasta é temporária** — o plano
é mover esses notebooks pra fora deste repositório (backup externo), não
deixá-los aqui a longo prazo. Não é mais o lugar de onde os pipelines rodam.

A estrutura interna espelha de onde cada notebook veio:

```
notebooks_antigos/
├── extract/imagens_satelite/step1_extracao_imagens_satelite.ipynb
├── transform/filtra_datacenter/step0_filtra_dados.ipynb
└── modeling/
    ├── modelo_classifica_imagem/step2_classificacao_imagens.ipynb
    ├── modelo_grupo_controle/step0b_cidades_similares.ipynb
    ├── modelo_grupo_controle/step0c_grupo_controle.ipynb
    └── modelo_impacto/
        ├── modelo_impacto.ipynb
        └── modelo_impacto_estagio2.ipynb
```

Cada um foi reescrito como script em `config.py` + `stepN_*.py` na pasta
correspondente (ver o README de cada uma). Se notar alguma diferença de
comportamento entre o notebook antigo e o script novo, o script novo é a
versão a corrigir — mas vale conferir aqui qual era a lógica original.
