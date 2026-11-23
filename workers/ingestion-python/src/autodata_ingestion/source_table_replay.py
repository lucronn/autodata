"""Restore authored table spans from one retained, checksum-bound HTML body."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from psycopg.rows import dict_row

from .article_document import build_ordered_document, validate_ordered_document
from .article_lifecycle_types import CapturedSource, HTML_TABLE_SPAN_LAYOUT, SourceArticleContext, digest_json
from .banktwo_connector import ArticleParser
from .source_article_capture import snapshot_id
from .source_media_replay import (
    MEDIA_REPLAY_SOURCE_VERSIONS, _MAX_OBJECT_BYTES, _check_review_quarantine,
    _context, _load_snapshots, _replay_fingerprint, _resource_binding, _rows,
    _source_replay_row,
)


TABLE_REPLAY_PROJECTION_VERSION = "source-projection-v5"
_SPAN_FIELDS = frozenset({"rowspan", "colspan"})


@dataclass(frozen=True)
class TableReplayBinding:
    row: dict
    snapshots: tuple
    context: SourceArticleContext

    @property
    def canonical_article_id(self):
        return self.row["canonical_article_id"]

    @property
    def source_revision_id(self):
        return self.row["source_revision_id"]

    @property
    def source_observation_id(self):
        return self.row["source_observation_id"]

    @property
    def source_fingerprint(self):
        return self.row["source_fingerprint"]

    @property
    def body_sha256(self):
        return self.row["resource_manifest"][0]["sha256"]


def load_table_replay_binding(cur, source_revision_id, *, lock=False):
    row = _source_replay_row(cur, source_revision_id)
    if row is None or row["projection_version"] not in MEDIA_REPLAY_SOURCE_VERSIONS:
        raise ValueError("SOURCE_TABLE_REPLAY_UNSUPPORTED")
    if row["membership_status"] != "active" or row["takedown_status"] != "active":
        raise ValueError("SOURCE_TABLE_REPLAY_WITHDRAWN")
    context = _context(row)
    manifest = _rows(row["resource_manifest"])
    provenance = _rows(row["resource_provenance"])
    body_ids = _resource_binding(row, context, manifest, provenance, ordinals=False, table_spans=True)
    if (row["projection_status"] != ("readable" if len(manifest) == 1 else "partial")
            or any(image.get("status") != "unavailable" for image in _rows(row["source_images"]))
            or validate_ordered_document(row["source_document"], strict=True)):
        raise ValueError("SOURCE_TABLE_REPLAY_UNSUPPORTED")
    evidence = context.evidence_ids or ("source:" + str(snapshot_id(manifest[0]["sha256"])),)
    if row["evidence_manifest"] != [
        {"evidence_id": item, "body_source_snapshot_id": str(row["body_source_snapshot_id"])}
        for item in evidence
    ]:
        raise ValueError("SOURCE_TABLE_REPLAY_BINDING_MISMATCH")
    snapshots = _load_snapshots(
        cur, body_ids | {context.descriptor_snapshot_id, context.resolution_snapshot_id},
        resource_ids=body_ids, lock=lock,
    )
    body = provenance[0]
    snapshot = next(saved for saved in snapshots if saved.id == row["body_source_snapshot_id"])
    if (snapshot.digest != body["sha256"] or snapshot.object_key != body["object_key"]
            or snapshot.artifact_digest != body["sha256"] or snapshot.artifact_key != body["object_key"]
            or snapshot.media_type != body["media_type"]):
        raise ValueError("SOURCE_TABLE_REPLAY_BINDING_MISMATCH")
    _check_review_quarantine(
        cur, body_ids | {context.descriptor_snapshot_id, context.resolution_snapshot_id}, lock=lock,
    )
    return TableReplayBinding(row, snapshots, context)


def _tables(document):
    return [block for block in document["blocks"] if block.get("type") == "table"]


def _add_spans(original, parsed):
    """Only decorate an original cell when the parsed cell proves the same value."""
    if parsed == original:
        return original
    if isinstance(parsed, dict) and isinstance(original, str):
        spans = {key: parsed[key] for key in _SPAN_FIELDS if key in parsed}
        if (spans and parsed == {"text": original, **spans}
                and all(type(value) is int and 1 < value <= (65534 if key == "rowspan" else 1000)
                        for key, value in spans.items())):
            return {"text": original, **spans}
    raise ValueError("SOURCE_TABLE_REPLAY_CELL_DRIFT")


def restore_table_spans(document, payload):
    """Validate the entire retained table grid before changing any cell geometry."""
    parser = ArticleParser(keep_html_table_spans=True)
    try:
        parser.feed(payload.decode("utf-8-sig"))
        parser.close()
    except (UnicodeError, ValueError):
        raise ValueError("SOURCE_TABLE_REPLAY_INVALID_HTML") from None
    if not parser.html_table_spans:
        raise ValueError("SOURCE_TABLE_REPLAY_UNCHANGED")
    parsed_tables = _tables(build_ordered_document({}, parser.blocks))
    corrected = deepcopy(document)
    original_tables = _tables(corrected)
    if len(parsed_tables) != len(original_tables):
        raise ValueError("SOURCE_TABLE_REPLAY_TABLE_DRIFT")
    grids = {}
    for original, parsed in zip(original_tables, parsed_tables, strict=True):
        rows, parsed_rows = original["rows"], parsed["rows"]
        if (original.get("columns", []) != parsed.get("columns", [])
                or len(rows) != len(parsed_rows)
                or any(not isinstance(row, list) or len(row) != len(other)
                       for row, other in zip(rows, parsed_rows, strict=True))):
            raise ValueError("SOURCE_TABLE_REPLAY_TABLE_DRIFT")
        new_rows = [
            [_add_spans(cell, updated) for cell, updated in zip(row, parsed_row, strict=True)]
            for row, parsed_row in zip(rows, parsed_rows, strict=True)
        ]
        old_identity = digest_json((rows, original.get("columns", [])))
        # Repeated indistinguishable grids cannot prove different geometries.
        if grids.setdefault(old_identity, new_rows) != new_rows:
            raise ValueError("SOURCE_TABLE_REPLAY_AMBIGUOUS_TABLE")
        original["rows"] = new_rows
    if corrected == document:
        raise ValueError("SOURCE_TABLE_REPLAY_UNCHANGED")
    if validate_ordered_document(corrected, strict=True):
        raise ValueError("SOURCE_TABLE_REPLAY_DOCUMENT_INVALID")
    return corrected


def preview_table_replay(repo, source_revision_id, *, object_store, deadline_seconds=30):
    if not 0 < deadline_seconds <= 30:
        raise ValueError("SOURCE_TABLE_REPLAY_DEADLINE_INVALID")
    deadline = monotonic() + deadline_seconds
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(_replay, repo, source_revision_id, object_store, deadline).result(timeout=deadline_seconds)
    except TimeoutError:
        raise ValueError("SOURCE_TABLE_REPLAY_DEADLINE") from None
    finally:
        # A late read has no path to storage writes.
        pool.shutdown(wait=False, cancel_futures=True)


def _replay(repo, source_revision_id, object_store, deadline):
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")
        binding = load_table_replay_binding(cur, source_revision_id)
    row = binding.row
    manifest, provenance = deepcopy(row["resource_manifest"]), deepcopy(row["resource_provenance"])
    body, owner = manifest[0], provenance[0]
    if monotonic() >= deadline:
        raise ValueError("SOURCE_TABLE_REPLAY_DEADLINE")
    payload = object_store.get_object(owner["object_key"], max_bytes=_MAX_OBJECT_BYTES)
    if not isinstance(payload, bytes) or len(payload) > _MAX_OBJECT_BYTES or sha256(payload).hexdigest() != body["sha256"]:
        raise ValueError("SOURCE_TABLE_REPLAY_BODY_MISMATCH")
    document = restore_table_spans(row["source_document"], payload)
    if monotonic() >= deadline:
        raise ValueError("SOURCE_TABLE_REPLAY_DEADLINE")
    body["html_table_span_layout"] = owner["html_table_span_layout"] = HTML_TABLE_SPAN_LAYOUT
    context = binding.context
    captured = CapturedSource(
        context, _replay_fingerprint(context, manifest), row["body_source_snapshot_id"],
        (owner,), manifest, provenance, document, row["source_images"], row["source_body"],
        row["source_steps"], row["evidence_manifest"], row["projection_status"], row["captured_at"],
        projection_version=TABLE_REPLAY_PROJECTION_VERSION,
    )
    return binding, captured
