"""Monta a pasta dist/ para o GitHub Pages a partir de site/.

site/index.html tem só o conteúdo da página; aqui ele ganha o esqueleto HTML (doctype, head).

Uso: python -I pipeline/build_pages.py
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DIST = ROOT / "dist"

SKELETON = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Histórico de vendas residenciais por edifício na cidade de São Paulo, a partir das guias de ITBI e do GeoSampa.">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}[hidden]{display:none!important}</style>
</head>
<body>
"""


def pagina():
    return SKELETON + (SITE / "index.html").read_text(encoding="utf-8") + "\n</body>\n</html>\n"


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / "index.html").write_text(pagina(), encoding="utf-8")
    arquivos = [SITE / "data" / "meta.json", SITE / "data" / "busca" / "index.json",
                *SITE.glob("data/**/*.json.gz"), *SITE.glob("glyphs/**/*.pbf"), SITE / "tiles" / "mapa.pmtiles"]
    for src in arquivos:
        dst = DIST / src.relative_to(SITE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    total = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"dist/: {len(arquivos) + 1} arquivos, {total / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
