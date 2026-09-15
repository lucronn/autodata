"""Deterministic cold/warm smoke for the natural-language chat flow.

The smoke deliberately runs the existing chat state machine with explicit
in-memory adapters.  It is suitable for a developer workstation and protected
CI: no database, NATS server, object store, credentials, or live provider is
needed.  The report keeps the cold source-visible revision, the normalized
revision, the asynchronous price refresh, worker events, and the warm replay
call budget separate so a passing run proves the intended lifecycle instead of
only proving that one JSON object can be constructed.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping
import uuid


ROOT = Path(__file__).parents[2]
WORKER_SRC = ROOT / "workers" / "ingestion-python" / "src"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from autodata_ingestion.chat_service import (  # noqa: E402
    ChatDependencies,
    ChatRuntime,
    InMemoryChatQueue,
    InMemoryChatRepository,
    configure_chat_runtime,
    create_chat_query,
    get_chat_query,
    process_chat_jobs,
    process_chat_price_jobs,
)
from autodata_ingestion.job_plan import build_quote_and_procedure  # noqa: E402
from autodata_ingestion.progress_events import ProgressEventStore  # noqa: E402
from autodata_ingestion.visual_vectorization import (  # noqa: E402
    DeterministicLocalVectorizer,
    vectorize_source_diagram,
)


DEFAULT_QUERY = "97 Toyota RAV4 brake line replacement procedure, and quote"
# Keep the vehicle phrase at the start so the production intent parser sees the
# same vehicle while the wording still exercises the normalized-cache path.
SEMANTIC_REPLAY_QUERY = "1997 Toyota RAV4 brake line replacement quote and procedure"
DEFAULT_IDEMPOTENCY_KEY = "chat-smoke-cold-001"
SEMANTIC_REPLAY_IDEMPOTENCY_KEY = "chat-smoke-warm-semantic-001"
SOURCE_URI = "https://source.test/rav4/brake-line-article-list"
SOURCE_VERSION = "fixture-rav4-brake-v1"
STALE_PRICED_AT = "2026-08-01T00:00:00Z"
REFRESHED_PRICED_AT = "2026-09-11T00:00:00Z"
DIAGRAM_URI = "https://source.test/rav4/brake-line.png"
MINIMAL_PNG = b"\x89PNG\r\n\x1a\n" + b"autodata-deterministic-diagram"

VEHICLE: dict[str, Any] = {
    "vehicle_id": "vehicle-1997-toyota-rav4-4wd",
    "candidate_key": "toyota-rav4-1997-4wd-us",
    "year": 1997,
    "make": "Toyota",
    "model": "RAV4",
    "region": "US",
    "drivetrain": "4WD",
    "engine_displacement_l": 2.0,
}

PRINCIPAL = {
    "owner_id": "chat-smoke-owner",
    "organization_id": "chat-smoke-org",
    "conversation_id": "chat-smoke-conversation",
}

BASE_CASE = {
    "name": "rav4_brake_line",
    "query": DEFAULT_QUERY,
    "warm_query": SEMANTIC_REPLAY_QUERY,
    "vehicle": VEHICLE,
    "source_uri": SOURCE_URI,
    "source_version": SOURCE_VERSION,
    "expects_overlap": True,
}

ADDITIONAL_CASES = (
    {
        "name": "silverado_oil_water_pumps",
        "query": "1999 Chevrolet Silverado 1500 2WD 5.3L oil pump and water pump replacement procedure, and quote",
        "warm_query": "1999 Chevrolet Silverado 1500 2WD 5.3L water pump and oil pump replacement quote and procedure",
        "vehicle": {
            "vehicle_id": "vehicle-1999-chevrolet-silverado-1500-2wd-5-3l",
            "candidate_key": "chevrolet-silverado-1500-1999-2wd-5-3l-us",
            "year": 1999,
            "make": "Chevrolet",
            "model": "Silverado 1500",
            "region": "US",
            "drivetrain": "2WD",
            "engine_displacement_l": 5.3,
        },
        "source_uri": "https://source.test/silverado-1500/oil-water-pump-articles",
        "source_version": "fixture-silverado-pumps-v1",
        "expects_overlap": True,
    },
    {
        "name": "tacoma_alternator",
        "query": "2024 Toyota Tacoma 4WD 3.5L alternator replacement procedure, and quote",
        "warm_query": "2024 Toyota Tacoma 4WD 3.5L alternator replacement quote and procedure",
        "vehicle": {
            "vehicle_id": "vehicle-2024-toyota-tacoma-4wd-3-5l",
            "candidate_key": "toyota-tacoma-2024-4wd-3-5l-us",
            "year": 2024,
            "make": "Toyota",
            "model": "Tacoma",
            "region": "US",
            "drivetrain": "4WD",
            "engine_displacement_l": 3.5,
        },
        "source_uri": "https://source.test/tacoma/alternator-article",
        "source_version": "fixture-tacoma-alternator-v1",
        "expects_overlap": False,
    },
)

SMOKE_CASES = (BASE_CASE, *ADDITIONAL_CASES)


def _case_for_query(message: str) -> dict[str, Any]:
    """Resolve a smoke query to one of the bounded deterministic fixtures."""

    lowered = str(message).casefold().replace("-", " ")
    for case in SMOKE_CASES:
        vehicle = case["vehicle"]
        year = int(vehicle["year"])
        year_tokens = {str(year), f"{year % 100:02d}"}
        model = str(vehicle["model"]).casefold()
        if any(token in lowered for token in year_tokens) and model in lowered:
            return case
    raise AssertionError(f"no deterministic smoke fixture for query: {message}")


def _evidence(
    evidence_id: str,
    locator: str,
    text: str,
    *,
    source_uri: str = SOURCE_URI,
    source_version: str = SOURCE_VERSION,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "locator": locator,
        "source_uri": source_uri,
        "source_version": source_version,
        "source_watermark": source_version,
        "extracted_text": text,
        "confidence": 1.0,
        "reviewer_state": "pending",
    }


def _operation(
    operation_id: str,
    action: str,
    duration_hours: float,
    evidence_id: str,
    *,
    category: str = "required",
    components: list[str] | None = None,
    shared_work_scope: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "operation_id": operation_id,
        "action": action,
        "duration_hours": duration_hours,
        "category": category,
        "evidence_ids": [evidence_id],
    }
    if components:
        result["components"] = list(components)
    if shared_work_scope:
        result["shared_work_scope"] = shared_work_scope
    return result


def fixture_articles() -> list[dict[str, Any]]:
    """Return a source-shaped article list with explicit overlap metadata."""

    return [
        {
            "article_id": "rav4-brake-line-1997",
            "title": "1997 Toyota RAV4 brake line replacement",
            "component": "brake_line",
            "vehicle": dict(VEHICLE),
            "body": "Replace the brake line and bleed the hydraulic system.",
            "evidence": [
                _evidence(
                    "evidence-rav4-brake-line",
                    "article:brake-line:body",
                    "Remove the old brake line and install the replacement line.",
                )
            ],
            "operations": [
                _operation(
                    "vehicle-access",
                    "Raise and support the vehicle",
                    0.4,
                    "evidence-rav4-brake-line",
                    shared_work_scope="vehicle-access",
                ),
                _operation(
                    "replace-brake-line",
                    "Replace the brake line",
                    1.2,
                    "evidence-rav4-brake-line",
                ),
            ],
            "parts": [
                {
                    "part_id": "rav4-brake-line-kit",
                    "source_part_number": "BL-RAV4-97",
                    "name": "Brake line kit",
                    "amount": 52.50,
                    "currency": "USD",
                    "priced_at": STALE_PRICED_AT,
                    "freshness": "stale",
                    "refresh_status": "queued",
                    "source_snapshot_id": "snapshot-rav4-parts-v1",
                    "source_uri": SOURCE_URI,
                    "evidence_ids": ["evidence-rav4-brake-line"],
                }
            ],
            "images": [{"url": DIAGRAM_URI, "alt": "Brake line routing diagram"}],
        },
        {
            "article_id": "rav4-brake-bleeding-1997",
            "title": "1997 Toyota RAV4 brake bleeding",
            "component": "brake_bleeding",
            "supporting_for": ["brake_line"],
            "support_category": "required",
            "vehicle": dict(VEHICLE),
            "body": "Bleed the brake system after opening the hydraulic circuit.",
            "evidence": [
                _evidence(
                    "evidence-rav4-brake-bleeding",
                    "article:brake-bleeding:body",
                    "Bleed the brake system and verify a firm pedal.",
                )
            ],
            "operations": [
                _operation(
                    "vehicle-access",
                    "Raise and support the vehicle",
                    0.4,
                    "evidence-rav4-brake-bleeding",
                    shared_work_scope="vehicle-access",
                ),
                _operation(
                    "bleed-brakes",
                    "Bleed the brake system",
                    0.6,
                    "evidence-rav4-brake-bleeding",
                ),
            ],
            "parts": [
                {
                    "part_id": "rav4-brake-fluid",
                    "source_part_number": "BF-DOT3-1QT",
                    "name": "DOT 3 brake fluid",
                    "amount": 18.99,
                    "currency": "USD",
                    "priced_at": STALE_PRICED_AT,
                    "freshness": "stale",
                    "refresh_status": "queued",
                    "source_snapshot_id": "snapshot-rav4-parts-v1",
                    "source_uri": SOURCE_URI,
                    "evidence_ids": ["evidence-rav4-brake-bleeding"],
                }
            ],
        },
        {
            "article_id": "rav4-brake-inspection-1997",
            "title": "1997 Toyota RAV4 brake system inspection",
            "component": "brake_inspection",
            "supporting_for": ["brake_line"],
            "support_category": "recommended",
            "vehicle": dict(VEHICLE),
            "body": "Inspect the brake system after completing the repair.",
            "evidence": [
                _evidence(
                    "evidence-rav4-brake-inspection",
                    "article:brake-inspection:body",
                    "Inspect fittings and verify the brake pedal after service.",
                )
            ],
            "operations": [
                _operation(
                    "vehicle-access",
                    "Raise and support the vehicle",
                    0.4,
                    "evidence-rav4-brake-inspection",
                    category="recommended",
                    shared_work_scope="vehicle-access",
                ),
                _operation(
                    "inspect-brake-system",
                    "Inspect the brake system",
                    0.4,
                    "evidence-rav4-brake-inspection",
                    category="recommended",
                ),
            ],
        },
    ]


def _fixture_article(
    case: Mapping[str, Any],
    *,
    article_id: str,
    title: str,
    component: str,
    body: str,
    evidence_id: str,
    evidence_text: str,
    operations: list[Mapping[str, Any]],
    part_id: str,
    part_number: str,
    part_name: str,
    amount: float,
) -> dict[str, Any]:
    source_uri = str(case["source_uri"])
    source_version = str(case["source_version"])
    return {
        "article_id": article_id,
        "title": title,
        "component": component,
        "vehicle": dict(case["vehicle"]),
        "source_uri": source_uri,
        "source_version": source_version,
        "source_watermark": source_version,
        "body": body,
        "evidence": [
            _evidence(
                evidence_id,
                f"article:{component}:body",
                evidence_text,
                source_uri=source_uri,
                source_version=source_version,
            )
        ],
        "operations": [dict(operation) for operation in operations],
        "parts": [
            {
                "part_id": part_id,
                "source_part_number": part_number,
                "name": part_name,
                "amount": amount,
                "currency": "USD",
                "priced_at": STALE_PRICED_AT,
                "freshness": "stale",
                "refresh_status": "queued",
                "source_snapshot_id": f"snapshot-{case['name']}-parts-v1",
                "source_uri": source_uri,
                "evidence_ids": [evidence_id],
            }
        ],
    }


def fixture_articles_for_case(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the source-shaped articles for a non-RAV4 acceptance case."""

    if case["name"] == "silverado_oil_water_pumps":
        return [
            _fixture_article(
                case,
                article_id="silverado-1500-oil-pump-1999",
                title="1999 Chevrolet Silverado 1500 5.3L oil pump replacement",
                component="oil_pump",
                body="Replace the oil pump after removing the shared engine access components.",
                evidence_id="evidence-silverado-oil-pump",
                evidence_text="Remove the oil pump and install the specified replacement.",
                operations=[
                    _operation(
                        "engine-access",
                        "Remove shared engine access components",
                        0.8,
                        "evidence-silverado-oil-pump",
                        components=["oil_pump"],
                        shared_work_scope="engine-access",
                    ),
                    _operation(
                        "replace-oil-pump",
                        "Replace the oil pump",
                        1.6,
                        "evidence-silverado-oil-pump",
                        components=["oil_pump"],
                    ),
                ],
                part_id="silverado-oil-pump",
                part_number="OP-SILVERADO-53",
                part_name="5.3L oil pump",
                amount=119.95,
            ),
            _fixture_article(
                case,
                article_id="silverado-1500-water-pump-1999",
                title="1999 Chevrolet Silverado 1500 5.3L water pump replacement",
                component="water_pump",
                body="Replace the water pump after removing the shared engine access components.",
                evidence_id="evidence-silverado-water-pump",
                evidence_text="Remove the water pump and install the specified replacement.",
                operations=[
                    _operation(
                        "engine-access",
                        "Remove shared engine access components",
                        0.8,
                        "evidence-silverado-water-pump",
                        components=["water_pump"],
                        shared_work_scope="engine-access",
                    ),
                    _operation(
                        "replace-water-pump",
                        "Replace the water pump",
                        1.3,
                        "evidence-silverado-water-pump",
                        components=["water_pump"],
                    ),
                ],
                part_id="silverado-water-pump",
                part_number="WP-SILVERADO-53",
                part_name="5.3L water pump",
                amount=87.40,
            ),
        ]
    if case["name"] == "tacoma_alternator":
        return [
            _fixture_article(
                case,
                article_id="tacoma-alternator-2024",
                title="2024 Toyota Tacoma 3.5L alternator replacement",
                component="alternator",
                body="Replace the alternator and verify charging output.",
                evidence_id="evidence-tacoma-alternator",
                evidence_text="Remove the alternator, install the replacement, and verify charging output.",
                operations=[
                    _operation(
                        "access-alternator",
                        "Access the alternator",
                        0.4,
                        "evidence-tacoma-alternator",
                        components=["alternator"],
                        shared_work_scope="access-alternator",
                    ),
                    _operation(
                        "replace-alternator",
                        "Replace the alternator",
                        1.1,
                        "evidence-tacoma-alternator",
                        components=["alternator"],
                    ),
                ],
                part_id="tacoma-alternator",
                part_number="ALT-TACOMA-35",
                part_name="3.5L alternator",
                amount=264.00,
            )
        ]
    raise AssertionError(f"no fixture articles for case: {case['name']}")


