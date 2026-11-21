"""Monta a pasta dist/ para o GitHub Pages a partir de site/.

site/index.html tem só o conteúdo da página; aqui ele ganha o esqueleto HTML (doctype, head).

Uso: python -I pipeline/build_pages.py
"""
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DIST = ROOT / "dist"

SITE_URL = os.environ.get("SITE_URL", "https://lucastyph.github.io/predio-a-predio/").rstrip("/") + "/"
DESCRICAO = "Quanto foi pago em cada venda de imóvel em São Paulo, prédio por prédio. Dados do ITBI desde 2005."

SKELETON = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{descricao}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Prédio a Prédio">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="Prédio a Prédio">
<meta property="og:description" content="{descricao}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{url}og.jpg?v={versao}">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Mapa de São Paulo com as quadras coloridas pelo preço do metro quadrado">
<meta name="twitter:card" content="summary_large_image">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}[hidden]{display:none!important}</style>
</head>
<body>
"""


def pagina():
    try:
        versao = json.loads((SITE / "data" / "meta.json").read_text(encoding="utf-8"))["atualizado"].replace("-", "")
    except (OSError, KeyError, ValueError):
        versao = "1"
    head = SKELETON.replace("{descricao}", DESCRICAO).replace("{url}", SITE_URL).replace("{versao}", versao)
    return head +(SITE / "index.html").read_text(encoding="utf-8") + "\n</body>\n</html>\n"


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / "index.html").write_text(pagina(), encoding="utf-8")
    arquivos = [SITE / "data" / "meta.json", SITE / "data" / "busca" / "index.json",
                *SITE.glob("data/**/*.json.gz"), *SITE.glob("glyphs/**/*.pbf"), SITE / "tiles" / "mapa.pmtiles", SITE / "og.jpg"]
    for src in arquivos:
        dst = DIST / src.relative_to(SITE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    total = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"dist/: {len(arquivos) + 1} arquivos, {total / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
