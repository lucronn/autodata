"""Deterministic process boundary for the fast-lane worker."""

from __future__ import annotations

import json
import asyncio
import os
import re
import time
from collections.abc import Mapping
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
    chat_query_request = os.getenv("AUTODATA_CHAT_QUERY_JSON", "").strip()
    if chat_query_request:
        return run_chat_query(chat_query_request)
    chat_selection_request = os.getenv("AUTODATA_CHAT_SELECTION_JSON", "").strip()
    if chat_selection_request:
        return run_chat_selection(chat_selection_request)
    if os.getenv("AUTODATA_CHAT_WORKER_ENABLED") == "1":
        return run_chat_worker_once()
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

        catalog = load_vehicle_knowledge_catalog(target, query=str(query))
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
    from .job_plan import (
        _components_from_query,
        compose_procedure_with_llm,
        plan_job,
        translate_job_query_with_llm,
    )

    detected_components = _components_from_query(query)
    if not detected_components and os.getenv("AUTODATA_MERCURY2_JOB_PLANS_ENABLED") == "1":
        try:
            from .mercury2 import Mercury2Client

            translation = translate_job_query_with_llm(
                Mercury2Client.from_environment(), query, vehicle
            )
            translated_components = translation.get("components", [])
            if translated_components:
                query = " ".join(str(component) for component in translated_components)
                source_info["query_translation"] = translation
        except Exception as error:  # noqa: BLE001 - deterministic parsing remains the safe fallback
            source_info["query_translation"] = {
                "generation": "deterministic_fallback",
                "status": "unavailable",
                "error": str(error),
            }
    catalog = request.get("catalog")
    if catalog is None:
        from .article_intake import VehicleTarget
        from .knowledge_catalog import load_vehicle_knowledge_catalog

        year = vehicle.get("model_year", vehicle.get("year"))
        if year is None:
            raise ValueError("job plan vehicle requires year")
        target = _vehicle_target_from_mapping(vehicle, year)
        catalog = load_vehicle_knowledge_catalog(target, query=query)
        cached_derived = _cached_derived_job_plan(query, vehicle, catalog)
        if cached_derived is not None:
            return {"worker": "ingestion", "lane": "fast", **cached_derived}
        if not catalog or _catalog_needs_job_plan_hydration(query, catalog):
            fallback_catalog, fallback_info = _load_autoapi_job_catalog(
                vehicle, target, query=query
            )
            catalog = fallback_catalog
            source_info.update(fallback_info)
    if not isinstance(catalog, (list, tuple)):
        raise ValueError("job plan catalog must be an array")

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


def configure_chat_worker(runtime=None):
    """Bind the worker to the same injected chat repository/queue as HTTP."""

    from .chat_service import ensure_chat_runtime

    return ensure_chat_runtime(runtime)


def run_chat_query(serialized_request: str, *, runtime=None) -> dict[str, object]:
    """Create or replay one chat query from a worker-compatible JSON envelope."""

    try:
        request = json.loads(serialized_request)
    except json.JSONDecodeError as error:
        raise ValueError("chat query request must be valid JSON") from error
    if not isinstance(request, dict):
        raise ValueError("chat query request must contain an object")
    message = request.get("message")
    idempotency_key = str(request.get("idempotency_key", "")).strip()
    principal = request.get("principal", {})
    if not isinstance(message, str) or not message.strip():
        raise ValueError("chat query request requires message")
    if not idempotency_key:
        raise ValueError("chat query request requires idempotency_key")
    if not isinstance(principal, Mapping):
        raise ValueError("chat query request principal must be an object")
    from .chat_service import create_chat_query

    configure_chat_worker(runtime)

    return create_chat_query(
        message,
        idempotency_key=idempotency_key,
        principal=principal,
        conversation_id=request.get("conversation_id"),
        request_params=request.get("request_params"),
    )


