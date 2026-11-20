"""Roda o pipeline completo: baixa as fontes, processa e monta o site.

Uso: python -I pipeline/atualizar.py [--pages]
  --pages  também monta dist/ para o GitHub Pages
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    ["download_itbi.py", "--force"],   # o arquivo do ano corrente muda todo mês
    ["download_ipca.py"],
    ["download_lotes.py"],
    ["download_base.py"],
    ["parse_itbi.py"],
    ["build_site_data.py"],
    ["build_tiles.py"],
]


def main():
    steps = list(STEPS)
    if "--pages" in sys.argv:
        steps.append(["build_pages.py"])
    for step in steps:
        t = time.time()
        print(f"\n=== {' '.join(step)}", flush=True)
        subprocess.run([sys.executable, "-I", "-W", "ignore", str(HERE / step[0]), *step[1:]], check=True)
        print(f"=== ok em {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
