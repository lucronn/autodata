"""Vehicle-scoped knowledge lookup with an injectable source fallback.

The lookup side of this module consumes normalized records only.  Source
resolution and first-fetch work are explicit dependencies so callers can use a
provider-specific integration in production and a deterministic connector in
tests without changing the orchestration contract.
"""

from __future__ import annotations

import hashlib
import inspect
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
    ) -> ResolvedSource | str | Mapping[str, Any] | None:
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


KNOWLEDGE_FALLBACK_EVENT_TYPE = "dataset.knowledge.fallback.requested"
KNOWLEDGE_FALLBACK_EVENT_VERSION = 1


class KnowledgeFallbackRequestError(ValueError):
    """A knowledge-fallback event cannot be safely processed."""


class PermanentKnowledgeFallbackError(KnowledgeFallbackRequestError):
    """A knowledge-fallback failure must not be retried."""


class RetryableKnowledgeFallbackError(RuntimeError):
    """A temporary dependency failure may be retried."""


@dataclass(frozen=True)
class KnowledgeFallbackRequest:
    """Validated version-one request received from the API event boundary."""

    event_id: str
    request_id: str
    projection_id: str
    correlation_id: str
    idempotency_key: str
    dataset_id: str
    revision_id: str
    vehicle_key: str
    region: str
    query: str
    keywords: tuple[str, ...]
    kind: str
    source_hint: Any | None = None

    @classmethod
    def from_envelope(cls, envelope: Mapping[str, Any]) -> KnowledgeFallbackRequest:
        if not isinstance(envelope, Mapping):
            raise PermanentKnowledgeFallbackError("knowledge fallback envelope must be an object")
        if envelope.get("event_type") != KNOWLEDGE_FALLBACK_EVENT_TYPE:
            raise PermanentKnowledgeFallbackError(
                f"knowledge fallback event type must be {KNOWLEDGE_FALLBACK_EVENT_TYPE}"
            )
        if envelope.get("event_version") != KNOWLEDGE_FALLBACK_EVENT_VERSION:
            raise PermanentKnowledgeFallbackError("knowledge fallback event version must be 1")
        for field in (
            "event_id",
            "occurred_at",
            "producer",
            "request_id",
            "projection_id",
            "correlation_id",
            "idempotency_key",
        ):
            if not str(envelope.get(field, "")).strip():
                raise PermanentKnowledgeFallbackError(
                    f"knowledge fallback event is missing {field}"
                )
        payload = envelope.get("payload")
        if not isinstance(payload, Mapping):
            raise PermanentKnowledgeFallbackError("knowledge fallback payload must be an object")
        required = (
            "vehicle_key",
            "region",
            "query",
            "keywords",
            "kind",
            "dataset_id",
            "revision_id",
        )
        for field in required:
            if field not in payload:
                raise PermanentKnowledgeFallbackError(
                    f"knowledge fallback payload is missing {field}"
                )

        vehicle_key = _required_fallback_text(payload, "vehicle_key")
        region = _required_fallback_text(payload, "region").upper()
        target = _target_from_vehicle_key(vehicle_key, region)
        query = _normalize_query(_required_fallback_text(payload, "query"))
        keywords = _normalize_keywords(_fallback_keywords(payload["keywords"]))
        if not _query_tokens(query, keywords):
            raise PermanentKnowledgeFallbackError(
                "knowledge fallback query requires query text or keywords"
            )
        kind = str(payload["kind"]).strip().casefold()
        if kind not in {"article", "procedure", "all"}:
            raise PermanentKnowledgeFallbackError(
                "knowledge fallback kind must be article, procedure, or all"
            )
        dataset_id = _required_fallback_text(payload, "dataset_id")
        revision_id = _required_fallback_text(payload, "revision_id")
        envelope_revision = envelope.get("revision_id")
        if envelope_revision is not None and str(envelope_revision).strip() != revision_id:
            raise PermanentKnowledgeFallbackError(
                "knowledge fallback payload revision_id does not match the event envelope"
            )
        source_hint = payload.get("source_hint")
        if source_hint is not None and not isinstance(source_hint, (str, Mapping)):
            raise PermanentKnowledgeFallbackError(
                "knowledge fallback source_hint must be a string or object"
            )
        return cls(
            event_id=str(envelope["event_id"]).strip(),
            request_id=str(envelope["request_id"]).strip(),
            projection_id=str(envelope["projection_id"]).strip(),
            correlation_id=str(envelope["correlation_id"]).strip(),
            idempotency_key=str(envelope["idempotency_key"]).strip(),
            dataset_id=dataset_id,
            revision_id=revision_id,
            vehicle_key=target.vehicle_key,
            region=target.region,
            query=query,
            keywords=keywords,
            kind=kind,
            source_hint=deepcopy(source_hint),
        )

    @property
    def target(self) -> VehicleTarget:
        return _target_from_vehicle_key(self.vehicle_key, self.region)

    def fingerprint(self) -> str:
        value = json.dumps(
            {
                "dataset_id": self.dataset_id,
                "revision_id": self.revision_id,
                "vehicle_key": self.vehicle_key,
                "region": self.region,
                "query": self.query,
                "keywords": self.keywords,
                "kind": self.kind,
                "source_hint": self.source_hint,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _StoredKnowledgeFallback:
    fingerprint: str
    payload: dict[str, Any]


class KnowledgeFallbackFulfillmentHandler:
    """Fulfill API fallback events while keeping source work off the read path."""

    def __init__(
        self,
        *,
        catalog: Iterable[Mapping[str, Any]] | Mapping[str, Any] = (),
        source_resolver: SourceResolver | Callable[..., Any],
        intake: Callable[..., VehicleArticleIntake] | None = None,
        persistence: Callable[..., Any] | None = None,
        result_store: Any | None = None,
    ) -> None:
        self.catalog = catalog
        self.source_resolver = source_resolver
        self.intake = intake
        self.persistence = persistence
        self._results: dict[str, _StoredKnowledgeFallback] = {}
        self.result_store = result_store if result_store is not None else self._results

    def handle(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        request = KnowledgeFallbackRequest.from_envelope(envelope)
        fingerprint = request.fingerprint()
        stored = self._get_stored(request.idempotency_key)
        if stored is not None:
            if stored.fingerprint != fingerprint:
                raise PermanentKnowledgeFallbackError(
                    "idempotency key was previously used for a different request"
                )
            return deepcopy(stored.payload)

        captured: list[VehicleArticleIntake] = []

        def intake_and_capture(source_uri: str, target: VehicleTarget, **options: Any) -> VehicleArticleIntake:
            ingest = self.intake or ingest_vehicle_article
            result = ingest(source_uri, target, **options)
            captured.append(result)
            return result

        try:
            result = query_vehicle_knowledge(
                request.target,
                request.query,
                catalog=self.catalog,
                source_resolver=self.source_resolver,
                keywords=request.keywords,
                kind=request.kind,
                ingest=intake_and_capture,
                source_hint=request.source_hint,
            )
            persistence_result = None
            if result.status == "fetched" and captured and self.persistence is not None:
                persistence_result = self.persistence(
                    captured[0].bundle,
                    captured[0].artifacts,
                    adapter_name="knowledge-fallback",
                )
        except Exception as error:
            raise classify_knowledge_fallback_error(error) from error

        result_payload = result.to_dict()
        publication = {
            "event_type": "dataset.knowledge.fallback.fulfilled",
            "event_version": KNOWLEDGE_FALLBACK_EVENT_VERSION,
            "event_id": "knowledge-publication:" + request.idempotency_key,
            "request_id": request.request_id,
            "projection_id": request.projection_id,
            "revision_id": request.revision_id,
            "correlation_id": request.correlation_id,
            "idempotency_key": request.idempotency_key,
            "dataset_id": request.dataset_id,
            "vehicle_key": request.vehicle_key,
            "query": request.query,
            "keywords": list(request.keywords),
            "kind": request.kind,
            "status": result.status,
            "results": deepcopy(result_payload["results"]),
            "evidence": deepcopy(result_payload["evidence"]),
            "source_uri": result.source_uri,
        }
        payload = {
            "status": "completed",
            "request_id": request.request_id,
            "idempotency_key": request.idempotency_key,
            "dataset_id": request.dataset_id,
            "revision_id": request.revision_id,
            "result": result_payload,
            "publication": publication,
        }
        if persistence_result is not None:
            payload["persistence"] = deepcopy(persistence_result)
        self._put_stored(request.idempotency_key, _StoredKnowledgeFallback(fingerprint, payload))
        return deepcopy(payload)

    def _get_stored(self, key: str) -> _StoredKnowledgeFallback | None:
        if isinstance(self.result_store, dict):
            return self.result_store.get(key)
        value = self.result_store.get(key)
        return value

    def _put_stored(self, key: str, value: _StoredKnowledgeFallback) -> None:
        if isinstance(self.result_store, dict):
            self.result_store[key] = value
        else:
            self.result_store.put(key, value)


def classify_knowledge_fallback_error(error: Exception) -> Exception:
    """Map dependency failures to the explicit retry/permanent contract."""

    if isinstance(error, (PermanentKnowledgeFallbackError, RetryableKnowledgeFallbackError)):
        return error
    if isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return RetryableKnowledgeFallbackError(str(error) or type(error).__name__)
    return PermanentKnowledgeFallbackError(str(error) or type(error).__name__)


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
    source_hint: Any | None = None,
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

    resolved = _coerce_resolved_source(
        _call_resolver(
            source_resolver,
            target,
            normalized_query,
            normalized_keywords,
            source_hint,
        )
    )
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
        require_match=True,
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
    source_hint: Any | None = None,
) -> Any:
    resolve = getattr(resolver, "resolve", None)
    if callable(resolve):
        return _invoke_resolver(resolve, target, query, keywords, source_hint)
    if not callable(resolver):
        raise TypeError("source resolver must be callable or expose resolve()")
    return _invoke_resolver(resolver, target, query, keywords, source_hint)


def _invoke_resolver(
    resolver: Callable[..., Any],
    target: VehicleTarget,
    query: str,
    keywords: tuple[str, ...],
    source_hint: Any | None,
) -> Any:
    arguments = (target, query, keywords)
    if source_hint is not None:
        try:
            inspect.signature(resolver).bind(*arguments, source_hint)
        except (TypeError, ValueError):
            pass
        else:
            return resolver(*arguments, source_hint)
    return resolver(*arguments)


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


def _required_fallback_text(payload: Mapping[str, Any], field: str) -> str:
    value = str(payload.get(field, "")).strip()
    if not value:
        raise PermanentKnowledgeFallbackError(
            f"knowledge fallback payload requires {field}"
        )
    return value


def _fallback_keywords(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise PermanentKnowledgeFallbackError(
            "knowledge fallback keywords must be an array of strings"
        )
    values = tuple(value)
    if any(not isinstance(item, str) for item in values):
        raise PermanentKnowledgeFallbackError(
            "knowledge fallback keywords must be an array of strings"
        )
    return values


def _target_from_vehicle_key(vehicle_key: str, region: str) -> VehicleTarget:
    parts = vehicle_key.casefold().split("-")
    if len(parts) < 4 or not parts[-2].isdigit():
        raise PermanentKnowledgeFallbackError(
            "knowledge fallback vehicle_key must be make-model-year-region"
        )
    if parts[-1] != region.casefold():
        raise PermanentKnowledgeFallbackError(
            "knowledge fallback vehicle_key region does not match payload region"
        )
    try:
        target = VehicleTarget(
            parts[0],
            "-".join(parts[1:-2]),
            int(parts[-2]),
            region,
        )
    except ValueError as error:
        raise PermanentKnowledgeFallbackError(str(error)) from error
    if target.vehicle_key.casefold() != vehicle_key.casefold():
        raise PermanentKnowledgeFallbackError(
            "knowledge fallback vehicle_key is not a canonical vehicle identity"
        )
    return target
