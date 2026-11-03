"""Loopback-only Source Connector v1 fixture; no live upstreams or credentials."""

import base64
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread, Lock
import time
from urllib.parse import unquote, urlsplit, parse_qs
from uuid import uuid4


class ConnectorFixture:
    def __init__(self, provider):
        self.provider = provider
        self.token = "fixture-" + provider
        self.resources = {}
        self.calls = []
        self.pages = []
        self.candidates = [
            {"opaque_ref": "vehicle:fixture", "label": "Fixture car", "confidence": 1}
        ]
        self.error = None
        self.delays = {}
        self.active = 0
        self.max_active = 0
        self.lock = Lock()

    def body(
        self, payload, media_type="text/html", ref="body", kind="article", assets=()
    ):
        self.resources[ref] = (payload, media_type, kind, list(assets))

    def envelope(self, **fields):
        return {
            "request_id": str(uuid4()),
            "provider": self.provider,
            "source_revision": "revision-1",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_locator": "fixture://" + self.provider,
            **fields,
        }

    def response(self, path):
        self.calls.append(path)
        parsed = urlsplit(path)
        if self.error:
            return self.error, {}
        if parsed.path.startswith("/v1/resources/"):
            ref = unquote(parsed.path[len("/v1/resources/") :])
            if ref not in self.resources:
                return 404, {}
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                time.sleep(self.delays.get(ref, 0))
            finally:
                with self.lock:
                    self.active -= 1
            payload, media, kind, assets = self.resources[ref]
            content = (
                {"content_base64": base64.b64encode(payload).decode()}
                if kind in ("asset", "binary")
                else {"content": payload.decode()}
            )
            return 200, self.envelope(
                kind=kind,
                media_type=media,
                sha256=sha256(payload).hexdigest(),
                **content,
                **(
                    {"asset_resource_refs": assets}
                    if kind in ("article", "text", "labor")
                    else {}
                )
            )
        if parsed.path == "/v1/vehicle-resolutions":
            return 200, self.envelope(
                selector={"year": 2024, "make": "Example", "model": "Car"},
                candidates=self.candidates,
            )
        if parsed.path.endswith("/articles"):
            cursor = parse_qs(parsed.query).get("cursor", ["0"])[0]
            page = (
                self.pages[int(cursor)]
                if self.pages
                else {"complete": True, "articles": []}
            )
            return 200, self.envelope(**page)
        return 404, {}


@contextmanager
def serve_connector(provider):
    fixture = ConnectorFixture(provider)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.do_GET()

        def do_GET(self):
            status, body = (
                fixture.response(self.path)
                if self.headers.get("Authorization") == "Bearer " + fixture.token
                else (401, {})
            )
            raw = json.dumps(body, indent=1).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except BrokenPipeError:
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fixture.url = "http://127.0.0.1:" + str(server.server_port)
    try:
        yield fixture
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
