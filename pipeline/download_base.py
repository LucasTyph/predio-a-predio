"""Baixa as camadas do GeoSampa usadas no mapa base (quadras, ruas, distritos, metrô/trem).

Grava GeoJSON em WGS84 em data/raw/geo/base/<camada>.geojson.
Uso: python -I pipeline/download_base.py
"""
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform  # noqa: E402
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "geo" / "base"
WFS = "https://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
TO_WGS = Transformer.from_crs("EPSG:31983", "EPSG:4326", always_xy=True).transform

LAYERS = {
    # camada: (propriedades, tolerância de simplificação em metros)
    "quadra_fiscal": (["cd_setor_fiscal", "cd_quadra_fiscal", "cd_tipo_quadra"], 1.0),
    "segmento_logradouro": (["codlog", "cd_tipo_logradouro", "cd_titulo_logradouro",
                             "tx_preposicao_logradouro", "nm_logradouro"], 1.5),
    "distrito_municipal": (["nm_distrito_municipal", "sg_distrito_municipal"], 8.0),
    "estacao_metro": (["nm_estacao_metro_trem", "nm_linha_metro_trem", "nm_empresa_metro_trem",
                       "tx_situacao_metro_trem"], 0),
    "linha_metro": (None, 3.0),
}


def get(params, tries=5):
    url = WFS + "?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def hits(layer):
    # resultType=hits subestima algumas camadas (ex.: segmento_logradouro); totalFeatures é confiável.
    d = get({"service": "WFS", "version": "2.0.0", "request": "GetFeature",
             "typeNames": f"geoportal:{layer}", "outputFormat": "application/json", "count": 1})
    return int(d.get("totalFeatures") or d.get("numberMatched"))


def page(layer, start, count):
    return get({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": f"geoportal:{layer}", "outputFormat": "application/json",
        **({"sortBy": "cd_identificador"} if layer in ("quadra_fiscal", "segmento_logradouro") else {}),
        "count": count, "startIndex": start,
    })["features"]


def baixa(layer):
    dest = OUT / f"{layer}.geojson"
    if dest.exists():
        print("skip", layer)
        return
    props, tol = LAYERS[layer]
    n = hits(layer)
    step = 20000
    starts = list(range(0, n, step))
    with ThreadPoolExecutor(max_workers=3) as ex:
        pages = list(ex.map(lambda s: page(layer, s, step), starts))
    feats = []
    for f in (f for p in pages for f in p):
        g = f.get("geometry")
        if not g:
            continue
        try:
            shp = shape(g)
        except (ValueError, TypeError):
            continue
        if tol:
            shp = shp.simplify(tol, preserve_topology=True)
        shp = transform(TO_WGS, shp)
        p = f["properties"]
        feats.append({"type": "Feature",
                      "properties": {k: p.get(k) for k in props} if props else p,
                      "geometry": mapping(shp)})
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, ensure_ascii=False)
    print(layer, n, len(feats), flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for layer in LAYERS:
        baixa(layer)


if __name__ == "__main__":
    main()
