from __future__ import annotations

import argparse
import json
import logging
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from tic_lab.service import AppError, Service

LOG = logging.getLogger("jev-tic-tac-toe")
STATIC = {
    "/": ("index.html", "text/html"),
    "/static/app.js": ("app.js", "text/javascript"),
    "/static/style.css": ("style.css", "text/css"),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send(self, data, status=200, mime="application/json"):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if mime == "application/json" else data
        self.send_response(status)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def guard(self):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in allowed:
            raise AppError("Local Host required.", 403)
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in allowed}:
            raise AppError("Origin not permitted.", 403)
        if self.command == "POST":
            if not secrets.compare_digest(self.headers.get("X-TTT-Token", ""), self.server.service.csrf):
                raise AppError("Reload the page to obtain a local session token.", 403)
            if self.headers.get_content_type() != "application/json":
                raise AppError("JSON required.", 415)

    def body(self):
        length = self.headers.get("Content-Length", "")
        if not length.isdecimal() or not 0 < int(length) < 65536:
            raise AppError("Invalid request length.", 413)
        try:
            data = json.loads(self.rfile.read(int(length)))
        except (UnicodeError, ValueError):
            raise AppError("Invalid JSON.") from None
        if not isinstance(data, dict):
            raise AppError("Expected an object.")
        return data

    def do_GET(self):
        try:
            self.guard()
            path = urlsplit(self.path).path
            if path == "/api/status":
                return self.send(self.server.service.status())
            if path == "/api/state":
                return self.send(self.server.service.snapshot())
            if path not in STATIC:
                raise AppError("Not found.", 404)
            filename, mime = STATIC[path]
            return self.send((ROOT / "web" / filename).read_bytes(), mime=mime)
        except AppError as exc:
            self.send({"error": str(exc)}, exc.status)
        except Exception:
            LOG.exception("GET failed")
            self.send({"error": "Local server error."}, 500)

    def do_POST(self):
        try:
            self.guard()
            data = self.body()
            path = urlsplit(self.path).path
            svc = self.server.service
            if path == "/api/new":
                result = svc.new(data)
            elif path == "/api/config":
                result = svc.configure(data)
            elif path == "/api/move":
                result = svc.human_move(data)
            elif path == "/api/step":
                result = svc.ai_step()
            elif path == "/api/play":
                result = svc.play()
            elif path == "/api/pause":
                result = svc.pause()
            else:
                raise AppError("Not found.", 404)
            self.send(result)
        except AppError as exc:
            self.send({"error": str(exc)}, exc.status)
        except Exception:
            LOG.exception("POST failed")
            self.send({"error": "Local server error."}, 500)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int):
        self.service = Service()
        super().__init__(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="Jev 3x3 tic-tac-toe benchmark")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    server = Server(args.port)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Jev × Tic-Tac-Toe: {url}", flush=True)
    if args.open:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
