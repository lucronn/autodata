"""Restore verified raster derivatives to retained, unsupported SVG slots."""

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from time import monotonic

from psycopg.rows import dict_row

from .article_document import validate_ordered_document
from .article_lifecycle_types import CapturedSource, HTML_TABLE_SPAN_LAYOUT, digest_json
from .source_article_capture import _image_nodes, snapshot_id, upload_resource
from .source_connector_client import SourceConnectorError, SourceEnvelopeV1, _safe_locator
from .source_media_replay import (
    _DERIVATION_FIELDS, _MANIFEST_FIELDS, _MAX_OBJECT_BYTES, _MAX_RESOURCES, _MAX_TOTAL_BYTES,
    _check_review_quarantine, _key, _load_snapshots, _replay_fingerprint, _source_ref, _uuid,
)
from .source_table_replay import TABLE_REPLAY_PROJECTION_VERSION, load_table_replay_binding, restore_table_spans
from .svg_rasterization import MAX_INPUT_BYTES, RASTERIZER_VERSION, rasterize_svg


_UNSUPPORTED = "UNSUPPORTED_ASSET_MEDIA"
_LEGACY_MISSING = "source image reference is missing"
_SVG_MEDIA = "image/svg+xml"


class _StagedBlobs:
    def __init__(self, body_size):
        self.data = {}
        self.total = body_size

    def put_object(self, key, payload, media_type):
        previous = self.data.get(key)
        if previous is not None:
            if previous != (payload, media_type):
                raise ValueError("SOURCE_SVG_RECOVERY_OBJECT_MISMATCH")
            return
        self.total += len(payload)
        if self.total > _MAX_TOTAL_BYTES:
            raise ValueError("SOURCE_SVG_RECOVERY_OBJECT_LIMIT")
        self.data[key] = (payload, media_type)


def check_svg_recovery_rights(cur, captured, *, lock=False, require_existing=False):
    """Recheck existing content-addressed owners, including after persistence."""
    expected = {
        resource["sha256"]: resource for resource in captured.resources
        if resource["role"] == "asset_original" or "derived_from_sha256" in resource
    }
    if not expected:
        raise ValueError("SOURCE_SVG_RECOVERY_BINDING_MISMATCH")
    rows = cur.execute(
        "SELECT source_snapshot_id FROM source_snapshots WHERE content_sha256 = ANY(%s)",
        (sorted(expected),),
    ).fetchall()
    ids = {row["source_snapshot_id"] for row in rows}
    if require_existing and len(ids) != len(expected):
        raise ValueError("SOURCE_SVG_RECOVERY_BINDING_MISMATCH")
    if ids:
        snapshots = _load_snapshots(cur, ids, resource_ids=ids, lock=lock)
        _check_review_quarantine(cur, ids, lock=lock)
        for snapshot in snapshots:
            resource = expected.get(snapshot.digest)
            if (resource is None or snapshot.object_key != resource["object_key"]
                    or snapshot.artifact_digest != resource["sha256"]
                    or snapshot.artifact_key != resource["object_key"]
                    or snapshot.media_type != resource["media_type"]):
                raise ValueError("SOURCE_SVG_RECOVERY_BINDING_MISMATCH")


def _bound_images(nodes, identifiers):
    identifiers = set(identifiers)
    found = {}
    for node in nodes:
        image_id = node.get("image_id")
        if not isinstance(image_id, str) or image_id not in identifiers:
            if node.get("unavailable_reason") == _UNSUPPORTED:
                raise ValueError("SOURCE_SVG_RECOVERY_BINDING_MISMATCH")
            continue
        # Older document builders lost the failure code even when the manifest retained it.
        if (image_id in found or node.get("status") != "unavailable"
                or node.get("unavailable_reason") not in (_UNSUPPORTED, _LEGACY_MISSING)
                or node.get("asset_id") != image_id
                or any(node.get(field) for field in (
                    "storage_key", "content_sha256", "url", "src", "href", "uri", "path", "asset_resource_ref",
                ))):
            raise ValueError("SOURCE_SVG_RECOVERY_BINDING_MISMATCH")
        found[image_id] = node
    if found.keys() != identifiers:
        raise ValueError("SOURCE_SVG_RECOVERY_BINDING_MISMATCH")
    return found


def _verify_asset(envelope, provider):
    if (not isinstance(envelope, SourceEnvelopeV1) or envelope.provider != provider
            or not isinstance(envelope.body, Mapping) or "asset_bindings" in envelope.body
            or envelope.body.get("kind") not in {"asset", "binary"}
            or envelope.body.get("media_type") != _SVG_MEDIA
            or not isinstance(envelope.raw_resource, bytes)
            or not 0 < len(envelope.raw_resource) <= MAX_INPUT_BYTES):
        raise ValueError("SOURCE_SVG_RECOVERY_ASSET_INVALID")
    try:
        _uuid(envelope.request_id)
        _source_ref(envelope.source_revision, 256)
        locator = _source_ref(envelope.source_locator or envelope.resource_uri)
        if (not _safe_locator(locator) or datetime.fromisoformat(envelope.fetched_at).utcoffset() is None
                or sha256(envelope.raw_resource).hexdigest() != envelope.body.get("sha256")):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("SOURCE_SVG_RECOVERY_ASSET_INVALID") from None


