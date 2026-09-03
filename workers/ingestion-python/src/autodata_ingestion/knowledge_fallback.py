"""Vehicle-scoped knowledge lookup with an injectable source fallback.

The lookup side of this module consumes normalized records only.  Source
resolution and first-fetch work are explicit dependencies so callers can use a
provider-specific integration in production and a deterministic connector in
tests without changing the orchestration contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .article_intake import VehicleArticleIntake, VehicleTarget, ingest_vehicle_article


class SourceResolver(Protocol):
    """Resolve one source for a vehicle-scoped query."""

    def __call__(
        self, target: VehicleTarget, query: str, keywords: tuple[str, ...]
    ) -> "ResolvedSource | str | Mapping[str, Any] | None":
        ...


@dataclass(frozen=True)
class ResolvedSource:
    """A source URL and optional connector selected by an injected resolver."""

    source_uri: str
    connector: Any | None = None
    source_version: str | None = None

    def __post_init__(self) -> None:
        source_uri = str(self.source_uri).strip()
        if not source_uri:
            raise ValueError("resolved source requires a source URI")
        source_version = (
            str(self.source_version).strip() if self.source_version is not None else None
        )
        object.__setattr__(self, "source_uri", source_uri)
        object.__setattr__(self, "source_version", source_version or None)


@dataclass(frozen=True)
class KnowledgeFallbackResult:
    """Stable, evidence-backed output of a cache lookup or source fetch."""

    status: str
    idempotency_key: str
    vehicle: dict[str, Any]
    query: str
    keywords: tuple[str, ...]
    results: tuple[dict[str, Any], ...]
    evidence: tuple[dict[str, Any], ...]
    source_uri: str | None = None
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-ready data without exposing mutable internal state."""

        return deepcopy(asdict(self))


