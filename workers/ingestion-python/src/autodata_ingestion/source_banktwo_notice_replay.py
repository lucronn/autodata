"""Rebuild an older Banktwo source with notices in their authored list positions."""

from time import monotonic

from psycopg.rows import dict_row

from .article_document import validate_ordered_document, walk_ordered_list_items
from .article_lifecycle_types import BANKTWO_LIST_NOTICE_LAYOUT, digest_json
from .source_article_capture import project_document
from .source_job_persistence import source_bound_rewrite_source_allowed
from .source_media_replay import (
    _asset_inventory, _capture_retained_layout, _read_objects, _validate_retained_layout_binding,
    load_media_replay_binding,
)


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
    try:
        _validate_retained_layout_binding(binding, captured, _DECLARED_LAYOUT)
    except ValueError:
        raise ValueError(_INVALID) from None
    before, after = binding.source_document, captured.source_document
    provenance = tuple(captured.resource_provenance)
    if (validate_ordered_document(after, strict=True)
            or {key: item for key, item in before.items() if key != "blocks"}
            != {key: item for key, item in after.items() if key != "blocks"}
            or list(_numbered_items(before)) != list(_numbered_items(after))
            or digest_json(after) == binding.source_document_hash
            or _asset_inventory(captured.source_images, provenance) != binding._source_assets
            or project_document(after) != (captured.source_body, captured.source_steps, captured.source_images)):
        raise ValueError(_DRIFT)


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
    options = {"keep_html_headings": binding.projection_version == "source-projection-v5"}
    previous = _capture_retained_layout(binding, verified, remaining, **options)
    if (digest_json(previous.source_document) != binding.source_document_hash
            or previous.source_fingerprint != binding.source_fingerprint
            or tuple(previous.resource_manifest) != binding.resource_manifest
            or tuple(previous.resource_provenance) != binding.resource_provenance
            or tuple(previous.evidence_manifest) != binding.evidence_manifest):
        raise ValueError(_DRIFT)
    corrected = _capture_retained_layout(binding, verified, remaining, **options, keep_banktwo_list_notices=True)
    validate_banktwo_notice_capture(binding, corrected)
    remaining()
    return binding, corrected