class DeterministicFakeMercury2:
    """A local model-shaped adapter that only reorders supplied operations."""

    calls: int = 0

    def complete_json(self, prompt: str) -> dict[str, Any]:
        self.calls += 1
        payload = json.loads(prompt)
        quote = payload["quote"]
        labor = quote["labor"]
        procedure = quote["procedure"]
        vehicle = payload.get("vehicle") or quote.get("vehicle") or {}
        vehicle_label = " ".join(
            str(vehicle.get(key, "")).strip()
            for key in ("year", "make", "model")
            if str(vehicle.get(key, "")).strip()
        )
        steps = []
        for operation in labor["operations"]:
            steps.append(
                {
                    "operation_id": operation["operation_id"],
                    "action": operation["action"],
                    "components": list(operation["components"]),
                    "category": operation["category"],
                    "source_article_ids": list(operation["source_article_ids"]),
                    "evidence_ids": list(operation["evidence_ids"]),
                    "requires_review": False,
                }
            )
        warnings = deepcopy(procedure.get("warnings", []))
        return {
            "title": f"{vehicle_label} repair procedure".strip(),
            "steps": steps,
            "warnings": warnings,
            "requires_review": bool(warnings),
            "excluded_operation_ids": [],
        }


class CountingVectorizer:
    """Count calls while delegating to the repository's deterministic fake."""

    def __init__(self) -> None:
        self.calls = 0
        self._delegate = DeterministicLocalVectorizer()

    def redraw(self, source_bytes: bytes, *, source_uri: str) -> dict[str, Any]:
        self.calls += 1
        return self._delegate.redraw(source_bytes, source_uri=source_uri)


