"""Deterministic process boundary for the fast-lane worker."""

from __future__ import annotations

import json
import asyncio
import os
import time


def run_once() -> dict[str, object]:
    """Run one explicitly configured local source-drop job or return a heartbeat."""

    source_directory = os.getenv("AUTODATA_SOURCE_DIRECTORY", "").strip()
    if source_directory:
        return run_source_directory(source_directory)
    source_uri = os.getenv("AUTODATA_SOURCE_URI", "").strip()
    if source_uri:
        return run_source_uri(source_uri)
    fast_event = os.getenv("AUTODATA_FAST_EVENT_JSON", "").strip()
    if fast_event:
        return run_fast_event(fast_event)

    return {"worker": "ingestion", "lane": "fast", "status": "idle"}


def run_source_directory(directory: str) -> dict[str, str | int | list[str]]:
    """Normalize one local source drop and optionally persist its records."""

    from .directory_connector import DirectorySourceConnector

    connector = DirectorySourceConnector(
        directory,
        os.getenv("AUTODATA_SOURCE_VERSION", "local-directory-v1"),
    )
    return _run_connector(connector)


def run_source_uri(source_uri: str) -> dict[str, str | int | list[str]]:
    """Fetch one HTTP(S) source URI and run the shared intake pipeline."""

    from .http_connector import HttpSourceConnector

    connector = HttpSourceConnector(
        source_uri,
        os.getenv("AUTODATA_SOURCE_VERSION", "") or None,
        timeout_seconds=float(os.getenv("AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS", "30")),
        max_bytes=int(os.getenv("AUTODATA_SOURCE_MAX_BYTES", str(50 * 1024 * 1024))),
        request_headers=_source_request_headers(),
    )
    return _run_connector(connector)


def run_fast_event(serialized_event: str) -> dict[str, object]:
    """Dispatch one validated fast-lane event through its source connector."""

    from .fast_lane import FastLaneRequest, connector_for_request

    try:
        envelope = json.loads(serialized_event)
    except json.JSONDecodeError as error:
        raise ValueError("AUTODATA_FAST_EVENT_JSON must be valid JSON") from error
    request = FastLaneRequest.from_envelope(envelope)
    connector = connector_for_request(
        request,
        request_headers=_source_request_headers(),
        timeout_seconds=float(os.getenv("AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS", "30")),
        max_bytes=int(os.getenv("AUTODATA_SOURCE_MAX_BYTES", str(50 * 1024 * 1024))),
    )
    return {
        **_run_connector(connector, publication=_publication_for_request(request)),
        "request_id": request.request_id,
        "projection_id": request.projection_id,
        "correlation_id": request.correlation_id,
        "idempotency_key": request.idempotency_key,
        "processing_version": request.processing_version,
    }


def run_nats_once() -> dict[str, object]:
    """Poll one durable fast-lane message through the shared source handler."""

    from .consumer import consume_once

    return asyncio.run(
        consume_once(
            _handle_fast_request,
            fetch_timeout=float(os.getenv("AUTODATA_FAST_CONSUMER_FETCH_TIMEOUT_SECONDS", "1")),
            max_deliveries=int(os.getenv("AUTODATA_FAST_CONSUMER_MAX_DELIVERIES", "3")),
        )
    )


def run_knowledge_fallback_once() -> dict[str, object]:
    """Poll one durable vehicle-scoped knowledge fallback request."""

    from .knowledge_fallback_consumer import consume_once
    from .knowledge_fallback_runtime import fulfill_once

    return asyncio.run(
        consume_once(
            fulfill_once,
            fetch_timeout=float(os.getenv("AUTODATA_KNOWLEDGE_CONSUMER_FETCH_TIMEOUT_SECONDS", "1")),
            max_deliveries=int(os.getenv("AUTODATA_KNOWLEDGE_CONSUMER_MAX_DELIVERIES", "3")),
        )
    )


