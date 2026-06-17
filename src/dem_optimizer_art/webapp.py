from __future__ import annotations

import argparse
import json
import mimetypes
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlparse

from .dem import prepare_surface
from .render import render


MAX_UPLOAD = 100 * 1024 * 1024
ALLOWED_SUFFIXES = {".csv", ".txt", ".tif", ".tiff", ".png", ".jpg", ".jpeg"}
WEB_ROOT = files("dem_optimizer_art").joinpath("web")


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], tuple[str, bytes] | None]:
    marker = "boundary="
    if marker not in content_type:
        raise ValueError("Expected multipart form data")
    boundary = ("--" + content_type.split(marker, 1)[1].strip().strip('"')).encode()
    fields: dict[str, str] = {}
    upload = None
    for part in body.split(boundary)[1:-1]:
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        headers_raw, separator, payload = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = headers_raw.decode("utf-8", "replace")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        params = {}
        for item in disposition.split(";")[1:]:
            key, _, value = item.strip().partition("=")
            params[key] = value.strip('"')
        name, filename = params.get("name"), params.get("filename")
        if filename:
            upload = (Path(filename).name, payload)
        elif name:
            fields[name] = payload.decode("utf-8")
    return fields, upload


class AppHandler(BaseHTTPRequestHandler):
    server_version = "DEMArt/0.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[ui] {self.address_string()} {fmt % args}")

    def _send(self, status: int, content_type: str, data: bytes, disposition: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, value: dict) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(value).encode())

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        relative = "index.html" if path == "/" else path.lstrip("/")
        if relative not in {"index.html", "app.js", "styles.css"}:
            self._json(404, {"error": "Not found"})
            return
        resource = WEB_ROOT.joinpath(relative)
        data = resource.read_bytes()
        self._send(200, mimetypes.guess_type(relative)[0] or "application/octet-stream", data)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_UPLOAD:
                raise ValueError("Upload must be between 1 byte and 100 MB")
            fields, upload = parse_multipart(self.headers.get("Content-Type", ""), self.rfile.read(length))
            if upload is None:
                raise ValueError("Choose a DEM file first")
            filename, payload = upload
            suffix = Path(filename).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise ValueError("Use CSV, GeoTIFF, PNG, or JPEG")
            smoothing = int(fields.get("smoothing", 8))
            resolution = int(fields.get("resolution", 96))
            with tempfile.TemporaryDirectory() as temp:
                dem_path = Path(temp) / ("upload" + suffix)
                dem_path.write_bytes(payload)
                surface = prepare_surface(dem_path, smoothing, resolution)
                if self.path == "/api/preview":
                    self._json(200, {"grid": surface.grid, "width": surface.width, "height": surface.height})
                elif self.path == "/api/render":
                    config = json.loads(fields.get("config", "{}"))
                    svg_path = Path(temp) / "artwork.svg"
                    render(surface, config, svg_path)
                    self._send(200, "image/svg+xml; charset=utf-8", svg_path.read_bytes(),
                               'attachment; filename="dem-optimizer-art.svg"')
                else:
                    self._json(404, {"error": "Not found"})
        except Exception as exc:
            self._json(400, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the local DEM Optimizer Art interface")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    address = f"http://127.0.0.1:{args.port}"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), AppHandler)
    print(f"DEM Optimizer Art UI: {address}")
    if not args.no_open:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
