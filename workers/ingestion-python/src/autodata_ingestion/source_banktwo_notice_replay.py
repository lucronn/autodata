"""Rebuild an older Banktwo source with notices in their authored list positions."""

from dataclasses import replace
from time import monotonic

from psycopg.rows import dict_row

from .article_document import validate_ordered_document, walk_ordered_list_items
from .article_lifecycle_store import _remap_snapshot_references
from .article_lifecycle_types import BANKTWO_LIST_NOTICE_LAYOUT, digest_json
from .source_article_capture import capture_source_article, project_document, snapshot_id
from .source_job_persistence import source_bound_rewrite_source_allowed
from .source_media_replay import (
    _OfflineConnector, _VerifyOnlySink, _asset_inventory, _read_objects, _replay_fingerprint,
    load_media_replay_binding,
)
from .svg_rasterization import RASTERIZER_VERSION, SUPPORTED_RASTERIZER_VERSIONS


_LAYOUT = "banktwo_list_notice_layout"
_DECLARED_LAYOUT = {_LAYOUT: BANKTWO_LIST_NOTICE_LAYOUT}
_INVALID = "SOURCE_BANKTWO_NOTICE_REPLAY_BINDING_MISMATCH"
_DRIFT = "SOURCE_BANKTWO_NOTICE_REPLAY_CONTENT_DRIFT"


def load_banktwo_notice_binding(cur, source_revision_id, *, lock=False):
    binding = load_media_replay_binding(cur, source_revision_id, positioned_labels=True, ordinals=True, lock=lock)
    if (binding.context.key.provider != "banktwo"
            or binding.projection_version not in {"source-projection-v3", "source-projection-v5"}
            or binding.resource_manifest[0]["media_type"] not in {"text/html", "application/hal+json"}
            or _LAYOUT in binding.resource_manifest[0] or _LAYOUT in binding.resource_provenance[0]):
        raise ValueError("SOURCE_BANKTWO_NOTICE_REPLAY_UNSUPPORTED")
    return binding


def _payload(value):
    if isinstance(value, dict):
        return {key: _payload(item) for key, item in value.items() if key not in ("block_id", "source_order", "image_id")}
    if isinstance(value, list):
        return [_payload(item) for item in value]
    return value


def _numbered_items(document):
    for block in document["blocks"]:
        if block["type"] == "ordered_list":
            for default_number, (item, ordinal) in enumerate(walk_ordered_list_items(block), 1):
                yield default_number if ordinal is None else ordinal, _payload(item)


def validate_banktwo_notice_capture(binding, captured):
    manifest = ({**binding.resource_manifest[0], **_DECLARED_LAYOUT}, *binding.resource_manifest[1:])
    provenance = ({**binding.resource_provenance[0], **_DECLARED_LAYOUT}, *binding.resource_provenance[1:])
    if (captured.context != binding.context or captured.captured_at != binding.captured_at
            or captured.projection_version != "source-projection-v5" or captured.projection_status != "readable"
            or captured.body_source_snapshot_id != binding.body_source_snapshot_id
            or tuple(captured.resource_manifest) != manifest or tuple(captured.resource_provenance) != provenance
            or captured.resources != provenance or tuple(captured.evidence_manifest) != binding.evidence_manifest
            or captured.source_fingerprint != _replay_fingerprint(binding.context, manifest, provenance[0].get("asset_bindings"))
            or captured.source_fingerprint == binding.source_fingerprint):
        raise ValueError(_INVALID)
    before, after = binding.source_document, captured.source_document
    if (validate_ordered_document(after, strict=True)
            or {key: item for key, item in before.items() if key != "blocks"}
            != {key: item for key, item in after.items() if key != "blocks"}
            or list(_numbered_items(before)) != list(_numbered_items(after))
            or digest_json(after) == binding.source_document_hash
            or _asset_inventory(captured.source_images, provenance) != binding._source_assets
            or project_document(after) != (captured.source_body, captured.source_steps, captured.source_images)):
        raise ValueError(_DRIFT)


def _parse(binding, objects, remaining, *, preserve_notices):
    connector = _OfflineConnector("banktwo", binding.resource_provenance, objects)
    parsed = capture_source_article(
        binding.context, registry={"banktwo": connector}, object_store=_VerifyOnlySink(objects),
        deadline_seconds=remaining(), keep_banktwo_list_notices=preserve_notices,
        keep_html_headings=binding.projection_version == "source-projection-v5",
    )
    snapshots = {str(snapshot_id(row["sha256"])): row["source_snapshot_id"] for row in binding.resource_provenance}
    manifest = [dict(row) for row in parsed.resource_manifest]
    provenance = _remap_snapshot_references(parsed.resource_provenance, snapshots)
    resources = [_remap_snapshot_references(row, snapshots) for row in parsed.resources]
    for index, (saved, refreshed) in enumerate(zip(binding.resource_manifest, manifest, strict=True)):
        if (saved.get("derivation_version") in SUPPORTED_RASTERIZER_VERSIONS
                and refreshed.get("derivation_version") == RASTERIZER_VERSION and refreshed["sha256"] == saved["sha256"]):
            # The original converter label remains accurate for these identical bytes.
            for row in (manifest[index], provenance[index], resources[index]):
                row["derivation_version"] = saved["derivation_version"]
    document = _remap_snapshot_references(parsed.source_document, snapshots)
    body, steps, images = project_document(document)
    return replace(
        parsed, captured_at=binding.captured_at, body_source_snapshot_id=binding.body_source_snapshot_id,
        source_fingerprint=_replay_fingerprint(binding.context, manifest, provenance[0].get("asset_bindings")),
        resources=tuple(resources), resource_manifest=manifest, resource_provenance=provenance,
        evidence_manifest=_remap_snapshot_references(parsed.evidence_manifest, snapshots),
        source_document=document, source_body=body, source_steps=steps, source_images=images,
    )


def preview_banktwo_notice_replay(repo, source_revision_id, *, object_store):
    deadline = monotonic() + 30

    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError("SOURCE_BANKTWO_NOTICE_REPLAY_DEADLINE")
        return seconds

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='5s'")
        binding = load_banktwo_notice_binding(cur, source_revision_id)
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (binding.canonical_article_id,),
        ).fetchone()
        if (article is None or article["current_source_revision_id"] != source_revision_id
                or article["descriptor_source_snapshot_id"] != binding.context.descriptor_snapshot_id
                or not source_bound_rewrite_source_allowed(cur, article, source_revision_id)):
            raise ValueError("SOURCE_BANKTWO_NOTICE_REPLAY_STALE")

    verified = _read_objects(binding, object_store, remaining)
    previous = _parse(binding, verified, remaining, preserve_notices=False)
    if (digest_json(previous.source_document) != binding.source_document_hash
            or previous.source_fingerprint != binding.source_fingerprint
            or tuple(previous.resource_manifest) != binding.resource_manifest
            or tuple(previous.resource_provenance) != binding.resource_provenance
            or tuple(previous.evidence_manifest) != binding.evidence_manifest):
        raise ValueError(_DRIFT)
    corrected = _parse(binding, verified, remaining, preserve_notices=True)
    validate_banktwo_notice_capture(binding, corrected)
    remaining()
    return binding, corrected
