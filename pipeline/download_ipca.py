"""Baixa a série mensal do IPCA (BCB/SGS série 433) para data/raw/vendor/ipca.json.

Uso: python -I pipeline/download_ipca.py
"""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "vendor" / "ipca.json"
URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2005"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except Exception:  # noqa: BLE001
            if i == 4:
                if OUT.exists():
                    print("IPCA indisponível; usando o arquivo existente")
                    return
                raise
            time.sleep(10 * (i + 1))
    if not data or "valor" not in data[-1]:
        raise SystemExit("Resposta do IPCA em formato inesperado")
    OUT.write_text(json.dumps(data), encoding="utf-8")
    print("IPCA até", data[-1]["data"])


if __name__ == "__main__":
    main()
