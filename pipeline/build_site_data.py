"""Monta os arquivos de dados do site a partir do ITBI (data/interim/itbi.parquet),
dos lotes fiscais (data/raw/geo/lotes) e das camadas base (data/raw/geo/base).

Saída em site/data/:
  setor/<SSS>.json.gz   edifícios do setor fiscal com polígono, resumo e todas as vendas
  busca.json.gz         índice de busca (endereço, nome do edifício, bairro, coordenadas)
  quadras.json.gz       quadras fiscais com o R$/m² mediano recente (mapa coroplético)
  ruas.json.gz          eixos de logradouros (rótulos das ruas)
  distritos.json.gz     distritos, metrô e trem
  meta.json             IPCA mensal, legendas de códigos e data de atualização

"Edifício" = endereço (logradouro + número) dentro de uma quadra fiscal. As unidades de um
condomínio compartilham esse endereço, então todas as vendas do prédio caem no mesmo grupo,
inclusive as vendas na planta feitas antes da individualização (registradas no SQL do terreno).

Uso: python -I pipeline/build_site_data.py
"""
import gzip
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INTERIM = ROOT / "data" / "interim"
LOTES = ROOT / "data" / "raw" / "geo" / "lotes"
BASE = ROOT / "data" / "raw" / "geo" / "base"
VENDOR = ROOT / "data" / "raw" / "vendor"
OUT = ROOT / "site" / "data"

USOS_RESIDENCIAIS = {10, 12, 13, 14, 20, 21, 22, 25}
APTO_RE = re.compile(r"\b(AP|APT|APTO|APART|APARTAMENTO|UNID|UN|CJ|FLAT|STUDIO|ST)\b\.?\s*\d", re.I)


def gz_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(path, "wb", compresslevel=9) as fh:
        fh.write(data)
    return len(data)


