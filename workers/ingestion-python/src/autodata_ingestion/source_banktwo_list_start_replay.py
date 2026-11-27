"""Restore supplier list starts without changing the retained procedure body."""

from time import monotonic

from psycopg.rows import dict_row

from .article_document import has_only_list_ordinal_additions, validate_ordered_document
from .article_lifecycle_types import BANKTWO_DOTTED_LIST_START_LAYOUT
from .source_article_capture import project_document
from .source_job_persistence import source_bound_rewrite_source_allowed
from .source_media_replay import (
    _BANKTWO_LIST_START_LAYOUTS,
    _asset_inventory,
    _capture_retained_layout,
    _read_objects,
    _validate_retained_layout_binding,
    load_media_replay_binding,
)


_LAYOUT = {"banktwo_dotted_list_start_layout": BANKTWO_DOTTED_LIST_START_LAYOUT}
_DRIFT = "SOURCE_BANKTWO_LIST_START_REPLAY_CONTENT_DRIFT"


def load_banktwo_list_start_binding(cur, source_revision_id, *, lock=False):
    binding = load_media_replay_binding(cur, source_revision_id, lock=lock, ordinals=True, banktwo_list_starts=True)
    if binding.projection_version != "source-projection-v5":
        raise ValueError("SOURCE_BANKTWO_LIST_START_REPLAY_UNSUPPORTED")
    return binding


def validate_banktwo_list_start_capture(binding, captured):
    _validate_retained_layout_binding(binding, captured, _LAYOUT)
    if (
        validate_ordered_document(captured.source_document, strict=True)
        or not has_only_list_ordinal_additions(binding.source_document, captured.source_document)
        or _asset_inventory(captured.source_images, captured.resource_provenance) != binding._source_assets
        or project_document(captured.source_document) != (captured.source_body, captured.source_steps, captured.source_images)
    ):
        raise ValueError(_DRIFT)


def preview_banktwo_list_start_replay(repo, source_revision_id, *, object_store):
    deadline = monotonic() + 30

    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError("SOURCE_BANKTWO_LIST_START_REPLAY_DEADLINE")
        return seconds

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='5s'")
        binding = load_banktwo_list_start_binding(cur, source_revision_id)
        article = cur.execute(
            "SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (binding.canonical_article_id,),
        ).fetchone()
        if (article is None or article["current_source_revision_id"] != source_revision_id
                or article["descriptor_source_snapshot_id"] != binding.context.descriptor_snapshot_id
                or not source_bound_rewrite_source_allowed(cur, article, source_revision_id)):
            raise ValueError("SOURCE_BANKTWO_LIST_START_REPLAY_STALE")

    verified = _read_objects(binding, object_store, remaining)
    options = {
        option: binding.resource_manifest[0].get(layout) == version
        for layout, (version, option) in _BANKTWO_LIST_START_LAYOUTS.items()
    }
    options["keep_html_headings"] = True
    previous = _capture_retained_layout(binding, verified, remaining, **options)
    if (
        previous.source_document != binding.source_document
        or previous.source_fingerprint != binding.source_fingerprint
        or tuple(previous.resource_manifest) != binding.resource_manifest
        or tuple(previous.resource_provenance) != binding.resource_provenance
        or tuple(previous.evidence_manifest) != binding.evidence_manifest
    ):
        raise ValueError(_DRIFT)
    corrected = _capture_retained_layout(binding, verified, remaining, **options, keep_banktwo_dotted_list_starts=True)
    validate_banktwo_list_start_capture(binding, corrected)
    remaining()
    return binding, corrected
