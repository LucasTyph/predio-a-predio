"""Baixa as planilhas de guias de ITBI pagas da página de transparência da Secretaria da Fazenda.

Lê a página, encontra todos os links .xlsx de "GUIAS DE ITBI PAGAS" e salva cada um em
data/raw/itbi/. O nome do arquivo de cada ano muda a cada atualização mensal, por isso a lista
é sempre lida da página em vez de fixa no código.

Uso: python -I pipeline/download_itbi.py [--force]
  --force  baixa de novo mesmo os arquivos que já existem
"""
import hashlib
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "itbi"
PAGE = "https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501"
UA = {"User-Agent": "Mozilla/5.0 (compatible; predio-a-predio/1.0)"}


def get(url, tries=4, timeout=300):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def links():
    html = get(PAGE).decode("utf-8", errors="replace")
    urls = re.findall(r'href="([^"]+\.xlsx)"', html, flags=re.I)
    out = []
    for u in urls:
        if "itbi" not in u.lower():
            continue
        u = urllib.parse.urljoin(PAGE, u.replace("&amp;", "&"))
        u = urllib.parse.quote(u, safe=":/%()?=&-_.~")
        if u not in out:
            out.append(u)
    return out


def nome(url):
    base = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_")
    h = hashlib.sha1(url.encode()).hexdigest()[:6]
    return f"{Path(base).stem}_{h}.xlsx"


def main():
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    lista = links()
    if not lista:
        raise SystemExit("Nenhum link de planilha de ITBI encontrado na página da Fazenda.")
    print(f"{len(lista)} planilhas na página", flush=True)
    atuais = set()
    for url in lista:
        dest = OUT / nome(url)
        atuais.add(dest.name)
        if dest.exists() and dest.stat().st_size > 0 and not force:
            print("já existe", dest.name, flush=True)
            continue
        data = get(url)
        if not data.startswith(b"PK"):
            raise SystemExit(f"Resposta inesperada (não é .xlsx) para {url}")
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
        print(f"baixado {dest.name} ({len(data) / 1e6:.1f} MB)", flush=True)
    # remove planilhas que saíram da página (ex.: o arquivo do ano corrente do mês anterior)
    for p in OUT.glob("*.xlsx"):
        if p.name not in atuais:
            p.unlink()
            print("removido (não está mais na página)", p.name, flush=True)


if __name__ == "__main__":
    main()
