"""Bounded internal HTTP adapter for vehicle article intake and knowledge lookup."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
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
    principal: Mapping[str, Any] | None = None,
    chat_runtime: Any | None = None,
) -> dict[str, object]:
    """Dispatch internal ingestion and chat requests without exposing internals."""

    if not isinstance(payload, Mapping):
        raise ValueError("request body must be an object")
    parsed_path = urlsplit(path)
    request_path = parsed_path.path
    request_principal = principal
    if request_principal is None:
        candidate_principal = payload.get("principal", {})
        if not isinstance(candidate_principal, Mapping):
            raise ValueError("chat request principal must be an object")
        request_principal = candidate_principal
    elif not isinstance(request_principal, Mapping):
        raise ValueError("chat request principal must be an object")
    if chat_runtime is not None:
        from .chat_service import configure_chat_runtime

        configure_chat_runtime(runtime=chat_runtime, allow_in_memory=True)
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
        if not message:
            raise ValueError("chat query message is required")
        if not idempotency_key:
            raise ValueError("chat query idempotency_key is required")
        if chat_create_runner is None:
            from .chat_service import create_chat_query

            chat_create_runner = create_chat_query
        return chat_create_runner(
            message,
            idempotency_key=idempotency_key,
            principal=request_principal,
            conversation_id=payload.get("conversation_id"),
            request_params=payload.get("request_params"),
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
            selection_principal = request_principal
            if principal is None:
                selection_principal = selection.pop("principal", None)
            return chat_select_runner(query_id, selection, principal=selection_principal)
        if chat_parts[4] == "events":
            if chat_events_runner is None:
                from .chat_service import iter_chat_events

                chat_events_runner = iter_chat_events
            query_params = parse_qs(parsed_path.query)
            last_event_id = payload.get("last_event_id") or query_params.get("last_event_id", [None])[0]
            events = chat_events_runner(
                query_id,
                last_event_id=str(last_event_id).strip() if last_event_id else None,
                principal=request_principal,
            )
            return {"query_id": query_id, "events": list(events)}
    if len(chat_parts) == 4 and chat_parts[:3] == ["v1", "chat", "queries"]:
        query_id = chat_parts[3]
        if not query_id:
            raise ValueError("chat query id is required")
        if chat_get_runner is None:
            from .chat_service import get_chat_query

            chat_get_runner = get_chat_query
        return chat_get_runner(query_id, principal=request_principal)
    raise ValueError("unknown ingestion service route")


def make_handler(internal_token: str = "", *, chat_runtime: Any | None = None):
    """Create a request handler bound to one secret-managed internal token."""

    if chat_runtime is not None:
        from .chat_service import configure_chat_runtime

        configure_chat_runtime(runtime=chat_runtime, allow_in_memory=True)
    configured_token = internal_token or os.getenv("AUTODATA_INGESTION_INTERNAL_TOKEN", "")

    class Handler(BaseHTTPRequestHandler):
        server_version = "autodata-ingestion/1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            request_path = urlsplit(self.path).path
            if request_path == "/healthz":
                self._write_json(200, {"status": "ok"})
                return
            if _is_chat_events_path(request_path):
                if not self._internal_authorized():
                    self._write_json(401, {"error": "internal authentication required"})
                    return
                query_id = request_path.strip("/").split("/")[3]
                query_params = parse_qs(urlsplit(self.path).query)
                last_event_id = self.headers.get("Last-Event-ID", "").strip() or (
                    query_params.get("last_event_id", [""])[0].strip()
                )
                try:
                    result = dispatch_request(
                        request_path,
                        {"last_event_id": last_event_id} if last_event_id else {},
                        principal=self._request_principal(),
                        chat_runtime=chat_runtime,
                    )
                    self._write_sse(result.get("events", []))
                except KeyError:
                    self._write_json(404, {"error": "chat query not found"})
                except PermissionError:
                    self._write_json(403, {"error": "chat owner authorization failed"})
                except ValueError as error:
                    self._write_json(409 if getattr(error, "http_status", 0) == 409 else 422, {"error": sanitize_http_error(error)})
                except Exception:  # noqa: BLE001 - do not expose worker failures
                    self._write_json(502, {"error": "ingestion dependency failed"})
                return
            if _is_chat_query_path(request_path):
                if not self._internal_authorized():
                    self._write_json(401, {"error": "internal authentication required"})
                    return
                try:
                    result = dispatch_request(
                        request_path,
                        {},
                        principal=self._request_principal(),
                        chat_runtime=chat_runtime,
                    )
                except KeyError:
                    self._write_json(404, {"error": "chat query not found"})
                except PermissionError:
                    self._write_json(403, {"error": "chat owner authorization failed"})
                except ValueError as error:
                    self._write_json(409 if getattr(error, "http_status", 0) == 409 else 422, {"error": sanitize_http_error(error)})
                except Exception:  # noqa: BLE001 - do not expose worker failures
                    self._write_json(502, {"error": "ingestion dependency failed"})
                else:
                    self._write_json(200, result)
                return
            self._write_json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            if configured_token and self.headers.get("X-Autodata-Internal-Token", "") != configured_token:
                self._write_json(401, {"error": "internal authentication required"})
                return
            path = urlsplit(self.path).path
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
                header_key = self.headers.get("Idempotency-Key", "").strip()
                body_key = str(body.get("idempotency_key", "")).strip() if isinstance(body, Mapping) else ""
                if header_key and body_key and header_key != body_key:
                    from .chat_service import ChatConflictError

                    raise ChatConflictError("Idempotency-Key header conflicts with request body")
                if isinstance(body, Mapping) and header_key:
                    body = dict(body)
                    body["idempotency_key"] = header_key
                result = dispatch_request(
                    path,
                    body,
                    principal=self._request_principal(),
                    chat_runtime=chat_runtime,
                )
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                self._write_json(409 if getattr(error, "http_status", 0) == 409 else 422, {"error": sanitize_http_error(error)})
                return
            except KeyError:
                self._write_json(404, {"error": "chat query not found"})
                return
            except PermissionError:
                self._write_json(403, {"error": "chat owner authorization failed"})
                return
            except Exception:  # noqa: BLE001 - source failures must be an HTTP error, not a traceback
                self._write_json(502, {"error": "ingestion dependency failed"})
                return
            self._write_json(200, result)

        def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
            self._method_not_allowed(_allowed_methods(urlsplit(self.path).path))

        def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler API
            self._method_not_allowed(_allowed_methods(urlsplit(self.path).path))

        def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
            self._method_not_allowed(_allowed_methods(urlsplit(self.path).path))

        def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler API
            allow = _allowed_methods(urlsplit(self.path).path)
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

        def _internal_authorized(self) -> bool:
            return not configured_token or self.headers.get("X-Autodata-Internal-Token", "") == configured_token

        def _request_principal(self) -> dict[str, str]:
            return {
                "owner_id": self.headers.get("X-Autodata-Owner-Id", "").strip(),
                "organization_id": self.headers.get("X-Autodata-Organization-Id", "").strip(),
            }

        def _method_not_allowed(self, allow: str) -> None:
            self.send_response(405)
            self.send_header("Allow", allow)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


MAX_EVENT_FRAME_BYTES = 256 * 1024
MAX_SSE_BYTES = 1 << 20


def _is_chat_query_path(path: str) -> bool:
    parts = path.strip("/").split("/")
    return len(parts) == 4 and parts[:3] == ["v1", "chat", "queries"] and bool(parts[3])


def _is_chat_events_path(path: str) -> bool:
    parts = path.strip("/").split("/")
    return len(parts) == 5 and parts[:3] == ["v1", "chat", "queries"] and parts[4] == "events" and bool(parts[3])


def _is_chat_selection_path(path: str) -> bool:
    parts = path.strip("/").split("/")
    return len(parts) == 5 and parts[:3] == ["v1", "chat", "queries"] and parts[4] == "selections" and bool(parts[3])


def _allowed_methods(path: str) -> str:
    if _is_chat_query_path(path) or _is_chat_events_path(path) or path == "/healthz":
        return "GET, OPTIONS"
    if _is_chat_selection_path(path) or path in {
        "/v1/article-intakes",
        "/v1/knowledge-queries",
        "/v1/job-plans",
        "/v1/chat/queries",
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
    from .chat_service import configure_chat_runtime_from_environment

    runtime = configure_chat_runtime_from_environment()
    server = ThreadingHTTPServer(
        (host, int(port_text)),
        make_handler(os.getenv("AUTODATA_INGESTION_INTERNAL_TOKEN", ""), chat_runtime=runtime),
    )
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
    "sanitize_http_error",
]