def norm_logr(s):
    s = (s or "").upper().strip()
    s = re.sub(r"[^A-Z0-9À-Ü ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fmt_num(n):
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return ""
    n = int(n)
    # 0 e 99999 são usados nas guias para "sem número"
    return "" if n in (0, 99999) else str(n)


def cod(s):
    m = re.match(r"\s*(\d+)\.", s or "")
    return int(m[1]) if m else 0


def round_coord(v):
    return round(float(v), 6)


# ---------------------------------------------------------------- ITBI
def carrega_itbi():
    df = pd.read_parquet(INTERIM / "itbi.parquet")
    planta = (df["uso"] == 0) & df["complemento"].str.contains(APTO_RE, regex=True)
    df = df[df["uso"].isin(USOS_RESIDENCIAIS) | planta].copy()
    df["planta"] = planta[df.index]
    df = df[df["data"].notna() & df["valor"].notna() & (df["data"] >= "2005-01-01") & (df["data"] <= pd.Timestamp.today())]
    df["setor"] = df["sql"].str[:3]
    df["quadra"] = df["sql"].str[3:6]
    df["lote"] = df["sql"].str[6:10]
    df["num"] = df["numero"].map(fmt_num)
    df["logr_n"] = df["logradouro"].map(norm_logr)
    df["nat"] = df["natureza"].map(cod)
    df["fin"] = df["financiamento"].map(cod)
    df["ano"] = df["data"].dt.year
    # Venda "limpa" para estatística de preço: compra e venda do imóvel inteiro, com área.
    ok = (
        (df["nat"] == 1) & (df["proporcao"].fillna(0) >= 99) & (df["area_construida"].fillna(0) >= 15)
        & (df["valor"] >= 5000) & ~df["planta"]
    )
    m2 = df["valor"] / df["area_construida"]
    ok &= m2.between(200, 80000)
    df["m2"] = np.where(ok, m2, np.nan)
    return df


# ---------------------------------------------------------------- lotes
def carrega_lotes(setor):
    p = LOTES / f"{setor}.csv"
    if not p.exists():
        return pd.DataFrame()
    lt = pd.read_csv(p, dtype=str, keep_default_na=False)
    lt["num"] = lt["numero"].str.extract(r"(\d+)", expand=False).fillna("").str.lstrip("0")
    lt["logr_n"] = lt["logradouro"].map(norm_logr)
    return lt


def parse_poly(s):
    if not s:
        return None
    pts = []
    for pair in s.split(";"):
        x, y = pair.split(",")
        pts.append([round(float(x), 6), round(float(y), 6)])
    return pts


# ---------------------------------------------------------------- quadras
def carrega_quadras():
    with open(BASE / "quadra_fiscal.geojson", encoding="utf-8") as fh:
        gj = json.load(fh)
    cent = {}
    for f in gj["features"]:
        p = f["properties"]
        g = f["geometry"]
        ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
        xs = [c[0] for c in ring]
        ys = [c[1] for c in ring]
        cent[(p["cd_setor_fiscal"], p["cd_quadra_fiscal"])] = (sum(ys) / len(ys), sum(xs) / len(xs))
    return gj, cent


def localiza(grupo_setor, lotes, quadra_cent):
    """Para cada edifício do setor, encontra o lote no GeoSampa.

    Ordem: (1) lote de condomínio/lote com mesmo número na quadra e mesmo logradouro;
    (2) mesmo número na quadra; (3) o próprio SQL (casas); (4) centróide da quadra."""
    res = {}
    by_num, by_lote = {}, {}
    if not lotes.empty:
        for r in lotes[lotes["lat"] != ""].itertuples(index=False):
            by_num.setdefault((r.quadra, r.num), []).append(r)
            if r.condominio == "00":
                by_lote[(r.quadra, r.lote)] = r
    for key, rows in grupo_setor:
        setor, quadra, logr_n, num = key
        hit = None
        how = "quadra"
        c = by_num.get((quadra, num)) if num else None
        if c:
            same = [r for r in c if r.logr_n == logr_n]
            pool = same or c
            cond = [r for r in pool if r.condominio != "00"]
            hit = (cond or pool)[0]
            how = "lote"
        if hit is None:
            for lote in rows["lote"]:
                if (quadra, lote) in by_lote:
                    hit = by_lote[(quadra, lote)]
                    how = "lote"
                    break
        if hit is not None:
            res[key] = (float(hit.lat), float(hit.lon), parse_poly(hit.poly), how)
        elif (setor, quadra) in quadra_cent:
            la, lo = quadra_cent[(setor, quadra)]
            res[key] = (la, lo, None, "quadra")
        else:
            res[key] = None
    return res


def moda(s):
    s = [x for x in s if x]
    if not s:
        return ""
    return Counter(s).most_common(1)[0][0]


def nome_edificio(refs, bairros):
    """O campo 'Referência' costuma trazer o nome do condomínio (ED ..., COND ...)."""
    cands = [r for r in list(refs) + list(bairros) if r and re.search(r"\b(ED|EDIF|EDIFICIO|COND|CONDOMINIO|RES|RESIDENCIAL)\b", r)]
    if cands:
        return Counter(cands).most_common(1)[0][0]
    return ""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("lendo ITBI...", flush=True)
    df = carrega_itbi()
    print("vendas residenciais", len(df), flush=True)
    quadras_gj, quadra_cent = carrega_quadras()

    df = df.sort_values("data")
    df["bkey"] = list(zip(df["setor"], df["quadra"], df["logr_n"], df["num"]))

    busca = []
    total_ok = total_lote = 0
    bid = 0
    hoje = df["data"].max()
    corte_recente = hoje - pd.DateOffset(years=3)
    quadra_stats = {}

    cols = ["sql", "setor", "quadra", "lote", "num", "logradouro", "bairro", "referencia", "cep",
            "complemento", "data", "valor", "area_construida", "nat", "fin", "valor_financiado",
            "proporcao", "venal_ref", "uso", "padrao", "acc", "planta", "m2", "bkey"]
    df["dnum"] = df["data"].dt.strftime("%Y%m%d").astype(int)
    corte = int(corte_recente.strftime("%Y%m%d"))
    nz = lambda v, d=0: d if v is None or (isinstance(v, float) and math.isnan(v)) else v  # noqa: E731

    for setor, ds in df.groupby("setor", sort=True):
        lotes = carrega_lotes(setor)
        recs = ds[cols + ["dnum"]].to_dict("records")
        grupos = {}
        for r in recs:
            grupos.setdefault(r["bkey"], []).append(r)
        loc = localiza([(k, {"lote": {r["lote"] for r in g}}) for k, g in grupos.items()], lotes, quadra_cent)
        edificios = []
        qvals = {}
        for key, g in grupos.items():
            _, quadra, _, num = key
            for r in g:
                if r["dnum"] >= corte and not math.isnan(r["m2"]):
                    qvals.setdefault(quadra, []).append(r["m2"])
            L = loc.get(key)
            if L is None:
                continue
            lat, lon, poly, how = L
            bid += 1
            total_ok += 1
            total_lote += how == "lote"
            vert = any(nz(r["uso"]) in (20, 21, 22, 25) or r["planta"] for r in g)
            unidades = len({r["sql"] for r in g})
            rec = [r["m2"] for r in g if r["dnum"] >= corte and not math.isnan(r["m2"])]
            med_rec = float(np.median(rec)) if rec else None
            accs = [int(r["acc"]) for r in g if nz(r["acc"]) > 1800]
            acc = Counter(accs).most_common(1)[0][0] if accs else None
            nome = nome_edificio([r["referencia"] for r in g], [r["bairro"] for r in g])
            logr = moda([r["logradouro"] for r in g])
            bairro = moda([r["bairro"] for r in g if not re.search(r"(ED|COND|AP|BL)", r["bairro"])])
            ceps = [str(int(r["cep"])) for r in g if nz(r["cep"]) > 0]
            vendas = [[
                r["dnum"], round(float(r["valor"]), 2), round(float(nz(r["area_construida"])), 1),
                r["complemento"], r["nat"], r["fin"], round(float(nz(r["valor_financiado"])), 2),
                round(float(nz(r["proporcao"], 100)), 2), round(float(nz(r["venal_ref"])), 2), r["sql"][6:],
                int(nz(r["uso"])), int(nz(r["padrao"])), int(r["acc"]) if nz(r["acc"]) > 1800 else 0,
                1 if r["planta"] else 0,
            ] for r in g]
            endereco = f"{logr}, {num}" if num else f"{logr}, s/n"
            edificios.append({
                "id": bid, "q": quadra, "e": endereco, "nm": nome, "b": bairro,
                "cep": moda(ceps), "lat": round_coord(lat), "lon": round_coord(lon), "poly": poly, "loc": how,
                "v": 1 if vert else 0, "u": unidades, "acc": acc,
                "m2": round(med_rec) if med_rec else None, "s": vendas,
            })
            busca.append([bid, setor, round_coord(lat), round_coord(lon), endereco, nome, bairro, len(g),
                          1 if vert else 0, round(med_rec) if med_rec else None])
        for q, v in qvals.items():
            quadra_stats[(setor, q)] = (float(np.median(v)), len(v))
        size = gz_json(OUT / "setor" / f"{setor}.json.gz", {"setor": setor, "ed": edificios})
        print(f"setor {setor}: {len(edificios)} edificios, {len(ds)} vendas, {size/1e6:.1f} MB", flush=True)

    print(f"edifícios {total_ok}, no lote exato {total_lote} ({total_lote/total_ok:.1%})", flush=True)
    gz_json(OUT / "busca.json.gz", busca)

    # quadras com estatística
    feats = []
    for f in quadras_gj["features"]:
        p = f["properties"]
        k = (p["cd_setor_fiscal"], p["cd_quadra_fiscal"])
        st = quadra_stats.get(k)
        feats.append({"type": "Feature", "geometry": quantize(f["geometry"]),
                      "properties": {"s": k[0], "q": k[1], "m2": round(st[0]) if st else None,
                                     "n": st[1] if st else 0}})
    gz_json(OUT / "quadras.json.gz", {"type": "FeatureCollection", "features": feats})

    # ruas: agrega nome
    with open(BASE / "segmento_logradouro.geojson", encoding="utf-8") as fh:
        ruas = json.load(fh)
    rf = []
    for f in ruas["features"]:
        p = f["properties"]
        nome = " ".join(x for x in [p.get("cd_tipo_logradouro"), p.get("cd_titulo_logradouro"),
                                    p.get("tx_preposicao_logradouro"), p.get("nm_logradouro")] if x)
        tipo = (p.get("cd_tipo_logradouro") or "").upper()
        rank = 1 if tipo in ("AV", "VD", "ROD", "EST", "MAR", "PTE", "TUN", "CMP") else 2
        rf.append({"type": "Feature", "geometry": quantize(f["geometry"]),
                   "properties": {"n": titulo(nome), "r": rank}})
    gz_json(OUT / "ruas.json.gz", {"type": "FeatureCollection", "features": rf})

    # distritos + transporte
    out = {}
    for layer in ["distrito_municipal", "estacao_metro", "linha_metro"]:
        p = BASE / f"{layer}.geojson"
        if p.exists():
            with open(p, encoding="utf-8") as fh:
                gj = json.load(fh)
            for f in gj["features"]:
                f["geometry"] = quantize(f["geometry"])
            out[layer] = gj
    gz_json(OUT / "distritos.json.gz", out)

    # IPCA (índice acumulado mensal, base = último mês)
    ipca = json.load(open(VENDOR / "ipca.json", encoding="utf-8"))
    idx = []
    acc = 1.0
    for row in ipca:
        d, m, y = row["data"].split("/")
        acc *= 1 + float(row["valor"]) / 100
        idx.append([int(y) * 100 + int(m), acc])
    ultimo = idx[-1][1]
    top = sorted((r for r in busca if r[8] and re.search(r"TATUAP", f"{r[6]} {r[4]}")), key=lambda r: -r[7])[:8]
    meta = {
        "destaques": top,
        "atualizado": date.today().isoformat(),
        "ultima_venda": hoje.strftime("%Y-%m-%d"),
        "primeira_venda": df["data"].min().strftime("%Y-%m-%d"),
        "ipca_ref": idx[-1][0],
        "ipca": {str(k): round(ultimo / v, 5) for k, v in idx},
        "n_vendas": int(len(df)),
        "n_edificios": int(total_ok),
    }
    with open(OUT / "meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    print("ok")


def quantize(g):
    def q(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], 5), round(c[1], 5)]
        return [q(x) for x in c]
    return {"type": g["type"], "coordinates": q(g["coordinates"])}


ABREV = {"R": "R.", "AV": "Av.", "PC": "Pç.", "AL": "Al.", "TV": "Tv.", "EST": "Estr.",
         "PCA": "Pç.", "VD": "Vd.", "LG": "Lgo.", "PTE": "Pte.", "ROD": "Rod.", "VL": "Vila"}


def titulo(nome):
    parts = nome.split()
    if not parts:
        return ""
    head = ABREV.get(parts[0], parts[0].title())
    minus = {"DE", "DA", "DO", "DAS", "DOS", "E"}
    rest = [w.lower() if w in minus else w.title() for w in parts[1:]]
    return " ".join([head] + rest)


if __name__ == "__main__":
    main()