@dataclass
class DeterministicChatAdapters:
    """Explicit source, model, normalization, pricing, and cache boundaries."""

    source_calls: int = 0
    normalizer_calls: int = 0
    composer_calls: int = 0
    price_refresh_calls: int = 0
    cache_lookups: int = 0
    normalized_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    model: DeterministicFakeMercury2 = field(default_factory=DeterministicFakeMercury2)
    vectorizer: CountingVectorizer = field(default_factory=CountingVectorizer)

    def vehicle_candidates(
        self, message: str, _principal: Mapping[str, Any]
    ) -> tuple[Mapping[str, Any], ...]:
        return (dict(_case_for_query(message)["vehicle"]),)

    def cache_lookup(
        self,
        _query: str,
        vehicle: Mapping[str, Any],
        intent: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        self.cache_lookups += 1
        key = self._cache_key(vehicle, intent)
        cached = self.normalized_cache.get(key)
        return deepcopy(cached) if cached is not None else None

    def source_retrieve(
        self,
        query: str,
        vehicle: Mapping[str, Any],
        _operations: Any,
    ) -> Mapping[str, Any]:
        self.source_calls += 1
        case = _case_for_query(query)
        articles = (
            fixture_articles()
            if case["name"] == BASE_CASE["name"]
            else fixture_articles_for_case(case)
        )
        provisional_steps = [
            {
                "sequence": index,
                "action": operation["action"],
                "source_article_ids": [article["article_id"]],
                "evidence_ids": list(operation["evidence_ids"]),
                "requires_review": True,
            }
            for index, (article, operation) in enumerate(
                (
                    (article, article["operations"][-1])
                    for article in articles
                    if article.get("operations")
                ),
                1,
            )
        ]
        return {
            "status": "source_unnormalized",
            "data_state": "source_unnormalized",
            "vehicle": dict(vehicle),
            "source_uri": case["source_uri"],
            "source_version": case["source_version"],
            "source_watermark": case["source_version"],
            "articles": articles,
            "procedure": {
                "status": "available_provisional",
                "title": "Brake line replacement (source preview)",
                "steps": provisional_steps,
                "requires_review": True,
            },
            "quote": {
                "labor": {
                    "required_hours": 1.8,
                    "recommended_hours": 0.0,
                    "total_hours": 1.8,
                    "overlap_hours_removed": 0.0,
                    "overlap_operations": [],
                },
                "parts": [],
                "parts_summary": {"items": [], "markup_applied": False},
            },
            "normalization_pending": True,
        }

    def normalize(
        self,
        _query: str,
        vehicle: Mapping[str, Any],
        source_result: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.normalizer_calls += 1
        return {
            "status": "ready",
            "data_state": "normalized",
            "vehicle": dict(vehicle),
            "source_uri": source_result["source_uri"],
            "source_version": source_result["source_version"],
            "source_watermark": source_result["source_watermark"],
            "articles": deepcopy(source_result["articles"]),
        }

    def compose(
        self,
        query: str,
        vehicle: Mapping[str, Any],
        articles: Any,
    ) -> Mapping[str, Any]:
        self.composer_calls += 1
        result = build_quote_and_procedure(
            query,
            vehicle,
            articles,
            mercury_client=self.model,
        )
        visual_artifacts: list[dict[str, Any]] = []
        if _case_for_query(query)["name"] == BASE_CASE["name"]:
            visual = vectorize_source_diagram(
                {"source_bytes": MINIMAL_PNG, "source_uri": DIAGRAM_URI},
                vectorizer=self.vectorizer,
            )
            visual.pop("derived_bytes", None)
            visual["source_article_ids"] = ["rav4-brake-line-1997"]
            visual["evidence_ids"] = ["evidence-rav4-brake-line"]
            visual_artifacts.append(visual)
        result["visual_artifacts"] = visual_artifacts
        procedure = dict(result["procedure"])
        procedure.update(
            {
                "status": "available_provisional",
                "requires_review": True,
                "visual_artifacts": deepcopy(visual_artifacts),
                "derived_article_id": result["derived_article"]["article_id"],
            }
        )
        result["procedure"] = procedure
        review_reasons = set(result.get("review_reasons", []))
        if visual_artifacts:
            review_reasons.add("visual_requires_review")
        result["review_reasons"] = sorted(review_reasons)
        result["status"] = "needs_review"
        result["data_state"] = "normalized"
        case = _case_for_query(query)
        result["source_uri"] = case["source_uri"]
        result["source_version"] = case["source_version"]
        result["source_watermark"] = case["source_version"]
        return result

    def refresh_prices(
        self,
        _query: str,
        _vehicle: Mapping[str, Any],
        answer: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.price_refresh_calls += 1
        quote = deepcopy(dict(answer["quote"]))
        refreshed_parts = []
        for raw_part in quote.get("parts", []):
            part = dict(raw_part)
            part.update(
                {
                    "priced_at": REFRESHED_PRICED_AT,
                    "freshness": "current",
                    "refresh_status": "current",
                    "source_snapshot_id": "snapshot-rav4-parts-v2",
                }
            )
            refreshed_parts.append(part)
        quote["parts"] = refreshed_parts
        parts_summary = deepcopy(dict(quote.get("parts_summary", {})))
        parts_summary["items"] = deepcopy(refreshed_parts)
        parts_summary["markup_applied"] = False
        quote["parts_summary"] = parts_summary
        return {
            "status": "current",
            "data_state": "normalized",
            "quote": quote,
            "revision_id": str(
                uuid.uuid5(uuid.NAMESPACE_URL, "autodata:chat-smoke:price-refresh:v1")
            ),
        }

    def persist(self, query: Mapping[str, Any]) -> None:
        answer = query.get("answer")
        if not isinstance(answer, Mapping):
            return
        if answer.get("data_state") != "normalized":
            return
        procedure = answer.get("procedure")
        quote = answer.get("quote")
        if not isinstance(procedure, Mapping) or not isinstance(quote, Mapping):
            return
        vehicle = answer.get("vehicle")
        if not isinstance(vehicle, Mapping):
            return
        operations = [
            {"component": str(value)}
            for value in quote.get("requested_components", [])
        ]
        key = self._cache_key(vehicle, {"requested_operations": operations})
        self.normalized_cache[key] = {
            "status": "ready",
            "cache_hit": True,
            "data_state": "normalized",
            "vehicle": deepcopy(dict(vehicle)),
            "procedure": deepcopy(dict(procedure)),
            "quote": deepcopy(dict(quote)),
            "source_watermark": answer.get("source_watermark", SOURCE_VERSION),
            "revision_id": answer.get("revision_id"),
            "derived_article": {
                "article_id": procedure.get("derived_article_id"),
                "revision_id": answer.get("revision_id"),
            },
        }

    @staticmethod
    def _cache_key(vehicle: Mapping[str, Any], intent: Mapping[str, Any]) -> str:
        components = []
        for operation in intent.get("requested_operations", []):
            if isinstance(operation, Mapping):
                components.append(
                    str(operation.get("component") or operation.get("operation_id") or "")
                    .strip()
                    .casefold()
                )
        if not components:
            components = [str(value).strip().casefold() for value in intent.get("requested_components", [])]
        identity = {
            "vehicle_id": vehicle.get("vehicle_id"),
            "year": vehicle.get("year"),
            "make": str(vehicle.get("make", "")).casefold(),
            "model": str(vehicle.get("model", "")).casefold(),
            "drivetrain": str(vehicle.get("drivetrain", "")).casefold(),
            "engine": vehicle.get("engine_displacement_l"),
            "components": sorted(set(components)),
        }
        return json.dumps(identity, sort_keys=True, separators=(",", ":"))


def _event_summary(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    message = payload.get("message") if isinstance(payload, Mapping) else ""
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "stage": event.get("stage"),
        "status": event.get("status"),
        "data_state": event.get("data_state"),
        "attempt": event.get("attempt", 0),
        "message": message,
    }


def _answer_snapshot(answer: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(dict(answer))
    snapshot["worker_stream"] = []
    return snapshot


def _update_snapshot(update: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(dict(update))
    answer = snapshot.get("answer")
    if isinstance(answer, Mapping):
        snapshot["answer"] = _answer_snapshot(answer)
    return snapshot


def _public_snapshot(query: Mapping[str, Any]) -> dict[str, Any]:
    answer = query.get("answer")
    return {
        "query_id": query.get("query_id"),
        "status": query.get("status"),
        "answer": _answer_snapshot(answer) if isinstance(answer, Mapping) else {},
        "updates": [
            _update_snapshot(update)
            for update in query.get("updates", [])
            if isinstance(update, Mapping)
        ],
        "workers": {
            "events": [
                _event_summary(event)
                for event in answer.get("worker_stream", [])
                if isinstance(event, Mapping)
            ]
            if isinstance(answer, Mapping)
            else []
        },
    }


def _call_counts(adapters: DeterministicChatAdapters) -> dict[str, int]:
    return {
        "source": adapters.source_calls,
        "normalizer": adapters.normalizer_calls,
        "model": adapters.model.calls,
        "composer": adapters.composer_calls,
        "price_refresh": adapters.price_refresh_calls,
        "vectorizer": adapters.vectorizer.calls,
    }


def _run_additional_case(
    case: Mapping[str, Any],
    *,
    adapters: DeterministicChatAdapters,
) -> dict[str, Any]:
    """Exercise one additional vehicle/component query through cold and warm paths."""

    case_name = str(case["name"])
    created = create_chat_query(
        str(case["query"]),
        idempotency_key=f"chat-smoke-{case_name}-cold-001",
        principal=PRINCIPAL,
    )
    process_chat_jobs(max_jobs=1)
    source_query = get_chat_query(created["query_id"], principal=PRINCIPAL)
    source_update = next(
        update
        for update in source_query["updates"]
        if update.get("data_state") == "source_unnormalized"
    )
    stale_answer = _answer_snapshot(source_query["answer"])
    stale_parts = stale_answer["quote"]["parts"]
    stale_part = dict(stale_parts[0])
    process_chat_price_jobs(max_jobs=1)
    refreshed_query = get_chat_query(created["query_id"], principal=PRINCIPAL)
    final_answer = refreshed_query["answer"]
    refreshed_part = dict(final_answer["quote"]["parts"][0])

    counts_before_warm = _call_counts(adapters)
    warm_query = create_chat_query(
        str(case["warm_query"]),
        idempotency_key=f"chat-smoke-{case_name}-warm-001",
        principal=PRINCIPAL,
    )
    counts_after_warm = _call_counts(adapters)
    warm_answer = warm_query["answer"]

    return {
        "name": case_name,
        "request": str(case["query"]),
        "warm_request": str(case["warm_query"]),
        "expected_vehicle_id": str(case["vehicle"]["vehicle_id"]),
        "expects_overlap": bool(case["expects_overlap"]),
        "cold": {
            "query_id": created["query_id"],
            "source_data_state": source_update["data_state"],
            "source_answer_status": source_update["answer_status"],
            "source_updates": [
                _update_snapshot(update)
                for update in source_query["updates"]
                if isinstance(update, Mapping)
            ],
            "source_workers": {
                "events": [
                    _event_summary(event)
                    for event in source_query["answer"]["worker_stream"]
                    if isinstance(event, Mapping)
                ]
            },
            "stale_price": {
                "priced_at": stale_part["priced_at"],
                "freshness": stale_part["freshness"],
                "returned_before_refresh": stale_part["freshness"] == "stale",
            },
            "answer": _answer_snapshot(final_answer),
            "revision_id": final_answer["revision_id"],
            "derived_article_id": final_answer["procedure"]["derived_article_id"],
            "priced_at": refreshed_part["priced_at"],
            "freshness": refreshed_part["freshness"],
        },
        "warm": {
            "query_id": warm_query["query_id"],
            "status": warm_query["status"],
            "revision_id": warm_answer["revision_id"],
            "derived_article_id": warm_answer["procedure"]["derived_article_id"],
            "source_calls": counts_after_warm["source"] - counts_before_warm["source"],
            "model_calls": counts_after_warm["model"] - counts_before_warm["model"],
            "cache_hit": True,
        },
    }


def run_smoke() -> dict[str, Any]:
    """Run the complete deterministic cold and warm chat lifecycle."""

    adapters = DeterministicChatAdapters()
    runtime = ChatRuntime(
        repository=InMemoryChatRepository(),
        queue=InMemoryChatQueue(),
        event_store=ProgressEventStore(),
        durable=False,
    )
    configure_chat_runtime(
        dependencies=ChatDependencies(
            vehicle_candidates=adapters.vehicle_candidates,
            normalized_cache=adapters.cache_lookup,
            source_retriever=adapters.source_retrieve,
            normalizer=adapters.normalize,
            price_refresher=adapters.refresh_prices,
            composer=adapters.compose,
            persist=adapters.persist,
        ),
        runtime=runtime,
        allow_in_memory=True,
    )

    try:
        cold_started_ns = time.perf_counter_ns()
        created = create_chat_query(
            DEFAULT_QUERY,
            idempotency_key=DEFAULT_IDEMPOTENCY_KEY,
            principal=PRINCIPAL,
        )
        initial = get_chat_query(created["query_id"], principal=PRINCIPAL)
        process_chat_jobs()
        source_query = get_chat_query(created["query_id"], principal=PRINCIPAL)
        source_update = next(
            update
            for update in source_query["updates"]
            if update.get("data_state") == "source_unnormalized"
        )
        source_snapshot = {
            "query_id": source_query["query_id"],
            "status": source_query["status"],
            "answer": _answer_snapshot(source_update["answer"]),
            "updates": [
                _update_snapshot(update)
                for update in source_query["updates"]
                if isinstance(update, Mapping)
            ],
            "workers": {
                "events": [
                    _event_summary(event)
                    for event in source_query["answer"]["worker_stream"]
                    if isinstance(event, Mapping)
                ]
            },
        }
        stale_answer = _answer_snapshot(source_query["answer"])
        stale_part = dict(stale_answer["quote"]["parts"][0])
        stale_snapshot = {
            "priced_at": stale_part["priced_at"],
            "freshness": stale_part["freshness"],
            "returned_before_refresh": stale_part["freshness"] == "stale",
        }
        process_chat_price_jobs()
        refreshed_query = get_chat_query(created["query_id"], principal=PRINCIPAL)
        cold_elapsed_ns = max(0, time.perf_counter_ns() - cold_started_ns)

        counts_before_same_replay = _call_counts(adapters)
        same_replay = create_chat_query(
            DEFAULT_QUERY,
            idempotency_key=DEFAULT_IDEMPOTENCY_KEY,
            principal=PRINCIPAL,
        )
        counts_after_same_replay = _call_counts(adapters)

        warm_started_ns = time.perf_counter_ns()
        semantic_replay = create_chat_query(
            SEMANTIC_REPLAY_QUERY,
            idempotency_key=SEMANTIC_REPLAY_IDEMPOTENCY_KEY,
            principal=PRINCIPAL,
        )
        warm_elapsed_ns = max(0, time.perf_counter_ns() - warm_started_ns)
        counts_after_warm = _call_counts(adapters)

        additional_cases = [
            _run_additional_case(case, adapters=adapters)
            for case in ADDITIONAL_CASES
        ]

        final_answer = refreshed_query["answer"]
        refreshed_part = dict(final_answer["quote"]["parts"][0])
        report: dict[str, Any] = {
            "smoke": "chat_quote_procedure",
            "status": "passed",
            "providers": {
                "source": "deterministic_fake",
                "model": "deterministic_fake_mercury_2",
                "vectorizer": "deterministic_local_vectorizer",
                "network_calls": 0,
            },
            "request": {
                "message": DEFAULT_QUERY,
                "vehicle": dict(VEHICLE),
            },
            "cold": {
                "query_id": created["query_id"],
                "initial": _public_snapshot(initial),
                "source": source_snapshot,
                "normalized": _public_snapshot(source_query),
                "stale_price": stale_snapshot,
                "refreshed": {
                    "query_id": refreshed_query["query_id"],
                    "revision_id": final_answer["revision_id"],
                    "derived_article_id": final_answer["procedure"]["derived_article_id"],
                    "answer": _answer_snapshot(final_answer),
                    "workers": {
                        "events": [
                            _event_summary(event)
                            for event in final_answer["worker_stream"]
                            if isinstance(event, Mapping)
                        ]
                    },
                    "priced_at": refreshed_part["priced_at"],
                    "freshness": refreshed_part["freshness"],
                },
                "visual": deepcopy(final_answer["procedure"]["visual_artifacts"][0]),
                "elapsed_ns": cold_elapsed_ns,
            },
            "warm": {
                "same_idempotency": {
                    "query_id": same_replay["query_id"],
                    "source_calls": counts_after_same_replay["source"] - counts_before_same_replay["source"],
                    "model_calls": counts_after_same_replay["model"] - counts_before_same_replay["model"],
                },
                "semantic_replay": {
                    "query_id": semantic_replay["query_id"],
                    "status": semantic_replay["status"],
                    "revision_id": semantic_replay["answer"]["revision_id"],
                    "derived_article_id": semantic_replay["answer"]["procedure"]["derived_article_id"],
                    "source_calls": counts_after_warm["source"] - counts_after_same_replay["source"],
                    "model_calls": counts_after_warm["model"] - counts_after_same_replay["model"],
                    "cache_hit": True,
                },
                "elapsed_ns": warm_elapsed_ns,
            },
            "additional_cases": additional_cases,
            "calls": _call_counts(adapters),
            "assertions": [
                "cold source data is visible before normalized publication",
                "normalized procedure and overlap-aware labor are published",
                "stale prices include priced_at before asynchronous refresh",
                "source-backed diagrams produce linked vector artifacts",
                "same-key and semantic warm replays make zero source/model calls",
                "additional vehicle/component queries resolve and warm-replay without source/model calls",
            ],
        }
        validate_smoke_report(report)
        return report
    finally:
        configure_chat_runtime()


def validate_smoke_report(report: Mapping[str, Any]) -> None:
    """Raise an assertion error unless the report proves the smoke contract."""

    assert report.get("status") == "passed"
    assert report.get("request", {}).get("message") == DEFAULT_QUERY
    assert report.get("providers", {}).get("network_calls") == 0

    cold = report["cold"]
    source = cold["source"]
    normalized = cold["normalized"]
    source_answer = source["answer"]
    normalized_answer = normalized["answer"]
    assert source_answer["data_state"] == "source_unnormalized"
    assert source_answer["source_unnormalized"]["articles"]
    assert source_answer["procedure"]["status"] == "available_provisional"
    assert normalized_answer["procedure"]["status"] in {"available_provisional", "ready"}
    assert normalized_answer["procedure"]["steps"]

    quote = normalized_answer["quote"]
    labor = quote["labor"]
    assert quote["parts_summary"]["markup_applied"] is False
    assert labor["required_hours"] >= 0
    assert labor["recommended_hours"] >= 0
    assert labor["overlap_hours_removed"] >= 0
    assert labor["overlap_operations"]
    assert quote["parts"]
    assert all(part.get("priced_at") for part in quote["parts"])
    assert any(update["data_state"] == "source_unnormalized" for update in source["updates"])
    assert normalized["workers"]["events"]

    stale = cold["stale_price"]
    assert stale["priced_at"] == STALE_PRICED_AT
    assert stale["returned_before_refresh"] is True
    refreshed = cold["refreshed"]
    assert refreshed["priced_at"] == REFRESHED_PRICED_AT
    assert refreshed["freshness"] == "current"
    assert refreshed["workers"]["events"]

    visual = cold["visual"]
    assert visual["renderable"] is True
    assert visual["review_state"] == "pending"
    assert visual["label"] == "AI-enhanced / UNREVIEWED"
    assert visual["source_uri"] == DIAGRAM_URI
    assert visual["source_artifact_id"] != visual["derived_artifact_id"]

    warm = report["warm"]
    assert warm["same_idempotency"]["query_id"] == cold["query_id"]
    assert warm["same_idempotency"]["source_calls"] == 0
    assert warm["same_idempotency"]["model_calls"] == 0
    assert warm["semantic_replay"]["source_calls"] == 0
    assert warm["semantic_replay"]["model_calls"] == 0
    assert warm["semantic_replay"]["revision_id"] == refreshed["revision_id"]
    assert warm["semantic_replay"]["derived_article_id"] == refreshed["derived_article_id"]

    additional_cases = report["additional_cases"]
    assert [case["name"] for case in additional_cases] == [
        "silverado_oil_water_pumps",
        "tacoma_alternator",
    ]
    for case in additional_cases:
        cold_case = case["cold"]
        answer = cold_case["answer"]
        vehicle = answer["vehicle"]
        procedure = answer["procedure"]
        quote = answer["quote"]
        assert vehicle["vehicle_id"] == case["expected_vehicle_id"]
        assert cold_case["source_data_state"] == "source_unnormalized"
        assert answer["answer_status"] == "available"
        assert procedure["status"] in {"available_provisional", "ready"}
        assert procedure["steps"]
        assert quote["parts"]
        assert quote["labor"]["total_hours"] >= 0
        assert quote["labor"]["overlap_hours_removed"] >= 0
        if case["expects_overlap"]:
            assert quote["labor"]["overlap_operations"]
        else:
            assert quote["labor"]["overlap_operations"] == []
        assert cold_case["stale_price"]["returned_before_refresh"] is True
        assert cold_case["priced_at"] == REFRESHED_PRICED_AT
        assert case["warm"]["status"] == "available"
        assert case["warm"]["revision_id"] == cold_case["revision_id"]
        assert case["warm"]["derived_article_id"] == cold_case["derived_article_id"]
        assert case["warm"]["source_calls"] == 0
        assert case["warm"]["model_calls"] == 0

    assert report["calls"] == {
        "source": 3,
        "normalizer": 3,
        "model": 3,
        "composer": 3,
        "price_refresh": 3,
        "vectorizer": 1,
    }


def main() -> int:
    report = run_smoke()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
