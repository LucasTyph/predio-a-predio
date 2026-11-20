"""Lê todas as planilhas de ITBI (data/raw/itbi/*.xlsx) e grava uma tabela única
em data/interim/itbi.parquet.

As planilhas têm uma aba por mês com as mesmas 28 colunas (os nomes variam um pouco entre
anos, então a leitura é por posição).

Uso: python -I pipeline/parse_itbi.py
"""
import datetime as dt
import re
from pathlib import Path

import pandas as pd
from python_calamine import CalamineWorkbook

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "itbi"
OUT = ROOT / "data" / "interim"

COLS = [
    "sql", "logradouro", "numero", "complemento", "bairro", "referencia", "cep",
    "natureza", "valor", "data", "venal_ref", "proporcao", "venal_ref_prop", "base_calculo",
    "financiamento", "valor_financiado", "cartorio", "matricula", "situacao_sql",
    "area_terreno", "testada", "fracao_ideal", "area_construida", "uso", "uso_desc",
    "padrao", "padrao_desc", "acc",
]
MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}


def to_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and v > 20000:  # serial do Excel
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
    if isinstance(v, str):
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", v.strip())
        if m:
            try:
                return dt.date(int(m[3]), int(m[2]), int(m[1]))
            except ValueError:
                return None
    return None


def le_ano(path):
    wb = CalamineWorkbook.from_path(str(path))
    frames = []
    for sn in wb.sheet_names:
        m = re.match(r"([A-Z]{3})[-_ ]?(\d{4})", sn.strip().upper())
        if not m or m[1] not in MESES:
            continue
        rows = wb.get_sheet_by_name(sn).to_python(skip_empty_area=True)
        if not rows:
            continue
        body = [r[:28] + [""] * (28 - len(r)) for r in rows[1:] if r and r[0] not in ("", None)]
        df = pd.DataFrame(body, columns=COLS)
        df["mes_ref"] = int(m[2]) * 100 + MESES[m[1]]
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLS)


def num(s):
    return pd.to_numeric(s.replace("", None), errors="coerce")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for p in sorted(RAW.glob("*.xlsx")):
        df = le_ano(p)
        print(p.name, len(df), flush=True)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    antes = len(df)
    df = df.drop_duplicates(subset=["sql", "data", "valor", "complemento", "natureza", "proporcao", "mes_ref"])
    if len(df) < antes:
        print("linhas repetidas entre planilhas removidas:", antes - len(df))

    sql = pd.to_numeric(df["sql"], errors="coerce")
    df = df[sql.notna()].copy()
    df["sql"] = sql[sql.notna()].astype("int64").map(lambda x: f"{x:011d}")
    for c in ["valor", "venal_ref", "proporcao", "venal_ref_prop", "base_calculo",
              "valor_financiado", "area_terreno", "testada", "fracao_ideal",
              "area_construida", "uso", "padrao", "acc", "cep"]:
        df[c] = num(df[c].astype(object))
    df["data"] = pd.to_datetime(df["data"].map(to_date), errors="coerce")
    for c in ["logradouro", "complemento", "bairro", "referencia", "natureza",
              "financiamento", "cartorio", "situacao_sql", "uso_desc", "padrao_desc"]:
        df[c] = df[c].astype(str).str.strip().replace({"nan": "", "None": ""})
    df["numero"] = num(df["numero"].astype(object))
    df["matricula"] = num(df["matricula"].astype(object))
    df.to_parquet(OUT / "itbi.parquet", index=False)
    print("total", len(df))


if __name__ == "__main__":
    main()
