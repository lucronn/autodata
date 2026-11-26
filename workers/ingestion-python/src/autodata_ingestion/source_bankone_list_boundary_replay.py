"""Restore authored list boundaries in retained Bankone HTML."""

from collections import Counter
from time import monotonic

from psycopg.rows import dict_row

from .article_document import validate_ordered_document
from .article_lifecycle_types import BANKONE_LIST_BOUNDARY_LAYOUT, digest_json
from .source_article_capture import project_document
from .source_bankone_order_replay import _without_generated_ids, load_bankone_order_binding
from .source_job_persistence import source_bound_rewrite_source_allowed
from .source_media_replay import _asset_inventory, _capture_retained_layout, _read_objects, _validate_retained_layout_binding

_LAYOUT = {"bankone_list_boundary_layout": BANKONE_LIST_BOUNDARY_LAYOUT}
_DRIFT = "SOURCE_BANKONE_LIST_BOUNDARY_REPLAY_CONTENT_DRIFT"


def load_bankone_list_boundary_binding(cur, source_revision_id, *, lock=False):
    return load_bankone_order_binding(
        cur, source_revision_id, lock=lock, has_positioned_flow=True, has_document_links=True,
    )


def _non_list_content(blocks):
    for block in blocks:
        if block["type"] not in {"ordered_list", "unordered_list"}:
            yield digest_json(_without_generated_ids(block))
            continue
        for item in block["items"]:
            if isinstance(item, str):
                yield digest_json({"text": item})
                continue
            if set(item) - {"text", "number", "blocks"}:
                raise ValueError(_DRIFT)
            text = item.get("text")
            if text or item.get("number") is not None:
                fields = {key: item[key] for key in ("text", "number") if key in item}
                yield digest_json(fields)
            yield from _non_list_content(item.get("blocks", []))


def validate_bankone_list_boundary_capture(binding, captured):
    _validate_retained_layout_binding(binding, captured, _LAYOUT)
    before, after = binding.source_document, captured.source_document
    if (before == after or validate_ordered_document(after, strict=True)
            or {key: value for key, value in before.items() if key != "blocks"}
            != {key: value for key, value in after.items() if key != "blocks"}
            or Counter(_non_list_content(before["blocks"])) != Counter(_non_list_content(after["blocks"]))
            or _without_generated_ids(project_document(before)[2]) != _without_generated_ids(captured.source_images)
            or _asset_inventory(captured.source_images, captured.resource_provenance) != binding._source_assets
            or project_document(after) != (captured.source_body, captured.source_steps, captured.source_images)):
        raise ValueError(_DRIFT)


def preview_bankone_list_boundary_replay(repo, source_revision_id, *, object_store):
    deadline = monotonic() + 30

    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError("SOURCE_BANKONE_LIST_BOUNDARY_REPLAY_DEADLINE")
        return seconds

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='5s'")
        binding = load_bankone_list_boundary_binding(cur, source_revision_id)
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (binding.canonical_article_id,),
        ).fetchone()
        if (article is None or article["descriptor_source_snapshot_id"] != binding.context.descriptor_snapshot_id
                or not source_bound_rewrite_source_allowed(cur, article, source_revision_id)):
            raise ValueError("SOURCE_BANKONE_LIST_BOUNDARY_REPLAY_STALE")

    verified = _read_objects(binding, object_store, remaining)
    options = dict(keep_html_headings=True, keep_bankone_html_flow=True, keep_html_document_links=True)
    legacy = _capture_retained_layout(binding, verified, remaining, **options)
    if (legacy.source_document != binding.source_document or legacy.source_fingerprint != binding.source_fingerprint
            or tuple(legacy.resource_manifest) != binding.resource_manifest
            or tuple(legacy.resource_provenance) != binding.resource_provenance
            or tuple(legacy.evidence_manifest) != binding.evidence_manifest):
        raise ValueError(_DRIFT)
    corrected = _capture_retained_layout(binding, verified, remaining, **options, keep_bankone_list_boundaries=True)
    validate_bankone_list_boundary_capture(binding, corrected)
    remaining()
    return binding, corrected
