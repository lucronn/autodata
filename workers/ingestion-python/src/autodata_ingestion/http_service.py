"""Bounded internal HTTP adapter for vehicle article intake and knowledge lookup."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


MAX_REQUEST_BYTES = 1 << 20


def dispatch_request(
    path: str,
    payload: Mapping[str, object],
    *,
    article_runner: Callable[[str, str], dict[str, object]] | None = None,
    knowledge_runner: Callable[[str], dict[str, object]] | None = None,
    job_runner: Callable[[str], dict[str, object]] | None = None,
) -> dict[str, object]:
    """Dispatch the two internal request shapes without exposing worker internals."""

    if not isinstance(payload, Mapping):
        raise ValueError("request body must be an object")
    if path == "/v1/article-intakes":
        source_uri = str(payload.get("source_uri", "")).strip()
        vehicle = payload.get("vehicle")
        if not source_uri or urlsplit(source_uri).scheme not in {"http", "https"}:
            raise ValueError("article intake source_uri must be an HTTP(S) URL")
        if not isinstance(vehicle, Mapping):
            raise ValueError("article intake vehicle must be an object")
        if article_runner is None:
            from .worker import run_article_url

            article_runner = run_article_url
        return article_runner(
            source_uri,
            json.dumps(dict(vehicle), ensure_ascii=False, sort_keys=True),
        )
    if path == "/v1/knowledge-queries":
        vehicle = payload.get("vehicle")
        query = str(payload.get("query", "")).strip()
        if not isinstance(vehicle, Mapping):
            raise ValueError("knowledge query vehicle must be an object")
        if not query and not payload.get("keywords"):
            raise ValueError("knowledge query requires query or keywords")
        if knowledge_runner is None:
            from .worker import run_vehicle_knowledge

            knowledge_runner = run_vehicle_knowledge
        return knowledge_runner(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))
    if path == "/v1/job-plans":
        vehicle = payload.get("vehicle")
        query = str(payload.get("query", "")).strip()
        if not isinstance(vehicle, Mapping):
            raise ValueError("job plan vehicle must be an object")
        if not query:
            raise ValueError("job plan query is required")
        if job_runner is None:
            from .worker import run_job_plan

            job_runner = run_job_plan
        return job_runner(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))
    raise ValueError("unknown ingestion service route")


def make_handler(internal_token: str = ""):
    """Create a request handler bound to one secret-managed internal token."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "autodata-ingestion/1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            if urlsplit(self.path).path != "/healthz":
                self._write_json(404, {"error": "not found"})
                return
            self._write_json(200, {"status": "ok"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            if internal_token and self.headers.get("X-Autodata-Internal-Token", "") != internal_token:
                self._write_json(401, {"error": "internal authentication required"})
                return
            path = urlsplit(self.path).path
            length_text = self.headers.get("Content-Length", "")
            try:
                length = int(length_text)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_REQUEST_BYTES:
                self._write_json(413, {"error": "request body exceeds the configured limit"})
                return
            try:
                body = json.loads(self.rfile.read(length))
                result = dispatch_request(path, body)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                self._write_json(422, {"error": str(error)})
                return
            except Exception:  # noqa: BLE001 - source failures must be an HTTP error, not a traceback
                self._write_json(502, {"error": "ingestion dependency failed"})
                return
            self._write_json(200, result)

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _write_json(self, status: int, value: object) -> None:
            body = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def run_server(address: str) -> None:
    """Serve the internal worker adapter until the container receives shutdown."""

    host, port_text = address.rsplit(":", 1)
    host = host or "0.0.0.0"
    server = ThreadingHTTPServer((host, int(port_text)), make_handler(os.getenv("AUTODATA_INGESTION_INTERNAL_TOKEN", "")))
    server.serve_forever()


def main() -> None:
    run_server(os.getenv("AUTODATA_INGESTION_HTTP_ADDR", ":8081"))


if __name__ == "__main__":
    main()


__all__ = ["MAX_REQUEST_BYTES", "dispatch_request", "make_handler", "run_server"]