def run_chat_selection(serialized_request: str, *, runtime=None) -> dict[str, object]:
    """Apply one pending chat vehicle selection from a worker JSON envelope."""

    try:
        request = json.loads(serialized_request)
    except json.JSONDecodeError as error:
        raise ValueError("chat selection request must be valid JSON") from error
    if not isinstance(request, dict):
        raise ValueError("chat selection request must contain an object")
    query_id = str(request.get("query_id", "")).strip()
    selection = request.get("selection", request)
    if not query_id:
        raise ValueError("chat selection request requires query_id")
    if not isinstance(selection, Mapping):
        raise ValueError("chat selection request selection must be an object")
    from .chat_service import select_chat_vehicle

    configure_chat_worker(runtime)

    return select_chat_vehicle(query_id, selection, principal=request.get("principal"))


def run_chat_worker_once(*, runtime=None) -> dict[str, object]:
    """Process one source job, then one independent price-refresh job.

    Source work keeps the fast lane ahead of refresh work. If no source job is
    due, the same worker process drains one price refresh so cached prices can
    update asynchronously without delaying the already published answer.
    """

    from .chat_service import process_chat_jobs, process_chat_price_jobs

    configure_chat_worker(runtime)

    processed = process_chat_jobs(max_jobs=1)
    if processed:
        return {
            "worker": "ingestion",
            "lane": "fast",
            "status": "completed",
            "query": processed[0],
        }

    refreshed = process_chat_price_jobs(max_jobs=1)
    if refreshed:
        return {
            "worker": "ingestion",
            "lane": "price_refresh",
            "status": "completed",
            "query": refreshed[0],
        }
    return {"worker": "ingestion", "lane": "fast", "status": "idle"}


def _catalog_needs_job_plan_hydration(
    query: str, catalog: list[dict[str, object]] | tuple[dict[str, object], ...]
) -> bool:
    """Return true when local rows cannot fulfill the requested job plan."""

    from .job_plan import _components_from_query, plan_job

    if not _components_from_query(query):
        return False
    preview = plan_job(query, {"make": "catalog", "model": "catalog"}, catalog=catalog)
    return any(
        str(reason).startswith(("missing_article:", "unknown_duration:"))
        for reason in preview.get("review_reasons", [])
    )


def _catalog_needs_procedure_content_hydration(
    query: str, catalog: list[dict[str, object]] | tuple[dict[str, object], ...]
) -> bool:
    """Return true when selected local articles lack source instructions."""

    from .job_plan import (
        _article_components,
        _article_procedure_instructions,
        _components_from_query,
    )

    requested = _components_from_query(query)
    if not requested:
        return False
    # Shared access articles (timing belt for both pumps) are part of the
    # reusable normalized set — treat them as required for a catalog hit.
    needed = list(
        dict.fromkeys(
            requested
            + (["timing_belt"] if {"oil_pump", "water_pump"} & set(requested) else [])
        )
    )
    articles: list[dict[str, object]] = []
    for record in catalog:
        if not isinstance(record, dict):
            continue
        article = record.get("article", record)
        if not isinstance(article, dict):
            continue
        # Combined / multi-component derived rows are ephemeral composition
        # outputs. They must not count as the normalized individual source.
        derived_components = article.get("derived_components")
        if isinstance(derived_components, list) and len(derived_components) > 1:
            continue
        article_id = str(article.get("article_id") or "")
        if article_id.startswith("combined:"):
            continue
        articles.append(article)
    for component in needed:
        candidates = [article for article in articles if component in _article_components(article)]
        if not candidates:
            return True
        for article in candidates:
            if _article_procedure_instructions(article):
                break
            body = str(article.get("body") or "").strip()
            if len(body) >= 80:
                break
        else:
            return True
    return False

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
        if isinstance(components, list) and components:
            if set(str(value) for value in components) != requested_set:
                continue
        if not _derived_article_covers_requested_components(article, requested_set):
            continue
        if not _derived_article_has_source_instructions(article, requested_set):
            continue
        if _mercury2_regeneration_required(article):
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


