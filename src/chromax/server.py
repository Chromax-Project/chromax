"""Authenticated local console. HTTP never applies privileged plans."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import grp
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit
from . import actions, backend, config, models, packages, system
from .common import ChromaxError, atomic_write, require_root


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, state, token, config_path="/etc/chromax/ai.json"):
        self.state, self.token, self.config_path = state, token, config_path
        self.inference_lock = threading.BoundedSemaphore(1)
        self.slots = threading.BoundedSemaphore(16)
        self.attempts = {}
        self.rate_lock = threading.Lock()
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "Chromax"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, fmt, *args):
        # Never log query strings, bearer tokens or user prompts.
        pass

    def respond(self, code, payload, content_type="application/json; charset=utf-8"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        value = self.headers.get("Authorization", "")
        return hmac.compare_digest(value.encode(), ("Bearer " + self.server.token).encode())

    def limited(self):
        # Bounded per-IP request accounting, with expiry to avoid state growth.
        now = time.monotonic()
        address = self.client_address[0]
        with self.server.rate_lock:
            attempts = self.server.attempts
            for key in list(attempts):
                if now - attempts[key][0] >= 60:
                    del attempts[key]
            if address not in attempts and len(attempts) >= 1024:
                return True
            start, count = attempts.get(address, (now, 0))
            attempts[address] = (start, count + 1)
            return count >= 120

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/app.js", "/style.css"):
            asset = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
            mime = {"/": "text/html", "/app.js": "text/javascript", "/style.css": "text/css"}[path]
            return self.respond(200, (Path(__file__).parent / "web" / asset).read_bytes(), mime + "; charset=utf-8")
        if path == "/healthz":
            return self.respond(200, {"status": "ok", "distribution": "chromax"})
        if self.limited():
            return self.respond(429, {"error": "Too many requests"})
        if not self.authorized():
            return self.respond(401, {"error": "Authentication required"})
        try:
            if path == "/v1/status":
                return self.respond(200, system.status())
            if path == "/v1/doctor":
                return self.respond(200, system.doctor(self.server.state))
            if path == "/v1/model":
                return self.respond(200, models.info(self.server.state))
            if path.startswith("/v1/plans/"):
                return self.respond(200, actions.get(self.server.state, path.rsplit("/", 1)[1]))
            return self.respond(404, {"error": "Unknown endpoint"})
        except (ChromaxError, ValueError) as error:
            return self.respond(400, {"error": str(error)})

    def do_POST(self):
        if self.limited():
            return self.respond(429, {"error": "Too many requests"})
        if not self.authorized():
            return self.respond(401, {"error": "Authentication required"})
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ChromaxError("Transfer encoding is not supported")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                return self.respond(413, {"error": "Request must be 1–65536 bytes"})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ChromaxError("Request must be a JSON object")
            path = urlsplit(self.path).path
            if path == "/v1/ask":
                if not self.server.inference_lock.acquire(blocking=False):
                    return self.respond(429, {"error": "The assistant is busy; try again shortly"})
                try:
                    answer = backend.ask(body.get("question"), system.status(), config.load(self.server.config_path))
                finally:
                    self.server.inference_lock.release()
                return self.respond(200, {"answer": answer})
            if path == "/v1/plans":
                return self.respond(201, actions.create(self.server.state, body.get("action"), body.get("arguments")))
            return self.respond(404, {"error": "Unknown endpoint; plans can only be applied from the local CLI"})
        except (ChromaxError, ValueError, TypeError) as error:
            return self.respond(400, {"error": str(error)})
        except Exception:
            return self.respond(500, {"error": "Internal error; inspect the local service log"})


def serve():
    require_root()
    token = secrets.token_urlsafe(32)
    path = Path("/run/chromax/token")
    atomic_write(path, token + "\n", 0o640)
    os.chown(path, 0, grp.getgrnam("chromax").gr_gid)
    # Default is loopback. A root-managed file can opt into a network listener.
    address = "127.0.0.1"
    listen = Path("/etc/chromax/listen")
    if listen.exists():
        address = listen.read_text().strip()
        if address not in ("127.0.0.1", "0.0.0.0"):
            raise ChromaxError("Listener must be 127.0.0.1 or 0.0.0.0")
    Server((address, 8080), "/var/lib/chromax", token).serve_forever()
