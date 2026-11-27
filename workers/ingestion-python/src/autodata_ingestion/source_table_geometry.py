"""Recover table geometry from archived supplier HTML without rewriting cells."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import re
from time import monotonic

from psycopg.rows import dict_row

from .article_document import build_ordered_document, validate_ordered_document
from .article_lifecycle_types import (
    CapturedSource, HTML_TABLE_CELL_HEADER_LAYOUT, HTML_TABLE_SPAN_LAYOUT, SOURCE_PROJECTION_VERSIONS,
)
from .banktwo_connector import ArticleParser
from .source_adapters import SourceResource, adapt_bound_article
from .source_article_capture import project_document
from .source_media_replay import (
    _MAX_OBJECT_BYTES, _check_review_quarantine, _context, _key, _load_snapshots, _replay_fingerprint,
    _rows, _source_replay_row, _uuid,
)
from .source_table_replay import TableReplayBinding


_SPANS = {"rowspan": 65_534, "colspan": 1_000}
_SCOPES = {"row", "col", "rowgroup", "colgroup"}
_GEOMETRY = {"table_header", "header_scope", *_SPANS}
_OPTIONS = {
    "keep_html_table_cell_headers": True, "keep_html_table_spans": True, "keep_html_nested_tables": True,
    "keep_html_table_captions": True, "keep_html_media_table_headers": True,
}
TABLE_GEOMETRY_PROJECTION_VERSION = "source-projection-v5"


def _cells(row):
    return row if isinstance(row, list) else row["cells"]


def _tables(blocks):
    for block in blocks:
        if block["type"] == "table":
            columns = block.get("columns") or []
            rows = [(True, columns)] if columns else []
            rows.extend((False, _cells(row)) for row in block["rows"])
            yield rows
            for _, cells in rows:
                for cell in cells:
                    if isinstance(cell, dict):
                        yield from _tables(cell.get("blocks") or [])
        elif block["type"] in {"ordered_list", "unordered_list"}:
            for item in block["items"]:
                if isinstance(item, dict):
                    yield from _tables(item.get("blocks") or [])


def _cell_text(value):
    if isinstance(value, str):
        return value
    if value.get("type") in {"image", "table"}:
        return ""
    parts = [value.get(field) for field in ("label", "text", "action", "caption")]
    parts.extend(value.get("instructions") or [])
    parts.extend(_cell_text(child) for field in ("blocks", "items") for child in value.get(field) or [])
    return " ".join(part for part in parts if isinstance(part, str) and part)


def _normalized_text(cell):
    return re.sub(r"\s+", " ", _cell_text(cell)).strip()


def _as_cell(value):
    return {"text": value} if isinstance(value, str) else value


def _geometry(cell):
    return {key: cell[key] for key in _GEOMETRY if key in cell}


def _valid_geometry(fields, *, existing):
    if any(type(fields[name]) is not int or not 1 < fields[name] <= maximum
           for name, maximum in _SPANS.items() if name in fields):
        return False
    if "table_header" in fields and fields["table_header"] is not True:
        return False
    if "header_scope" in fields:
        return fields["header_scope"] in _SCOPES and (fields.get("table_header") or existing.get("table_header")) is True
    return True


def _aligned_cells(before, after):
    previous = list(_tables(before["blocks"]))
    current = list(_tables(after["blocks"]))
    if len(previous) != len(current):
        raise ValueError("SOURCE_TABLE_GEOMETRY_TABLE_DRIFT")
    for old_rows, new_rows in zip(previous, current, strict=True):
        if [len(cells) for _, cells in old_rows] != [len(cells) for _, cells in new_rows]:
            raise ValueError("SOURCE_TABLE_GEOMETRY_ROW_DRIFT")
        for (old_columns, old_cells), (new_columns, new_cells) in zip(old_rows, new_rows, strict=True):
            yield old_columns, old_cells, new_columns, new_cells


def restore_table_geometry(document, markup):
    """Join every source cell to its stored position before adding typed fields."""
    parser = ArticleParser(**_OPTIONS)
    parser.feed(markup)
    parser.close()
    return _restore_from_blocks(document, parser.blocks)


def _restore_from_blocks(document, blocks):
    projected = build_ordered_document({}, blocks, preserve_marked_cells=True, preserve_structured_columns=True)
    restored = deepcopy(document)
    for before_columns, before, after_columns, after in _aligned_cells(restored, projected):
        previous_text = tuple(map(_normalized_text, before))
        if previous_text != tuple(map(_normalized_text, after)):
            raise ValueError("SOURCE_TABLE_GEOMETRY_CELL_DRIFT")
        for index, (stored, candidate) in enumerate(zip(before, after, strict=True)):
            original = _as_cell(stored)
            upcoming = _geometry(_as_cell(candidate))
            retained = _geometry(original)
            if any(upcoming.get(key) != value for key, value in retained.items()):
                raise ValueError("SOURCE_TABLE_GEOMETRY_EXISTING_ROLE_DRIFT")
            if before_columns:
                upcoming = {key: value for key, value in upcoming.items() if key not in {"table_header", "header_scope"}}
            elif after_columns and "table_header" not in upcoming:
                raise ValueError("SOURCE_TABLE_GEOMETRY_UNPROVED_HEADER")
            extra = {key: value for key, value in upcoming.items() if key not in retained}
            if not _valid_geometry(extra, existing=retained):
                raise ValueError("SOURCE_TABLE_GEOMETRY_INVALID_ROLE")
            if extra:
                before[index] = {**original, **extra}
    if restored == document:
        raise ValueError("SOURCE_TABLE_GEOMETRY_UNCHANGED")
    if not has_only_table_geometry_additions(document, restored) or validate_ordered_document(restored, strict=True):
        raise ValueError("SOURCE_TABLE_GEOMETRY_DOCUMENT_INVALID")
    return restored


def has_only_table_geometry_additions(before, after):
    """Check that removing valid cell geometry additions yields the same document."""
    original = deepcopy(after)
    changed = False
    try:
        # Restore nested cells first so the enclosing cell can match exactly.
        for _, previous, _, current in reversed(list(_aligned_cells(before, original))):
            for index, (old_cell, new_cell) in enumerate(zip(previous, current, strict=True)):
                if old_cell == new_cell or not isinstance(new_cell, dict):
                    continue
                old = _as_cell(old_cell)
                fields = {key: new_cell[key] for key in _GEOMETRY if key in new_cell and key not in old}
                if fields and _valid_geometry(fields, existing=old) and new_cell == {**old, **fields}:
                    changed = True
                    current[index] = old_cell
    except (TypeError, KeyError, ValueError):
        return False
    return changed and original == before


def transfer_table_geometry(original, restored, target):
    """Apply proven geometry to the same cells in a normalized or published document."""
    if not has_only_table_geometry_additions(original, restored):
        raise ValueError("SOURCE_TABLE_GEOMETRY_DOCUMENT_INVALID")
    result = deepcopy(target)
    for (_, before, _, after), (original_columns, _, target_columns, target_cells) in zip(
        _aligned_cells(original, restored), _aligned_cells(original, result), strict=True,
    ):
        if original_columns != target_columns or tuple(map(_normalized_text, before)) != tuple(map(_normalized_text, target_cells)):
            raise ValueError("SOURCE_TABLE_GEOMETRY_CELL_DRIFT")
        for index, (old, new, destination) in enumerate(zip(before, after, target_cells, strict=True)):
            if old == new:
                continue
            old_fields, target_fields = _geometry(_as_cell(old)), _geometry(_as_cell(destination))
            if old_fields != target_fields:
                raise ValueError("SOURCE_TABLE_GEOMETRY_EXISTING_ROLE_DRIFT")
            additions = {key: value for key, value in _geometry(_as_cell(new)).items() if key not in old_fields}
            target_cells[index] = {**_as_cell(destination), **additions}
    if not has_only_table_geometry_additions(target, result) or validate_ordered_document(result, strict=True):
        raise ValueError("SOURCE_TABLE_GEOMETRY_DOCUMENT_INVALID")
    return result


def load_table_geometry_binding(cur, source_revision_id, *, lock=False):
    """Validate the retained document, resource receipts, and current source rights."""
    row = _source_replay_row(cur, source_revision_id)
    if (
        row is None or row["provider_slug"] not in {"bankone", "banktwo"}
        or row["projection_version"] not in SOURCE_PROJECTION_VERSIONS
        or row["vehicle_configuration_id"] is None or row["projection_status"] != "readable"
        or row["membership_status"] != "active" or row["takedown_status"] != "active"
        or validate_ordered_document(row["source_document"], strict=True)
    ):
        raise ValueError("SOURCE_TABLE_GEOMETRY_UNSUPPORTED")
    context = _context(row)
    manifest, provenance = _rows(row["resource_manifest"]), _rows(row["resource_provenance"])
    if not manifest or len(manifest) != len(provenance):
        raise ValueError("SOURCE_TABLE_GEOMETRY_BINDING_MISMATCH")
    body = manifest[0]
    if (body.get("role") != "body" or body.get("media_type") not in {"text/html", "application/hal+json"}
            or body.get("html_table_cell_header_layout") is not None
            or body.get("opaque_ref") != (context.descriptor.get("resource_ref") or context.descriptor.get("body_resource_ref"))
            or _uuid(provenance[0].get("source_snapshot_id")) != row["body_source_snapshot_id"]
            or _replay_fingerprint(context, manifest, provenance[0].get("asset_bindings")) != row["source_fingerprint"]):
        raise ValueError("SOURCE_TABLE_GEOMETRY_BINDING_MISMATCH")
    resources = {}
    for entry, owner in zip(manifest, provenance, strict=True):
        if (owner.get("provider") != row["provider_slug"]
                or any(owner.get(key) != value for key, value in entry.items())):
            raise ValueError("SOURCE_TABLE_GEOMETRY_BINDING_MISMATCH")
        if entry.get("failure_code"):
            if (entry.get("role") != "asset" or set(owner) != {*entry, "provider"}
                    or set(entry) != {"role", "opaque_ref", "failure_code"}):
                raise ValueError("SOURCE_TABLE_GEOMETRY_BINDING_MISMATCH")
            continue
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or owner.get("object_key") != _key(digest):
            raise ValueError("SOURCE_TABLE_GEOMETRY_BINDING_MISMATCH")
        item = (digest, owner["object_key"], entry.get("media_type"))
        source_id = _uuid(owner.get("source_snapshot_id"))
        if resources.setdefault(source_id, item) != item:
            raise ValueError("SOURCE_TABLE_GEOMETRY_BINDING_MISMATCH")
    ids = set(resources) | {context.descriptor_snapshot_id, context.resolution_snapshot_id}
    snapshots = _load_snapshots(cur, ids, resource_ids=set(resources), lock=lock)
    for snapshot in snapshots:
        if snapshot.id in resources and (
            resources[snapshot.id] != (snapshot.digest, snapshot.object_key, snapshot.media_type)
            or snapshot.digest != snapshot.artifact_digest or snapshot.object_key != snapshot.artifact_key
        ):
            raise ValueError("SOURCE_TABLE_GEOMETRY_BINDING_MISMATCH")
    _check_review_quarantine(cur, ids, lock=lock)
    return TableReplayBinding(row, snapshots, context)


def _replay(captured_binding, object_store):
    row, context = captured_binding.row, captured_binding.context
    manifest, provenance = deepcopy(row["resource_manifest"]), deepcopy(row["resource_provenance"])
    owner = provenance[0]
    raw = object_store.get_object(owner["object_key"], max_bytes=_MAX_OBJECT_BYTES)
    if not isinstance(raw, bytes) or len(raw) > _MAX_OBJECT_BYTES or sha256(raw).hexdigest() != owner["sha256"]:
        raise ValueError("SOURCE_TABLE_GEOMETRY_BODY_MISMATCH")
    body = SourceResource.from_bytes(owner["locator"], owner["source_revision"], raw, owner["media_type"], owner["locator"])
    parsed = adapt_bound_article(body, context, **_OPTIONS)
    document = _restore_from_blocks(row["source_document"], parsed["blocks"])
    if project_document(document) != project_document(row["source_document"]):
        raise ValueError("SOURCE_TABLE_GEOMETRY_PROJECTION_DRIFT")
    markers = {"html_table_cell_header_layout": HTML_TABLE_CELL_HEADER_LAYOUT}
    if parsed.get("html_table_spans"):
        markers["html_table_span_layout"] = HTML_TABLE_SPAN_LAYOUT
    manifest[0].update(markers)
    owner.update(markers)
    version = max(row["projection_version"], TABLE_GEOMETRY_PROJECTION_VERSION, key=SOURCE_PROJECTION_VERSIONS.index)
    return CapturedSource(
        context, _replay_fingerprint(context, manifest, owner.get("asset_bindings")), row["body_source_snapshot_id"],
        tuple(item for item in provenance if not item.get("failure_code")), manifest, provenance, document,
        row["source_images"], row["source_body"], row["source_steps"], row["evidence_manifest"],
        row["projection_status"], row["captured_at"], projection_version=version,
    )


def preview_table_geometry(repo, source_revision_id, *, object_store, deadline_seconds=30):
    if not 0 < deadline_seconds <= 30:
        raise ValueError("SOURCE_TABLE_GEOMETRY_DEADLINE_INVALID")
    deadline = monotonic() + deadline_seconds
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='5s'")
        binding = load_table_geometry_binding(cur, source_revision_id)
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        captured = pool.submit(_replay, binding, object_store).result(timeout=max(0, deadline - monotonic()))
    except TimeoutError:
        raise ValueError("SOURCE_TABLE_GEOMETRY_DEADLINE") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return binding, captured