def _derived_article_has_source_instructions(
    article: Mapping[str, object], requested: set[str]
) -> bool:
    """Require source-authored procedure text before reusing a warm revision.

    A composed row can have complete component and labor metadata while still
    containing only generated operation labels. Reusing that row would hide
    the source article body that a cold lookup could hydrate. A step action is
    accepted as instructional only when it carries more detail than a generic
    component verb; explicit instructions always count when they are present.
    """

    body = " ".join(str(article.get("body") or "").split()).strip()
    title = " ".join(str(article.get("title") or "").split()).strip()
    if body and body.casefold() != title.casefold() and (
        len(body) >= len(title) + 40
        or len(re.findall(r"[a-z0-9]+", body.casefold())) >= 8
    ):
        return True

    procedure = article.get("procedure")
    if not isinstance(procedure, Mapping):
        return False
    steps = procedure.get("steps", ())
    if not isinstance(steps, (list, tuple)) or not steps:
        return False
    covered: set[str] = set()
    instructional: set[str] = set()
    for step in steps:
        if isinstance(step, str):
            text = " ".join(step.split()).strip()
            if text and not _is_generic_derived_action(text):
                instructional.update(requested)
                covered.update(requested)
            continue
        if not isinstance(step, Mapping):
            continue
        values = step.get("components", step.get("component", ()))
        if isinstance(values, str):
            values = [values]
        components = {
            str(value).strip()
            for value in values
            if str(value).strip()
        } if isinstance(values, (list, tuple, set)) else set()
        covered.update(components)
        instructions = step.get("instructions", step.get("instruction", ()))
        if isinstance(instructions, str):
            instructions = [instructions]
        for instruction in instructions if isinstance(instructions, (list, tuple)) else ():
            text = " ".join(str(instruction or "").split()).strip()
            if text:
                instructional.update(components)
    return requested.issubset(instructional) and requested.issubset(covered)


def _is_generic_derived_action(action: str) -> bool:
    """Identify a label-only operation without rejecting detailed source text."""

    normalized = re.sub(r"[^a-z0-9]+", " ", action.casefold()).strip()
    if not normalized:
        return True
    if normalized.endswith(" r r"):
        return True
    if re.fullmatch(
        r"[a-z0-9]+(?: [a-z0-9]+){0,7} (?:replacement|service|repair|inspection|installation|removal)",
        normalized,
    ):
        return True
    return bool(
        re.fullmatch(
            r"(?:remove|install|replace|service|inspect|check|repair) "
            r"[a-z0-9]+(?: [a-z0-9]+){0,3}",
            normalized,
        )
    )


def _derived_article_covers_requested_components(
    article: Mapping[str, object], requested: set[str]
) -> bool:
    """Reject a warm composition that names work it does not actually cover."""

    covered: set[str] = set()

    procedure = article.get("procedure")
    if isinstance(procedure, Mapping):
        steps = procedure.get("steps", ())
        if isinstance(steps, (list, tuple)):
            for step in steps:
                if not isinstance(step, Mapping):
                    continue
                values = step.get("components", step.get("component", ()))
                if isinstance(values, str):
                    values = [values]
                if isinstance(values, (list, tuple, set)):
                    covered.update(str(value) for value in values if str(value).strip())

    labor = article.get("labor")
    if isinstance(labor, Mapping):
        operations = labor.get("operations", ())
        if isinstance(operations, (list, tuple)):
            for operation in operations:
                if not isinstance(operation, Mapping):
                    continue
                values = operation.get("components", operation.get("component", ()))
                if isinstance(values, str):
                    values = [values]
                if isinstance(values, (list, tuple, set)):
                    covered.update(str(value) for value in values if str(value).strip())

    if requested.issubset(covered):
        return True
    # A single-component persisted row may legitimately contain only a labor
    # summary while its instructional content is still pending. It is safe to
    # reuse that row for the one requested component; a multi-component row
    # must prove coverage for every requested component before being reused.
    declared = {str(value) for value in article.get("derived_components", [])}
    return len(requested) == 1 and declared == requested


