"""Empacota os arquivos binários do site como texto base64 (.txt).

O Artifact só serve tipos web comuns (json, txt, ...), não .gz nem .pbf. Os dados ficam
comprimidos em gzip e codificados em base64; a página decodifica e descomprime no navegador.

  site/data/**/X.json.gz  ->  site/data/**/X.txt
  site/glyphs/sans/R.pbf  ->  site/glyphs/sans/R.txt

Uso: python -I pipeline/pack_site.py
"""
import base64
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


def main():
    n = 0
    for src in list(SITE.glob("data/**/*.json.gz")) + list(SITE.glob("glyphs/**/*.pbf")):
        name = src.name.removesuffix(".json.gz").removesuffix(".pbf") + ".txt"
        dst = src.with_name(name)
        dst.write_bytes(base64.b64encode(src.read_bytes()))
        n += 1
    print(n, "arquivos empacotados")


if __name__ == "__main__":
    main()
