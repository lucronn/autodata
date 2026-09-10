"""Deterministic process boundary for the fast-lane worker."""

from __future__ import annotations

import json
import asyncio
import os
import time
from dataclasses import replace


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
    job_plan_request = os.getenv("AUTODATA_JOB_PLAN_REQUEST_JSON", "").strip()
    if job_plan_request:
        return run_job_plan(job_plan_request)
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

    vehicles = normalize_vehicle_list_json(
        values,
        default_region=os.getenv("AUTODATA_SOURCE_REGION") or None,
    )
    result: dict[str, object] = {
        "worker": "ingestion",
        "lane": "fast",
        "status": "needs_review" if _selection_needs_review(vehicles) else "ready",
        "vehicles": vehicles,
        "vehicle_count": len(vehicles),
    }
    if os.getenv("AUTODATA_SOURCE_PERSIST") == "1":
        from .vehicle_selection_persistence import persist_vehicle_selection_list

        result["persistence"] = persist_vehicle_selection_list(
            values,
            source_uri=os.getenv(
                "AUTODATA_VEHICLE_LIST_SOURCE_URI", "input://vehicle-list"
            ),
            source_version=os.getenv(
                "AUTODATA_SOURCE_VERSION", "vehicle-list-v1"
            ),
            region=os.getenv("AUTODATA_SOURCE_REGION") or None,
        )
        _attach_persistence_ids(vehicles, result["persistence"])
        observations = result["persistence"].get("observations")
        if isinstance(observations, list) and any(
            isinstance(observation, dict)
            and observation.get("resolution_status") == "needs_review"
            for observation in observations
        ):
            result["status"] = "needs_review"
    return result


def _selection_needs_review(vehicles: list[dict[str, object]]) -> bool:
    for vehicle in vehicles:
        configurations = vehicle.get("configurations", [])
        if not isinstance(configurations, list):
            continue
        if any(
            isinstance(configuration, dict)
            and configuration.get("status") == "needs_review"
            for configuration in configurations
        ):
            return True
    return False


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
    target = _vehicle_target_from_mapping(target_value, year)
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

    target = _vehicle_target_from_mapping(vehicle, year)
    query = request.get("query", "")
    keywords = request.get("keywords", ())
    if isinstance(keywords, str) or not isinstance(keywords, (list, tuple)):
        raise ValueError("knowledge request keywords must be an array of strings")
    if any(not isinstance(keyword, str) for keyword in keywords):
        raise ValueError("knowledge request keywords must be an array of strings")

    if "catalog" in request:
        catalog = request["catalog"]
    else:
        from .knowledge_catalog import load_vehicle_knowledge_catalog

        catalog = load_vehicle_knowledge_catalog(target)
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


def run_job_plan(serialized_request: str) -> dict[str, object]:
    """Calculate a multi-component labor plan from normalized vehicle articles."""

    try:
        request = json.loads(serialized_request)
    except json.JSONDecodeError as error:
        raise ValueError("job plan request must be valid JSON") from error
    if not isinstance(request, dict):
        raise ValueError("job plan request must contain an object")
    query = str(request.get("query", "")).strip()
    vehicle = request.get("vehicle")
    if not query or not isinstance(vehicle, dict):
        raise ValueError("job plan request requires query and vehicle")

    source_info: dict[str, object] = {"mode": "normalized_cache"}
    catalog = request.get("catalog")
    if catalog is None:
        from .article_intake import VehicleTarget
        from .knowledge_catalog import load_vehicle_knowledge_catalog

        year = vehicle.get("model_year", vehicle.get("year"))
        if year is None:
            raise ValueError("job plan vehicle requires year")
        target = _vehicle_target_from_mapping(vehicle, year)
        catalog = load_vehicle_knowledge_catalog(target)
        if not catalog:
            catalog, source_info = _load_autoapi_job_catalog(vehicle, target)
    if not isinstance(catalog, (list, tuple)):
        raise ValueError("job plan catalog must be an array")

    from .job_plan import _components_from_query, compose_procedure_with_llm, plan_job

    cached_derived = _cached_derived_job_plan(query, vehicle, catalog)
    if cached_derived is not None:
        return {"worker": "ingestion", "lane": "fast", **cached_derived}

    result = plan_job(query, vehicle, catalog=catalog, source_info=source_info)
    if os.getenv("AUTODATA_MERCURY2_JOB_PLANS_ENABLED") == "1" and result.get("selected_articles"):
        selected_ids = set(str(value) for value in result["selected_articles"])
        selected_articles = [
            record.get("article", record)
            for record in catalog
            if isinstance(record, dict)
            and isinstance(record.get("article", record), dict)
            and str(record.get("article", record).get("article_id", "")) in selected_ids
        ]
        try:
            from .mercury2 import Mercury2Client

            client = Mercury2Client.from_environment()
            result["procedure"] = compose_procedure_with_llm(
                client,
                query,
                vehicle,
                selected_articles,
                result["labor"],
                result["procedure"],
            )
            result["llm_status"] = "generated"
        except Exception as error:  # noqa: BLE001 - retain safe deterministic draft
            result["llm_status"] = "unavailable"
            result["llm_error"] = str(error)
            result["procedure"]["generation"] = "deterministic_fallback"
    if os.getenv("AUTODATA_SOURCE_PERSIST") == "1" and result.get("selected_articles"):
        from .derived_article_persistence import persist_derived_article

        result["derived_article_persistence"] = persist_derived_article(result, vehicle=vehicle)
    return {"worker": "ingestion", "lane": "fast", **result}


