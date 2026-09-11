"""Production composition for vehicle-scoped knowledge fallback fulfillment."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import uuid
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from .article_intake import VehicleTarget
from .autoapi_connector import AutoAPIConnector, fetch_required_source_resources
from .http_connector import HttpSourceConnector
from .knowledge_fallback import (
    KnowledgeFallbackFulfillmentHandler,
    KnowledgeFallbackRequest,
    PermanentKnowledgeFallbackError,
    ResolvedSource,
)
from .pricing import read_cached_price_or_queue_refresh


def fulfill_once(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve, normalize, persist, and publish one fallback request."""

    request = KnowledgeFallbackRequest.from_envelope(envelope)
    catalog = load_revision_catalog(request.projection_id)

    def persist(bundle: Any, artifacts: Any, *, adapter_name: str) -> dict[str, Any]:
        from .bundle_persistence import persist_source_bundle

        return persist_source_bundle(bundle, artifacts, adapter_name=adapter_name)

    source_resolver = ConfiguredKnowledgeSourceResolver(
        source_persister=persist_source_payloads
    )
    handler = KnowledgeFallbackFulfillmentHandler(
        catalog=catalog,
        source_resolver=source_resolver,
        persistence=persist,
    )
    try:
        result = handler.handle(dict(envelope))
    except PermanentKnowledgeFallbackError as error:
        if source_resolver.last_source_references:
            result = _source_unnormalized_failure(request, source_resolver, error)
        else:
            raise
    result = _expose_provisional_source_result(
        result, source_resolver.last_source_references
    )
    result = _refresh_result_prices(result)
    if result["result"]["status"] == "fetched":
        result["publication"] = publish_fallback_revision(request, result)
    return result


class ConfiguredKnowledgeSourceResolver:
    """Resolve a URL from an explicit hint or a configured URL template."""

    def __init__(self, *, source_persister: Any | None = None) -> None:
        self.source_persister = source_persister
        self.last_source_references: tuple[dict[str, Any], ...] = ()
        self.last_source_persistence: dict[str, Any] | None = None
        self.last_autoapi_result: dict[str, Any] | None = None

    def __call__(
        self,
        target: VehicleTarget,
        query: str,
        keywords: tuple[str, ...],
        source_hint: Any | None = None,
    ) -> ResolvedSource:
        if _is_autoapi_request(source_hint):
            return self._resolve_autoapi(target, query, keywords, source_hint)
        source_uri, source_version = _source_configuration(
            target, query, keywords, source_hint
        )
        connector: Any = HttpSourceConnector(
            source_uri,
            source_version,
            timeout_seconds=float(os.getenv("AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS", "30")),
            max_bytes=int(os.getenv("AUTODATA_SOURCE_MAX_BYTES", str(50 * 1024 * 1024))),
            request_headers=_source_headers(),
        )
        if self.source_persister is not None:
            connector = _PersistingSourceConnector(
                connector,
                self.source_persister,
                on_persisted=self._record_persistence,
            )
        return ResolvedSource(
            source_uri,
            source_version=source_version,
            connector=connector,
        )

    def _resolve_autoapi(
        self,
        target: VehicleTarget,
        query: str,
        keywords: tuple[str, ...],
        source_hint: Any | None,
    ) -> ResolvedSource:
        hint = source_hint if isinstance(source_hint, Mapping) else {}
        base_url = (
            hint.get("base_url")
            or hint.get("autoapi_base_url")
            or os.getenv("AUTODATA_AUTOAPI_BASE_URL", "")
        )
        if not str(base_url).strip():
            raise LookupError("AutoAPI source configuration requires a base URL")
        content_source = str(
            hint.get("content_source")
            or os.getenv("AUTODATA_AUTOAPI_CONTENT_SOURCE", "GeneralMotors")
        ).strip()
        source_version = str(
            hint.get("source_version")
            or os.getenv("AUTODATA_AUTOAPI_SOURCE_VERSION", "autoapi-http-v1")
        ).strip()
        vehicle_id = str(
            hint.get("vehicle_id")
            or hint.get("autoapi_vehicle_id")
            or target.vehicle_key
        ).strip()
        operations = hint.get("operations")
        if not isinstance(operations, (list, tuple)):
            operations = [
                {
                    "article_title": query,
                    "keywords": list(keywords),
                    "requires_parts": bool(hint.get("requires_parts")),
                }
            ]
        connector = AutoAPIConnector(
            str(base_url),
            content_source=content_source,
            source_version=source_version,
            timeout_seconds=float(
                os.getenv("AUTODATA_AUTOAPI_TIMEOUT_SECONDS", "30")
            ),
            max_bytes=int(
                os.getenv("AUTODATA_AUTOAPI_MAX_BYTES", str(50 * 1024 * 1024))
            ),
        )
        source_connector = _AutoAPIKnowledgeSourceConnector(
            connector,
            vehicle_id=vehicle_id,
            vehicle=target.as_dict(),
            operations=tuple(
                dict(operation)
                for operation in operations
                if isinstance(operation, Mapping)
            )
            or ({"article_title": query},),
            source_persister=self.source_persister,
            on_persisted=self._record_persistence,
            on_result=self._record_autoapi_result,
        )
        return ResolvedSource(
            str(base_url).strip().rstrip("/"),
            source_version=source_version,
            connector=source_connector,
        )

    def _record_persistence(
        self, result: Any, resources: tuple[Any, ...]
    ) -> None:
        self.last_source_persistence = (
            deepcopy(dict(result)) if isinstance(result, Mapping) else None
        )
        references = (
            result.get("source_references")
            if isinstance(result, Mapping)
            else None
        )
        self.last_source_references = tuple(
            _safe_source_references(references or resources)
        )

    def _record_autoapi_result(self, result: dict[str, Any]) -> None:
        self.last_autoapi_result = deepcopy(result)
        if not self.last_source_references:
            self.last_source_references = tuple(
                _safe_source_references(result.get("source_references", ()))
            )


