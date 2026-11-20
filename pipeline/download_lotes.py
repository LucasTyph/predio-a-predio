"""Baixa os lotes fiscais do GeoSampa (WFS geoportal:lote_cidadao), um arquivo por setor fiscal.

Guarda, para cada lote, a chave fiscal (setor, quadra, condomínio, lote), endereço, uso e o
centróide em WGS84, além do polígono simplificado (para destacar o edifício no mapa).

Uso: python -I pipeline/download_lotes.py
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "geo" / "lotes"
WFS = "https://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
PROPS = [
    "cd_setor_fiscal", "cd_quadra_fiscal", "cd_condominio", "cd_lote", "cd_tipo_lote",
    "nm_logradouro_completo", "cd_numero_porta", "tx_situ_lote", "dc_tipo_uso_imovel",
    "qt_area_construida", "ge_poligono",
]
TO_WGS = Transformer.from_crs("EPSG:31983", "EPSG:4326", always_xy=True)


def wfs_get(params, tries=5):
    url = WFS + "?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def setores():
    d = wfs_get({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": "geoportal:setor_fiscal", "outputFormat": "application/json",
        "propertyName": "cd_setor_fiscal",
    })
    return sorted({f["properties"]["cd_setor_fiscal"] for f in d["features"]})


def baixa_setor(setor):
    dest = OUT / f"{setor}.csv"
    if dest.exists() and dest.stat().st_size > 0:
        return setor, "skip"
    rows = []
    start, page = 0, 10000
    while True:
        d = wfs_get({
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": "geoportal:lote_cidadao", "outputFormat": "application/json",
            "propertyName": ",".join(PROPS),
            "CQL_FILTER": f"cd_setor_fiscal='{setor}'",
            "sortBy": "cd_identificador", "count": page, "startIndex": start,
        })
        feats = d.get("features", [])
        for f in feats:
            p = f["properties"]
            g = f.get("geometry")
            lon = lat = None
            poly = ""
            if g:
                try:
                    shp = shape(g)
                    c = shp.representative_point()
                    lon, lat = TO_WGS.transform(c.x, c.y)
                    s = shp.simplify(0.8)
                    if s.geom_type == "MultiPolygon":
                        s = max(s.geoms, key=lambda q: q.area)
                    if s.geom_type == "Polygon":
                        pts = [TO_WGS.transform(x, y) for x, y in s.exterior.coords]
                        poly = ";".join(f"{x:.6f},{y:.6f}" for x, y in pts)
                except Exception:  # noqa: BLE001
                    pass
            rows.append([
                p.get("cd_setor_fiscal"), p.get("cd_quadra_fiscal"), p.get("cd_condominio"),
                p.get("cd_lote"), p.get("cd_tipo_lote"), p.get("nm_logradouro_completo"),
                p.get("cd_numero_porta"), p.get("tx_situ_lote"), p.get("dc_tipo_uso_imovel"),
                p.get("qt_area_construida"),
                f"{lat:.6f}" if lat else "", f"{lon:.6f}" if lon else "", poly,
            ])
        if len(feats) < page:
            break
        start += page
    tmp = dest.with_suffix(".part")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["setor", "quadra", "condominio", "lote", "tipo_lote", "logradouro", "numero",
                    "situacao", "uso", "area_construida", "lat", "lon", "poly"])
        w.writerows(rows)
    tmp.replace(dest)
    return setor, len(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lista = setores()
    if len(sys.argv) > 1:
        lista = [s for s in lista if s in sys.argv[1:]]
    print(f"{len(lista)} setores", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(baixa_setor, s): s for s in lista}
        for fut in as_completed(futs):
            done += 1
            try:
                s, n = fut.result()
                print(f"[{done}/{len(lista)}] setor {s}: {n}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{done}/{len(lista)}] setor {futs[fut]}: ERRO {e}", flush=True)


if __name__ == "__main__":
    main()