def derive_idempotency_key(
    target: VehicleTarget, query: str, keywords: Iterable[str] = ()
) -> str:
    """Derive a request identity from canonical vehicle/query inputs only."""

    normalized_query = _normalize_query(query)
    normalized_keywords = _normalize_keywords(keywords)
    payload = json.dumps(
        {
            "vehicle_key": target.vehicle_key,
            "query": normalized_query,
            "keywords": normalized_keywords,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "knowledge-fallback:" + hashlib.sha256(payload).hexdigest()


def query_vehicle_knowledge(
    target: VehicleTarget,
    query: str,
    *,
    catalog: Iterable[Mapping[str, Any]] | Mapping[str, Any],
    source_resolver: SourceResolver | Callable[..., Any],
    keywords: Iterable[str] = (),
    kind: str = "all",
    ingest: Callable[..., VehicleArticleIntake] | None = None,
) -> KnowledgeFallbackResult:
    """Search normalized vehicle records and fetch exactly one fallback source.

    ``catalog`` may be an iterable of normalized result records, or a mapping
    containing ``results``/``articles``/``procedures``.  A cache record must
    carry a matching ``vehicle_key`` or explicit vehicle identity; records
    without vehicle scope are ignored.  ``source_resolver`` receives the
    normalized target, query, and sorted unique keywords.  The optional
    ``ingest`` dependency defaults to :func:`ingest_vehicle_article` and is
    intentionally injectable for deterministic replay tests.
    """

    normalized_query = _normalize_query(query)
    normalized_keywords = _normalize_keywords(keywords)
    query_tokens = _query_tokens(normalized_query, normalized_keywords)
    if not query_tokens:
        raise ValueError("knowledge query requires query text or keywords")
    normalized_kind = str(kind).strip().casefold()
    if normalized_kind not in {"article", "procedure", "all"}:
        raise ValueError("knowledge kind must be article, procedure, or all")

    idempotency_key = derive_idempotency_key(target, normalized_query, normalized_keywords)
    catalog_records = _catalog_records(catalog)
    cache_results = _rank_records(
        catalog_records,
        target,
        query_tokens,
        normalized_kind,
        require_match=True,
    )
    if cache_results:
        evidence = _unique_evidence(
            evidence
            for result in cache_results
            for evidence in result["evidence"]
        )
        return KnowledgeFallbackResult(
            status="cache_hit",
            idempotency_key=idempotency_key,
            vehicle=target.as_dict(),
            query=normalized_query,
            keywords=normalized_keywords,
            results=tuple(cache_results),
            evidence=evidence,
        )

    resolved = _coerce_resolved_source(_call_resolver(source_resolver, target, normalized_query, normalized_keywords))
    if resolved is None:
        raise LookupError("source resolver returned no source for the knowledge query")

    ingest_fn = ingest or ingest_vehicle_article
    intake = _run_intake(ingest_fn, resolved, target)
    intake_evidence = _unique_evidence(getattr(intake.bundle, "evidence", ()))
    if intake.status != "ready":
        return KnowledgeFallbackResult(
            status="rejected",
            idempotency_key=idempotency_key,
            vehicle=target.as_dict(),
            query=normalized_query,
            keywords=normalized_keywords,
            results=(),
            evidence=intake_evidence,
            source_uri=resolved.source_uri,
            rejection_reason=intake.rejection_reason or "article_not_ready",
        )

    if not _matches_target(getattr(intake.bundle, "vehicle", None), target):
        return KnowledgeFallbackResult(
            status="rejected",
            idempotency_key=idempotency_key,
            vehicle=target.as_dict(),
            query=normalized_query,
            keywords=normalized_keywords,
            results=(),
            evidence=intake_evidence,
            source_uri=resolved.source_uri,
            rejection_reason="vehicle_identity_mismatch",
        )

    fetched_records = _fetched_records(intake)
    fetched_results = _rank_records(
        fetched_records,
        target,
        query_tokens,
        normalized_kind,
        require_match=False,
    )
    return KnowledgeFallbackResult(
        status="fetched",
        idempotency_key=idempotency_key,
        vehicle=target.as_dict(),
        query=normalized_query,
        keywords=normalized_keywords,
        results=tuple(fetched_results),
        evidence=intake_evidence,
        source_uri=resolved.source_uri,
    )


def _run_intake(
    ingest: Callable[..., VehicleArticleIntake],
    source: ResolvedSource,
    target: VehicleTarget,
) -> VehicleArticleIntake:
    options: dict[str, Any] = {}
    if source.connector is not None:
        options["connector"] = source.connector
    if source.source_version is not None:
        options["source_version"] = source.source_version
    return ingest(source.source_uri, target, **options)


def _call_resolver(
    resolver: SourceResolver | Callable[..., Any],
    target: VehicleTarget,
    query: str,
    keywords: tuple[str, ...],
) -> Any:
    resolve = getattr(resolver, "resolve", None)
    if callable(resolve):
        return resolve(target, query, keywords)
    if not callable(resolver):
        raise TypeError("source resolver must be callable or expose resolve()")
    return resolver(target, query, keywords)


def _coerce_resolved_source(value: Any) -> ResolvedSource | None:
    if value is None:
        return None
    if isinstance(value, ResolvedSource):
        return value
    if isinstance(value, str):
        return ResolvedSource(value)
    if isinstance(value, Mapping):
        source_uri = value.get("source_uri", value.get("url"))
        if source_uri is None:
            raise ValueError("resolved source mapping requires source_uri or url")
        return ResolvedSource(
            source_uri,
            value.get("connector"),
            value.get("source_version"),
        )
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        if len(value) != 2:
            raise ValueError("resolved source sequence must contain URL and connector")
        return ResolvedSource(value[0], value[1])
    raise TypeError("source resolver returned an unsupported source descriptor")


def _catalog_records(catalog: Iterable[Mapping[str, Any]] | Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if isinstance(catalog, Mapping):
        shared_vehicle = {
            key: catalog[key]
            for key in ("vehicle_key", "vehicle", "vehicle_identity")
            if key in catalog
        }
        shared_evidence = catalog.get("evidence", ())
        if isinstance(catalog.get("results"), Iterable) and not isinstance(catalog["results"], (str, bytes, Mapping)):
            entries = catalog["results"]
        else:
            entries = []
            for key in ("articles", "procedures"):
                values = catalog.get(key, ())
                if isinstance(values, Iterable) and not isinstance(values, (str, bytes, Mapping)):
                    entries.extend({**shared_vehicle, "kind": key[:-1], "evidence": shared_evidence, **entry} for entry in values if isinstance(entry, Mapping))
        if not entries:
            entries = [catalog]
        return [entry for entry in entries if isinstance(entry, Mapping)]
    return [entry for entry in catalog if isinstance(entry, Mapping)]


def _rank_records(
    records: Iterable[Mapping[str, Any]],
    target: VehicleTarget,
    query_tokens: tuple[str, ...],
    kind: str,
    *,
    require_match: bool,
) -> list[dict[str, Any]]:
    ranked: list[tuple[float, str, str, dict[str, Any]]] = []
    for raw_record in records:
        record = _record_parts(raw_record)
        if record is None or (
            kind != "all" and record["kind"] != kind
        ):
            continue
        if not _record_matches_target(raw_record, target):
            continue
        score = _score(record["kind"], record["payload"], query_tokens)
        if require_match and score == 0:
            continue
        result = _result_record(record, score, raw_record)
        ranked.append((score, record["id"], record["kind"], result))
    ranked.sort(key=lambda item: (-item[0], item[2], item[1]))
    return [item[3] for item in ranked]


def _record_parts(record: Mapping[str, Any]) -> dict[str, Any] | None:
    raw_kind = str(record.get("kind", "")).strip().casefold()
    if raw_kind in {"article", "procedure"}:
        payload = record.get(raw_kind, record)
        if not isinstance(payload, Mapping):
            return None
        kind = raw_kind
    elif record.get("article_id") or record.get("articleId"):
        payload = record
        kind = "article"
    elif record.get("procedure_id") or record.get("procedureId"):
        payload = record
        kind = "procedure"
    else:
        return None
    id_keys = ("article_id", "articleId", "id") if kind == "article" else ("procedure_id", "procedureId", "id")
    identifier = next((str(payload[key]).strip() for key in id_keys if str(payload.get(key, "")).strip()), "")
    if not identifier:
        return None
    return {"kind": kind, "id": identifier, "payload": payload}


def _result_record(
    record: Mapping[str, Any], score: float, raw_record: Mapping[str, Any]
) -> dict[str, Any]:
    payload = deepcopy(dict(record["payload"]))
    if record["kind"] == "article":
        payload.setdefault("article_id", record["id"])
        result = {
            "kind": "article",
            "id": record["id"],
            "score": round(score, 6),
            "article": payload,
        }
    else:
        payload.setdefault("procedure_id", record["id"])
        payload.setdefault("section", "procedures")
        payload.setdefault("excerpt", payload.get("text", payload.get("content", "")))
        result = {
            "kind": "procedure",
            "id": record["id"],
            "score": round(score, 6),
            "procedure": payload,
        }
    result["evidence"] = deepcopy(list(_record_evidence(raw_record)))
    return result


def _fetched_records(intake: VehicleArticleIntake) -> list[dict[str, Any]]:
    evidence_by_id = {
        str(item["evidence_id"]): item
        for item in intake.bundle.evidence
        if isinstance(item, Mapping) and item.get("evidence_id")
    }
    records: list[dict[str, Any]] = []
    for article in intake.bundle.articles:
        if not isinstance(article, Mapping):
            continue
        identifiers = article.get("evidence_ids", ())
        if not identifiers and article.get("evidence_id"):
            identifiers = (article["evidence_id"],)
        records.append(
            {
                "kind": "article",
                "vehicle_key": intake.target.vehicle_key,
                "article": dict(article),
                "evidence": [evidence_by_id[str(identifier)] for identifier in identifiers if str(identifier) in evidence_by_id],
            }
        )
    return records


def _record_evidence(record: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    evidence = record.get("evidence", ())
    if isinstance(evidence, Mapping):
        return (evidence,)
    if isinstance(evidence, Iterable) and not isinstance(evidence, (str, bytes)):
        return (item for item in evidence if isinstance(item, Mapping))
    return ()


def _unique_evidence(evidence: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    unique: dict[str, dict[str, Any]] = {}
    for item in evidence:
        if not isinstance(item, Mapping):
            continue
        identifier = str(item.get("evidence_id", ""))
        if identifier:
            unique.setdefault(identifier, deepcopy(dict(item)))
    return tuple(unique[key] for key in sorted(unique))


def _record_matches_target(record: Mapping[str, Any], target: VehicleTarget) -> bool:
    vehicle_key = record.get("vehicle_key")
    if vehicle_key is None:
        vehicle = record.get("vehicle_identity", record.get("vehicle"))
        if isinstance(vehicle, Mapping):
            vehicle_key = vehicle.get("vehicle_key")
            if vehicle_key is None:
                return _matches_target(vehicle, target)
    return str(vehicle_key).casefold() == target.vehicle_key.casefold() if vehicle_key else False


def _matches_target(vehicle: Any, target: VehicleTarget) -> bool:
    if not isinstance(vehicle, Mapping):
        return False
    if vehicle.get("vehicle_key"):
        return str(vehicle["vehicle_key"]).casefold() == target.vehicle_key.casefold()
    try:
        return (
            str(vehicle.get("make", "")).strip().casefold() == target.make.casefold()
            and str(vehicle.get("model", "")).strip().casefold() == target.model.casefold()
            and int(vehicle.get("model_year", vehicle.get("year"))) == target.model_year
            and str(vehicle.get("region", "")).strip().upper() == target.region
            and (
                not target.trim
                or str(vehicle.get("trim", "")).strip().casefold() == target.trim.casefold()
            )
        )
    except (TypeError, ValueError):
        return False


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query).strip()).strip()


def _normalize_keywords(keywords: Iterable[str]) -> tuple[str, ...]:
    if isinstance(keywords, str):
        keywords = (keywords,)
    normalized = {re.sub(r"\s+", " ", str(keyword).strip()).casefold() for keyword in keywords}
    return tuple(sorted(keyword for keyword in normalized if keyword))


def _query_tokens(query: str, keywords: Iterable[str]) -> tuple[str, ...]:
    values = " ".join((query, *keywords)).casefold()
    return tuple(sorted(set(re.findall(r"[a-z0-9]+", values))))


def _score(kind: str, payload: Mapping[str, Any], query_tokens: Sequence[str]) -> float:
    if kind == "article":
        fields = (
            payload.get("article_id", payload.get("articleId", payload.get("id", ""))),
            payload.get("article_key", ""),
            payload.get("bucket", ""),
            payload.get("title", ""),
            payload.get("bulletin_number", payload.get("bulletinNumber", "")),
            payload.get("release_date", payload.get("releaseDate", "")),
            payload.get("body", payload.get("articleBody", payload.get("content", ""))),
            payload.get("steps", ""),
        )
    else:
        fields = (
            payload.get("section", ""),
            payload.get("excerpt", payload.get("text", payload.get("content", ""))),
            payload.get("matched_terms", ""),
        )
    searchable = set(re.findall(r"[a-z0-9]+", " ".join(_text(value) for value in fields).casefold()))
    return sum(token in searchable for token in query_tokens) / len(query_tokens)


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {value[key]}" for key in sorted(value))
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value)
    return str(value or "")