def _asset_resources(ref, envelope, blobs, remaining):
    try:
        original = upload_resource(envelope, ref, "asset_original", blobs)
    except SourceConnectorError:
        raise ValueError("SOURCE_SVG_RECOVERY_ASSET_INVALID") from None
    png = rasterize_svg(envelope.raw_resource, timeout=remaining())
    digest = sha256(png).hexdigest()
    key = _key(digest)
    blobs.put_object(key, png, "image/png")
    derivative = {
        **original, "role": "asset", "media_type": "image/png", "sha256": digest,
        "object_key": key, "source_snapshot_id": str(snapshot_id(digest)),
        "derived_from_sha256": original["sha256"], "derivation_version": RASTERIZER_VERSION,
    }
    return original, derivative


def build_svg_recovery(repo, source_revision_id, *, object_store, assets):
    """Return an exact retained binding, repaired projection, and staged blobs."""
    deadline = monotonic() + 30
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(_build, repo, source_revision_id, object_store, assets, deadline).result(timeout=30)
    except TimeoutError:
        raise ValueError("SOURCE_SVG_RECOVERY_DEADLINE") from None
    finally:
        # A late read or rasterization has no path to storage writes.
        pool.shutdown(wait=False, cancel_futures=True)


def _build(repo, source_revision_id, object_store, assets, deadline):
    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError("SOURCE_SVG_RECOVERY_DEADLINE")
        return seconds

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")
        binding = load_table_replay_binding(cur, source_revision_id)
    row = binding.row
    old_manifest, old_provenance = row["resource_manifest"], row["resource_provenance"]
    refs = {entry["opaque_ref"] for entry in old_manifest[1:] if entry["failure_code"] == _UNSUPPORTED}
    if (not refs or not isinstance(assets, Mapping) or assets.keys() != refs
            or len(old_manifest) + len(refs) > _MAX_RESOURCES):
        raise ValueError("SOURCE_SVG_RECOVERY_BINDING_MISMATCH")
    provider = binding.context.key.provider
    identifiers = {ref: digest_json({"provider": provider, "ref": ref}) for ref in refs}
    for envelope in assets.values():
        _verify_asset(envelope, provider)

    remaining()
    body, owner = deepcopy((old_manifest[0], old_provenance[0]))
    payload = object_store.get_object(owner["object_key"], max_bytes=_MAX_OBJECT_BYTES)
    if not isinstance(payload, bytes) or len(payload) > _MAX_OBJECT_BYTES or sha256(payload).hexdigest() != body["sha256"]:
        raise ValueError("SOURCE_SVG_RECOVERY_BODY_MISMATCH")
    try:
        document = restore_table_spans(row["source_document"], payload)
    except ValueError as error:
        if str(error) != "SOURCE_TABLE_REPLAY_UNCHANGED":
            raise
        document = deepcopy(row["source_document"])
    else:
        body["html_table_span_layout"] = owner["html_table_span_layout"] = HTML_TABLE_SPAN_LAYOUT
    images = deepcopy(row["source_images"])
    targets = _bound_images(_image_nodes(document["blocks"]), identifiers.values())
    projected = _bound_images(images, identifiers.values())
    if targets != projected:
        raise ValueError("SOURCE_SVG_RECOVERY_BINDING_MISMATCH")

    manifest, provenance, resources = [body], [owner], [owner]
    blobs = _StagedBlobs(len(payload))
    for entry, failed_owner in zip(old_manifest[1:], old_provenance[1:], strict=True):
        ref = entry["opaque_ref"]
        if ref not in refs:
            manifest.append(deepcopy(entry))
            provenance.append(deepcopy(failed_owner))
            continue
        original, derivative = _asset_resources(ref, assets[ref], blobs, remaining)
        resources.extend((original, derivative))
        provenance.extend((original, derivative))
        manifest.append({field: original[field] for field in _MANIFEST_FIELDS})
        manifest.append({field: derivative[field] for field in _MANIFEST_FIELDS | _DERIVATION_FIELDS})
        digest, key = derivative["sha256"], derivative["object_key"]
        for node in (targets[identifiers[ref]], projected[identifiers[ref]]):
            del node["unavailable_reason"]
            node.update(
                status="available", media_type="image/png", image_id=digest, content_sha256=digest,
                asset_id=key, storage_key=key,
            )

    if validate_ordered_document(document, strict=True):
        raise ValueError("SOURCE_SVG_RECOVERY_DOCUMENT_INVALID")
    partial = any("failure_code" in entry for entry in manifest) or any(
        image.get("status") == "unavailable" for image in images
    )
    captured = CapturedSource(
        binding.context, _replay_fingerprint(binding.context, manifest), row["body_source_snapshot_id"],
        tuple(resources), manifest, provenance, document, images, row["source_body"], row["source_steps"],
        row["evidence_manifest"], "partial" if partial else "readable", row["captured_at"],
        projection_version=TABLE_REPLAY_PROJECTION_VERSION,
    )
    remaining()
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")
        check_svg_recovery_rights(cur, captured)
    return binding, captured, blobs.data
