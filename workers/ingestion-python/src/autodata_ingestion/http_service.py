"""Bounded internal HTTP adapter for vehicle article intake and knowledge lookup."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


MAX_REQUEST_BYTES = 1 << 20


def dispatch_request(
    path: str,
    payload: Mapping[str, object],
    *,
    article_runner: Callable[[str, str], dict[str, object]] | None = None,
    knowledge_runner: Callable[[str], dict[str, object]] | None = None,
    job_runner: Callable[[str], dict[str, object]] | None = None,
    chat_create_runner: Callable[..., dict[str, object]] | None = None,
    chat_select_runner: Callable[..., dict[str, object]] | None = None,
    chat_get_runner: Callable[[str], dict[str, object]] | None = None,
    chat_events_runner: Callable[..., object] | None = None,
) -> dict[str, object]:
    """Dispatch internal ingestion and chat requests without exposing internals."""

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
    chat_parts = request_path.strip("/").split("/")
    if chat_parts == ["v1", "chat", "queries"]:
        message = str(payload.get("message", "")).strip()
        idempotency_key = str(payload.get("idempotency_key", "")).strip()
        principal = payload.get("principal", {})
        if not message:
            raise ValueError("chat query message is required")
        if not idempotency_key:
            raise ValueError("chat query idempotency_key is required")
        if not isinstance(principal, Mapping):
            raise ValueError("chat query principal must be an object")
        if chat_create_runner is None:
            from .chat_service import create_chat_query

            chat_create_runner = create_chat_query
        return chat_create_runner(
            message,
            idempotency_key=idempotency_key,
            principal=principal,
        )
    if len(chat_parts) == 5 and chat_parts[:3] == ["v1", "chat", "queries"]:
        query_id = chat_parts[3]
        if not query_id:
            raise ValueError("chat query id is required")
        if chat_parts[4] == "selections":
            if chat_select_runner is None:
                from .chat_service import select_chat_vehicle

                chat_select_runner = select_chat_vehicle
            selection = dict(payload)
            return chat_select_runner(query_id, selection)
        if chat_parts[4] == "events":
            if chat_events_runner is None:
                from .chat_service import iter_chat_events

                chat_events_runner = iter_chat_events
            query_params = parse_qs(parsed_path.query)
            last_event_id = payload.get("last_event_id") or query_params.get("last_event_id", [None])[0]
            events = chat_events_runner(
                query_id,
                last_event_id=str(last_event_id).strip() if last_event_id else None,
            )
            return {"query_id": query_id, "events": list(events)}
    if len(chat_parts) == 4 and chat_parts[:3] == ["v1", "chat", "queries"]:
        query_id = chat_parts[3]
        if not query_id:
            raise ValueError("chat query id is required")
        if chat_get_runner is None:
            from .chat_service import get_chat_query

            chat_get_runner = get_chat_query
        return chat_get_runner(query_id)
    raise ValueError("unknown ingestion service route")


def make_handler(internal_token: str = ""):
    """Create a request handler bound to one secret-managed internal token."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "autodata-ingestion/1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            request_path = urlsplit(self.path).path
            if request_path == "/healthz":
                self._write_json(200, {"status": "ok"})
                return
            if _is_chat_events_path(request_path):
                query_id = request_path.strip("/").split("/")[3]
                query_params = parse_qs(urlsplit(self.path).query)
                last_event_id = self.headers.get("Last-Event-ID", "").strip() or (
                    query_params.get("last_event_id", [""])[0].strip()
                )
                try:
                    result = dispatch_request(
                        request_path,
                        {"last_event_id": last_event_id} if last_event_id else {},
                    )
                    self._write_sse(result.get("events", []))
                except KeyError:
                    self._write_json(404, {"error": "chat query not found"})
                except ValueError as error:
                    self._write_json(422, {"error": str(error)})
                except Exception:  # noqa: BLE001 - do not expose worker failures
                    self._write_json(502, {"error": "ingestion dependency failed"})
                return
            if _is_chat_query_path(request_path):
                try:
                    result = dispatch_request(request_path, {})
                except KeyError:
                    self._write_json(404, {"error": "chat query not found"})
                except ValueError as error:
                    self._write_json(422, {"error": str(error)})
                except Exception:  # noqa: BLE001 - do not expose worker failures
                    self._write_json(502, {"error": "ingestion dependency failed"})
                else:
                    self._write_json(200, result)
                return
            self._write_json(404, {"error": "not found"})

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
                if isinstance(body, Mapping) and self.headers.get("Idempotency-Key", "").strip():
                    body = dict(body)
                    body.setdefault("idempotency_key", self.headers["Idempotency-Key"].strip())
                result = dispatch_request(path, body)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                self._write_json(422, {"error": str(error)})
            except KeyError:
                self._write_json(404, {"error": "chat query not found"})
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

        def _write_sse(self, events: object) -> None:
            from .progress_events import event_to_sse

            if not isinstance(events, list):
                events = []
            frames: list[str] = []
            total_bytes = 0
            for event in events:
                frame = event_to_sse(event)
                frame_bytes = len(frame.encode("utf-8"))
                if frame_bytes > MAX_EVENT_FRAME_BYTES or total_bytes + frame_bytes > MAX_SSE_BYTES:
                    break
                frames.append(frame)
                total_bytes += frame_bytes
            body = "".join(frames).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


MAX_EVENT_FRAME_BYTES = 256 * 1024
MAX_SSE_BYTES = 1 << 20


def _is_chat_query_path(path: str) -> bool:
    parts = path.strip("/").split("/")
    return len(parts) == 4 and parts[:3] == ["v1", "chat", "queries"] and bool(parts[3])


def _is_chat_events_path(path: str) -> bool:
    parts = path.strip("/").split("/")
    return len(parts) == 5 and parts[:3] == ["v1", "chat", "queries"] and parts[4] == "events" and bool(parts[3])


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


__all__ = [
    "MAX_EVENT_FRAME_BYTES",
    "MAX_REQUEST_BYTES",
    "MAX_SSE_BYTES",
    "dispatch_request",
    "make_handler",
    "run_server",
]
