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
    """Dispatch supported internal ingestion requests without exposing internals."""

    if not isinstance(payload, Mapping):
        raise ValueError("request body must be an object")
    parsed_path = urlsplit(path)
    request_path = parsed_path.path
    if request_path == "/v1/article-intakes":
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
    if request_path == "/v1/knowledge-queries":
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
    if request_path == "/v1/job-plans":
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
    configured_token = internal_token or os.getenv("AUTODATA_INGESTION_INTERNAL_TOKEN", "")

    class Handler(BaseHTTPRequestHandler):
        server_version = "autodata-ingestion/1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            request_path = urlsplit(self.path).path
            if request_path == "/healthz":
                self._write_json(200, {"status": "ok"})
                return
            self._write_json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            if configured_token and self.headers.get("X-Autodata-Internal-Token", "") != configured_token:
                self._write_json(401, {"error": "internal authentication required"})
                return
            path = urlsplit(self.path).path
            if path.startswith("/v1/chat/"):
                self._write_json(404, {"error": "not found"})
                return
            allowed = _allowed_methods(path)
            if "POST" not in allowed.split(", "):
                self._method_not_allowed(allowed)
                return
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
                self._write_json(409 if getattr(error, "http_status", 0) == 409 else 422, {"error": sanitize_http_error(error)})
                return
            except Exception:  # noqa: BLE001 - source failures must be an HTTP error, not a traceback
                self._write_json(502, {"error": "ingestion dependency failed"})
                return
            self._write_json(200, result)

        def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
            if _is_retired_chat_path(urlsplit(self.path).path):
                self._write_json(404, {"error": "not found"})
                return
            self._method_not_allowed(_allowed_methods(urlsplit(self.path).path))

        def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler API
            if _is_retired_chat_path(urlsplit(self.path).path):
                self._write_json(404, {"error": "not found"})
                return
            self._method_not_allowed(_allowed_methods(urlsplit(self.path).path))

        def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
            if _is_retired_chat_path(urlsplit(self.path).path):
                self._write_json(404, {"error": "not found"})
                return
            self._method_not_allowed(_allowed_methods(urlsplit(self.path).path))

        def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler API
            path = urlsplit(self.path).path
            if _is_retired_chat_path(path):
                self._write_json(404, {"error": "not found"})
                return
            allow = _allowed_methods(path)
            self.send_response(204)
            self.send_header("Allow", allow)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _write_json(self, status: int, value: object) -> None:
            body = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _method_not_allowed(self, allow: str) -> None:
            self.send_response(405)
            self.send_header("Allow", allow)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


def _is_retired_chat_path(path: str) -> bool:
    return path == "/v1/chat" or path.startswith("/v1/chat/")


def _allowed_methods(path: str) -> str:
    if path == "/healthz":
        return "GET, OPTIONS"
    if path in {
        "/v1/article-intakes",
        "/v1/knowledge-queries",
        "/v1/job-plans",
    }:
        return "POST, OPTIONS"
    return "GET, POST, OPTIONS"


def sanitize_http_error(error: BaseException) -> str:
    from .progress_events import sanitize_text

    return sanitize_text(error, limit=240) or "invalid request"


def run_server(address: str) -> None:
    """Serve the internal worker adapter until the container receives shutdown."""

    host, port_text = address.rsplit(":", 1)
    host = host or "0.0.0.0"
    server = ThreadingHTTPServer(
        (host, int(port_text)),
        make_handler(os.getenv("AUTODATA_INGESTION_INTERNAL_TOKEN", "")),
    )
    server.serve_forever()


def main() -> None:
    run_server(os.getenv("AUTODATA_INGESTION_HTTP_ADDR", ":8081"))


if __name__ == "__main__":
    main()


__all__ = [
    "MAX_REQUEST_BYTES",
    "dispatch_request",
    "make_handler",
    "run_server",
    "sanitize_http_error",
]