def _is_autoapi_request(source_hint: Any | None) -> bool:
    if isinstance(source_hint, Mapping):
        provider = str(
            source_hint.get("provider")
            or source_hint.get("source_provider")
            or ""
        ).strip().casefold()
        return provider == "autoapi" or source_hint.get("autoapi") is True
    return (
        os.getenv("AUTODATA_KNOWLEDGE_SOURCE_PROVIDER", "").strip().casefold()
        == "autoapi"
        and bool(os.getenv("AUTODATA_AUTOAPI_BASE_URL", "").strip())
    ) or bool(os.getenv("AUTODATA_AUTOAPI_BASE_URL", "").strip())


def _safe_source_references(references: Any) -> list[dict[str, Any]]:
    if isinstance(references, Mapping):
        references = references.get("source_references", ())
    if not isinstance(references, (list, tuple)):
        references = (references,) if references else ()
    safe: list[dict[str, Any]] = []
    for reference in references:
        if isinstance(reference, Mapping):
            values = reference
        else:
            values = {
                "source_uri": getattr(reference, "source_uri", None),
                "source_version": getattr(reference, "source_version", None),
                "content_sha256": getattr(reference, "content_sha256", None),
                "source_snapshot_id": getattr(reference, "source_snapshot_id", None),
                "source_artifact_id": getattr(reference, "source_artifact_id", None),
                "object_key": getattr(reference, "object_key", None),
            }
        item = {
            key: str(values[key])
            for key in (
                "source_uri",
                "source_version",
                "content_sha256",
                "source_snapshot_id",
                "source_artifact_id",
                "object_key",
            )
            if values.get(key) is not None and str(values[key]).strip()
        }
        if item.get("source_uri") or item.get("content_sha256"):
            safe.append(item)
    return safe


class _PersistingSourceConnector:
    """Persist immutable source bytes before the intake normalizer sees them."""

    def __init__(
        self,
        delegate: Any,
        persister: Any,
        *,
        on_persisted: Any | None = None,
    ) -> None:
        self._delegate = delegate
        self._persister = persister
        self._on_persisted = on_persisted
        self.name = str(getattr(delegate, "name", "source"))

    def fetch(self, request: dict[str, Any]) -> list[Any]:
        resources = list(self._delegate.fetch(request))
        result = _invoke_source_persister(
            self._persister, tuple(resources), adapter_name=self.name
        )
        if callable(self._on_persisted):
            self._on_persisted(result, tuple(resources))
        return resources