def _mercury2_regeneration_required(article: Mapping[str, object]) -> bool:
    """Regenerate an old deterministic composition when Mercury-2 is configured."""

    if isinstance(article.get("derived_components"), (list, tuple, set)):
        from .derived_article_persistence import DERIVED_ARTICLE_CONTRACT_VERSION

        try:
            cached_contract_version = int(article.get("contract_version") or 0)
        except (TypeError, ValueError):
            cached_contract_version = 0
        if cached_contract_version < DERIVED_ARTICLE_CONTRACT_VERSION:
            return True

    procedure = article.get("procedure")
    declared_components = {
        str(value).strip()
        for value in article.get("derived_components", [])
        if str(value).strip()
    } if isinstance(article.get("derived_components"), (list, tuple, set)) else set()
    if not declared_components and isinstance(procedure, Mapping):
        steps = procedure.get("steps")
        if isinstance(steps, list):
            declared_components = {
                str(value).strip()
                for step in steps
                if isinstance(step, Mapping)
                for value in step.get("components", [])
                if str(value).strip()
            }
    if len(declared_components) > 1 and isinstance(procedure, Mapping):
        overlap_groups = procedure.get("overlap_groups")
        steps = procedure.get("steps")
        has_shared_step = isinstance(steps, list) and any(
            isinstance(step, Mapping)
            and (
                str(step.get("operation_id", "")).startswith("shared:")
                or len({str(value) for value in step.get("components", []) if str(value).strip()}) > 1
            )
            for step in steps
        )
        if not has_shared_step or not isinstance(overlap_groups, list) or not overlap_groups:
            return (
                os.getenv("AUTODATA_MERCURY2_JOB_PLANS_ENABLED") == "1"
                and bool(os.getenv("INCEPTION_API_KEY", "").strip())
            )
        if _derived_procedure_has_redundant_shared_steps(article):
            return (
                os.getenv("AUTODATA_MERCURY2_JOB_PLANS_ENABLED") == "1"
                and bool(os.getenv("INCEPTION_API_KEY", "").strip())
            )

    if (
        os.getenv("AUTODATA_MERCURY2_JOB_PLANS_ENABLED") == "1"
        and bool(os.getenv("INCEPTION_API_KEY", "").strip())
        and str(article.get("model") or "deterministic") in {"mercury-2", "generated"}
        and not _derived_procedure_covers_shared_labor(article)
    ):
        return True
    return (
        os.getenv("AUTODATA_MERCURY2_JOB_PLANS_ENABLED") == "1"
        and bool(os.getenv("INCEPTION_API_KEY", "").strip())
        and str(article.get("model") or "deterministic") not in {"mercury-2", "generated"}
    )


def _derived_procedure_covers_shared_labor(article: Mapping[str, object]) -> bool:
    """Require cached LLM procedures to retain multi-component shared work."""

    labor = article.get("labor")
    procedure = article.get("procedure")
    if not isinstance(labor, Mapping) or not isinstance(procedure, Mapping):
        return True
    operations = labor.get("operations", [])
    steps = procedure.get("steps", [])
    if not isinstance(operations, list) or not isinstance(steps, list):
        return True
    for operation in operations:
        if not isinstance(operation, Mapping):
            continue
        components = {str(value) for value in operation.get("components", []) if str(value).strip()}
        if len(components) < 2:
            continue
        if not any(
            components.issubset(
                {str(value) for value in step.get("components", []) if str(value).strip()}
            )
            for step in steps
            if isinstance(step, Mapping)
        ):
            return False
    return True


