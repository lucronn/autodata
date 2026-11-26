"""Restore positioned labels from the same verified body and image bytes."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import replace
import math
from time import monotonic

from psycopg.rows import dict_row

from .article_document import validate_ordered_document
from .article_lifecycle_store import _remap_snapshot_references
from .article_lifecycle_types import CapturedSource, LEADING_DECIMAL_LAYOUT
from .positioned_figure import FIGURE_LABEL_LAYOUT
from .source_article_capture import WORKSHOP_CAPTURE_OPTIONS, capture_source_article, snapshot_id
from .source_media_replay import (
    _OfflineConnector, _VerifyOnlySink, _asset_inventory, _context, _read_objects, _replay_fingerprint,
    _source_replay_row,
    load_media_replay_binding, media_replay_document_hash,
)


_LAYOUT_KEY = "html_positioned_figure_layout"


def validate_positioned_figure_replay(binding, captured):
    manifest = ({**binding.resource_manifest[0], _LAYOUT_KEY: FIGURE_LABEL_LAYOUT}, *binding.resource_manifest[1:])
    provenance = ({**binding.resource_provenance[0], _LAYOUT_KEY: FIGURE_LABEL_LAYOUT}, *binding.resource_provenance[1:])
    # Decimal text can move out of the paragraph parser with its diagram label.
    if (manifest[0].get("leading_decimal_layout") == LEADING_DECIMAL_LAYOUT
            and "leading_decimal_layout" not in captured.resource_manifest[0]):
        del manifest[0]["leading_decimal_layout"]
        del provenance[0]["leading_decimal_layout"]
    if (captured.context != binding.context or captured.body_source_snapshot_id != binding.body_source_snapshot_id
            or captured.captured_at != binding.captured_at or captured.projection_status != "readable"
            or tuple(captured.resource_manifest) != manifest or tuple(captured.resource_provenance) != provenance
            or captured.resources != provenance or tuple(captured.evidence_manifest) != binding.evidence_manifest
            or captured.source_fingerprint != _replay_fingerprint(binding.context, manifest, provenance[0].get("asset_bindings"))
            or media_replay_document_hash(captured) == binding.source_document_hash
            or _asset_inventory(captured.source_images, provenance) != binding._source_assets
            or validate_ordered_document(captured.source_document, strict=True)):
        raise ValueError("SOURCE_FIGURE_LABEL_REPLAY_MISMATCH")


def verify_stored_positioned_figure_replay(cur, previous_id, source_id, *, lock):
    binding = load_media_replay_binding(cur, previous_id, lock=lock, positioned_labels=True)
    row = _source_replay_row(cur, source_id)
    if (row is None or row["canonical_article_id"] != binding.canonical_article_id
            or row["projection_version"] != "source-projection-v5"):
        raise ValueError("SOURCE_FIGURE_LABEL_REPLAY_MISMATCH")
    captured = CapturedSource(
        _context(row), row["source_fingerprint"], row["body_source_snapshot_id"],
        tuple(row["resource_provenance"]), row["resource_manifest"], row["resource_provenance"],
        row["source_document"], row["source_images"], row["source_body"], row["source_steps"],
        row["evidence_manifest"], row["projection_status"], row["captured_at"],
        projection_version=row["projection_version"],
    )
    validate_positioned_figure_replay(binding, captured)
    return binding, captured, (row["source_observation_id"], row["source_fetch_job_id"], row["request_generation"])


def _replay(repo, source_revision_id, object_store, deadline):
    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError("SOURCE_FIGURE_LABEL_REPLAY_DEADLINE")
        return seconds

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        binding = load_media_replay_binding(cur, source_revision_id, positioned_labels=True)
    verified = _read_objects(binding, object_store, remaining)
    snapshot_ids = {str(snapshot_id(item["sha256"])): item["source_snapshot_id"] for item in binding.resource_provenance}

    def capture(keep_labels):
        client = _OfflineConnector(binding.context.key.provider, binding.resource_provenance, verified)
        captured = capture_source_article(
            binding.context, registry={client.provider: client}, object_store=_VerifyOnlySink(verified),
            deadline_seconds=remaining(), **{**WORKSHOP_CAPTURE_OPTIONS, "keep_positioned_figure_labels": keep_labels},
        )
        return replace(
            captured, captured_at=binding.captured_at, body_source_snapshot_id=binding.body_source_snapshot_id,
            resources=tuple(_remap_snapshot_references(item, snapshot_ids) for item in captured.resources),
            resource_provenance=_remap_snapshot_references(captured.resource_provenance, snapshot_ids),
            evidence_manifest=_remap_snapshot_references(captured.evidence_manifest, snapshot_ids),
            source_document=_remap_snapshot_references(captured.source_document, snapshot_ids),
        )

    baseline = capture(False)
    if (media_replay_document_hash(baseline) != binding.source_document_hash
            or baseline.source_fingerprint != binding.source_fingerprint
            or tuple(baseline.resource_provenance) != binding.resource_provenance):
        raise ValueError("SOURCE_FIGURE_LABEL_REPLAY_BASELINE_CHANGED")
    corrected = capture(True)
    validate_positioned_figure_replay(binding, corrected)
    remaining()
    return binding, corrected


def preview_positioned_figure_replay(repo, source_revision_id, *, object_store, deadline_seconds=30):
    if (type(deadline_seconds) not in (int, float) or not math.isfinite(deadline_seconds)
            or not 0 < deadline_seconds <= 30):
        raise ValueError("SOURCE_FIGURE_LABEL_REPLAY_DEADLINE_INVALID")
    deadline = monotonic() + deadline_seconds
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(_replay, repo, source_revision_id, object_store, deadline).result(timeout=deadline_seconds)
    except TimeoutError:
        raise ValueError("SOURCE_FIGURE_LABEL_REPLAY_DEADLINE") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
