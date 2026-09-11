from pathlib import Path
import subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
NBS=[
"NB01_sentinela_verde.py",
"NB02_treinamento_random_forest.py",
"NB03_aplicacao_temporal.py",
"NB04_analise_temporal_impacto.py",
"NB05_cruzamento_multifonte.py",
"NB06_analise_integrada.py",
]
for nb in NBS:
    print("\n"+"="*90+"\nEXECUTANDO "+nb+"\n"+"="*90)
    subprocess.run([sys.executable,str(ROOT/"notebooks"/nb)],cwd=ROOT,check=True)
print("\nPipeline Sentinela Verde concluído.")
