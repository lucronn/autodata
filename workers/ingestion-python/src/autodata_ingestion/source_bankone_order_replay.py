"""Replay a retained Bankone HTML article through the authored flow parser."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import math
import re
from time import monotonic

from psycopg.rows import dict_row

from .article_document import validate_ordered_document
from .article_lifecycle_store import _remap_snapshot_references
from .article_lifecycle_types import (
    BANKONE_HTML_FLOW_LAYOUT, HTML_DOCUMENT_LINK_LAYOUT, HTML_INLINE_ARTICLE_LINK_LAYOUT,
    HTML_TABLE_SPAN_LAYOUT, digest_json,
)
from .source_article_capture import WORKSHOP_CAPTURE_OPTIONS, capture_source_article, project_document, snapshot_id
from .source_connector_client import SourceConnectorError
from .source_job_persistence import source_bound_rewrite_source_allowed
from .source_media_replay import (
    MediaReplayBinding, _OfflineConnector, _VerifyOnlySink, _asset_inventory, _check_review_quarantine,
    _context, _load_snapshots, _read_objects, _replay_fingerprint, _resource_binding, _rows,
    _source_replay_row, _uuid,
)


BANKONE_ORDER_PROJECTION_VERSION = "source-projection-v5"
_UNSUPPORTED = "SOURCE_BANKONE_ORDER_REPLAY_UNSUPPORTED"
_BINDING = "SOURCE_BANKONE_ORDER_REPLAY_BINDING_MISMATCH"
_FLOW_DRIFT = "SOURCE_BANKONE_ORDER_REPLAY_FLOW_DRIFT"
_DEADLINE = "SOURCE_BANKONE_ORDER_REPLAY_DEADLINE"
_SPAN = "html_table_span_layout"
_LAYOUT = "bankone_html_flow_layout"
_POSITIONS = "bankone_graphic_position_bindings"
_GRAPHIC_LOCATOR = re.compile(r"bankone:asset:[0-9a-f]{24}")


@dataclass(frozen=True)
class BankoneOrderBinding(MediaReplayBinding):
    source_body: str
    source_steps: tuple[dict, ...]
    source_images: tuple[dict, ...]


def _graphic_bindings(provenance):
    bindings = {}
    for resource in provenance[1::2]:
        locator, ref = resource["locator"], resource["opaque_ref"]
        if not _GRAPHIC_LOCATOR.fullmatch(locator) or locator in bindings:
            raise ValueError(_BINDING)
        bindings[locator] = ref
    return bindings


def _legacy_resource_ids(row, context, manifest, provenance, *, has_positioned_flow=False, has_document_links=False):
    if (
        len(manifest) < 3 or len(manifest) != len(provenance)
        or manifest[0].get("role") != "body" or manifest[0].get("media_type") != "text/html"
        or [entry.get("role") for entry in manifest[1:]] != ["asset_original", "asset"] * (len(manifest) // 2)
        or "asset_bindings" in provenance[0]
    ):
        raise ValueError(_UNSUPPORTED)
    if _replay_fingerprint(context, manifest) != row["source_fingerprint"]:
        raise ValueError(_BINDING)
    known_layout = (
        {"html_document_link_layout": HTML_DOCUMENT_LINK_LAYOUT} if has_document_links
        else {_SPAN: HTML_TABLE_SPAN_LAYOUT}
    )
    if has_positioned_flow:
        known_layout.update({_LAYOUT: BANKONE_HTML_FLOW_LAYOUT, _POSITIONS: _graphic_bindings(provenance)})
    if any(entry.get(key) != value for entry in (manifest[0], provenance[0]) for key, value in known_layout.items()):
        raise ValueError(_UNSUPPORTED)
    # The layout markers are verified above. Check ordinary media bindings on
    # the same receipts without those layout-specific fields.
    receipts = ({key: value for key, value in manifest[0].items() if key not in known_layout}, *manifest[1:])
    owners = ({key: value for key, value in provenance[0].items() if key not in known_layout}, *provenance[1:])
    return _resource_binding(
        {**row, "source_fingerprint": _replay_fingerprint(context, receipts)},
        context, receipts, owners, ordinals=False,
    )


def load_bankone_order_binding(cur, source_revision_id, *, lock=False, has_positioned_flow=False, has_document_links=False):
    """Bind the retained source and read the rights of every retained snapshot."""
    row = _source_replay_row(cur, source_revision_id)
    if (
        row is None or row["provider_slug"] != "bankone" or row["vehicle_configuration_id"] is None
        or row["projection_version"] != BANKONE_ORDER_PROJECTION_VERSION
        or row["current_canonical_revision_id"] is None or row["projection_status"] != "readable"
    ):
        raise ValueError(_UNSUPPORTED)
    if row["membership_status"] != "active" or row["takedown_status"] != "active":
        raise ValueError("SOURCE_MEDIA_REPLAY_WITHDRAWN")
    context = _context(row)
    manifest = _rows(row["resource_manifest"])
    provenance = _rows(row["resource_provenance"])
    resource_ids = _legacy_resource_ids(row, context, manifest, provenance,
                                        has_positioned_flow=has_positioned_flow, has_document_links=has_document_links)
    _graphic_bindings(provenance)
    evidence = _rows(row["evidence_manifest"])
    if not context.evidence_ids or evidence != tuple(
        {"evidence_id": ident, "body_source_snapshot_id": str(row["body_source_snapshot_id"])}
        for ident in context.evidence_ids
    ):
        raise ValueError(_BINDING)
    if (
        validate_ordered_document(row["source_document"], strict=True)
        or project_document(row["source_document"]) != (row["source_body"], row["source_steps"], row["source_images"])
    ):
        raise ValueError(_BINDING)
    snapshot_ids = resource_ids | {context.descriptor_snapshot_id, context.resolution_snapshot_id}
    snapshots = _load_snapshots(cur, snapshot_ids, resource_ids=resource_ids, lock=lock)
    _check_review_quarantine(cur, snapshot_ids, lock=lock)
    by_id = {snapshot.id: snapshot for snapshot in snapshots}
    for resource in provenance:
        snapshot = by_id[_uuid(resource["source_snapshot_id"])]
        if (
            snapshot.digest != resource["sha256"] or snapshot.object_key != resource["object_key"]
            or snapshot.artifact_digest != resource["sha256"] or snapshot.artifact_key != resource["object_key"]
            or snapshot.media_type != resource["media_type"]
        ):
            raise ValueError(_BINDING)
    return BankoneOrderBinding(
        canonical_article_id=row["canonical_article_id"], source_revision_id=row["source_revision_id"],
        source_observation_id=row["source_observation_id"], projection_version=row["projection_version"],
        source_fingerprint=row["source_fingerprint"], body_sha256=manifest[0]["sha256"],
        body_source_snapshot_id=row["body_source_snapshot_id"], context=context,
        resource_manifest=manifest, resource_provenance=provenance, evidence_manifest=evidence,
        source_document_hash=digest_json(row["source_document"]), source_document=row["source_document"],
        _source_assets=_asset_inventory(row["source_images"], provenance),
        captured_at=row["captured_at"], snapshots=snapshots,
        source_body=row["source_body"], source_steps=_rows(row["source_steps"]), source_images=_rows(row["source_images"]),
    )


def _without_generated_ids(node):
    if isinstance(node, dict):
        return {key: _without_generated_ids(value) for key, value in node.items()
                if key not in {"block_id", "source_order", "image_id"}}
    if isinstance(node, list):
        return [_without_generated_ids(item) for item in node]
    return node


def _published_figure_unchanged(legacy, authored):
    original = _without_generated_ids(legacy)
    updated = _without_generated_ids(authored)
    for figure in (original, updated):
        if figure.get("unavailable_reason") is None:
            figure.pop("unavailable_reason", None)
    if original["alt"] == "Article illustration":
        # A positioned figure can restore alt text from the retained HTML.
        original.pop("alt")
        updated.pop("alt")
    return original == updated


def _protected_flow(document):
    """Compare item order and the remaining blocks' order independently."""
    blocks, items = [], []
    for original in document["blocks"]:
        block = _without_generated_ids(original)
        if block["type"] == "unordered_list":
            items.extend((block, item) for item in block.pop("items"))
        elif block["type"] != "image":
            if block["type"] == "heading":
                # The fresh parse can recognize an authored section label.
                block.pop("level")
                block["type"] = "paragraph"
            blocks.append(block)
    return blocks, items


