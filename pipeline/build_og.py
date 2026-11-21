"""Gera a imagem de prévia para links compartilhados (WhatsApp, redes sociais): site/og.jpg.

1200x630, com o título do site e o mapa das quadras colorido pelo R$/m² mediano, desenhado a
partir de data/tiles_src/quadras.geojsonl e das faixas de cor em site/data/meta.json.

Uso: python -I pipeline/build_og.py
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
W, H, K = 1200, 630, 2  # K = superamostragem para suavizar as bordas

BG = (238, 241, 244)
FG = (19, 23, 28)
FG2 = (77, 86, 98)
NODATA = (221, 226, 232)
RAMP = [(205, 226, 251), (158, 197, 244), (109, 167, 236), (57, 135, 229), (37, 106, 191), (24, 79, 149), (13, 54, 107)]


def merc(lon, lat):
    x = math.radians(lon)
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def cor(m2, breaks):
    if m2 is None:
        return NODATA
    i = sum(1 for b in breaks if m2 >= b)
    return RAMP[i]


def aneis(geom):
    if geom["type"] == "Polygon":
        yield geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield poly[0]


def wrap(draw, text, font, largura):
    linhas, atual = [], ""
    for palavra in text.split():
        teste = (atual + " " + palavra).strip()
        if draw.textlength(teste, font=font) <= largura:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def main():
    meta = json.loads((ROOT / "site" / "data" / "meta.json").read_text(encoding="utf-8"))
    breaks = meta.get("breaks") or [4000, 6000, 8000, 10000, 13000, 17000]
    feats = []
    with open(ROOT / "data" / "tiles_src" / "quadras.geojsonl", encoding="utf-8") as fh:
        for line in fh:
            f = json.loads(line)
            feats.append((f["properties"].get("m2"), [[merc(x, y) for x, y in ring] for ring in aneis(f["geometry"])]))

    xs = [x for _, rings in feats for ring in rings for x, _ in ring]
    ys = [y for _, rings in feats for ring in rings for _, y in ring]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    # caixa do mapa: metade direita, com margem
    bx0, by0, bx1, by1 = 600, 24, 1176, 606
    esc = min((bx1 - bx0) / (x1 - x0), (by1 - by0) / (y1 - y0))
    ox = bx0 + ((bx1 - bx0) - (x1 - x0) * esc) / 2
    oy = by0 + ((by1 - by0) - (y1 - y0) * esc) / 2

    img = Image.new("RGB", (W * K, H * K), BG)
    d = ImageDraw.Draw(img)
    for m2, rings in sorted(feats, key=lambda f: f[0] is not None):
        c = cor(m2, breaks)
        for ring in rings:
            pts = [((ox + (x - x0) * esc) * K, (oy + (y1 - y) * esc) * K) for x, y in ring]
            if len(pts) >= 3:
                d.polygon(pts, fill=c)

    titulo = ImageFont.truetype(str(FONTS / "Archivo-SemiBold.ttf"), 76 * K)
    corpo = ImageFont.truetype(str(FONTS / "Inter-Regular.ttf"), 31 * K)
    nota = ImageFont.truetype(str(FONTS / "Inter-Regular.ttf"), 22 * K)
    x, y = 64 * K, 150 * K
    d.text((x, y), "Prédio a", font=titulo, fill=FG)
    d.text((x, y + 84 * K), "Prédio", font=titulo, fill=FG)
    y += 214 * K
    for linha in wrap(d, "Quanto foi pago em cada venda de imóvel em São Paulo, prédio por prédio, desde 2005.", corpo, 480 * K):
        d.text((x, y), linha, font=corpo, fill=FG2)
        y += 44 * K
    n = meta.get("n_vendas")
    rodape = f"{n / 1e6:.1f} milhões de vendas do ITBI".replace(".", ",") if n else "Vendas do ITBI"
    d.text((x, H * K - 86 * K), rodape + " · cor do mapa: R$/m²", font=nota, fill=FG2)

    out = ROOT / "site" / "og.jpg"
    img.resize((W, H), Image.LANCZOS).save(out, "JPEG", quality=86, optimize=True, progressive=True)
    print(f"{out.relative_to(ROOT)}: {out.stat().st_size / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
