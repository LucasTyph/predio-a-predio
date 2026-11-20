"""Servidor local do site (python -I pipeline/serve.py). Serve site/ em UTF-8 na porta 8765,
imitando o esqueleto do Artifact, que já declara o charset."""
import functools
import http.server
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


SKELETON = ('<!doctype html><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            '<style>[hidden]{display:none!important} body{margin:0}</style>')


class H(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
                      ".gz": "application/gzip", ".pbf": "application/x-protobuf"}

    def do_GET(self):
        # Imita o esqueleto que o Artifact adiciona (doctype, charset e viewport) em volta da página.
        if self.path.split("?")[0] in ("/", "/index.html"):
            body = (SKELETON + (SITE / "index.html").read_text(encoding="utf-8")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def guess_type(self, path):
        for ext, t in self.extensions_map.items():
            if ext and str(path).endswith(ext):
                return t
        return super().guess_type(path)


http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(H, directory=str(SITE))).serve_forever()