class _AutoAPIKnowledgeSourceConnector:
    """Adapt the multi-resource AutoAPI read-through result to article intake."""

    name = "autoapi"

    def __init__(
        self,
        connector: AutoAPIConnector,
        *,
        vehicle_id: str,
        vehicle: Mapping[str, Any],
        operations: tuple[Mapping[str, Any], ...],
        source_persister: Any | None,
        on_persisted: Any | None,
        on_result: Any | None,
    ) -> None:
        self._connector = connector
        self._vehicle_id = vehicle_id
        self._vehicle = dict(vehicle)
        self._operations = operations
        self._source_persister = source_persister
        self._on_persisted = on_persisted
        self._on_result = on_result
        self.last_result: dict[str, Any] | None = None
        self.last_price_persistence: dict[str, Any] | None = None

    def fetch(self, _request: dict[str, Any]) -> list[Any]:
        result = fetch_required_source_resources(
            {**self._vehicle, "vehicle_id": self._vehicle_id},
            self._operations,
            self._connector,
        )
        self.last_result = result
        if callable(self._on_result):
            self._on_result(result)
        resources = tuple(result.get("source_resources", ()))
        if self._source_persister is not None:
            persistence = _invoke_source_persister(
                self._source_persister, resources, adapter_name=self.name
            )
            if callable(self._on_persisted):
                self._on_persisted(persistence, resources)
            if result.get("parts"):
                self.last_price_persistence = persist_price_snapshots(result["parts"])
        selected = next(
            (
                resource
                for resource in resources
                if "/article/" in resource.source_uri.casefold()
                and "/labor/" not in resource.source_uri.casefold()
            ),
            None,
        )
        if selected is None and resources:
            selected = resources[0]
        if selected is None:
            raise LookupError("AutoAPI returned no source resources")
        return [selected]


def _invoke_source_persister(
    persister: Any, resources: tuple[Any, ...], *, adapter_name: str
) -> Any:
    try:
        inspect.signature(persister).bind(resources, adapter_name=adapter_name)
    except (TypeError, ValueError):
        return persister(resources)
    return persister(resources, adapter_name=adapter_name)


def _expose_provisional_source_result(
    result: dict[str, Any],
    source_references: Any = (),
) -> dict[str, Any]:
    """Map an intake rejection to a useful, explicitly unnormalized result."""

    if not isinstance(result, dict) or not isinstance(result.get("result"), Mapping):
        return result
    payload = dict(result["result"])
    if payload.get("status") != "rejected":
        return result
    reason = str(payload.get("rejection_reason") or "").strip()
    references = _safe_source_references(source_references)
    if references:
        payload["source_references"] = references
    if reason == "vehicle_identity_mismatch":
        payload["status"] = "needs_review"
        payload["data_state"] = "needs_review"
    else:
        payload["status"] = "source_unnormalized"
        payload["data_state"] = "source_unnormalized"
        payload["source_unnormalized"] = {
            "source_uri": payload.get("source_uri"),
            "evidence": deepcopy(payload.get("evidence", ())),
            "rejection_reason": reason or "normalization_pending",
        }
        if references:
            payload["source_unnormalized"]["source_references"] = references
    result["result"] = payload
    publication = result.get("publication")
    if isinstance(publication, dict):
        publication["status"] = payload["status"]
    return result


def _source_unnormalized_failure(
    request: KnowledgeFallbackRequest,
    resolver: ConfiguredKnowledgeSourceResolver,
    error: Exception,
) -> dict[str, Any]:
    references = _safe_source_references(resolver.last_source_references)
    source_uri = references[0].get("source_uri") if references else None
    result = {
        "status": "source_unnormalized",
        "data_state": "source_unnormalized",
        "idempotency_key": request.idempotency_key,
        "vehicle": request.target.as_dict(),
        "query": request.query,
        "keywords": request.keywords,
        "results": (),
        "evidence": (),
        "source_uri": source_uri,
        "rejection_reason": "normalization_pending",
        "source_references": references,
        "source_unnormalized": {
            "source_references": references,
            "rejection_reason": "normalization_pending",
            "error_type": type(error).__name__,
        },
    }
    return {
        "status": "completed",
        "request_id": request.request_id,
        "idempotency_key": request.idempotency_key,
        "dataset_id": request.dataset_id,
        "revision_id": request.revision_id,
        "result": result,
        "publication": {
            "event_type": "dataset.knowledge.fallback.fulfilled",
            "event_version": 1,
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
            "status": "source_unnormalized",
            "results": [],
            "evidence": [],
            "source_uri": source_uri,
        },
    }


def _refresh_result_prices(result: dict[str, Any]) -> dict[str, Any]:
    """Annotate cached part prices without waiting for a source refresh."""

    if not isinstance(result, dict) or not isinstance(result.get("result"), Mapping):
        return result
    payload = dict(result["result"])
    now = datetime.now(UTC)

    def refresh_parts(value: Any) -> Any:
        if not isinstance(value, list):
            return value
        refreshed: list[Any] = []
        for part in value:
            if not isinstance(part, Mapping) or part.get("priced_at") is None:
                refreshed.append(part)
                continue
            refreshed.append(
                read_cached_price_or_queue_refresh(
                    part,
                    now=now,
                    refresh=queue_price_refresh,
                )
            )
        return refreshed

    if isinstance(payload.get("parts"), list):
        payload["parts"] = refresh_parts(payload["parts"])
    for entry in payload.get("results", ()):
        if isinstance(entry, Mapping) and isinstance(entry.get("parts"), list):
            entry["parts"] = refresh_parts(entry["parts"])
    result["result"] = payload
    return result