def _cached_derived_job_plan(
    query: str,
    vehicle: dict[str, object],
    catalog: list[dict[str, object]] | tuple[dict[str, object], ...],
) -> dict[str, object] | None:
    """Return a persisted composition without re-running planning or the LLM."""

    from .job_plan import _components_from_query

    requested = _components_from_query(query)
    if not requested:
        return None
    requested_set = set(requested)
    for record in catalog:
        if not isinstance(record, dict):
            continue
        article = record.get("article", record)
        if not isinstance(article, dict):
            continue
        components = article.get("derived_components")
        if not isinstance(components, list) or set(str(value) for value in components) != requested_set:
            continue
        status = str(article.get("status") or "needs_review")
        return {
            "status": status,
            "vehicle": dict(vehicle),
            "requested_components": requested,
            "selected_articles": [str(value) for value in article.get("source_article_ids", [])],
            "review_reasons": [] if status == "ready" else ["persisted_derived_article_requires_review"],
            "labor": article.get("labor", {}),
            "procedure": article.get("procedure", {}),
            "images": article.get("images", []),
            "source": {"mode": "derived_article_cache", "source_watermark": article.get("source_version")},
            "derived_article": {
                "article_id": article.get("article_id"),
                "revision_id": article.get("derived_revision_id"),
                "title": article.get("title"),
                "status": status,
                "fingerprint": article.get("fingerprint"),
                "source_article_ids": [str(value) for value in article.get("source_article_ids", [])],
                "evidence_ids": [str(value) for value in article.get("evidence_ids", [])],
            },
            "cache_hit": True,
        }
    return None