def validate_bankone_order_capture(binding, captured):
    """Check the scoped successor's resource bindings and permitted flow changes."""
    additions = {_LAYOUT: BANKONE_HTML_FLOW_LAYOUT, _POSITIONS: _graphic_bindings(binding.resource_provenance)}
    manifest = ({**binding.resource_manifest[0], **additions}, *binding.resource_manifest[1:])
    provenance = ({**binding.resource_provenance[0], **additions}, *binding.resource_provenance[1:])
    if (
        captured.context != binding.context or captured.projection_version != BANKONE_ORDER_PROJECTION_VERSION
        or captured.body_source_snapshot_id != binding.body_source_snapshot_id
        or captured.captured_at != binding.captured_at or captured.projection_status != "readable"
        or tuple(captured.resource_manifest) != manifest or tuple(captured.resource_provenance) != provenance
        or captured.resources != provenance or tuple(captured.evidence_manifest) != binding.evidence_manifest
        or captured.source_fingerprint != _replay_fingerprint(binding.context, manifest)
        or captured.source_fingerprint == binding.source_fingerprint
    ):
        raise ValueError(_BINDING)
    if (
        validate_ordered_document(captured.source_document, strict=True)
        or project_document(captured.source_document) != (
            captured.source_body, captured.source_steps, captured.source_images,
        )
        or _asset_inventory(captured.source_images, provenance) != binding._source_assets
        or not all(_published_figure_unchanged(legacy, authored)
                   for legacy, authored in zip(binding.source_images, captured.source_images, strict=True))
    ):
        raise ValueError(_FLOW_DRIFT)
    old_blocks = binding.source_document["blocks"]
    figure_count = len(binding.source_images)
    if (
        [block["type"] for block in old_blocks[-figure_count:]] != ["image"] * figure_count
        or {key: value for key, value in binding.source_document.items() if key != "blocks"}
            != {key: value for key, value in captured.source_document.items() if key != "blocks"}
        or captured.source_body == binding.source_body
        or Counter(captured.source_body.splitlines()) != Counter(binding.source_body.splitlines())
        or _protected_flow(binding.source_document) != _protected_flow(captured.source_document)
    ):
        raise ValueError(_FLOW_DRIFT)


