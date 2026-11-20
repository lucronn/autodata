"""Bounded, read-only replay of article media from retained source observations."""

from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
import re
from time import monotonic
from uuid import UUID

from psycopg.rows import dict_row

from .article_document import validate_ordered_document
from .article_lifecycle_store import _remap_snapshot_references
from .article_lifecycle_types import (
    ArticleKey,
    CapturedSource,
    SourceArticleContext,
    article_id,
    digest_json,
    validate_ref,
)
from .source_article_capture import capture_source_article, project_document, snapshot_id
from .source_connector_client import (
    SourceConnectorError,
    SourceEnvelopeV1,
    _safe_locator,
    _valid_asset_bindings,
)

MEDIA_REPLAY_SOURCE_VERSIONS = frozenset({"source-projection-v1", "source-projection-v2"})
MEDIA_REPLAY_PROJECTION_VERSION = "source-projection-v3"

_MAX_OBJECT_BYTES = 1024 * 1024  # ArticleObjectStore.get_object's retained-object bound.
_MAX_TOTAL_BYTES = 8 * _MAX_OBJECT_BYTES
_MAX_RESOURCES = 32
_BODY_MEDIA = frozenset({"text/html", "application/json", "application/hal+json", "application/pdf"})
_RASTER_MEDIA = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
_MANIFEST_FIELDS = frozenset({"role", "opaque_ref", "sha256", "media_type"})
_PROVENANCE_FIELDS = _MANIFEST_FIELDS | {
    "provider", "object_key", "source_snapshot_id", "source_revision",
    "request_id", "fetched_at", "locator",
}
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class _Snapshot:
    id: UUID
    digest: str
    object_key: str
    takedown_status: str
    artifact_digest: str | None
    artifact_key: str | None
    media_type: str | None


@dataclass(frozen=True)
class MediaReplayBinding:
    """Retained identity and original rights used for preview and locked apply."""

    canonical_article_id: UUID
    source_revision_id: UUID
    source_observation_id: UUID
    projection_version: str
    source_fingerprint: str
    body_sha256: str
    body_source_snapshot_id: UUID
    context: SourceArticleContext
    resource_manifest: tuple[dict, ...]
    resource_provenance: tuple[dict, ...]
    evidence_manifest: tuple[dict, ...]
    source_document_hash: str
    _source_blocks: Counter
    _source_assets: Counter
    captured_at: datetime
    snapshots: tuple[_Snapshot, ...]


def media_replay_document_hash(captured: CapturedSource) -> str:
    return digest_json(captured.source_document)


def _key(digest: str) -> str:
    return "sources/" + digest[:16] + "/" + digest


def _rows(value):
    if not isinstance(value, list) or not all(isinstance(entry, dict) for entry in value):
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    return tuple(value)


def _uuid(value):
    try:
        return value if isinstance(value, UUID) else UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH") from None


def _source_ref(value, limit=2048):
    try:
        validate_ref(value, limit)
    except ValueError:
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH") from None
    return value


def _context(row) -> SourceArticleContext:
    saved = row["captured_context"]
    if (not isinstance(saved, dict) or set(saved) != {"vehicle", "descriptor", "evidence_ids"}
            or not isinstance(saved["vehicle"], dict) or not isinstance(saved["descriptor"], dict)
            or not isinstance(saved["evidence_ids"], list)
            or any(not isinstance(item, str) or not item for item in saved["evidence_ids"])):
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    try:
        key = ArticleKey(
            row["provider_slug"], row["vehicle_id"], row["vehicle_configuration_id"],
            row["source_vehicle_ref"], row["source_article_ref"],
        )
    except ValueError:
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH") from None
    if article_id(key) != row["canonical_article_id"]:
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    return SourceArticleContext(
        key, saved["vehicle"], saved["descriptor"], row["descriptor_source_snapshot_id"],
        row["resolution_source_snapshot_id"], tuple(saved["evidence_ids"]),
    )