def _handle_fast_request(request: object) -> dict[str, str | int | list[str]]:
    from .fast_lane import FastLaneRequest, FastLaneRequestError, connector_for_request

    if not isinstance(request, FastLaneRequest):
        raise TypeError("fast-lane handler received an invalid request")
    if os.getenv("AUTODATA_SOURCE_PERSIST") != "1":
        raise FastLaneRequestError(
            "durable fast-lane consumption requires AUTODATA_SOURCE_PERSIST=1"
        )
    connector = connector_for_request(
        request,
        request_headers=_source_request_headers(),
        timeout_seconds=float(os.getenv("AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS", "30")),
        max_bytes=int(os.getenv("AUTODATA_SOURCE_MAX_BYTES", str(50 * 1024 * 1024))),
    )
    return _run_connector(connector, publication=_publication_for_request(request))


def _source_request_headers() -> dict[str, str]:
    raw_headers = os.getenv("AUTODATA_SOURCE_REQUEST_HEADERS_JSON", "").strip()
    if not raw_headers:
        return {}
    try:
        headers = json.loads(raw_headers)
    except json.JSONDecodeError as error:
        raise ValueError("AUTODATA_SOURCE_REQUEST_HEADERS_JSON must be valid JSON") from error
    if not isinstance(headers, dict) or any(not isinstance(value, str) for value in headers.values()):
        raise ValueError("AUTODATA_SOURCE_REQUEST_HEADERS_JSON must be an object of string values")
    return {str(key): value for key, value in headers.items()}


def _run_connector(
    connector: object,
    *,
    publication: object | None = None,
) -> dict[str, str | int | list[str] | dict[str, object]]:
    artifacts, bundle, quality = _collect_connector(connector)
    persistence = None
    if os.getenv("AUTODATA_SOURCE_PERSIST") == "1":
        from .bundle_persistence import persist_source_bundle

        persistence = persist_source_bundle(
            bundle,
            artifacts,
            adapter_name=connector.name,
            publication=publication,
        )

    result: dict[str, str | int | list[str] | dict[str, object]] = {
        "worker": "ingestion",
        "lane": "fast",
        "status": bundle.status if quality.status == "pass" else quality.status,
        "bundle_status": bundle.status,
        "quality_status": quality.status,
        "source_artifacts": len(artifacts),
        "evidence": len(bundle.evidence),
        "quarantined": len(bundle.quarantined),
        "conflicts": len(bundle.conflicts),
        "quarantine_reasons": sorted({str(item.get("reason")) for item in bundle.quarantined}),
    }
    if bundle.vehicle is not None:
        result["vehicle_key"] = bundle.vehicle["vehicle_key"]
    if persistence is not None:
        result["persistence_status"] = str(persistence.get("status", "unknown"))
        if "publication" in persistence:
            result["publication"] = persistence["publication"]
    return result


def _collect_connector(connector: object):
    from .quality import evaluate_source_bundle
    from .source_adapters import adapt_source_resource
    from .source_bundle import normalize_source_bundle

    resources = connector.fetch({})
    artifacts = [adapt_source_resource(resource) for resource in resources]
    bundle = normalize_source_bundle(
        artifacts,
        os.getenv("AUTODATA_SOURCE_REGION", "US"),
    )
    quality = evaluate_source_bundle(bundle)
    return artifacts, bundle, quality


def _publication_for_request(request: object):
    from .fast_lane import FastLaneRequest
    from .fast_lane_persistence import FastLanePublication

    if not isinstance(request, FastLaneRequest):
        raise TypeError("publication requires a FastLaneRequest")
    return FastLanePublication(
        request_id=request.request_id,
        projection_id=request.projection_id,
        correlation_id=request.correlation_id,
        idempotency_key=request.idempotency_key,
        processing_version=request.processing_version,
    )


def main() -> None:
    interval = float(os.getenv("AUTODATA_WORKER_HEARTBEAT_SECONDS", "30"))
    consumer_enabled = os.getenv("AUTODATA_FAST_CONSUMER_ENABLED") == "1"
    knowledge_consumer_enabled = os.getenv("AUTODATA_KNOWLEDGE_CONSUMER_ENABLED") == "1"
    if os.getenv("AUTODATA_WORKER_ONCE") == "1":
        if knowledge_consumer_enabled:
            result = run_knowledge_fallback_once()
        else:
            result = run_nats_once() if consumer_enabled else run_once()
        print(json.dumps(result, sort_keys=True))
        return
    while True:
        if knowledge_consumer_enabled:
            result = run_knowledge_fallback_once()
        else:
            result = run_nats_once() if consumer_enabled else run_once()
        print(json.dumps(result, sort_keys=True), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