def persist_source_payloads(
    resources: Any,
    *,
    adapter_name: str = "knowledge-fallback",
) -> dict[str, Any]:
    """Retain source bytes and source snapshot rows before normalization.

    ``persist_source_bundle`` remains responsible for normalized rows.  This
    earlier boundary stores the immutable object and source snapshot, making a
    normalization failure replayable without another provider request.
    """

    from .bundle_persistence import _persist_snapshots, store_source_artifacts
    from .source_adapters import SourceArtifact, SourceResource, adapt_source_resource

    resource_list = tuple(resources)
    if not resource_list:
        return {"status": "no_source_payloads", "source_snapshots": 0}
    if not all(isinstance(resource, SourceResource) for resource in resource_list):
        raise TypeError("source payload retention requires SourceResource values")

    raw_artifacts = [
        _raw_source_artifact(resource, SourceArtifact)
        for resource in resource_list
    ]
    store_source_artifacts(raw_artifacts)
    import psycopg
    from psycopg.types.json import Jsonb

    now = datetime.now(UTC).replace(microsecond=0)
    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            snapshot_ids = _persist_snapshots(
                cursor, raw_artifacts, adapter_name, now, Jsonb
            )
            _persist_raw_artifact_rows(
                cursor, raw_artifacts, snapshot_ids, now, Jsonb
            )
        connection.commit()
    source_references = tuple(
        _source_reference(resource, snapshot_ids[resource.content_sha256])
        for resource in resource_list
    )
    try:
        adapted_artifacts = [
            adapt_source_resource(resource) for resource in resource_list
        ]
    except Exception as error:  # noqa: BLE001 - raw retention must survive adapter failure
        return {
            "status": "source_unnormalized",
            "source_snapshots": len(snapshot_ids),
            "source_snapshot_ids": tuple(sorted(snapshot_ids.values())),
            "source_references": source_references,
            "adaptation_error": {"error_type": type(error).__name__},
        }
    return {
        "status": "persisted",
        "source_snapshots": len(snapshot_ids),
        "source_snapshot_ids": tuple(sorted(snapshot_ids.values())),
        "source_artifacts": len(adapted_artifacts),
        "source_references": source_references,
    }


def _raw_source_artifact(resource: Any, artifact_type: Any) -> Any:
    media_type = str(resource.media_type).split(";", 1)[0].casefold()
    if media_type in {"application/json", "application/problem+json", "text/json"}:
        kind = "structured"
    elif media_type == "image/svg+xml":
        kind = "diagram"
    elif media_type in {"text/html", "application/pdf", "text/plain"}:
        kind = "document"
    else:
        kind = "quarantine"
    return artifact_type(
        kind=kind,
        source_uri=resource.source_uri,
        source_version=resource.source_version,
        media_type=resource.media_type,
        content_sha256=resource.content_sha256,
        payload=resource.payload,
        raw_payload=resource.payload,
        metadata={
            **resource.metadata,
            "retention_status": "raw",
            "source_uri": resource.source_uri,
            "source_version": resource.source_version,
            "content_sha256": resource.content_sha256,
            "locator": resource.locator,
        },
    )


def _persist_raw_artifact_rows(
    cursor: Any,
    artifacts: list[Any],
    snapshot_ids: Mapping[str, str],
    now: datetime,
    jsonb: Any,
) -> None:
    for artifact in artifacts:
        cursor.execute(
            """
            INSERT INTO source_artifacts
                (source_artifact_id, source_snapshot_id, artifact_kind, media_type,
                 content_sha256, object_key, metadata, extraction_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'needs_review')
            ON CONFLICT (content_sha256) DO UPDATE SET
                source_snapshot_id = EXCLUDED.source_snapshot_id,
                object_key = EXCLUDED.object_key,
                metadata = EXCLUDED.metadata
            """,
            (
                str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"autodata-bundle:source-artifact:{artifact.content_sha256}",
                    )
                ),
                snapshot_ids[artifact.content_sha256],
                artifact.kind,
                artifact.media_type,
                artifact.content_sha256,
                artifact.object_key,
                jsonb(
                    {
                        **artifact.metadata,
                        "retained_at": now.isoformat(),
                    }
                ),
            ),
        )


def _source_reference(resource: Any, source_snapshot_id: str) -> dict[str, Any]:
    return {
        "source_uri": resource.source_uri,
        "source_version": resource.source_version,
        "content_sha256": resource.content_sha256,
        "source_snapshot_id": str(source_snapshot_id),
        "source_artifact_id": str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"autodata-bundle:source-artifact:{resource.content_sha256}",
            )
        ),
        "object_key": (
            f"sources/{resource.content_sha256[:16]}/{resource.content_sha256}"
        ),
    }