def _resource_binding(row, context, manifest, provenance):
    if row["projection_status"] != "readable" or not 1 < len(manifest) <= _MAX_RESOURCES:
        raise ValueError("SOURCE_MEDIA_REPLAY_UNSUPPORTED")
    if len(provenance) != len(manifest):
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    body_ref = _source_ref(context.descriptor.get("resource_ref") or context.descriptor.get("body_resource_ref"))
    if context.descriptor.get("labor_resource_ref"):
        raise ValueError("SOURCE_MEDIA_REPLAY_UNSUPPORTED")
    references = set()
    snapshots = set()
    for index, (entry, owner) in enumerate(zip(manifest, provenance, strict=True)):
        role, mime = entry.get("role"), entry.get("media_type")
        if index == 0:
            supported = role == "body" and isinstance(mime, str) and mime in _BODY_MEDIA
        else:
            supported = role in ("asset", "embedded_asset") and isinstance(mime, str) and mime in _RASTER_MEDIA
        if not supported or set(entry) != _MANIFEST_FIELDS:
            raise ValueError("SOURCE_MEDIA_REPLAY_UNSUPPORTED")
        owner_fields = set(owner)
        expected_fields = _PROVENANCE_FIELDS
        if role == "body" and "asset_bindings" in owner:
            expected_fields = expected_fields | {"asset_bindings"}
        if (owner_fields != expected_fields or owner.get("provider") != context.key.provider
                or any(owner.get(key) != entry[key] for key in _MANIFEST_FIELDS)):
            raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")

        ref = _source_ref(entry["opaque_ref"])
        digest = entry["sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
        if ref in references or owner["object_key"] != _key(digest):
            raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
        references.add(ref)
        source_snapshot_id = _uuid(owner["source_snapshot_id"])
        snapshots.add(source_snapshot_id)
        _uuid(owner["request_id"])
        _source_ref(owner["source_revision"], 256)
        if not _safe_locator(_source_ref(owner["locator"])):
            raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
        try:
            if datetime.fromisoformat(owner["fetched_at"]).utcoffset() is None:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH") from None

        if role == "body" and (
            source_snapshot_id != row["body_source_snapshot_id"] or ref != body_ref
            or owner["source_revision"] != row["body_provider_revision"]
        ):
            raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
        if role == "embedded_asset":
            if ref != "embedded:" + manifest[0]["sha256"] + ":" + digest:
                raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
            if any(owner[key] != provenance[0][key] for key in ("source_revision", "request_id", "fetched_at", "locator")):
                raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")

    direct_refs = [entry["opaque_ref"] for entry in manifest if entry["role"] == "asset"]
    declared_refs = context.descriptor.get("asset_resource_refs", [])
    if not isinstance(declared_refs, list) or any(
        not isinstance(ref, str) or ref not in direct_refs for ref in declared_refs
    ):
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    bindings = provenance[0].get("asset_bindings")
    if "asset_bindings" in provenance[0] and not _valid_asset_bindings(bindings, direct_refs):
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    body = manifest[0]
    fingerprint = {
        "provider": context.key.provider,
        "body_ref": body_ref,
        "body_sha256": body["sha256"],
        "body_media_type": body["media_type"],
        "resource_manifest": manifest,
    }
    if bindings:
        fingerprint["asset_bindings"] = sorted(bindings, key=lambda item: item["source_url"])
    if digest_json(fingerprint) != row["source_fingerprint"]:
        raise ValueError("SOURCE_MEDIA_REPLAY_FINGERPRINT_MISMATCH")
    return snapshots


def _load_snapshots(cur, ids, *, lock):
    sql = """
        SELECT s.source_snapshot_id, s.content_sha256, s.object_key, s.takedown_status,
               a.content_sha256 AS artifact_digest, a.object_key AS artifact_key, a.media_type
        FROM source_snapshots s
        LEFT JOIN source_artifacts a USING (source_snapshot_id)
        WHERE s.source_snapshot_id = ANY(%s)
        ORDER BY s.source_snapshot_id"""
    if lock:
        sql += " FOR SHARE OF s"
    snapshots = tuple(
        _Snapshot(
            row["source_snapshot_id"], row["content_sha256"], row["object_key"],
            row["takedown_status"], row["artifact_digest"], row["artifact_key"], row["media_type"],
        )
        for row in cur.execute(sql, (sorted(ids),)).fetchall()
    )
    if {snapshot.id for snapshot in snapshots} != ids:
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    if any(snapshot.takedown_status != "active" for snapshot in snapshots):
        raise ValueError("SOURCE_MEDIA_REPLAY_WITHDRAWN")
    return snapshots


def _asset_inventory(images, provenance):
    if not isinstance(images, (tuple, list)) or not images:
        raise ValueError("SOURCE_MEDIA_REPLAY_ASSET_DRIFT")
    allowed = {
        (row["sha256"], row["object_key"], row["media_type"])
        for row in provenance if row["role"] != "body"
    }
    counter = Counter()
    for image in images:
        if not isinstance(image, dict) or image.get("status") != "available":
            raise ValueError("SOURCE_MEDIA_REPLAY_ASSET_DRIFT")
        asset = tuple(image.get(field) for field in ("content_sha256", "storage_key", "media_type"))
        if not all(isinstance(value, str) for value in asset) or asset not in allowed:
            raise ValueError("SOURCE_MEDIA_REPLAY_ASSET_DRIFT")
        counter[asset] += 1
    if counter.keys() != allowed:
        raise ValueError("SOURCE_MEDIA_REPLAY_ASSET_DRIFT")
    return counter


def _block_inventory(document):
    """Compare protected text and structure independently of image/page order."""
    def without_media(value):
        if isinstance(value, list):
            return [
                without_media(child) for child in value
                if not isinstance(child, dict) or child.get("type") != "image"
            ]
        if not isinstance(value, dict):
            return value
        cleaned = {
            key: without_media(child) for key, child in value.items()
            if key not in ("images", "block_id", "source_order")
        }
        # A table cell with only text uses the scalar compatibility shape.
        if cleaned.keys() == {"text"}:
            return cleaned["text"]
        return cleaned

    if not isinstance(document, dict) or not isinstance(document.get("blocks"), list):
        raise ValueError("SOURCE_MEDIA_REPLAY_DOCUMENT_INVALID")
    return Counter(digest_json(block) for block in without_media(document["blocks"]))


def load_media_replay_binding(cur, source_revision_id, *, lock=False) -> MediaReplayBinding:
    """Select one immutable source observation and all its current snapshot rights."""
    row = cur.execute("""
        SELECT s.source_revision_id, s.canonical_article_id, s.source_fingerprint,
               s.body_source_snapshot_id, s.resource_manifest, s.evidence_manifest,
               s.source_document, s.source_images, s.captured_at, s.projection_status,
               s.projection_version, a.provider_slug, a.vehicle_id, a.vehicle_configuration_id,
               a.source_vehicle_ref, a.source_article_ref, a.membership_status, a.takedown_status,
               o.source_observation_id, o.body_provider_revision, o.resource_provenance,
               o.captured_context, o.descriptor_source_snapshot_id, o.resolution_source_snapshot_id
        FROM canonical_article_source_revisions s
        JOIN canonical_articles a USING (canonical_article_id)
        JOIN LATERAL (
            SELECT * FROM canonical_article_source_observations o
            WHERE o.source_revision_id = s.source_revision_id
              AND o.canonical_article_id = s.canonical_article_id
            ORDER BY o.captured_at, o.source_observation_id
            LIMIT 1
        ) o ON true
        WHERE s.source_revision_id = %s
        """, (source_revision_id,)).fetchone()
    if row is None:
        raise ValueError("SOURCE_MEDIA_REPLAY_SOURCE_NOT_FOUND")
    if row["projection_version"] not in MEDIA_REPLAY_SOURCE_VERSIONS:
        raise ValueError("SOURCE_MEDIA_REPLAY_UNSUPPORTED")
    if row["membership_status"] != "active" or row["takedown_status"] != "active":
        raise ValueError("SOURCE_MEDIA_REPLAY_WITHDRAWN")

    context = _context(row)
    manifest = _rows(row["resource_manifest"])
    provenance = _rows(row["resource_provenance"])
    evidence = _rows(row["evidence_manifest"])
    snapshot_ids = _resource_binding(row, context, manifest, provenance)
    expected_evidence = context.evidence_ids or ("source:" + str(snapshot_id(manifest[0]["sha256"])),)
    if evidence != tuple(
        {"evidence_id": item, "body_source_snapshot_id": str(row["body_source_snapshot_id"])}
        for item in expected_evidence
    ):
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    snapshots = _load_snapshots(
        cur, snapshot_ids | {context.descriptor_snapshot_id, context.resolution_snapshot_id}, lock=lock,
    )
    snapshots_by_id = {snapshot.id: snapshot for snapshot in snapshots}
    for resource in provenance:
        snapshot = snapshots_by_id[_uuid(resource["source_snapshot_id"])]
        if (snapshot.digest != resource["sha256"] or snapshot.object_key != resource["object_key"]
                or snapshot.artifact_digest != resource["sha256"]
                or snapshot.artifact_key != resource["object_key"]
                or snapshot.media_type != resource["media_type"]):
            raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    return MediaReplayBinding(
        canonical_article_id=row["canonical_article_id"],
        source_revision_id=row["source_revision_id"],
        source_observation_id=row["source_observation_id"],
        projection_version=row["projection_version"],
        source_fingerprint=row["source_fingerprint"],
        body_sha256=manifest[0]["sha256"],
        body_source_snapshot_id=row["body_source_snapshot_id"],
        context=context,
        resource_manifest=manifest,
        resource_provenance=provenance,
        evidence_manifest=evidence,
        source_document_hash=digest_json(row["source_document"]),
        _source_blocks=_block_inventory(row["source_document"]),
        _source_assets=_asset_inventory(row["source_images"], provenance),
        captured_at=row["captured_at"],
        snapshots=snapshots,
    )


def validate_media_replay_result(binding: MediaReplayBinding, captured: CapturedSource) -> None:
    """Revalidate an offline replay against the exact retained observation."""
    if (
        captured.projection_version != MEDIA_REPLAY_PROJECTION_VERSION
        or captured.context != binding.context
        or captured.body_source_snapshot_id != binding.body_source_snapshot_id
        or captured.captured_at != binding.captured_at
        or captured.source_fingerprint != binding.source_fingerprint
        or tuple(captured.resource_manifest) != binding.resource_manifest
        or tuple(captured.resource_provenance) != binding.resource_provenance
        or tuple(captured.evidence_manifest) != binding.evidence_manifest
        or captured.resources != binding.resource_provenance
        or captured.projection_status != "readable"
    ):
        raise ValueError("SOURCE_MEDIA_REPLAY_BINDING_MISMATCH")
    if validate_ordered_document(captured.source_document, strict=True):
        raise ValueError("SOURCE_MEDIA_REPLAY_DOCUMENT_INVALID")
    if _block_inventory(captured.source_document) != binding._source_blocks:
        raise ValueError("SOURCE_MEDIA_REPLAY_TEXT_DRIFT")
    if _asset_inventory(captured.source_images, binding.resource_provenance) != binding._source_assets:
        raise ValueError("SOURCE_MEDIA_REPLAY_ASSET_DRIFT")
    if project_document(captured.source_document) != (
        captured.source_body, captured.source_steps, captured.source_images,
    ):
        raise ValueError("SOURCE_MEDIA_REPLAY_PROJECTION_DRIFT")
    if media_replay_document_hash(captured) == binding.source_document_hash:
        raise ValueError("SOURCE_MEDIA_REPLAY_UNCHANGED")


def _raster_matches(mime: str, payload: bytes) -> bool:
    # Match the public image reader's raster signatures before replaying bytes.
    if mime == "image/png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return payload.startswith(b"\xff\xd8\xff")
    if mime == "image/gif":
        return payload.startswith((b"GIF87a", b"GIF89a"))
    return payload.startswith(b"RIFF") and payload[8:15] == b"WEBPVP8"


def _read_objects(binding, object_store, remaining):
    verified = {}
    total = 0
    for resource in binding.resource_provenance:
        remaining()
        key, mime = resource["object_key"], resource["media_type"]
        if key in verified:
            if verified[key][1] != mime:
                raise ValueError("SOURCE_MEDIA_REPLAY_OBJECT_MISMATCH")
            continue
        limit = min(_MAX_OBJECT_BYTES, _MAX_TOTAL_BYTES - total)
        if limit <= 0:
            raise ValueError("SOURCE_MEDIA_REPLAY_OBJECT_LIMIT")
        try:
            data = object_store.get_object(key, max_bytes=limit)
        except Exception:
            raise ValueError("SOURCE_MEDIA_REPLAY_OBJECT_UNAVAILABLE") from None
        remaining()
        if (not isinstance(data, bytes) or not 0 < len(data) <= limit
                or sha256(data).hexdigest() != resource["sha256"]
                or (mime in _RASTER_MEDIA and not _raster_matches(mime, data))):
            raise ValueError("SOURCE_MEDIA_REPLAY_OBJECT_MISMATCH")
        total += len(data)
        verified[key] = (data, mime)
    return verified


class _OfflineConnector:
    def __init__(self, provider, resources, verified):
        self.provider = provider
        self._envelopes = {}
        direct_refs = [row["opaque_ref"] for row in resources if row["role"] == "asset"]
        for resource in resources:
            role = resource["role"]
            if role == "embedded_asset":
                continue
            body = {"kind": "article" if role == "body" else "asset",
                    "media_type": resource["media_type"], "sha256": resource["sha256"]}
            if role == "body":
                body["asset_resource_refs"] = direct_refs
                if "asset_bindings" in resource:
                    body["asset_bindings"] = resource["asset_bindings"]
            self._envelopes[resource["opaque_ref"]] = SourceEnvelopeV1(
                resource["request_id"], self.provider, resource["source_revision"],
                resource["fetched_at"], resource["locator"], body,
                raw_resource=verified[resource["object_key"]][0],
            )

    def read_resource(self, ref, *, timeout):
        if timeout <= 0 or ref not in self._envelopes:
            raise SourceConnectorError("SOURCE_MEDIA_REPLAY_UNBOUND_RESOURCE")
        return self._envelopes[ref]


class _VerifyOnlySink:
    def __init__(self, verified):
        self._verified = verified

    def put_object(self, key, payload, media_type):
        if self._verified.get(key) != (payload, media_type):
            raise ValueError("SOURCE_MEDIA_REPLAY_OBJECT_MISMATCH")


def _replay(repo, source_revision_id, object_store, deadline):
    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError("SOURCE_MEDIA_REPLAY_DEADLINE")
        return seconds

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        binding = load_media_replay_binding(cur, source_revision_id)
    verified = _read_objects(binding, object_store, remaining)
    client = _OfflineConnector(binding.context.key.provider, binding.resource_provenance, verified)
    try:
        replayed = capture_source_article(
            binding.context, registry={client.provider: client},
            object_store=_VerifyOnlySink(verified), deadline_seconds=remaining(),
        )
    except SourceConnectorError as error:
        code = "DEADLINE" if error.code in ("CAPTURE_DEADLINE", "UPSTREAM_UNAVAILABLE") else "CAPTURE_MISMATCH"
        raise ValueError("SOURCE_MEDIA_REPLAY_" + code) from None
    remaining()
    snapshot_ids = {
        str(snapshot_id(resource["sha256"])): resource["source_snapshot_id"]
        for resource in binding.resource_provenance
    }
    captured = replace(
        replayed, projection_version=MEDIA_REPLAY_PROJECTION_VERSION,
        captured_at=binding.captured_at, body_source_snapshot_id=binding.body_source_snapshot_id,
        resources=tuple(_remap_snapshot_references(resource, snapshot_ids) for resource in replayed.resources),
        resource_provenance=_remap_snapshot_references(replayed.resource_provenance, snapshot_ids),
        evidence_manifest=_remap_snapshot_references(replayed.evidence_manifest, snapshot_ids),
    )
    validate_media_replay_result(binding, captured)
    remaining()
    return binding, captured


def preview_media_replay(repo, source_revision_id, *, object_store, deadline_seconds=30):
    """Read one eligible retained source and produce a changed v3 projection."""
    if not 0 < deadline_seconds <= 30:
        raise ValueError("SOURCE_MEDIA_REPLAY_DEADLINE_INVALID")
    deadline = monotonic() + deadline_seconds
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(_replay, repo, source_revision_id, object_store, deadline).result(
            timeout=deadline_seconds,
        )
    except TimeoutError:
        raise ValueError("SOURCE_MEDIA_REPLAY_DEADLINE") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def reproject_media_source(repo, source_revision_id, *, object_store, deadline_seconds=30) -> CapturedSource:
    """Return only the new projection for callers that do not apply it."""
    return preview_media_replay(
        repo, source_revision_id, object_store=object_store, deadline_seconds=deadline_seconds,
    )[1]
