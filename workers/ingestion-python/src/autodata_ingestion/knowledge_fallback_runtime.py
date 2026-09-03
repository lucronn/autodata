"""Production composition for vehicle-scoped knowledge fallback fulfillment."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from .article_intake import VehicleTarget
from .http_connector import HttpSourceConnector
from .knowledge_fallback import (
    KnowledgeFallbackFulfillmentHandler,
    KnowledgeFallbackRequest,
    ResolvedSource,
)


def fulfill_once(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve, normalize, persist, and publish one fallback request."""

    request = KnowledgeFallbackRequest.from_envelope(envelope)
    catalog = load_revision_catalog(request.projection_id)

    def persist(bundle: Any, artifacts: Any, *, adapter_name: str) -> dict[str, Any]:
        from .bundle_persistence import persist_source_bundle

        return persist_source_bundle(bundle, artifacts, adapter_name=adapter_name)

    handler = KnowledgeFallbackFulfillmentHandler(
        catalog=catalog,
        source_resolver=ConfiguredKnowledgeSourceResolver(),
        persistence=persist,
    )
    result = handler.handle(dict(envelope))
    if result["result"]["status"] == "fetched":
        result["publication"] = publish_fallback_revision(request, result)
    return result


class ConfiguredKnowledgeSourceResolver:
    """Resolve a URL from an explicit hint or a configured URL template."""

    def __call__(
        self,
        target: VehicleTarget,
        query: str,
        keywords: tuple[str, ...],
        source_hint: Any | None = None,
    ) -> ResolvedSource:
        source_uri, source_version = _source_configuration(
            target, query, keywords, source_hint
        )
        return ResolvedSource(
            source_uri,
            source_version=source_version,
            connector=HttpSourceConnector(
                source_uri,
                source_version,
                timeout_seconds=float(os.getenv("AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS", "30")),
                max_bytes=int(os.getenv("AUTODATA_SOURCE_MAX_BYTES", str(50 * 1024 * 1024))),
                request_headers=_source_headers(),
            ),
        )


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