def persist_price_snapshots(parts: Any) -> dict[str, Any]:
    """Persist canonical source prices using the immutable snapshot identity."""

    records = [
        deepcopy(dict(part))
        for part in parts
        if isinstance(part, Mapping)
        and _first_text(part, "parts_price_snapshot_id")
    ]
    if not records:
        return {"status": "no_price_snapshots", "price_snapshots": 0}
    import psycopg
    from psycopg.types.json import Jsonb

    snapshot_ids: list[str] = []
    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            for part in records:
                if part.get("markup_applied") is not False:
                    raise ValueError("source price snapshots cannot include markup")
                snapshot_id = _first_text(part, "parts_price_snapshot_id")
                source_snapshot_id = _first_text(part, "source_snapshot_id")
                canonical_part_id = _first_text(part, "canonical_part_id")
                source_part_number = _first_text(part, "source_part_number")
                currency = _first_text(part, "currency")
                if (
                    not snapshot_id
                    or not source_snapshot_id
                    or not canonical_part_id
                    or not source_part_number
                ):
                    raise ValueError("price snapshot identity is incomplete")
                if currency is None or len(currency) != 3 or not currency.isalpha():
                    raise ValueError("price snapshot currency must be three letters")
                try:
                    amount = float(part["amount"])
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError("price snapshot amount must be numeric") from error
                if amount < 0:
                    raise ValueError("price snapshot amount must be non-negative")
                priced_at = _snapshot_timestamp(part.get("priced_at"))
                cursor.execute(
                    """
                    INSERT INTO parts_price_snapshots
                        (parts_price_snapshot_id, canonical_part_id,
                         source_part_number, source_snapshot_id, amount, currency,
                         priced_at, freshness, refresh_status, markup_applied,
                         source_uri, source_part_payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s)
                    ON CONFLICT (canonical_part_id, source_snapshot_id, priced_at)
                    DO NOTHING
                    """,
                    (
                        snapshot_id,
                        canonical_part_id,
                        source_part_number,
                        source_snapshot_id,
                        amount,
                        currency.upper(),
                        priced_at,
                        _first_text(part, "freshness") or "unknown",
                        _first_text(part, "refresh_status") or "current",
                        _first_text(part, "source_uri", "sourceUri"),
                        Jsonb(part),
                    ),
                )
                snapshot_ids.append(snapshot_id)
        connection.commit()
    return {
        "status": "persisted",
        "price_snapshots": len(snapshot_ids),
        "price_snapshot_ids": tuple(snapshot_ids),
    }


