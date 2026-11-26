"""Reproject separately authored Bankone definition headings from stored HTML."""

from time import monotonic

from psycopg.rows import dict_row

from .article_document import validate_ordered_document
from .article_lifecycle_types import BANKONE_DEFINITION_HEADING_LAYOUT
from .source_article_capture import project_document
from .source_bankone_order_replay import _without_generated_ids, load_bankone_order_binding
from .source_job_persistence import source_bound_rewrite_source_allowed
from .source_media_replay import _asset_inventory, _capture_retained_layout, _read_objects, _validate_retained_layout_binding

_LAYOUT = {"bankone_definition_heading_layout": BANKONE_DEFINITION_HEADING_LAYOUT}
_DRIFT = "SOURCE_BANKONE_DEFINITION_HEADING_REPLAY_CONTENT_DRIFT"


def load_bankone_definition_heading_binding(cur, source_revision_id, *, lock=False):
    return load_bankone_order_binding(cur, source_revision_id, lock=lock, has_positioned_flow=True)


def validate_bankone_definition_heading_capture(binding, captured):
    _validate_retained_layout_binding(binding, captured, _LAYOUT)
    before, after = binding.source_document, captured.source_document
    if (validate_ordered_document(after, strict=True)
            or {key: item for key, item in before.items() if key != "blocks"}
            != {key: item for key, item in after.items() if key != "blocks"}
            or _asset_inventory(captured.source_images, captured.resource_provenance) != binding._source_assets
            or project_document(after) != (captured.source_body, captured.source_steps, captured.source_images)):
        raise ValueError(_DRIFT)

    old = _without_generated_ids(before["blocks"])
    new = _without_generated_ids(after["blocks"])
    if len(new) != len(old) + 1:
        raise ValueError(_DRIFT)
    for position, prior in enumerate(old):
        if prior == new[position]:
            continue
        term, title = new[position:position+2]
        if (prior["type"] != "paragraph"
                or prior.get("text") not in (term.get("text", "") + title.get("text", ""),
                    term.get("text", "") + " " + title.get("text", ""))
                or term != {**prior, "type": "heading", "level": 2, "text": term.get("text")}
                or title != {**prior, "type": "heading", "level": 3, "text": title.get("text")}
                or old[position+1:] != new[position+2:]):
            raise ValueError(_DRIFT)
        return
    raise ValueError(_DRIFT)


def preview_bankone_definition_heading_replay(repo, source_revision_id, *, object_store):
    deadline = monotonic() + 30

    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError("SOURCE_BANKONE_DEFINITION_HEADING_REPLAY_DEADLINE")
        return seconds

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='5s'")
        binding = load_bankone_definition_heading_binding(cur, source_revision_id)
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (binding.canonical_article_id,),
        ).fetchone()
        if (article is None or article["descriptor_source_snapshot_id"] != binding.context.descriptor_snapshot_id
                or not source_bound_rewrite_source_allowed(cur, article, source_revision_id)):
            raise ValueError("SOURCE_BANKONE_DEFINITION_HEADING_REPLAY_STALE")

    verified = _read_objects(binding, object_store, remaining)
    options = dict(keep_html_headings=True, keep_bankone_html_flow=True, keep_html_table_spans=True)
    legacy = _capture_retained_layout(binding, verified, remaining, **options)
    if (legacy.source_document != binding.source_document or legacy.source_fingerprint != binding.source_fingerprint
            or tuple(legacy.resource_manifest) != binding.resource_manifest
            or tuple(legacy.resource_provenance) != binding.resource_provenance
            or tuple(legacy.evidence_manifest) != binding.evidence_manifest):
        raise ValueError(_DRIFT)
    corrected = _capture_retained_layout(binding, verified, remaining, **options, keep_bankone_definition_headings=True)
    validate_bankone_definition_heading_capture(binding, corrected)
    remaining()
    return binding, corrected