def _derived_procedure_has_redundant_shared_steps(article: Mapping[str, object]) -> bool:
    """Detect cached responses that emit a covered operation twice."""

    procedure = article.get("procedure")
    if not isinstance(procedure, Mapping):
        return False
    steps = procedure.get("steps", [])
    if not isinstance(steps, list):
        return False
    shared_coverage = {
        str(operation_id).strip()
        for step in steps
        if isinstance(step, Mapping)
        and str(step.get("operation_id", "")).startswith("shared:")
        for operation_id in step.get("covered_operation_ids", [])
        if str(operation_id).strip()
    }
    return any(
        isinstance(step, Mapping)
        and not str(step.get("operation_id", "")).startswith("shared:")
        and str(step.get("operation_id", "")).strip() in shared_coverage
        for step in steps
    )


def _load_autoapi_job_catalog(
    vehicle: dict[str, object], target: object, *, query: str = ""
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Hydrate one Bankone source vehicle through Source Connector v1."""

    from urllib.parse import quote

    from .job_plan import plan_job
    from .source_adapters import SourceResource, adapt_source_resource
    from .source_bundle import normalize_source_bundle
    from .source_connector_client import SourceConnectorError, source_connector_registry

    connector = source_connector_registry().get("bankone")
    if connector is None:
        return [], {"mode": "source_unavailable", "reason": "bankone_not_configured"}

    selector: dict[str, object] = {
        "year": int(vehicle.get("model_year", vehicle.get("year", 0))),
        "make": str(vehicle.get("make") or ""),
        "model": str(vehicle.get("model") or ""),
        "region": str(vehicle.get("region") or os.getenv("AUTODATA_SOURCE_REGION", "US")),
    }
    configuration = " ".join(
        str(value).strip()
        for value in (vehicle.get("trim"), vehicle.get("engine"), vehicle.get("drivetrain"))
        if value not in (None, "")
    )
    if configuration:
        selector["configuration"] = configuration
    explicit_ref = str(vehicle.get("source_vehicle_ref") or "").strip()
    if explicit_ref:
        source_vehicle_ref = explicit_ref
    else:
        resolution = connector.resolve_vehicle(selector)
        candidates = resolution.body["candidates"]
        if len(candidates) != 1:
            raise SourceConnectorError("AMBIGUOUS" if candidates else "NOT_FOUND")
        source_vehicle_ref = str(candidates[0]["opaque_ref"])

    pages = []
    source_articles: list[dict[str, object]] = []
    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(1000):
        page = connector.list_articles(source_vehicle_ref, cursor)
        pages.append(page)
        source_articles.extend(dict(item) for item in page.body["articles"])
        if page.complete:
            break
        cursor = page.next_cursor
        if cursor is None or cursor in seen:
            raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
        seen.add(cursor)
    else:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    if not pages:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")

    persisted_provider = pages[0].persisted_provider
    requested_article_id = str(vehicle.get("requested_article_id") or "").strip()

    def article_id_for(item: Mapping[str, object]) -> str:
        opaque_ref = str(item["opaque_ref"])
        if requested_article_id and (
            requested_article_id == opaque_ref
            or requested_article_id.rsplit(":", 1)[-1] == opaque_ref.rsplit(":", 1)[-1]
        ):
            return requested_article_id
        return f"{persisted_provider}:{source_vehicle_ref}:{opaque_ref}"

    article_details = [
        {
            "id": article_id_for(item),
            "title": item["title"],
            "bucket": item.get("category"),
            "component": item.get("component"),
            "resource_ref": item.get("resource_ref"),
            "labor_resource_ref": item.get("labor_resource_ref"),
            "asset_resource_refs": item.get("asset_resource_refs", []),
        }
        for item in source_articles
    ]
    source_locator = pages[0].source_locator or (
        f"{connector.base_url}/v1/vehicles/{quote(source_vehicle_ref, safe='')}/articles"
    )
    source_payload = {
        "kind": "vehicle",
        "year": selector["year"],
        "make": selector["make"],
        "model": selector["model"],
        "region": selector["region"],
        "trim": vehicle.get("trim"),
        "drivetrain": vehicle.get("drivetrain"),
        "engine": vehicle.get("engine_displacement_l", vehicle.get("engine")),
        "articleDetails": article_details,
    }
    index_resource = SourceResource.from_bytes(
        source_locator,
        pages[0].source_revision,
        json.dumps(source_payload, sort_keys=True, separators=(",", ":")).encode(),
        "application/json",
        locator=source_locator,
        metadata={
            "provider": persisted_provider,
            "source_provider": "bankone",
            "vehicle_id": source_vehicle_ref,
            "request_ids": [page.request_id for page in pages],
            "page_locators": [page.source_locator for page in pages if page.source_locator],
        },
    )
    index_artifact = adapt_source_resource(index_resource)
    expected_vehicle = dict(vehicle)
    index_bundle = normalize_source_bundle(
        [index_artifact],
        str(vehicle.get("region") or "US"),
        expected_vehicle=expected_vehicle,
        preserve_article_order=True,
    )
    canonical_vehicle = index_bundle.vehicle
    if canonical_vehicle is None:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    list_records = [
        {
            "kind": "article",
            "vehicle_key": canonical_vehicle.get("vehicle_key"),
            "vehicle_identity": dict(canonical_vehicle),
            "article": dict(article),
            "evidence": [],
        }
        for article in index_bundle.articles
    ]

    selected_ids: set[str] = set()
    selected_items: list[dict[str, object]] = []
    if query and list_records:
        planned = plan_job(query, vehicle, catalog=list_records)
        selected_ids.update(str(value) for value in planned.get("selected_articles", []))
    if requested_article_id:
        selected = [
            article_id_for(item)
            for item in source_articles
            if article_id_for(item) == requested_article_id
        ]
        selected_ids.update(selected)

    artifacts = [index_artifact]
    targeted_article_count = 0
    targeted_labor_count = 0
    if selected_ids:
        selected_items = [
            item for item in source_articles if article_id_for(item) in selected_ids
        ]
        for item in selected_items:
            article_id = article_id_for(item)
            refs = [item.get("resource_ref"), item.get("labor_resource_ref")]
            refs.extend(item.get("asset_resource_refs") or [])
            fetched_article = False
            for resource_ref in dict.fromkeys(str(ref) for ref in refs if ref):
                resource = connector.read_resource(resource_ref).to_source_resource()
                if resource_ref == item.get("resource_ref"):
                    resource = replace(
                        resource,
                        metadata={**resource.metadata, "target_article_id": article_id},
                    )
                    fetched_article = True
                artifacts.append(adapt_source_resource(resource))
                if resource_ref != item.get("resource_ref"):
                    targeted_labor_count += int(resource_ref == item.get("labor_resource_ref"))
            targeted_article_count += int(fetched_article)

    normalized = normalize_source_bundle(
        artifacts,
        str(vehicle.get("region") or "US"),
        expected_vehicle=expected_vehicle,
        preserve_article_order=True,
    )
    from .procedure_normalize import normalize_procedure_article

    normalized_articles = []
    selected_id_by_title = {
        str(item.get("title") or "").strip().casefold(): article_id_for(item)
        for item in selected_items if selected_ids
    }
    for article in normalized.articles:
        if article.get("body") or article.get("steps"):
            article = normalize_procedure_article(article)
        selected_id = selected_id_by_title.get(str(article.get("title") or "").strip().casefold())
        if selected_id:
            article["article_id"] = selected_id
        normalized_articles.append(article)
    normalized = replace(normalized, articles=tuple(normalized_articles))

    if os.getenv("AUTODATA_SOURCE_PERSIST") == "1":
        from .procedure_images import localize_procedure_images

        localized_articles = []
        for article in normalized.articles:
            try:
                localized_articles.append(
                    localize_procedure_images(article, vehicle=normalized.vehicle or vehicle)
                )
            except Exception:  # noqa: BLE001 - retain readable text if media storage is unavailable
                localized_articles.append(article)
        normalized = replace(normalized, articles=tuple(localized_articles))
        from .bundle_persistence import persist_source_bundle

        persist_source_bundle(normalized, artifacts, adapter_name="autoapi")

    evidence_by_id = {
        str(item["evidence_id"]): item
        for item in normalized.evidence
        if item.get("evidence_id")
    }
    records = [
        {
            "kind": "article",
            "vehicle_key": canonical_vehicle.get("vehicle_key"),
            "vehicle_identity": dict(canonical_vehicle),
            "article": dict(article),
            "evidence": (
                [evidence_by_id[str(article["evidence_id"])] ]
                if article.get("evidence_id") and str(article["evidence_id"]) in evidence_by_id
                else []
            ),
        }
        for article in normalized.articles
    ]
    return records, {
        "mode": "source_connector_v1",
        "content_source": "autoapi",
        "source_provider": "bankone",
        "traversal": "vehicle_article_index",
        "vehicle_count": 1,
        "materialized_records": len(records),
        "index_read_count": len(pages),
        "targeted_article_fetch_count": targeted_article_count,
        "targeted_labor_fetch_count": targeted_labor_count,
    }


def _article_lookup_title(article: Mapping[str, object]) -> str:
    values = [article.get("title"), article.get("subtitle")]
    return " ".join(" ".join(str(value or "").split()) for value in values if value).casefold()


_LABOR_OPERATION_WORDS = frozenset({
    "adjust",
    "adjustment",
    "check",
    "inspect",
    "inspection",
    "install",
    "installation",
    "overhaul",
    "r",
    "remove",
    "removal",
    "replace",
    "replacement",
    "repair",
    "rpr",
    "service",
    "servicing",
    "test",
    "testing",
})


def _article_component_key(article: Mapping[str, object]) -> str:
    tokens = re.findall(r"[a-z0-9]+", _article_lookup_title(article))
    return " ".join(token for token in tokens if token not in _LABOR_OPERATION_WORDS)


def _match_labor_article_id(
    procedure: Mapping[str, object], labor_articles: list[Mapping[str, object]]
) -> str | None:
    """Match one labor row without guessing across ambiguous qualifiers."""

    procedure_title = _article_lookup_title(procedure)
    exact = [
        article
        for article in labor_articles
        if _article_lookup_title(article) == procedure_title
    ]
    candidates = exact or [
        article
        for article in labor_articles
        if _article_component_key(article)
        and _article_component_key(article) == _article_component_key(procedure)
    ]
    if len(candidates) != 1:
        return None
    article_id = str(candidates[0].get("article_id") or "").strip()
    return article_id or None


def _is_labor_article(article: Mapping[str, object]) -> bool:
    return str(article.get("article_id") or "").casefold().startswith("l:") or str(article.get("bucket") or "").casefold() == "labor"


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
    chat_worker_enabled = os.getenv("AUTODATA_CHAT_WORKER_ENABLED") == "1"
    if os.getenv("AUTODATA_WORKER_ONCE") == "1":
        if knowledge_consumer_enabled:
            result = run_knowledge_fallback_once()
        elif chat_worker_enabled:
            result = run_chat_worker_once()
        else:
            result = run_nats_once() if consumer_enabled else run_once()
        print(json.dumps(result, sort_keys=True))
        return
    while True:
        if knowledge_consumer_enabled:
            result = run_knowledge_fallback_once()
        elif chat_worker_enabled:
            result = run_chat_worker_once()
        else:
            result = run_nats_once() if consumer_enabled else run_once()
        print(json.dumps(result, sort_keys=True), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
