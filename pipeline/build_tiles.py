"""Gera o mapa em tiles vetoriais (site/tiles/mapa.pmtiles) com o tippecanoe.

Cada camada de data/tiles_src/*.geojsonl vira um PMTiles com a sua faixa de zoom, e o
tile-join junta tudo num arquivo só. O navegador baixa só os tiles da área visível
(requisições HTTP Range, que o GitHub Pages aceita).

Precisa do tippecanoe 2.x (no Ubuntu: apt install tippecanoe). No Windows, rode pelo WSL
definindo o prefixo dos comandos, por exemplo:
  set TIPPECANOE_PREFIX=wsl.exe -d Ubuntu-24.04 -- /home/usuario/tippe/root/usr/bin/

Uso: python -I pipeline/build_tiles.py
"""
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = "data/tiles_src"
TMP = "data/tiles"
OUT = "site/tiles/mapa.pmtiles"

# camada: (zoom mínimo, zoom máximo, opções extras)
CAMADAS = {
    "quadras": (10, 16, ["--simplification=2", "--drop-smallest-as-needed"]),
    "distritos": (10, 16, ["--simplification=4"]),
    "distritos_rotulo": (10, 14, []),
    "metro_linhas": (10, 16, ["--simplification=2"]),
    "metro_estacoes": (11, 16, []),
    "avenidas": (12, 16, ["--simplification=2"]),
    "ruas": (14, 16, ["--simplification=2"]),
    "edificios": (13, 16, []),
    "lotes": (15, 16, ["--simplification=2"]),
}


def cmd(nome):
    prefix = os.environ.get("TIPPECANOE_PREFIX", "")
    parts = shlex.split(prefix, posix=True) if prefix else []
    if parts:
        parts[-1] = parts[-1] + nome  # o prefixo termina na pasta dos binários
        return parts
    return [nome]


def run(args):
    print(" ".join(args[-3:]), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    (ROOT / TMP).mkdir(parents=True, exist_ok=True)
    (ROOT / OUT).parent.mkdir(parents=True, exist_ok=True)
    partes = []
    for nome, (zmin, zmax, extra) in CAMADAS.items():
        src = f"{SRC}/{nome}.geojsonl"
        if not (ROOT / src).exists():
            print("sem dados para", nome)
            continue
        dest = f"{TMP}/{nome}.pmtiles"
        run(cmd("tippecanoe") + [
            "-o", dest, "--force", "--quiet", "-l", nome, f"-Z{zmin}", f"-z{zmax}",
            "-r1", "--no-feature-limit", *extra, src])
        partes.append(dest)
    run(cmd("tile-join") + ["-o", OUT, "--force", "--quiet", "-n", "Predio a Predio",
                            "--attribution", "Prefeitura de São Paulo (ITBI, GeoSampa)", *partes])
    print(f"{OUT}: {(ROOT / OUT).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