def _load_autoapi_job_catalog(vehicle: dict[str, object], target: object) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Hydrate the requested vehicle from AutoAPI only after a local miss.

    A configured provider vehicle ID performs one vehicle bundle fetch. Without
    that ID, the connector performs its complete year/make/model traversal so
    the same miss warms the complete selector/article-list cache.
    """

    base_url = os.getenv("AUTODATA_AUTOAPI_BASE_URL", "").strip()
    if not base_url:
        return [], {"mode": "source_unavailable", "reason": "autoapi_not_configured"}
    from .autoapi_connector import AutoAPIConnector
    from .source_adapters import adapt_source_resource
    from .source_bundle import normalize_source_bundle

    connector = AutoAPIConnector(
        base_url,
        content_source=os.getenv("AUTODATA_AUTOAPI_CONTENT_SOURCE", "GeneralMotors"),
        default_region=str(vehicle.get("region") or os.getenv("AUTODATA_SOURCE_REGION", "US")),
        source_version=os.getenv("AUTODATA_AUTOAPI_SOURCE_VERSION", "autoapi-http-v1"),
        vehicle_max_concurrency=int(os.getenv("AUTODATA_AUTOAPI_VEHICLE_CONCURRENCY", "4")),
        retry_attempts=int(os.getenv("AUTODATA_AUTOAPI_RETRY_ATTEMPTS", "3")),
        retry_backoff_seconds=float(os.getenv("AUTODATA_AUTOAPI_RETRY_BACKOFF_SECONDS", "0.25")),
    )
    provider_vehicle_id = str(vehicle.get("autoapi_vehicle_id") or vehicle.get("provider_vehicle_id") or "").strip()
    if provider_vehicle_id:
        bundle = connector.fetch_vehicle_bundle({"vehicle_id": provider_vehicle_id, **vehicle})
        bundles = (bundle,)
        traversal = "vehicle_bundle"
    else:
        catalog = connector.fetch_catalog()
        bundles = tuple(item for item in catalog.vehicles if _same_vehicle_family(item.vehicle, vehicle))
        traversal = "full_catalog"
        if os.getenv("AUTODATA_SOURCE_PERSIST") == "1" and catalog.vehicles:
            from .autoapi_batch import execute_autoapi_batch

            execute_autoapi_batch(
                catalog.to_batches(),
                source_version=connector.source_version,
                persist=True,
                adapter_name=connector.name,
                selector_rows=catalog.selection_rows,
                selector_source_uri=f"{base_url.rstrip('/')}/v1/api/years",
            )
    records: list[dict[str, object]] = []
    for bundle in bundles:
        artifacts = [adapt_source_resource(resource) for resource in bundle.resources]
        normalized = normalize_source_bundle(
            artifacts,
            str(vehicle.get("region") or "US"),
            expected_vehicle=dict(bundle.vehicle),
        )
        if os.getenv("AUTODATA_SOURCE_PERSIST") == "1":
            from .bundle_persistence import persist_source_bundle

            persist_source_bundle(normalized, artifacts, adapter_name=connector.name)
        evidence_by_id = {str(item["evidence_id"]): item for item in normalized.evidence if item.get("evidence_id")}
        for article in normalized.articles:
            records.append({
                "kind": "article",
                "vehicle_key": bundle.vehicle.get("vehicle_key"),
                "vehicle_identity": dict(bundle.vehicle),
                "article": dict(article),
                "evidence": (
                    [evidence_by_id[str(article["evidence_id"])] ]
                    if article.get("evidence_id") and str(article["evidence_id"]) in evidence_by_id
                    else []
                ),
            })
    return records, {"mode": "autoapi_fallback", "traversal": traversal, "vehicle_count": len(bundles), "materialized_records": len(records)}


def _same_vehicle_family(left: dict[str, object], right: dict[str, object]) -> bool:
    return all(str(left.get(key, "")).casefold() == str(right.get(key, "")).casefold() for key in ("year", "make", "model"))


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


def _vehicle_target_from_mapping(value: dict[str, object], year: object):
    from .article_intake import VehicleTarget

    return VehicleTarget(
        value["make"],
        value["model"],
        year,
        value["region"],
        value.get("trim"),
        value.get("body_style", value.get("bodyStyle")),
        value.get("drivetrain", value.get("driveType")),
        value.get(
            "engine_displacement_l",
            value.get("engine", value.get("engineDisplacementL")),
        ),
    )


def _attach_persistence_ids(
    vehicles: list[dict[str, object]], persistence: object
) -> None:
    """Add durable IDs to selector rows without changing their stable keys."""

    if not isinstance(persistence, dict):
        return
    observations = persistence.get("observations")
    if not isinstance(observations, list):
        return
    by_configuration: dict[str, dict[str, object]] = {}
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        key = observation.get("configuration_key")
        if isinstance(key, str) and key:
            by_configuration.setdefault(key, observation)
    for vehicle in vehicles:
        vehicle_observations = [
            item
            for item in observations
            if isinstance(item, dict)
            and item.get("vehicle_key") == vehicle.get("vehicle_id_key")
        ]
        if vehicle_observations:
            vehicle_id = vehicle_observations[0].get("vehicle_id")
            if vehicle_id:
                vehicle["vehicle_id"] = vehicle_id
        for configuration in vehicle.get("configurations", []):
            if not isinstance(configuration, dict):
                continue
            key = configuration.get("configuration_key")
            persisted = by_configuration.get(key) if isinstance(key, str) else None
            if persisted is None:
                continue
            for field in (
                "vehicle_id",
                "vehicle_configuration_id",
                "observation_id",
                "resolution_status",
            ):
                if persisted.get(field) is not None:
                    configuration[field] = persisted[field]


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
    extractor, extractor_error = _configured_mercury2_extractor()
    artifacts = []
    for resource in resources:
        artifact = adapt_source_resource(resource)
        if extractor is not None and artifact.kind == "structured" and not artifact.candidates:
            try:
                candidates = tuple(extractor.extract(resource))
            except Exception as error:  # noqa: BLE001 - source review must survive advisory failures
                artifact = replace(
                    artifact,
                    metadata={
                        **artifact.metadata,
                        "extraction_mode": "mercury-2",
                        "extraction_status": "needs_review",
                        "extraction_error": str(error),
                    },
                )
            else:
                artifact = replace(
                    artifact,
                    candidates=candidates,
                    metadata={
                        **artifact.metadata,
                        "extraction_mode": "mercury-2",
                        "candidate_count": len(candidates),
                        "extraction_status": "candidate_ready" if candidates else "needs_review",
                    },
                )
        elif extractor_error is not None and artifact.kind == "structured" and not artifact.candidates:
            artifact = replace(
                artifact,
                metadata={
                    **artifact.metadata,
                    "extraction_mode": "mercury-2",
                    "extraction_status": "needs_review",
                    "extraction_error": extractor_error,
                },
            )
        artifacts.append(artifact)
    bundle = normalize_source_bundle(
        artifacts,
        os.getenv("AUTODATA_SOURCE_REGION", "US"),
    )
    quality = evaluate_source_bundle(bundle)
    return artifacts, bundle, quality


def _configured_mercury2_extractor():
    """Return the opt-in advisory extractor or a review-safe configuration error."""

    from .mercury2 import configured_source_extractor

    return configured_source_extractor()


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