def _replay(repo, source_revision_id, object_store, deadline):
    def remaining():
        seconds = deadline - monotonic()
        if seconds <= 0:
            raise ValueError(_DEADLINE)
        return seconds

    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '5s'")
        binding = load_bankone_order_binding(cur, source_revision_id)
        article = cur.execute("""
            SELECT a.* FROM canonical_articles a
            JOIN canonical_article_revisions published
              ON published.canonical_article_revision_id = a.current_canonical_revision_id
             AND published.canonical_article_id = a.canonical_article_id
             AND published.source_revision_id = a.current_source_revision_id
            WHERE a.canonical_article_id = %s AND published.status = 'published'
        """, (binding.canonical_article_id,)).fetchone()
        if (
            article is None or article["descriptor_source_snapshot_id"] != binding.context.descriptor_snapshot_id
            or not source_bound_rewrite_source_allowed(cur, article, binding.source_revision_id)
        ):
            raise ValueError("SOURCE_MEDIA_REPLAY_WITHDRAWN")
    verified = _read_objects(binding, object_store, remaining)
    connector = _OfflineConnector("bankone", binding.resource_provenance, verified)
    try:
        replay = capture_source_article(
            binding.context, registry={"bankone": connector}, object_store=_VerifyOnlySink(verified),
            deadline_seconds=remaining(), **{
                **WORKSHOP_CAPTURE_OPTIONS,
                "keep_inline_article_links": (
                    binding.resource_manifest[0].get("html_inline_article_link_layout") == HTML_INLINE_ARTICLE_LINK_LAYOUT
                ),
            },
        )
    except SourceConnectorError as error:
        code = _DEADLINE if error.code in ("CAPTURE_DEADLINE", "UPSTREAM_UNAVAILABLE") else _FLOW_DRIFT
        raise ValueError(code) from None
    snapshot_ids = {str(snapshot_id(row["sha256"])): row["source_snapshot_id"] for row in binding.resource_provenance}
    captured = replace(
        replay, captured_at=binding.captured_at, body_source_snapshot_id=binding.body_source_snapshot_id,
        resources=tuple(_remap_snapshot_references(row, snapshot_ids) for row in replay.resources),
        resource_manifest=_remap_snapshot_references(replay.resource_manifest, snapshot_ids),
        resource_provenance=_remap_snapshot_references(replay.resource_provenance, snapshot_ids),
        evidence_manifest=_remap_snapshot_references(replay.evidence_manifest, snapshot_ids),
    )
    validate_bankone_order_capture(binding, captured)
    remaining()
    return binding, captured


def preview_bankone_order_replay(repo, source_revision_id, *, object_store, deadline_seconds=30):
    if (isinstance(deadline_seconds, bool) or not isinstance(deadline_seconds, (int, float))
            or not math.isfinite(deadline_seconds) or not 0 < deadline_seconds <= 30):
        raise ValueError(_DEADLINE)
    deadline = monotonic() + deadline_seconds
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(_replay, repo, source_revision_id, object_store, deadline).result(timeout=deadline_seconds)
    except TimeoutError:
        raise ValueError(_DEADLINE) from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