def _snapshot_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("price snapshot priced_at must be an ISO timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("price snapshot priced_at must be timezone-aware")
    return parsed.astimezone(UTC)


def queue_price_refresh(
    part: Mapping[str, Any], *, max_attempts: int = 3
) -> dict[str, Any]:
    """Insert one idempotent durable price-refresh attempt."""

    if not isinstance(part, Mapping):
        raise TypeError("price refresh part must be a mapping")
    if max_attempts < 1:
        raise ValueError("maximum price refresh attempts must be positive")
    snapshot_id = _first_text(
        part,
        "parts_price_snapshot_id",
        "price_snapshot_row_id",
        "price_snapshot_id",
    )
    if not snapshot_id:
        raise ValueError("price refresh requires parts_price_snapshot_id")
    refresh_request_id = _price_refresh_key(part)
    import psycopg

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT refresh_attempt_number, refresh_status,
                       refresh_idempotency_key, failure
                FROM parts_price_snapshot_refreshes
                WHERE parts_price_snapshot_id = %s
                  AND (
                      refresh_idempotency_key = %s
                      OR refresh_idempotency_key LIKE %s
                  )
                ORDER BY refresh_attempt_number DESC
                LIMIT 1
                FOR UPDATE
                """,
                (
                    snapshot_id,
                    refresh_request_id,
                    f"{refresh_request_id}:attempt:%",
                ),
            )
            existing = cursor.fetchone()
            if existing is not None:
                previous_attempt, previous_status, previous_key, previous_failure = existing
                previous_attempt = int(previous_attempt)
                if previous_status in {"queued", "processing", "current"}:
                    return {
                        "status": str(previous_status),
                        "refresh_idempotency_key": str(previous_key),
                        "refresh_request_id": refresh_request_id,
                        "refresh_attempt_number": previous_attempt,
                    }
                if previous_attempt >= max_attempts:
                    return {
                        "status": "dead_letter",
                        "refresh_idempotency_key": str(previous_key),
                        "refresh_request_id": refresh_request_id,
                        "refresh_attempt_number": previous_attempt,
                        "retryable": False,
                        "failure": deepcopy(previous_failure),
                    }
                attempt_number = previous_attempt + 1
            else:
                attempt_number = 1
            refresh_key = _refresh_attempt_key(refresh_request_id, attempt_number)
            cursor.execute(
                """
                INSERT INTO parts_price_snapshot_refreshes
                    (parts_price_snapshot_refresh_id, parts_price_snapshot_id,
                     refresh_attempt_number, refresh_idempotency_key,
                     refresh_status, requested_at)
                VALUES (%s, %s, %s, %s, 'queued', now())
                ON CONFLICT DO NOTHING
                """,
                (
                    str(uuid.uuid5(uuid.NAMESPACE_URL, refresh_key)),
                    snapshot_id,
                    attempt_number,
                    refresh_key,
                ),
            )
            cursor.execute(
                """
                SELECT refresh_attempt_number, refresh_status
                FROM parts_price_snapshot_refreshes
                WHERE refresh_idempotency_key = %s
                """,
                (refresh_key,),
            )
            row = cursor.fetchone()
        connection.commit()
    if row is None:
        raise RuntimeError("price refresh was not persisted")
    return {
        "status": str(row[1]),
        "refresh_idempotency_key": refresh_key,
        "refresh_request_id": refresh_request_id,
        "refresh_attempt_number": int(row[0]),
    }


def record_price_refresh_failure(
    refresh_idempotency_key: str,
    error: Exception,
    *,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Record failure state and publish one event when retries are exhausted."""

    if not str(refresh_idempotency_key).strip():
        raise ValueError("price refresh idempotency key is required")
    if max_attempts < 1:
        raise ValueError("maximum price refresh attempts must be positive")
    failure = {
        "error_type": type(error).__name__,
        "message": str(error).strip() or type(error).__name__,
    }
    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT parts_price_snapshot_refresh_id::text, refresh_attempt_number,
                       refresh_status
                FROM parts_price_snapshot_refreshes
                WHERE refresh_idempotency_key = %s
                FOR UPDATE
                """,
                (refresh_idempotency_key,),
            )
            row = cursor.fetchone()
            if row is None:
                return {
                    "status": "not_found",
                    "refresh_idempotency_key": refresh_idempotency_key,
                }
            refresh_id, attempt_number, current_status = row
            if current_status == "current":
                return {
                    "status": "current",
                    "refresh_idempotency_key": refresh_idempotency_key,
                    "refresh_attempt_number": int(attempt_number),
                }
            exhausted = int(attempt_number) >= max_attempts
            cursor.execute(
                """
                UPDATE parts_price_snapshot_refreshes
                SET refresh_status = 'failed', failure = %s, completed_at = now()
                WHERE parts_price_snapshot_refresh_id = %s
                """,
                (Jsonb(failure), refresh_id),
            )
            if exhausted:
                dead_letter_key = (
                    f"price-refresh-dead-letter:{refresh_idempotency_key}:{attempt_number}"
                )
                cursor.execute(
                    """
                    INSERT INTO publication_events
                        (publication_event_id, event_type, event_version,
                         correlation_id, idempotency_key, payload, published_at,
                         producer)
                    VALUES (%s, 'chat.price.refresh.dead_letter', 1, %s, %s,
                            %s, now(), 'pricing-runtime')
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """,
                    (
                        str(uuid.uuid5(uuid.NAMESPACE_URL, dead_letter_key)),
                        str(uuid.uuid5(uuid.NAMESPACE_URL, refresh_idempotency_key)),
                        dead_letter_key,
                        Jsonb(
                            {
                                "refresh_idempotency_key": refresh_idempotency_key,
                                "refresh_attempt_number": int(attempt_number),
                                "failure": failure,
                            }
                        ),
                    ),
                )
        connection.commit()
    return {
        "status": "dead_letter" if exhausted else "failed",
        "refresh_idempotency_key": refresh_idempotency_key,
        "refresh_attempt_number": int(attempt_number),
        "retryable": not exhausted,
        "failure": failure,
    }


def _source_configuration(
    target: VehicleTarget,
    query: str,
    keywords: tuple[str, ...],
    source_hint: Any | None,
) -> tuple[str, str | None]:
    hint = source_hint
    if isinstance(hint, Mapping):
        uri = hint.get("url") or hint.get("source_uri") or hint.get("uri")
        version = hint.get("source_version")
    else:
        uri, version = hint, None
    if not str(uri or "").strip():
        template = os.getenv("AUTODATA_KNOWLEDGE_SOURCE_URL_TEMPLATE", "").strip()
        if not template:
            raise LookupError(
                "knowledge source resolver requires source_hint or "
                "AUTODATA_KNOWLEDGE_SOURCE_URL_TEMPLATE"
            )
        try:
            uri = template.format(
                make=target.make,
                model=target.model,
                year=target.model_year,
                region=target.region,
                vehicle_key=target.vehicle_key,
                query=query,
                keywords=",".join(keywords),
            )
        except (KeyError, ValueError) as error:
            raise ValueError("knowledge source URL template has invalid placeholders") from error
        version = os.getenv("AUTODATA_KNOWLEDGE_SOURCE_VERSION", "") or None
    parsed = urlsplit(str(uri).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("knowledge source resolver produced a non-HTTP URL")
    if parsed.username or parsed.password:
        raise ValueError("knowledge source URL must not contain credentials")
    return parsed.geturl(), str(version).strip() or None


def _source_headers() -> dict[str, str]:
    raw = os.getenv("AUTODATA_SOURCE_REQUEST_HEADERS_JSON", "").strip()
    if not raw:
        return {}
    headers = json.loads(raw)
    if not isinstance(headers, dict) or any(not isinstance(value, str) for value in headers.values()):
        raise ValueError("AUTODATA_SOURCE_REQUEST_HEADERS_JSON must be an object of string values")
    return {str(key): value for key, value in headers.items()}


def _first_text(value: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        candidate = value.get(key)
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return None


def _price_refresh_key(part: Mapping[str, Any]) -> str:
    request_id = _first_text(part, "refresh_request_id", "refresh_id")
    if request_id:
        return _refresh_request_root(request_id)
    supplied = _first_text(part, "refresh_idempotency_key")
    if supplied:
        return _refresh_request_root(supplied)
    priced_at = part.get("priced_at", "")
    if isinstance(priced_at, datetime):
        priced_at = priced_at.astimezone(UTC).isoformat()
    else:
        priced_at = _canonical_refresh_timestamp(str(priced_at).strip())
    identity = json.dumps(
        {
            "canonical_part_id": _first_text(
                part, "canonical_part_id", "part_id", "canonical_id"
            )
            or "",
            "source_part_number": _first_text(
                part,
                "source_part_number",
                "part_number",
                "partNumber",
                "sourcePartNumber",
            )
            or "",
            "source_snapshot_id": _first_text(
                part, "source_snapshot_id", "price_snapshot_id", "snapshot_id"
            )
            or "",
            "priced_at": priced_at,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "price-refresh:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _refresh_request_root(value: str) -> str:
    return re.sub(r":attempt:\\d+$", "", str(value).strip())


def _refresh_attempt_key(request_id: str, attempt_number: int) -> str:
    return f"{_refresh_request_root(request_id)}:attempt:{int(attempt_number)}"


def _canonical_refresh_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return value
    return parsed.astimezone(UTC).isoformat()


def load_revision_catalog(projection_id: str) -> dict[str, Any]:
    """Load only the latest normalized projection content for warm lookup."""

    import psycopg

    with psycopg.connect(_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT content
                FROM dataset_revisions
                WHERE dataset_projection_id = %s
                  AND published_at IS NOT NULL
                ORDER BY revision_number DESC
                LIMIT 1
                """,
                (projection_id,),
            )
            row = cursor.fetchone()
    if row is None or not isinstance(row[0], dict):
        return {}
    content = json.loads(json.dumps(row[0]))
    vehicle_key = str(content.get("vehicle_identity", {}).get("vehicle_key", "")).strip()
    if vehicle_key:
        for article in content.get("articles", []):
            if isinstance(article, dict):
                article.setdefault("vehicle_key", vehicle_key)
    return content


