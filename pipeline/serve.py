"""Servidor local do site: python -I pipeline/serve.py  ->  http://localhost:8765

Serve site/ com o mesmo esqueleto HTML que pipeline/build_pages.py acrescenta e com suporte a
requisições HTTP Range, que o mapa (PMTiles) usa para baixar só os tiles visíveis.
"""
import functools
import http.server
import importlib.util
import os
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
_spec = importlib.util.spec_from_file_location("build_pages", Path(__file__).with_name("build_pages.py"))
_bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bp)


class H(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
                      ".gz": "application/gzip", ".pbf": "application/x-protobuf",
                      ".pmtiles": "application/octet-stream"}

    def guess_type(self, path):
        for ext, t in self.extensions_map.items():
            if ext and str(path).endswith(ext):
                return t
        return super().guess_type(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0]
        if path in ("/", "/index.html"):
            body = _bp.pagina().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d+)-(\d*)$", rng or "")
        f = Path(self.translate_path(path))
        if m and f.is_file():
            size = f.stat().st_size
            start = int(m[1])
            end = min(int(m[2]) if m[2] else size - 1, size - 1)
            if start >= size:
                self.send_error(416)
                return
            with open(f, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start + 1)
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(str(f)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()


if __name__ == "__main__":
    os.chdir(SITE)
    http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(H, directory=str(SITE))).serve_forever()
