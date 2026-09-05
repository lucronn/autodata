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
    article_uri = os.getenv("AUTODATA_ARTICLE_URI", "").strip()
    if article_uri:
        return run_article_url(article_uri, os.getenv("AUTODATA_ARTICLE_VEHICLE_JSON", ""))
    knowledge_request = os.getenv("AUTODATA_KNOWLEDGE_REQUEST_JSON", "").strip()
    if knowledge_request:
        return run_vehicle_knowledge(knowledge_request)
    vehicle_list = os.getenv("AUTODATA_VEHICLE_LIST_JSON", "").strip()
    if vehicle_list:
        return run_vehicle_selection(vehicle_list)

    return {"worker": "ingestion", "lane": "fast", "status": "idle"}


def run_vehicle_selection(serialized_vehicle_list: str) -> dict[str, object]:
    """Normalize a JSON vehicle list for selection and identity resolution."""

    try:
        values = json.loads(serialized_vehicle_list)
    except json.JSONDecodeError as error:
        raise ValueError("AUTODATA_VEHICLE_LIST_JSON must be valid JSON") from error
    if not isinstance(values, list):
        raise ValueError("AUTODATA_VEHICLE_LIST_JSON must contain an array")
    from .vehicle_selection import normalize_vehicle_list_json

    vehicles = normalize_vehicle_list_json(values)
    return {
        "worker": "ingestion",
        "lane": "fast",
        "status": "ready",
        "vehicles": vehicles,
        "vehicle_count": len(vehicles),
    }


def run_article_url(source_uri: str, serialized_vehicle: str) -> dict[str, object]:
    """Fetch one URL for a target vehicle and return normalized article JSON."""

    try:
        target_value = json.loads(serialized_vehicle)
    except json.JSONDecodeError as error:
        raise ValueError("AUTODATA_ARTICLE_VEHICLE_JSON must be valid JSON") from error
    if not isinstance(target_value, dict):
        raise ValueError("AUTODATA_ARTICLE_VEHICLE_JSON must contain an object")
    from .article_intake import VehicleTarget, ingest_vehicle_article
    from .http_connector import HttpSourceConnector

    required = {"make", "model", "region"}
    if not required.issubset(target_value):
        raise ValueError("article vehicle must include make, model, year, and region")
    year = target_value.get("model_year", target_value.get("year"))
    if year is None:
        raise ValueError("article vehicle must include make, model, year, and region")
    target = VehicleTarget(
        target_value["make"],
        target_value["model"],
        year,
        target_value["region"],
        target_value.get("trim"),
    )
    connector = HttpSourceConnector(
        source_uri,
        os.getenv("AUTODATA_SOURCE_VERSION", "") or None,
        timeout_seconds=float(os.getenv("AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS", "30")),
        max_bytes=int(os.getenv("AUTODATA_SOURCE_MAX_BYTES", str(50 * 1024 * 1024))),
        request_headers=_source_request_headers(),
    )
    intake = ingest_vehicle_article(source_uri, target, connector=connector)
    result: dict[str, object] = {
        "worker": "ingestion",
        "lane": "fast",
        "status": intake.status,
        "rejection_reason": intake.rejection_reason,
        "source_uri": intake.source_uri,
        "vehicle": intake.bundle.vehicle,
        "articles": list(intake.bundle.articles),
        "evidence": list(intake.bundle.evidence),
        "quarantined": list(intake.bundle.quarantined),
        "conflicts": list(intake.bundle.conflicts),
    }
    persistence = _persist_article_intake(intake, adapter_name=connector.name)
    if persistence is not None:
        result["persistence"] = persistence
    return result


def run_vehicle_knowledge(serialized_request: str) -> dict[str, object]:
    """Resolve a vehicle-scoped query from the normalized catalog or HTTP source."""

    try:
        request = json.loads(serialized_request)
    except json.JSONDecodeError as error:
        raise ValueError("AUTODATA_KNOWLEDGE_REQUEST_JSON must be valid JSON") from error
    if not isinstance(request, dict):
        raise ValueError("AUTODATA_KNOWLEDGE_REQUEST_JSON must contain an object")

    vehicle = request.get("vehicle")
    if not isinstance(vehicle, dict):
        raise ValueError("knowledge request vehicle must be an object")
    year = vehicle.get("model_year", vehicle.get("year"))
    required = {"make", "model", "region"}
    if year is None or not required.issubset(vehicle):
        raise ValueError("knowledge request vehicle must include make, model, year, and region")

    from .article_intake import VehicleTarget
    from .knowledge_fallback import HttpKnowledgeSourceResolver, query_vehicle_knowledge

    target = VehicleTarget(
        vehicle["make"],
        vehicle["model"],
        year,
        vehicle["region"],
        vehicle.get("trim"),
    )
    query = request.get("query", "")
    keywords = request.get("keywords", ())
    if isinstance(keywords, str) or not isinstance(keywords, (list, tuple)):
        raise ValueError("knowledge request keywords must be an array of strings")
    if any(not isinstance(keyword, str) for keyword in keywords):
        raise ValueError("knowledge request keywords must be an array of strings")

    catalog = request.get("catalog", [])
    source_template = request.get("source_uri_template") or os.getenv(
        "AUTODATA_KNOWLEDGE_SOURCE_URI_TEMPLATE", ""
    ).strip()
    source_uri = request.get("source_uri")
    if source_uri is not None:
        source_template = str(source_uri).strip()
    source_version = request.get("source_version") or os.getenv("AUTODATA_SOURCE_VERSION") or None
    resolver = HttpKnowledgeSourceResolver(
        source_template,
        source_version=source_version,
        timeout_seconds=float(os.getenv("AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS", "30")),
        max_bytes=int(os.getenv("AUTODATA_SOURCE_MAX_BYTES", str(50 * 1024 * 1024))),
        request_headers=_source_request_headers(),
    ) if source_template else lambda *_args: None

    def ingest_and_persist(source_uri: str, target: object, **options: object):
        from .article_intake import ingest_vehicle_article

        intake = ingest_vehicle_article(source_uri, target, **options)
        _persist_article_intake(intake, adapter_name="knowledge-fallback")
        return intake

    result = query_vehicle_knowledge(
        target,
        query,
        catalog=catalog,
        source_resolver=resolver,
        keywords=keywords,
        kind=request.get("kind", "all"),
        ingest=ingest_and_persist,
    )
    return {"worker": "ingestion", "lane": "fast", **result.to_dict()}


def _persist_article_intake(intake: object, *, adapter_name: str) -> dict[str, object] | None:
    """Persist a ready article intake only when explicitly enabled."""

    if os.getenv("AUTODATA_SOURCE_PERSIST") != "1":
        return None
    from .article_intake import VehicleArticleIntake

    if not isinstance(intake, VehicleArticleIntake) or intake.status != "ready":
        return None
    from .bundle_persistence import persist_source_bundle

    return persist_source_bundle(
        intake.bundle,
        intake.artifacts,
        adapter_name=adapter_name,
    )


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
    if os.getenv("AUTODATA_WORKER_ONCE") == "1":
        result = run_nats_once() if consumer_enabled else run_once()
        print(json.dumps(result, sort_keys=True))
        return
    while True:
        result = run_nats_once() if consumer_enabled else run_once()
        print(json.dumps(result, sort_keys=True), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