def publish_fallback_revision(
    request: KnowledgeFallbackRequest, fulfillment: Mapping[str, Any]
) -> dict[str, Any]:
    """Append one immutable article revision and its section-published outbox row."""

    import psycopg
    from psycopg.types.json import Jsonb

    result = fulfillment["result"]
    articles = [
        {**entry["article"], "vehicle_key": request.vehicle_key}
        for entry in result.get("results", [])
        if isinstance(entry, Mapping) and isinstance(entry.get("article"), Mapping)
    ]
    if not articles:
        return {"status": "no_publication", "request_id": request.request_id}
    now = datetime.now(UTC).replace(microsecond=0)
    publication_key = f"knowledge-fallback:published:v1:{request.idempotency_key}"
    with psycopg.connect(**_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT publication_event_id::text, dataset_revision_id::text "
                "FROM publication_events WHERE idempotency_key = %s",
                (publication_key,),
            )
            existing = cursor.fetchone()
            if existing is not None:
                return {"status": "already_published", "revision_id": existing[1], "idempotency_key": publication_key}
            cursor.execute(
                """
                SELECT dataset_revision_id::text, revision_number, availability,
                       source_watermark, content
                FROM dataset_revisions
                WHERE dataset_projection_id = %s AND published_at IS NOT NULL
                ORDER BY revision_number DESC
                LIMIT 1
                FOR UPDATE
                """,
                (request.projection_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("fallback projection has no published revision")
            previous_revision_id, revision_number, availability, watermark, content = row
            next_content = dict(content)
            existing_articles = list(next_content.get("articles", []))
            existing_fingerprints = {
                str(article.get("normalized_fingerprint"))
                for article in existing_articles
                if isinstance(article, Mapping) and article.get("normalized_fingerprint")
            }
            existing_article_ids = {
                str(article.get("article_id"))
                for article in existing_articles
                if isinstance(article, Mapping) and article.get("article_id")
            }
            added_articles: list[Mapping[str, Any]] = []
            for article in articles:
                fingerprint = str(article.get("normalized_fingerprint", ""))
                article_id = str(article.get("article_id", ""))
                if (fingerprint and fingerprint in existing_fingerprints) or (
                    not fingerprint and article_id and article_id in existing_article_ids
                ):
                    continue
                existing_articles.append(article)
                added_articles.append(article)
                if fingerprint:
                    existing_fingerprints.add(fingerprint)
                if article_id:
                    existing_article_ids.add(article_id)
            if not added_articles:
                return {
                    "status": "already_present",
                    "revision_id": previous_revision_id,
                    "idempotency_key": publication_key,
                }
            next_content["articles"] = existing_articles
            revision_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata:knowledge:{publication_key}"))
            source_watermark = next((str(item.get("source_version")) for item in result.get("evidence", []) if item.get("source_version")), watermark)
            cursor.execute(
                """
                INSERT INTO dataset_revisions
                    (dataset_revision_id, dataset_projection_id, revision_number,
                     availability, source_watermark, schema_version, changelog,
                     content, published_at)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s, %s)
                ON CONFLICT (dataset_projection_id, revision_number) DO NOTHING
                """,
                (
                    revision_id, request.projection_id, int(revision_number) + 1,
                    availability, source_watermark,
                    Jsonb({"kind": "knowledge-fallback", "previous_revision_id": previous_revision_id, "request_id": request.request_id, "idempotency_key": request.idempotency_key}),
                    Jsonb(next_content), now,
                ),
            )
            cursor.execute(
                """
                INSERT INTO dataset_section_status
                    (dataset_projection_id, section_name, status,
                     last_published_revision_id, updated_at)
                VALUES (%s, 'articles', 'complete', %s, %s)
                ON CONFLICT (dataset_projection_id, section_name)
                DO UPDATE SET status = 'complete',
                              last_published_revision_id = EXCLUDED.last_published_revision_id,
                              updated_at = EXCLUDED.updated_at
                """,
                (request.projection_id, revision_id, now),
            )
            evidence_ids = [
                str(item["evidence_id"])
                for item in result.get("evidence", [])
                if isinstance(item, Mapping) and item.get("evidence_id")
            ]
            if evidence_ids:
                cursor.execute(
                    "UPDATE extraction_evidence "
                    "SET dataset_revision_id = %s "
                    "WHERE extraction_evidence_id = ANY(%s::uuid[])",
                    (revision_id, evidence_ids),
                )
            cursor.execute(
                """
                INSERT INTO publication_events
                    (publication_event_id, event_type, event_version,
                     dataset_request_id, dataset_projection_id, dataset_revision_id,
                     correlation_id, idempotency_key, payload, published_at, producer)
                SELECT %s, 'dataset.section.published', 1, dp.dataset_request_id,
                       %s, %s, %s, %s, %s, %s, 'knowledge-fallback-worker'
                FROM dataset_projections dp
                WHERE dp.dataset_projection_id = %s
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata:event:{publication_key}")),
                    request.projection_id, revision_id, request.correlation_id,
                    publication_key,
                    Jsonb({"section": "articles", "source_uri": result.get("source_uri"), "evidence": result.get("evidence", []), "request_id": request.request_id}),
                    now, request.projection_id,
                ),
            )
        connection.commit()
    return {"status": "published", "revision_id": revision_id, "idempotency_key": publication_key}


def _conninfo() -> dict[str, Any]:
    host, port = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    return {
        "host": host,
        "port": int(port),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": os.environ["AUTODATA_POSTGRES_PASSWORD"],
    }
