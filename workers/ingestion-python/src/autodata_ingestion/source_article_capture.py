"""Bounded provider-bound capture; immutable public projection from actual bytes."""

from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from copy import deepcopy
from datetime import datetime, timezone
from functools import partial
from hashlib import sha256
from io import BytesIO
from threading import Lock
import json
import time
import base64
from uuid import NAMESPACE_URL, uuid5
from .article_lifecycle_types import (
    BANKONE_DEFINITION_HEADING_LAYOUT,
    BANKONE_LIST_BOUNDARY_LAYOUT,
    BANKONE_HTML_FLOW_LAYOUT,
    BANKTWO_DOTTED_LIST_START_LAYOUT, BANKTWO_LIST_NOTICE_LAYOUT,
    CapturedSource,
    HTML_BOUND_IMAGE_LAYOUT,
    HTML_DOCUMENT_LINK_LAYOUT,
    HTML_INLINE_ARTICLE_LINK_LAYOUT,
    HTML_FIGURE_CAPTION_LAYOUT,
    HTML_FLOW_FIGURE_CAPTION_LAYOUT,
    HTML_MEDIA_TABLE_HEADER_LAYOUT,
    HTML_TABLE_CELL_HEADER_LAYOUT,
    HTML_MULTILINE_FIGURE_CAPTION_LAYOUT,
    HTML_NESTED_TABLE_LAYOUT,
    HTML_NUMERIC_SUPERSCRIPT_LAYOUT,
    HTML_SECTION_TITLE_LAYOUT,
    HTML_TABLE_CAPTION_LAYOUT,
    HTML_TABLE_SPAN_LAYOUT,
    LEADING_DECIMAL_LAYOUT,
    MAX_LINKED_PDFS,
    MIXED_HTML_PDF_LAYOUT,
    MISSING_TABLE_IMAGE_CAPTION_LAYOUT,
    MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V2,
    MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V3,
    PDF_BLANK_PAGE_LAYOUT,
    PDF_CLIPPED_FIGURE_LAYOUT,
    PDF_COMPACT_FIGURE_LAYOUT,
    PDF_FAST_PNG_ENCODING,
    PDF_LEGACY_FIGURE_LAYOUT,
    PDF_REPEAT_MARGIN_LAYOUT,
    PDF_SINGLE_LINE_FIGURE_LAYOUT,
    PDF_WORDLESS_FIGURE_LAYOUT,
    STRUCTURED_HEADING_IMAGE_LAYOUT,
    STRUCTURED_TABLE_CELL_ORDER_LAYOUT,
    STRUCTURED_TABLE_COLUMN_ORDER_LAYOUT,
    STRUCTURED_TABLE_COLUMNS_LAYOUT,
    STRUCTURED_TABLE_NESTED_MEDIA_LAYOUT,
    ResourceRef,
    article_id,
    digest_json,
)
from .banktwo_service_schedule import banktwo_service_schedule
from .source_adapters import adapt_bound_article, adapt_bound_pdf_embed
from .source_connector_client import SourceConnectorError
from .article_document import (
    ConnectorBankoneGraphic, ConnectorDocumentEmbed, LeadingDecimalStepParser, authored_image_caption, build_ordered_document,
    segment_plain_article_text, table_image_summaries, validate_ordered_document, walk_ordered_list_items,
)
from .svg_rasterization import rasterize_svg, SVGUnavailable, RASTERIZER_VERSION


_MAX_BODY_PREVIEW_BYTES = 256 * 1024
_LEGACY_SVG_RECOVERY_INCOMPLETE = "SOURCE_LEGACY_SVG_RECOVERY_INCOMPLETE"

# Keep in sync with the raster types accepted by the catalog image endpoint.
DISPLAYABLE_RASTER_MEDIA = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
RASTER_FORMATS = {media: media.split("/")[1].upper() for media in DISPLAYABLE_RASTER_MEDIA}


def read_raster_dimensions(payload, media_type):
    format_name = RASTER_FORMATS.get(media_type)
    if format_name is None:
        return None
    from PIL import Image

    try:
        with Image.open(BytesIO(payload), formats=[format_name]) as image:
            width, height = image.size
            if not 1 <= width <= 10000 or not 1 <= height <= 10000:
                return None
            if image.getexif().get(274) in (5, 6, 7, 8):
                width, height = height, width
            return width, height
    except (Image.DecompressionBombError, OSError, ValueError, SyntaxError, EOFError):
        return None


def snapshot_id(digest):
    return uuid5(NAMESPACE_URL, "autodata:source-blob:v1:" + digest)


def upload_resource(envelope, opaque_ref, role, object_store):
    """Object store implements put_object(key, bytes, media_type); success is required."""
    resource = envelope.to_source_resource()
    digest = resource.content_sha256
    key = "sources/" + digest[:16] + "/" + digest
    object_store.put_object(key, resource.payload, resource.media_type)
    return {
        "provider": envelope.provider,
        "opaque_ref": opaque_ref,
        "role": role,
        "media_type": resource.media_type,
        "sha256": digest,
        "object_key": key,
        "source_snapshot_id": str(snapshot_id(digest)),
        "source_revision": envelope.source_revision,
        "request_id": envelope.request_id,
        "fetched_at": envelope.fetched_at,
        "locator": envelope.source_locator or envelope.resource_uri,
        **({"asset_bindings": deepcopy(resource.metadata["asset_bindings"])}
           if "asset_bindings" in resource.metadata else {}),
        **({"article_link_bindings": deepcopy(resource.metadata["article_link_bindings"])}
           if resource.metadata.get("article_link_bindings") else {}),
    }


def upload_envelope(envelope, role, object_store):
    """Persist exact index/resolution bytes, never a reconstructed JSON envelope."""

    if envelope.raw_envelope is None:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    raw = envelope.raw_envelope
    digest = sha256(raw).hexdigest()
    key = "sources/" + digest[:16] + "/" + digest
    object_store.put_object(key, raw, "application/json")
    return {
        "provider": envelope.provider,
        "opaque_ref": role,
        "role": role,
        "media_type": "application/json",
        "sha256": digest,
        "object_key": key,
        "source_snapshot_id": str(snapshot_id(digest)),
        "source_revision": envelope.source_revision,
        "request_id": envelope.request_id,
        "fetched_at": envelope.fetched_at,
        "locator": envelope.source_locator or "connector:" + role,
    }


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in list(value.values()):
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _image_nodes(value, *, image_container=False):
    """Include kind-less figures in the ordered document's nested images arrays."""
    if isinstance(value, dict):
        if (
            image_container
            or str(value.get("type") or value.get("kind") or "").casefold() == "image"
        ):
            yield value
        items = value.get("items")
        if value.get("type") in ("ordered_list", "unordered_list") and isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    yield from _image_nodes(item.get("images", []), image_container=True)
                    yield from _image_nodes(item.get("blocks", []))
            yield from _image_nodes(value.get("images", []), image_container=True)
            return
        for key, child in list(value.items()):
            yield from _image_nodes(child, image_container=key == "images")
    elif isinstance(value, list):
        for child in value:
            yield from _image_nodes(child, image_container=image_container)


def _embedded_images(blocks):
    return [
        node for node in _walk(blocks)
        if (node.get("kind") or node.get("type")) == "image"
        and not node.get("asset_resource_ref") and node.get("url", "").startswith("data:image/")
    ]


def _bind_bankone_graphics(blocks, resources, declared_refs):
    """Use verified connector asset receipts from this article's declared assets."""
    declared_refs = set(declared_refs)
    by_locator = {}
    for resource in resources:
        if (
            resource["provider"] == "bankone" and resource["role"] in {"asset", "asset_original"}
            and resource["opaque_ref"] in declared_refs
        ):
            by_locator.setdefault(resource["locator"], set()).add(resource["opaque_ref"])
    bindings = {}
    for node in _image_nodes(blocks):
        if isinstance(node, ConnectorBankoneGraphic):
            matches = by_locator.get(node.graphic_locator)
            if matches and len(matches) == 1:
                ref = next(iter(matches))
                node["asset_resource_ref"] = ref
                bindings[node.graphic_locator] = ref
    return bindings


def _recovered_bankone_svg_digests(blocks, refs, bindings, resources, localized):
    """Require one authored position and a retained SVG/PNG pair for every legacy ref."""
    placements = Counter(
        node["asset_resource_ref"] for node in _image_nodes(blocks)
        if node.get("asset_resource_ref") in refs
    )
    if not refs.issubset(bindings.values()) or placements != Counter(refs):
        raise SourceConnectorError(_LEGACY_SVG_RECOVERY_INCOMPLETE)
    originals = {
        resource["opaque_ref"]: resource["sha256"] for resource in resources
        if resource["role"] == "asset_original" and resource["provider"] == "bankone"
        and resource["media_type"] == "image/svg+xml"
    }
    digests = Counter()
    for ref in refs:
        png = localized.get(ref)
        if (ref not in originals or png is None or png["media_type"] != "image/png"
                or png.get("derived_from_sha256") != originals[ref]
                or png.get("derivation_version") != RASTERIZER_VERSION):
            raise SourceConnectorError(_LEGACY_SVG_RECOVERY_INCOMPLETE)
        digests[png["sha256"]] += 1
    return digests


def _embedded_image_bytes(uri):
    header, encoded = uri.split(",", 1)
    media = header[5:].split(";", 1)[0].strip().lower()
    if ";base64" not in header or media == "image/svg+xml":
        raise ValueError("unsupported embedded figure")
    payload = base64.b64decode(encoded, validate=True)
    digest = sha256(payload).hexdigest()
    key = "sources/" + digest[:16] + "/" + digest
    return media, payload, digest, key


def _attach_figure_captions(blocks, key):
    ordered = []
    resume = 0
    for index, block in enumerate(blocks):
        if index < resume:
            continue
        caption = block.pop(key, None)
        if isinstance(caption, str):
            caption = [caption]
        if isinstance(caption, list) and caption and block.get("status") == "available":
            end = index + 1 + len(caption)
            parts = blocks[index + 1:end]
            if len(parts) == len(caption) and all(
                part.get("_html_figure_caption_text") is True and part.get("text") == text
                for part, text in zip(parts, caption, strict=True)
            ):
                block["caption"] = " ".join(caption)
                resume = end
        block.pop("_html_figure_caption_text", None)
        ordered.append(block)
    blocks[:] = ordered


def _mark_json_table_cells(blocks, *, keep_rows, keep_columns):
    """Keep authored figure order and nested media in structured table cells."""
    textual = {"text", "paragraph", "callout", "warning", "caution", "note", "hint", "important"}
    containers = {"ordered_list", "unordered_list", "list", "table", "grid"}
    structured = textual | containers | {
        "image", "heading", "title", "section", "step", "instruction", "link", "anchor",
        "break", "hr", "separator",
    }
    nested_media = False

    def has_ordered_media(cell):
        nonlocal nested_media
        children = cell.get("blocks") if isinstance(cell, dict) else None
        if not isinstance(children, list) or any(not isinstance(child, dict) for child in children):
            return False
        kinds = [str(child.get("type") or child.get("kind") or "text").casefold() for child in children]
        if containers.intersection(kinds) and all(kind in structured for kind in kinds) and any(_image_nodes(children)):
            nested_media = True
            return True
        return ("image" in kinds and all(kind == "image" or kind in textual for kind in kinds)
                and any(kind in textual for kind in kinds[kinds.index("image") + 1:]))

    ordered_rows = []
    ordered_columns = []
    for node in _walk(blocks):
        # The connector document supplies the content, never private layout flags.
        for private in ("_ordered_html_table_cell", "_ordered_json_table_cell", "_preserve_cell_block_order"):
            node.pop(private, None)
        if str(node.get("type") or node.get("kind") or "").casefold() not in ("table", "grid"):
            continue
        columns = node.get("columns")
        if keep_columns and isinstance(columns, list):
            ordered_columns.extend(cell for cell in columns if has_ordered_media(cell))
        rows = node.get("rows")
        if not keep_rows or not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                row = row.get("cells") or row.get("values") or row.get("blocks")
            if isinstance(row, list):
                ordered_rows.extend(cell for cell in row if has_ordered_media(cell))
    for cell in ordered_rows + ordered_columns:
        cell["_ordered_json_table_cell"] = True
    return bool(ordered_rows), bool(ordered_columns), nested_media


def _retain_missing_table_captions(table, missing_refs, first_image_ids):
    """Share a missing figure's identity when legacy table dedup loses or repeats captions."""
    captions = {}
    legacy_captions = {}
    for image in table_image_summaries(table):
        ref = missing_refs.get(id(image))
        if ref is None:
            continue
        caption = authored_image_caption(image)
        legacy_captions.setdefault(ref, {}).setdefault(image["image_id"], caption)
        if caption:
            captions.setdefault(ref, set()).add(caption)
    distinct_refs = {ref for ref, values in captions.items() if len(values) > 1}
    single_caption_repairs = {
        ref for ref, values in captions.items()
        if len(values) == 1 and list(legacy_captions[ref].values()) != list(values)
    }
    affected_refs = distinct_refs | single_caption_repairs
    if not affected_refs:
        return set(), False
    # The legacy ID includes the running asset position, which can differ
    # after an intervening image. Use the first captured ID inside this table.
    for image in _image_nodes(table):
        ref = missing_refs.get(id(image))
        if ref in affected_refs:
            image["image_id"] = first_image_ids[ref]
    return {first_image_ids[ref] for ref in affected_refs}, bool(single_caption_repairs)


def _drop_duplicate_missing_table_summaries(blocks, missing_image_refs):
    def caption_key(image):
        ref = missing_image_refs.get(image.get("image_id"))
        caption = image.get("caption")
        return (ref, caption) if ref and caption else None

    tables = [block for block in _walk(blocks) if block.get("type") == "table" and block.get("images")]
    repaired = False
    # Process nested tables first so outer tables see only retained cell figures.
    for table in reversed(tables):
        cell_captions = {}
        for cells in (table.get("columns", []), table.get("rows", [])):
            for image in _image_nodes(cells):
                key = caption_key(image)
                if key:
                    cell_captions.setdefault(key, set()).add(image["image_id"])
        retained = []
        for image in table["images"]:
            ids = cell_captions.get(caption_key(image))
            # Readers already suppress a summary with the same image ID and caption.
            if not ids or image.get("image_id") in ids:
                retained.append(image)
        if len(retained) != len(table["images"]):
            repaired = True
            if retained:
                table["images"] = retained
            else:
                del table["images"]
    return repaired


def project_document(
    document, *, include_cell_figure_captions=False, include_table_captions=False, include_flow_figure_captions=False,
):
    """Compatibility fields derived only from the authoritative ordered document."""
    texts = []
    steps = []
    images = [deepcopy(node) for node in _image_nodes(document.get("blocks", []))]

    def visit(value, *, strings=False, cell=False):
        if isinstance(value, str):
            if strings:
                texts.append(value)
        elif isinstance(value, list):
            for child in value:
                visit(child, strings=strings, cell=cell)
        elif isinstance(value, dict):
            node = value
            if isinstance(node.get("text"), str) and node["text"]:
                texts.append(node["text"])
            if ((include_cell_figure_captions if cell else include_flow_figure_captions)
                    and node.get("type") == "image" and node.get("caption")):
                texts.append(node["caption"])
            if include_table_captions and node.get("type") == "table" and node.get("label"):
                texts.append(node["label"])
            if node.get("type") == "step" and isinstance(node.get("text"), str):
                steps.append(
                    {
                        "number": node.get("number", len(steps) + 1),
                        "text": node["text"],
                        "evidence_ids": node.get("evidence_ids", []),
                    }
                )
            ordered_list = node.get("type") == "ordered_list"
            if ordered_list:
                for item, ordinal in walk_ordered_list_items(node):
                    text = item.get("text") if isinstance(item, dict) else item
                    if isinstance(text, str) and text.strip():
                        steps.append({
                            "number": len(steps) + 1 if ordinal is None else ordinal, "text": text,
                            "evidence_ids": node.get("evidence_ids", []),
                        })
                    visit(item, strings=True)
            for key, child in node.items():
                if key in ("text", "images") or (key == "items" and ordered_list):
                    continue
                if isinstance(child, (dict, list)):
                    visit(child, strings=key in ("columns", "rows", "items"),
                          cell=cell or (node.get("type") == "table" and key in ("columns", "rows")))

    visit(document.get("blocks", []))
    return "\n".join(texts), steps, images


def _replace_pdf_embeds(value, documents, *, pending=False):
    """Expand signed connector document bindings in their original block positions."""
    if isinstance(value, dict):
        children = value.get("blocks")
        if isinstance(children, list) and any(isinstance(node, ConnectorDocumentEmbed) for node in children):
            value["_preserve_cell_block_order"] = True
        for child in value.values():
            _replace_pdf_embeds(child, documents, pending=pending)
    elif isinstance(value, list):
        expanded = []
        for node in value:
            if isinstance(node, ConnectorDocumentEmbed):
                ref = node.get("asset_resource_ref")
                if node.get("text"):
                    expanded.append({"kind": "link", "text": node["text"]})
                if ref in documents:
                    blocks, evidence, _ = documents[ref]
                    expanded.extend({**deepcopy(block), "evidence_ids": evidence} for block in blocks)
                elif not pending:
                    expanded.append({
                        "kind": "callout", "label": "Embedded document unavailable",
                        "text": "This document could not be prepared for Workshop.",
                    })
            else:
                _replace_pdf_embeds(node, documents, pending=pending)
                expanded.append(node)
        value[:] = expanded


def _source_body_preview(
    context, article, *, step_parser, keep_json_rows, keep_json_columns, linked_documents=None,
):
    blocks = deepcopy(article["blocks"])
    if article.get("authored_json_blocks"):
        _mark_json_table_cells(blocks, keep_rows=keep_json_rows, keep_columns=keep_json_columns)
    if linked_documents:
        _replace_pdf_embeds(blocks, linked_documents, pending=True)
    document = build_ordered_document(
        {"article_id": str(article_id(context.key)), "evidence_ids": list(context.evidence_ids)},
        blocks, preserve_marked_cells=True, preserve_structured_columns=True, step_parser=step_parser,
    )
    for node in _image_nodes(document["blocks"]):
        # Keep the authored location without any unverified figure locator or
        # alt text derived from the connector's media attributes.
        fields = {
            key: node[key] for key in ("type", "block_id", "source_order", "evidence_ids", "caption")
            if key in node
        }
        node.clear()
        node.update(fields, status="unavailable", unavailable_reason="SOURCE_MEDIA_PENDING")
    for node in _walk(document):
        node.pop("href", None)
        node.pop("source_locator", None)
    text, _, _ = project_document(document, include_cell_figure_captions=True, include_flow_figure_captions=True)
    if (not text.strip() or text.strip() == str(context.descriptor.get("title", "")).strip()
            or len(json.dumps(document, ensure_ascii=False).encode()) > _MAX_BODY_PREVIEW_BYTES
            or validate_ordered_document(document)):
        return None
    return document


WORKSHOP_CAPTURE_OPTIONS = {
    "keep_embedded_pdf": True,
    "keep_html_headings": True,
    "keep_bound_pdf_iframes": True,
    "keep_pdf_figure_order": True,
    "keep_multiple_pdf_figures": True,
    "keep_html_table_image_order": True,
    "keep_repeated_pdf_figures": True,
    "keep_pdf_figures_with_margins": True,
    "keep_clipped_pdf_figures": True,
    "keep_compact_pdf_figures": True,
    "keep_single_line_pdf_figures": True,
    "skip_blank_linked_pdf_pages": True,
    "keep_wordless_linked_pdf_figures": True,
    "keep_html_figure_captions": True,
    "keep_html_flow_figure_captions": True,
    "keep_html_multiline_figure_captions": True,
    "keep_html_table_captions": True,
    "keep_html_media_table_headers": True,
    "keep_html_table_spans": True,
    "keep_html_nested_tables": True,
    "keep_structured_table_columns": True,
    "keep_structured_table_cell_order": True,
    "keep_structured_table_column_order": True,
    "keep_image_only_headings": True,
    "keep_ordered_step_instructions": True,
    "keep_image_only_step_instructions": True,
    "keep_leading_decimals": True,
    "keep_html_numeric_superscripts": True,
    "keep_html_document_links": True,
    "keep_inline_article_links": True,
    "keep_html_section_titles": True,
    "keep_bankone_html_flow": True,
    "keep_banktwo_list_notices": True,
    "keep_banktwo_dotted_list_starts": True,
    "keep_bankone_definition_headings": True,
    "keep_bankone_list_boundaries": True,
    "keep_mixed_html_pdf_embeds": True,
    "keep_bound_html_images": True,
    "keep_positioned_figure_labels": True,
}


def capture_source_article(
    context, *, registry, object_store, deadline_seconds=30.0,
    keep_embedded_pdf=False, keep_html_headings=False, keep_bound_pdf_iframes=False,
    keep_pdf_figure_order=False, keep_multiple_pdf_figures=False, keep_html_table_image_order=False,
    keep_repeated_pdf_figures=False, keep_pdf_figures_with_margins=False, keep_clipped_pdf_figures=False,
    keep_compact_pdf_figures=False,
    keep_html_figure_captions=False, keep_html_table_captions=False, keep_html_flow_figure_captions=False,
    keep_html_table_spans=False,
    keep_html_media_table_headers=False,
    keep_html_table_cell_headers=False,
    keep_html_nested_tables=False,
    keep_html_multiline_figure_captions=False,
    skip_blank_linked_pdf_pages=False,
    keep_wordless_linked_pdf_figures=False,
    keep_single_line_pdf_figures=False,
    keep_structured_table_columns=False,
    keep_structured_table_cell_order=False,
    keep_structured_table_column_order=False,
    keep_image_only_headings=False,
    keep_ordered_step_instructions=False,
    keep_image_only_step_instructions=False,
    keep_leading_decimals=False,
    keep_html_numeric_superscripts=False,
    keep_html_document_links=False,
    keep_inline_article_links=False,
    keep_html_section_titles=False,
    keep_bankone_html_flow=False,
    keep_banktwo_list_notices=False,
    keep_banktwo_dotted_list_starts=False,
    keep_bankone_definition_headings=False,
    keep_bankone_list_boundaries=False,
    keep_mixed_html_pdf_embeds=False,
    keep_bound_html_images=False,
    keep_positioned_figure_labels=False,
    on_body_preview=None,
    on_linked_preview=None,
):
    if not 0 < deadline_seconds <= 30:
        raise ValueError("capture deadline must be within 30 seconds")
    provider = context.key.provider
    step_parser = LeadingDecimalStepParser() if keep_leading_decimals else None
    if provider not in registry:
        raise SourceConnectorError("NOT_CONFIGURED")
    client = registry[provider]
    if client.provider != provider:
        raise SourceConnectorError("INVALID_UPSTREAM_RESPONSE")
    deadline = time.monotonic() + deadline_seconds
    cache = {}

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise SourceConnectorError("UPSTREAM_UNAVAILABLE", retryable=True)
        return seconds

    def read(ref):
        bound = ResourceRef(provider, ref)
        if bound not in cache:
            cache[bound] = client.read_resource(ref, timeout=remaining())
        return cache[bound]

    raster_dimensions = {}
    raster_dimensions_lock = Lock()

    class BoundedObjects:
        """Bound caller latency, not an adapter's already-running network request.

        Runtime adapters must configure their own socket timeouts. On timeout the
        only possible late effect is a content-addressed blob upload; no worker
        thread can commit lifecycle observations or publish an article.
        """

        def put_object(self, key, payload, media_type):
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True)
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                pool.submit(object_store.put_object, key, payload, media_type).result(timeout=timeout)
            except TimeoutError:
                raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True) from None
            except Exception:
                # SDK and transport exceptions have no shared OSError base.
                raise SourceConnectorError(
                    "ASSET_STORAGE_UNAVAILABLE", retryable=True
                ) from None
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
            dimensions = read_raster_dimensions(payload, media_type)
            if dimensions is not None:
                with raster_dimensions_lock:
                    raster_dimensions[key] = dimensions

    bounded_objects = BoundedObjects()

    body_ref = context.descriptor.get("resource_ref") or context.descriptor.get(
        "body_resource_ref"
    )
    if not body_ref:
        raise SourceConnectorError("SOURCE_NOT_FOUND")
    body_pool = ThreadPoolExecutor(max_workers=1)
    try:
        body = body_pool.submit(read, body_ref).result(timeout=remaining())
    except TimeoutError:
        raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True) from None
    except SourceConnectorError as error:
        if error.status == 404:
            raise SourceConnectorError("SOURCE_NOT_FOUND") from None
        raise
    finally:
        body_pool.shutdown(wait=False, cancel_futures=True)

    legacy_pdf_roots = context.legacy_published_pdf_roots | context.published_legacy_pdf_layout_roots

    def retain_repeats(digest):
        return keep_repeated_pdf_figures and digest not in legacy_pdf_roots

    def retain_repeats_with_margins(digest):
        return keep_pdf_figures_with_margins and digest not in context.legacy_published_pdf_margin_roots

    def retain_clipped_figures(digest):
        return keep_clipped_pdf_figures and digest not in context.legacy_published_pdf_clipped_roots

    def retain_compact_figures(digest):
        return keep_compact_pdf_figures and digest not in context.legacy_published_pdf_compact_roots

    def plan_assets(article, blocks):
        for node in _image_nodes(blocks):
            node["kind"] = node["type"] = "image"
        refs = (
            list(context.descriptor.get("asset_resource_refs") or [])
            + list(body.body.get("asset_resource_refs") or [])
            + list(article.get("asset_resource_refs") or [])
        )
        for node in _walk(blocks):
            if (node.get("kind") or node.get("type")) == "image" and node.get(
                "asset_resource_ref"
            ):
                refs.append(node["asset_resource_ref"])
        # A provider JSON block cannot authorize a document fetch by declaring a marker.
        linked_refs = dict.fromkeys(
            node["asset_resource_ref"] for node in _walk(blocks)
            if isinstance(node, ConnectorDocumentEmbed)
            and node["asset_resource_ref"] in (body.body.get("asset_resource_refs") or [])
            and node["asset_resource_ref"] != body_ref
        )
        selected_documents = set(list(linked_refs)[:MAX_LINKED_PDFS])
        # Stable dedupe retains the first source position; opaque refs are never normalized.
        refs = list(dict.fromkeys(ref for ref in refs if ref not in linked_refs))
        labor_ref = context.descriptor.get("labor_resource_ref")
        optional = [(ref, "asset") for ref in refs]
        optional += [(ref, "document_asset") for ref in linked_refs if ref in selected_documents]
        if labor_ref and labor_ref not in refs and labor_ref not in linked_refs and labor_ref != body_ref:
            optional.append((labor_ref, "labor"))
        return refs, linked_refs, optional

    def fetch_order(tasks):
        # A linked preview can use the document while unrelated assets are
        # pending. Keep final processing in the original manifest order.
        if on_linked_preview is None:
            return tasks
        return sorted(tasks, key=lambda task: task[1] != "document_asset")

    def positioned_media_refs(article):
        return set(article.get("untyped_pdf_embed_refs", ())) | {
            node["asset_resource_ref"] for node in _walk(article["blocks"])
            if (isinstance(node, ConnectorDocumentEmbed) or (node.get("kind") or node.get("type")) == "image")
            and isinstance(node.get("asset_resource_ref"), str)
        }

    def native_pdf_blocks(page_texts):
        parser = LeadingDecimalStepParser() if keep_leading_decimals else None
        return [
            block for _, text in page_texts
            for block in segment_plain_article_text(text, step_parser=parser)
        ]

    # All requests share one deadline; no more than four can run concurrently.
    def fetch(pair, defer_pdf=False, native_ready=None):
        ref, role = pair
        originals = []
        try:
            envelope = read(ref)
            if defer_pdf and envelope.body["media_type"] == "application/pdf":
                # Keep the connector response cached until this PDF is given a slot.
                return ref, "document_asset", None, "DOCUMENT_LIMIT", originals, None
            if role == "document_asset":
                payload = envelope.to_source_resource()
                if payload.media_type != "application/pdf":
                    return ref, role, None, "UNSUPPORTED_DOCUMENT_MEDIA", originals, None
                resource = upload_resource(envelope, ref, role, bounded_objects)
                # Use the fast codec for a first capture. Match the encoding
                # in the stored manifest when recapturing the same document.
                fast_png = (
                    payload.content_sha256 in context.fast_linked_pdf_png_roots
                    or on_linked_preview is not None
                )
                if fast_png:
                    resource["pdf_figure_encoding"] = PDF_FAST_PNG_ENCODING

                def native_text(page_texts):
                    blocks = native_pdf_blocks(page_texts)
                    if blocks:
                        native_ready.set_result((resource, blocks))

                try:
                    linked_step_parser = LeadingDecimalStepParser() if keep_leading_decimals else None
                    adapted = adapt_bound_pdf_embed(
                        payload, require_complete_ocr=True, keep_pdf_figure_order=keep_pdf_figure_order,
                        keep_multiple_pdf_figures=keep_multiple_pdf_figures,
                        keep_repeated_pdf_figures=retain_repeats(payload.content_sha256),
                        keep_pdf_figures_with_margins=retain_repeats_with_margins(payload.content_sha256),
                        keep_clipped_pdf_figures=retain_clipped_figures(payload.content_sha256),
                        keep_compact_pdf_figures=retain_compact_figures(payload.content_sha256),
                        keep_single_line_compact_figures=keep_single_line_pdf_figures,
                        keep_wordless_pdf_figures=keep_wordless_linked_pdf_figures,
                        step_parser=linked_step_parser,
                        on_native_text=native_text if native_ready is not None else None,
                        fast_png=fast_png,
                        skip_blank_pages=(
                            skip_blank_linked_pdf_pages
                            and payload.content_sha256 not in context.legacy_published_pdf_blank_roots
                        ),
                    )
                    if linked_step_parser is not None and linked_step_parser.preserved:
                        adapted["preserved_leading_decimals"] = True
                except ValueError:
                    adapted = None
                if not adapted or not adapted["blocks"]:
                    return ref, role, None, "DOCUMENT_EXTRACTION_UNAVAILABLE", [resource], None
                return ref, role, resource, None, originals, adapted
            resource = upload_resource(envelope, ref, role, bounded_objects)
            if role == "asset" and resource["media_type"] == "image/svg+xml":
                original = {**resource, "role": "asset_original"}
                originals.append(original)
                png = rasterize_svg(envelope.to_source_resource().payload, timeout=remaining())
                digest = sha256(png).hexdigest()
                key = "sources/" + digest[:16] + "/" + digest
                bounded_objects.put_object(key, png, "image/png")
                resource = {
                    **resource, "media_type": "image/png", "sha256": digest,
                    "object_key": key, "source_snapshot_id": str(snapshot_id(digest)),
                    "derived_from_sha256": original["sha256"],
                    "derivation_version": RASTERIZER_VERSION,
                }
            if role == "asset" and resource["media_type"] not in DISPLAYABLE_RASTER_MEDIA:
                if resource["media_type"].startswith("image/"):
                    originals.append({**resource, "role": "asset_original"})
                return ref, role, None, "UNSUPPORTED_ASSET_MEDIA", originals, None
            return ref, role, resource, None, originals, None
        except SVGUnavailable as error:
            return ref, role, None, str(error), originals, None
        except SourceConnectorError as error:
            return (
                ref,
                role,
                None,
                "SOURCE_NOT_FOUND" if error.status == 404 else error.code,
                originals,
                None,
            )

    early_figures = set()
    figure_lock = Lock()
    figure_writes = {}
    deferred_figures = {}
    hidden_fallback_refs = set()

    def build_preview(article, linked_documents=None):
        try:
            return _source_body_preview(
                context, article, step_parser=LeadingDecimalStepParser() if keep_leading_decimals else None,
                keep_json_rows=keep_structured_table_cell_order,
                keep_json_columns=keep_structured_table_columns and keep_structured_table_column_order,
                linked_documents=linked_documents,
            )
        except (ValueError, TypeError, KeyError):
            # Later media preparation can make an incomplete initial projection readable.
            return None

    def publish_linked_preview(article, body_resource, linked_refs, ready_parts):
        if time.monotonic() >= deadline:
            return
        ordered = [ready_parts[ref] for ref in linked_refs if ref in ready_parts]
        preview = build_preview(article, {
            resource["opaque_ref"]: (blocks, ["source:" + resource["source_snapshot_id"]], [])
            for resource, blocks in ordered
        })
        if preview is not None and time.monotonic() < deadline:
            on_linked_preview(body_resource, body_preview, linked_document=preview,
                              linked_resources=tuple(resource for resource, _ in ordered))

    def store_document_figures(blocks):
        for node in _embedded_images(blocks):
            try:
                media, payload, _, key = _embedded_image_bytes(node["url"])
                with figure_lock:
                    if (key, media) in early_figures:
                        continue
                bounded_objects.put_object(key, payload, media)
                with figure_lock:
                    early_figures.add((key, media))
            except (ValueError, TypeError, SourceConnectorError):
                continue  # The final projection records any figure failure.

    parser_pool = ThreadPoolExecutor(max_workers=1)
    body_resource = None
    body_preview = None
    pool = None
    try:
        caption_settings = {
            "keep_html_figure_captions": (keep_html_figure_captions, context.legacy_published_html_figure_body),
            "keep_html_flow_figure_captions": (keep_html_flow_figure_captions, context.legacy_published_html_flow_figure_body),
            "keep_html_multiline_figure_captions": (
                keep_html_multiline_figure_captions, context.legacy_published_html_multiline_figure_body,
            ),
        }
        body_digest = body.body["sha256"]
        prior_svg_refs = context.legacy_published_bankone_svg_refs
        recover_legacy_bankone_svg = bool(
            keep_bankone_html_flow and provider == "bankone" and body.body["media_type"] == "text/html"
            and body_digest == context.legacy_published_bankone_flow_body and prior_svg_refs
        )
        body_asset_refs = body.body.get("asset_resource_refs") or []
        if recover_legacy_bankone_svg and not prior_svg_refs.issubset(body_asset_refs):
            raise SourceConnectorError(_LEGACY_SVG_RECOVERY_INCOMPLETE)
        legacy_captions = {
            name: enabled and (recover_legacy_bankone_svg or body_digest != legacy)
            for name, (enabled, legacy) in caption_settings.items()
        }
        refreshed_captions = {name: enabled for name, (enabled, _) in caption_settings.items() if enabled and not legacy_captions[name]}
        body_payload = body.to_source_resource()
        adapt = partial(
            adapt_bound_article, body_payload, context,
            keep_positioned_figure_labels=(
                keep_positioned_figure_labels and body_digest != context.legacy_published_positioned_label_body
            ),
            keep_embedded_pdf=keep_embedded_pdf, keep_html_headings=keep_html_headings,
            keep_bound_pdf_iframes=keep_bound_pdf_iframes,
            keep_pdf_figure_order=keep_pdf_figure_order,
            keep_multiple_pdf_figures=keep_multiple_pdf_figures,
            keep_html_table_image_order=keep_html_table_image_order,
            keep_repeated_pdf_figures=retain_repeats(body.body["sha256"]),
            keep_pdf_figures_with_margins=retain_repeats_with_margins(body.body["sha256"]),
            keep_clipped_pdf_figures=retain_clipped_figures(body.body["sha256"]),
            keep_compact_pdf_figures=retain_compact_figures(body.body["sha256"]),
            keep_html_table_captions=(
                keep_html_table_captions and body.body["sha256"] != context.legacy_published_html_table_caption_body
            ),
            keep_html_table_spans=keep_html_table_spans,
            keep_html_media_table_headers=keep_html_media_table_headers,
            keep_html_table_cell_headers=(
                keep_html_table_cell_headers and body_digest != context.legacy_published_html_table_cell_header_body
            ),
            keep_html_nested_tables=keep_html_nested_tables,
            keep_html_numeric_superscripts=keep_html_numeric_superscripts,
            keep_html_document_links=(
                keep_html_document_links and body_digest != context.legacy_published_html_document_link_body
            ),
            keep_html_section_titles=(
                keep_html_section_titles and body_digest != context.legacy_published_html_section_title_body
            ),
            keep_bankone_html_flow=(
                keep_bankone_html_flow
                and (recover_legacy_bankone_svg or body_digest != context.legacy_published_bankone_flow_body)
            ),
            keep_bankone_definition_headings=(
                keep_bankone_definition_headings and body_digest != context.legacy_published_bankone_definition_heading_body
            ),
            keep_bankone_list_boundaries=(
                keep_bankone_list_boundaries and body_digest != context.legacy_published_bankone_list_boundary_body
            ),
            keep_banktwo_list_notices=(
                keep_banktwo_list_notices and body_digest != context.legacy_published_banktwo_list_notice_body
            ),
            keep_banktwo_dotted_list_starts=(
                keep_banktwo_dotted_list_starts and body_digest != context.legacy_published_banktwo_dotted_list_start_body
            ),
            keep_mixed_html_pdf_embeds=keep_mixed_html_pdf_embeds,
            keep_structured_table_cell_order=keep_structured_table_cell_order or (
                keep_structured_table_columns and keep_structured_table_column_order
            ),
            keep_image_only_headings=keep_image_only_headings,
            keep_ordered_step_instructions=keep_ordered_step_instructions,
            keep_image_only_step_instructions=keep_image_only_step_instructions,
            keep_bound_html_images=keep_bound_html_images,
            declared_image_refs=frozenset(
                list(context.descriptor.get("asset_resource_refs") or ()) + list(body.body.get("asset_resource_refs") or ())
            ) if keep_bound_html_images else frozenset(),
            **legacy_captions,
        )

        def parse(**options):
            article = adapt(**options)
            # The new binding creates a separate projection for unchanged bytes.
            # Keep captions even when the previous projection omitted them.
            if article.get("html_bound_images") and refreshed_captions:
                article = adapt(**options, **refreshed_captions)
            if mirrors := article.get("html_image_mirrors"):
                article = adapt(
                    **options, **refreshed_captions, skip_noscript_images=mirrors,
                    lazy_image_alts=article.get("html_lazy_image_alts"),
                )
            return article

        primary_text = (
            Future() if on_body_preview is not None and not context.has_stored_source
            and body_payload.media_type == "application/pdf" and keep_pdf_figure_order else None
        )
        body_parse = parser_pool.submit(
            parse, step_parser=step_parser, on_primary_pdf_text=primary_text.set_result if primary_text is not None else None,
        )
        if primary_text is not None:
            ready, _ = wait((body_parse, primary_text), timeout=remaining(), return_when=FIRST_COMPLETED)
            if primary_text in ready and body_parse not in ready:
                native_preview = build_preview({"blocks": native_pdf_blocks(primary_text.result())})
                if native_preview is not None and time.monotonic() < deadline:
                    body_resource = upload_resource(body, body_ref, "body", bounded_objects)
                    on_body_preview(body_resource, native_preview)
        article = body_parse.result(timeout=remaining())
        if recover_legacy_bankone_svg:
            on_linked_preview = None
        elif on_body_preview is not None or on_linked_preview is not None:
            body_preview = build_preview(article)
            if body_preview is not None and on_body_preview is not None:
                if body_resource is None:
                    body_resource = upload_resource(body, body_ref, "body", bounded_objects)
                on_body_preview(body_resource, body_preview)
        candidates = article.get("untyped_pdf_embed_refs", ())
        if candidates:
            _, positioned, planned = plan_assets(article, article["blocks"])
            roles = dict(planned)
            candidates = [ref for ref in candidates if ref in roles and ref != body_ref]
        if candidates:
            initial_media_refs = positioned_media_refs(article)
            # Normal assets share the same workers. Optional reads must not hold
            # up PDF preparation or the corresponding HTML projection.
            if body_resource is None:
                body_resource = upload_resource(body, body_ref, "body", bounded_objects)
            pool = ThreadPoolExecutor(max_workers=4)
            reading = {ref for ref in candidates if roles[ref] == "asset"}
            futures = {
                ref: pool.submit(fetch, (ref, role), ref in reading)
                for ref, role in fetch_order(planned)
            }
            inferred = set(candidates)
            pending = {futures[ref]: ref for ref, role in planned if ref in inferred or role == "document_asset"}
            capacity = max(0, MAX_LINKED_PDFS - len(positioned))
            verified = set()
            projected_refs = frozenset()
            projection = None
            # Resolve a lone inferred link for the preview without changing
            # the final projection. Mixed candidates keep full verification.
            sole_inferred = (
                candidates[0] if on_linked_preview is not None and not positioned and len(candidates) == 1 else None
            )
            inferred_text = None
            while pending or projection is not None:
                waiting = set(pending)
                if projection is not None:
                    waiting.add(projection)
                if inferred_text is not None:
                    waiting.add(inferred_text)
                done, _ = wait(waiting, timeout=max(0, deadline - time.monotonic()), return_when=FIRST_COMPLETED)
                if not done:
                    break
                if inferred_text in done:
                    done.remove(inferred_text)
                    if not futures[sole_inferred].done() and time.monotonic() < deadline:
                        part = inferred_text.result()
                        try:
                            native_article = parser_pool.submit(
                                parse, step_parser=LeadingDecimalStepParser() if keep_leading_decimals else None,
                                resolved_pdf_refs=frozenset({sole_inferred}),
                            ).result(timeout=max(0, deadline - time.monotonic()))
                            _, native_links, _ = plan_assets(native_article, deepcopy(native_article["blocks"]))
                        except (ValueError, TypeError, KeyError, UnicodeError, TimeoutError):
                            native_links = {}
                        if sole_inferred in native_links:
                            publish_linked_preview(native_article, body_resource, native_links, {sole_inferred: part})
                    inferred_text = None
                if projection in done:
                    article = projection.result()
                    step_parser = projected_steps
                    # A successful object hides its fallback, including media only found there.
                    hidden_fallback_refs = initial_media_refs - positioned_media_refs(article)
                    done.remove(projection)
                    projection = None
                acquired = set()
                for future in done:
                    ref = pending.pop(future)
                    if ref in hidden_fallback_refs:
                        continue
                    if ref in reading:
                        reading.remove(ref)
                        if future.result()[1] == "document_asset":
                            acquired.add(ref)
                    else:
                        if ref == sole_inferred:
                            inferred_text = None
                        adapted = future.result()[-1]
                        if adapted is not None:
                            if ref in inferred:
                                verified.add(ref)
                            if deadline > time.monotonic():
                                if on_linked_preview is None:
                                    figure_writes[ref] = pool.submit(store_document_figures, adapted["blocks"])
                                else:
                                    deferred_figures[ref] = adapted["blocks"]
                for future, ref in tuple(pending.items()):
                    if ref in hidden_fallback_refs:
                        del pending[future]
                        future.cancel()
                if deadline <= time.monotonic():
                    break
                # Rank ready PDFs in source order. Pending or non-PDF reads take no slot.
                for ref in [ref for ref in candidates if ref in acquired][:capacity]:
                    if ref == sole_inferred:
                        inferred_text = Future()
                    future = pool.submit(fetch, (ref, "document_asset"), native_ready=inferred_text)
                    futures[ref] = future
                    pending[future] = ref
                    capacity -= 1
                if projection is None and verified != projected_refs:
                    projected_refs = frozenset(verified)
                    projected_steps = LeadingDecimalStepParser() if keep_leading_decimals else None
                    projection = parser_pool.submit(parse, step_parser=projected_steps, resolved_pdf_refs=projected_refs)
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        code = (
            "WRONG_APPLICABILITY"
            if "applicability" in str(error)
            else "INVALID_ARTICLE_BODY"
        )
        raise SourceConnectorError(code) from None
    except TimeoutError:
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True) from None
    except BaseException:
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        raise
    finally:
        parser_pool.shutdown(wait=False, cancel_futures=True)
    blocks = deepcopy(article["blocks"])
    html_figure_captions = article.get("html_figure_captions") is True
    html_flow_figure_captions = article.get("html_flow_figure_captions") is True
    html_multiline_figure_captions = article.get("html_multiline_figure_captions") is True
    html_table_captions = article.get("html_table_captions") is True
    html_table_spans = article.get("html_table_spans") is True
    html_media_table_headers = article.get("html_media_table_headers") is True
    html_table_cell_headers = article.get("html_table_cell_headers") is True
    html_nested_tables = article.get("html_nested_tables") is True
    html_numeric_superscripts = article.get("html_numeric_superscripts") is True
    positioned_figure_labels = article.get("positioned_figure_labels") is True
    handled_pdf_embeds = article.get("handled_pdf_embeds") is True
    # Both HTML and mixed HAL carry confirmed anchor labels on the placed nodes.
    html_document_links = article.get("html_document_links") is True or (
        handled_pdf_embeds and any(
            isinstance(node, ConnectorDocumentEmbed) and node.get("text") for node in _walk(blocks)
        )
    )
    html_bound_images = article.get("html_bound_images") is True
    mixed_html_pdf_embeds = article.get("mixed_html_pdf_embeds") is True
    html_section_titles = article.get("html_section_titles") is True
    bankone_html_flow = article.get("bankone_html_flow") is True
    banktwo_list_notices = article.get("banktwo_list_notices") is True
    banktwo_dotted_list_starts = article.get("banktwo_dotted_list_starts") is True
    bankone_definition_headings = article.get("bankone_definition_headings") is True
    bankone_list_boundaries = article.get("bankone_list_boundaries") is True
    positioned_html_table_images = article.get("positioned_html_table_images") is True
    positioned_pdf_figures = article.get("positioned_pdf_figures") is True
    retained_pdf_repeats = article.get("retained_repeated_pdf_figures") is True
    pdf_asset_order = article.get("pdf_legacy_asset_order", [])
    structured_table_cell_order = structured_table_column_order = structured_table_nested_media = False
    authored_json_blocks = article.get("authored_json_blocks") is True
    if authored_json_blocks:
        structured_table_cell_order, structured_table_column_order, structured_table_nested_media = _mark_json_table_cells(
            blocks, keep_rows=keep_structured_table_cell_order,
            keep_columns=keep_structured_table_columns and keep_structured_table_column_order,
        )
    image_only_headings = article.get("image_only_headings") is True
    step_layout = article.get("ordered_step_instructions_layout")
    structured_table_columns = keep_structured_table_columns and not html_media_table_headers and any(
        str(node.get("type") or node.get("kind") or "").casefold() in {"table", "grid"}
        and isinstance(node.get("columns"), list) and any(isinstance(column, dict) for column in node["columns"])
        for node in _walk(blocks)
    )
    new_structure = (
        structured_table_columns or structured_table_cell_order or step_layout or html_table_captions or html_flow_figure_captions
        or html_table_spans or html_media_table_headers or html_table_cell_headers or html_nested_tables
        or html_numeric_superscripts or image_only_headings
        or html_bound_images or html_document_links or html_section_titles or bankone_html_flow or banktwo_list_notices
        or positioned_figure_labels or bankone_definition_headings or bankone_list_boundaries or banktwo_dotted_list_starts
        or article.get("embedded_pdf")
        or (article.get("authored_html_headings") and any(block.get("kind") == "heading" for block in _walk(blocks)))
    )
    refs, linked_refs, optional = plan_assets(article, blocks)
    if hidden_fallback_refs:
        refs = [ref for ref in refs if ref not in hidden_fallback_refs]
        optional = [(ref, role) for ref, role in optional if role != "asset" or ref not in hidden_fallback_refs]
    selected_documents = set(list(linked_refs)[:MAX_LINKED_PDFS])
    for node in _walk(blocks):
        if (
            (node.get("kind") or node.get("type")) == "image"
            and not node.get("asset_resource_ref")
            and node.get("url") in refs
        ):
            node["asset_resource_ref"] = node["url"]
    resources = [body_resource if body_resource is not None else upload_resource(body, body_ref, "body", bounded_objects)]
    manifest = [
        {k: resources[0][k] for k in ("role", "opaque_ref", "sha256", "media_type")}
    ]
    if "article_link_bindings" in resources[0]:
        manifest[0]["article_link_bindings"] = deepcopy(resources[0]["article_link_bindings"])
    if article.get("retained_pdf_figures_with_margins") is True:
        resources[0]["pdf_figure_layout"] = manifest[0]["pdf_figure_layout"] = PDF_REPEAT_MARGIN_LAYOUT
    if article.get("retained_clipped_pdf_figures") is True:
        resources[0]["pdf_clipped_figure_layout"] = manifest[0]["pdf_clipped_figure_layout"] = PDF_CLIPPED_FIGURE_LAYOUT
    if article.get("positioned_compact_pdf_figures") is True:
        resources[0]["pdf_compact_figure_layout"] = manifest[0]["pdf_compact_figure_layout"] = PDF_COMPACT_FIGURE_LAYOUT
    if html_figure_captions:
        resources[0]["html_figure_caption_layout"] = manifest[0]["html_figure_caption_layout"] = HTML_FIGURE_CAPTION_LAYOUT
    if html_flow_figure_captions:
        resources[0]["html_flow_figure_caption_layout"] = manifest[0]["html_flow_figure_caption_layout"] = HTML_FLOW_FIGURE_CAPTION_LAYOUT
    if html_multiline_figure_captions:
        resources[0]["html_multiline_figure_caption_layout"] = manifest[0]["html_multiline_figure_caption_layout"] = HTML_MULTILINE_FIGURE_CAPTION_LAYOUT
    if html_table_captions:
        resources[0]["html_table_caption_layout"] = manifest[0]["html_table_caption_layout"] = HTML_TABLE_CAPTION_LAYOUT
    if html_table_spans:
        resources[0]["html_table_span_layout"] = manifest[0]["html_table_span_layout"] = HTML_TABLE_SPAN_LAYOUT
    if html_media_table_headers:
        resources[0]["html_media_table_header_layout"] = manifest[0]["html_media_table_header_layout"] = HTML_MEDIA_TABLE_HEADER_LAYOUT
    if html_table_cell_headers:
        resources[0]["html_table_cell_header_layout"] = manifest[0]["html_table_cell_header_layout"] = HTML_TABLE_CELL_HEADER_LAYOUT
    if html_nested_tables:
        resources[0]["html_nested_table_layout"] = manifest[0]["html_nested_table_layout"] = HTML_NESTED_TABLE_LAYOUT
    if html_numeric_superscripts:
        resources[0]["html_numeric_superscript_layout"] = manifest[0]["html_numeric_superscript_layout"] = HTML_NUMERIC_SUPERSCRIPT_LAYOUT
    if html_document_links:
        resources[0]["html_document_link_layout"] = manifest[0]["html_document_link_layout"] = HTML_DOCUMENT_LINK_LAYOUT
    if html_section_titles:
        resources[0]["html_section_title_layout"] = manifest[0]["html_section_title_layout"] = HTML_SECTION_TITLE_LAYOUT
    if bankone_definition_headings:
        resources[0]["bankone_definition_heading_layout"] = manifest[0]["bankone_definition_heading_layout"] = (
            BANKONE_DEFINITION_HEADING_LAYOUT
        )
    if bankone_list_boundaries:
        resources[0]["bankone_list_boundary_layout"] = manifest[0]["bankone_list_boundary_layout"] = (
            BANKONE_LIST_BOUNDARY_LAYOUT
        )
    if banktwo_list_notices:
        resources[0]["banktwo_list_notice_layout"] = manifest[0]["banktwo_list_notice_layout"] = BANKTWO_LIST_NOTICE_LAYOUT
    if banktwo_dotted_list_starts:
        resources[0]["banktwo_dotted_list_start_layout"] = manifest[0]["banktwo_dotted_list_start_layout"] = (
            BANKTWO_DOTTED_LIST_START_LAYOUT
        )
    if html_bound_images:
        resources[0]["html_bound_image_layout"] = manifest[0]["html_bound_image_layout"] = HTML_BOUND_IMAGE_LAYOUT
    if positioned_figure_labels:
        from .positioned_figure import FIGURE_LABEL_LAYOUT
        resources[0]["html_positioned_figure_layout"] = manifest[0]["html_positioned_figure_layout"] = FIGURE_LABEL_LAYOUT
    if mixed_html_pdf_embeds:
        resources[0]["mixed_html_pdf_layout"] = manifest[0]["mixed_html_pdf_layout"] = MIXED_HTML_PDF_LAYOUT
    if structured_table_columns:
        resources[0]["structured_table_columns_layout"] = manifest[0]["structured_table_columns_layout"] = STRUCTURED_TABLE_COLUMNS_LAYOUT
    if structured_table_cell_order:
        resources[0]["structured_table_cell_order_layout"] = manifest[0]["structured_table_cell_order_layout"] = STRUCTURED_TABLE_CELL_ORDER_LAYOUT
    if structured_table_column_order:
        resources[0]["structured_table_column_order_layout"] = manifest[0]["structured_table_column_order_layout"] = STRUCTURED_TABLE_COLUMN_ORDER_LAYOUT
    if structured_table_nested_media:
        resources[0]["structured_table_nested_media_layout"] = manifest[0]["structured_table_nested_media_layout"] = STRUCTURED_TABLE_NESTED_MEDIA_LAYOUT
    if image_only_headings:
        resources[0]["structured_heading_image_layout"] = manifest[0]["structured_heading_image_layout"] = STRUCTURED_HEADING_IMAGE_LAYOUT
    if step_layout:
        resources[0]["ordered_step_instructions_layout"] = manifest[0]["ordered_step_instructions_layout"] = step_layout
    provenance = [deepcopy(resources[0])]
    failures = {}
    localized = {}
    documents = {}
    missing_asset_refs = set()
    linked_decimal_preserved = False

    if pool is None:
        pool = ThreadPoolExecutor(max_workers=4)
        futures = {}
    native_documents = {}
    for ref, role in fetch_order(optional):
        if ref not in futures:
            native_ready = None
            if on_linked_preview is not None and role == "document_asset":
                native_ready = native_documents[ref] = Future()
            futures[ref] = pool.submit(fetch, (ref, role), native_ready=native_ready)
    if on_linked_preview is not None and selected_documents:
        pending_documents = {futures[ref]: ref for ref in linked_refs if ref in selected_documents}
        preview_parts = {}
        try:
            while pending_documents and time.monotonic() < deadline:
                ready, _ = wait([*pending_documents, *native_documents.values()], timeout=max(0, deadline - time.monotonic()),
                                return_when=FIRST_COMPLETED)
                if not ready:
                    break
                preview_changed = False
                for ref, signal in tuple(native_documents.items()):
                    if signal in ready or futures[ref] in ready:
                        del native_documents[ref]
                        if signal in ready and futures[ref] not in ready:
                            preview_parts[ref] = signal.result()
                            preview_changed = True
                ready_refs = []
                for future in ready:
                    ref = pending_documents.pop(future, None)
                    if ref is None:
                        continue
                    _, role, resource, _, _, adapted = future.result()
                    if role == "document_asset" and resource is not None and adapted is not None:
                        ready_refs.append(ref)
                        preview_parts[ref] = (resource, adapted["blocks"])
                if ready_refs or preview_changed:
                    publish_linked_preview(article, resources[0], linked_refs, preview_parts)
                for ref in ready_refs:
                    if ref in deferred_figures and time.monotonic() < deadline:
                        figure_writes[ref] = pool.submit(store_document_figures, deferred_figures[ref])
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)
            raise
    work = [futures[ref] for ref, _ in optional]
    work.extend(figure_writes[ref] for ref, _ in optional if ref in figure_writes)
    done, _ = wait(work, timeout=max(0, deadline - time.monotonic()))
    with figure_lock:
        stored_embedded_images = early_figures.copy()
    for ref, role in optional:
        future = futures[ref]
        if future not in done:
            future.cancel()
            resource = None
            failure = "CAPTURE_DEADLINE"
        else:
            _, fetched_role, resource, failure, originals, adapted = future.result()
            if role == "asset" and fetched_role == "document_asset" and adapted is not None:
                # An inferred document without a position stays a regular asset.
                resource, failure, adapted = None, "UNSUPPORTED_ASSET_MEDIA", None
            else:
                role = fetched_role
            if adapted is not None:
                documents[ref] = (adapted["blocks"], ["source:" + resource["source_snapshot_id"]],
                                  adapted.get("pdf_legacy_asset_order", []))
                positioned_pdf_figures |= adapted.get("positioned_pdf_figures") is True
                retained_pdf_repeats |= adapted.get("retained_repeated_pdf_figures") is True
                linked_decimal_preserved |= adapted.get("preserved_leading_decimals") is True
                if adapted.get("retained_pdf_figures_with_margins") is True:
                    resource["pdf_figure_layout"] = PDF_REPEAT_MARGIN_LAYOUT
                if adapted.get("retained_clipped_pdf_figures") is True:
                    resource["pdf_clipped_figure_layout"] = PDF_CLIPPED_FIGURE_LAYOUT
                if adapted.get("positioned_compact_pdf_figures") is True:
                    resource["pdf_compact_figure_layout"] = PDF_COMPACT_FIGURE_LAYOUT
                if adapted.get("positioned_single_line_pdf_figures") is True:
                    resource["pdf_single_line_figure_layout"] = PDF_SINGLE_LINE_FIGURE_LAYOUT
                if adapted.get("skipped_blank_pages") is True:
                    resource["pdf_blank_page_layout"] = PDF_BLANK_PAGE_LAYOUT
                if adapted.get("retained_wordless_pdf_figures") is True:
                    resource["pdf_wordless_figure_layout"] = PDF_WORDLESS_FIGURE_LAYOUT
            for original in originals:
                resources.append(original)
                provenance.append(deepcopy(original))
                manifest.append({k: original[k] for k in ("role", "opaque_ref", "sha256", "media_type")})
        if resource:
            resources.append(resource)
            provenance.append(deepcopy(resource))
            manifest.append(
                {key: resource[key] for key in (
                    "role", "opaque_ref", "sha256", "media_type", "derived_from_sha256", "derivation_version",
                    "pdf_figure_layout", "pdf_clipped_figure_layout", "pdf_compact_figure_layout",
                    "pdf_blank_page_layout", "pdf_single_line_figure_layout",
                    "pdf_wordless_figure_layout", "pdf_figure_encoding",
                ) if key in resource}
            )
            if role == "asset":
                localized[ref] = resource
        else:
            failures[ref] = failure
            if role == "asset" and failure == "SOURCE_NOT_FOUND":
                missing_asset_refs.add(ref)
            entry = {"role": role, "opaque_ref": ref, "failure_code": failure}
            manifest.append(entry)
            provenance.append({"provider": provider, **entry})
    pool.shutdown(wait=False, cancel_futures=True)
    for ref in linked_refs:
        if ref not in selected_documents:
            failure = {"role": "document_asset", "opaque_ref": ref, "failure_code": "DOCUMENT_LIMIT"}
            failures[ref] = failure["failure_code"]
            manifest.append(failure)
            provenance.append({"provider": provider, **failure})

    # Keep the older per-root fence when another PDF promotes the article to
    # v10. After promotion, continue recording the fence for the same bytes.
    fenced_roots = legacy_pdf_roots if retained_pdf_repeats else context.published_legacy_pdf_layout_roots
    if keep_repeated_pdf_figures and fenced_roots:
        body_is_pdf = resources[0]["media_type"] == "application/pdf" or article.get("embedded_pdf") is True
        for records in (resources, manifest, provenance):
            for record in records:
                if record.get("sha256") not in fenced_roots:
                    continue
                role = record["role"]
                if (role == "body" and body_is_pdf) or (role == "document_asset" and record["media_type"] == "application/pdf"):
                    record["pdf_figure_layout"] = PDF_LEGACY_FIGURE_LAYOUT
    if handled_pdf_embeds:
        _replace_pdf_embeds(blocks, documents)
    bindings = {}
    if bankone_html_flow:
        bindings = _bind_bankone_graphics(blocks, resources, body_asset_refs)
        for record in (resources[0], provenance[0], manifest[0]):
            record["bankone_html_flow_layout"] = BANKONE_HTML_FLOW_LAYOUT
            record["bankone_graphic_position_bindings"] = bindings
    if recover_legacy_bankone_svg:
        recovered_svg_digests = _recovered_bankone_svg_digests(
            blocks, prior_svg_refs, bindings, resources, localized,
        )

    # Embedded figures are derived only from verified bytes and never fetched by URL.
    evidence_sources = {
        "source:" + resource["source_snapshot_id"]: resource
        for resource in resources if resource["role"] == "document_asset"
    }
    embedded_nodes = _embedded_images(blocks)
    pdf_asset_orders = {(): pdf_asset_order} if pdf_asset_order else {}
    pdf_asset_orders.update({tuple(evidence): order for _, evidence, order in documents.values() if order})
    if pdf_asset_orders:
        # Reorder only each PDF figure's upload slots. Display order must not
        # change the manifest and fingerprint of the same retained source.
        ranks = {
            evidence: {image_id: (group, rank)
                       for group, order in enumerate(orders) for rank, image_id in enumerate(order)}
            for evidence, orders in pdf_asset_orders.items()
        }
        pending_groups = {}
        for position, node in enumerate(embedded_nodes):
            evidence = node.get("evidence_ids")
            evidence = tuple(evidence) if isinstance(evidence, list) and all(isinstance(e, str) for e in evidence) else ()
            rank = ranks.get(evidence, {}).get(node.get("image_id"))
            if rank is None:
                continue
            group = (evidence, rank[0])
            pending = pending_groups.setdefault(group, [])
            pending.append((position, rank[1], node))
            if len(pending) == len(pdf_asset_orders[evidence][rank[0]]):
                for slot, assigned in zip(pending, sorted(pending, key=lambda entry: entry[1])):
                    embedded_nodes[slot[0]] = assigned[2]
                del pending_groups[group]
    uploaded_embedded_images = set()
    for node in embedded_nodes:
        uri = node["url"]
        try:
            media, payload, digest, key = _embedded_image_bytes(uri)
            evidence = node.get("evidence_ids")
            parent = next(
                (evidence_sources[item] for item in evidence if isinstance(item, str) and item in evidence_sources),
                resources[0],
            ) if isinstance(evidence, list) else resources[0]
            ref = "embedded:" + parent["sha256"] + ":" + digest
            repeated = retained_pdf_repeats and node.get("_retained_repeated_pdf_figure") is True
            if repeated and localized.get(ref, {}).get("media_type") == media:
                node["asset_resource_ref"] = ref
                continue
            if (key, media) not in stored_embedded_images and (
                not retained_pdf_repeats or (key, media) not in uploaded_embedded_images
            ):
                bounded_objects.put_object(key, payload, media)
            if retained_pdf_repeats:
                uploaded_embedded_images.add((key, media))
            displayable = media in DISPLAYABLE_RASTER_MEDIA
            local = {
                "provider": provider,
                "opaque_ref": ref,
                "role": "embedded_asset" if displayable else "asset_original",
                "media_type": media,
                "sha256": digest,
                "object_key": key,
                "source_snapshot_id": str(snapshot_id(digest)),
                "source_revision": parent["source_revision"],
                "request_id": parent["request_id"],
                "fetched_at": parent["fetched_at"],
                "locator": parent["locator"],
            }
            if displayable:
                localized[ref] = local
            else:
                node["reason"] = "UNSUPPORTED_ASSET_MEDIA"
            resources.append(local)
            provenance.append(deepcopy(local))
            manifest.append(
                {
                    k: local[k]
                    for k in ("role", "opaque_ref", "sha256", "media_type")
                }
            )
            node["asset_resource_ref"] = ref
        except (ValueError, TypeError):
            node["reason"] = "INVALID_EMBEDDED_IMAGE"
        except SourceConnectorError as error:
            node["reason"] = error.code
    positioned = set()
    image_records = {}
    missing_refs = {}
    missing_image_refs = {}
    first_missing_image_ids = {}
    authored_images = set()
    for node in _walk(blocks):
        if not html_table_spans:
            node.pop("_html_table_cell_spans", None)
        if not html_table_cell_headers:
            node.pop("_html_table_cell_header", None)
        if not html_nested_tables:
            node.pop("_html_literal_table_text", None)
        # No executable/provider URLs or upstream-supplied source_original enter the projection.
        for key in (
            "source_original",
            "source_url",
            "href",
            "url",
            "src",
            "locator",
            "uri",
            "path",
            "storage_key",
            "artifact_key",
            "object_key",
            "asset_id",
            "content_sha256",
            "source_snapshot_id",
        ):
            node.pop(key, None)
        if (node.get("kind") or node.get("type")) == "image":
            ref = node.pop("asset_resource_ref", None)
            positioned.add(ref)
            local = localized.get(ref)
            document_evidence = [evidence for evidence in node.get("evidence_ids", [])
                                 if isinstance(evidence, str) and evidence in evidence_sources] if isinstance(node.get("evidence_ids"), list) else []
            node.update(
                {
                    "image_id": (
                        local["sha256"]
                        if local
                        else digest_json(
                            {
                                "provider": provider,
                                "ref": ref,
                                "position": len(positioned),
                            }
                        )
                    ),
                    "status": "available" if local else "unavailable",
                    "evidence_ids": document_evidence or list(context.evidence_ids),
                }
            )
            if local:
                authored_images.add(node["image_id"])
                node.update(
                    {
                        "storage_key": local["object_key"],
                        "content_sha256": local["sha256"],
                        "media_type": local["media_type"],
                    }
                )
            else:
                node.update(
                    {
                        "fetch_failed": True,
                        "reason": failures.get(
                            ref, node.get("reason", "UNBOUND_SOURCE_IMAGE")
                        ),
                    }
                )
                if authored_json_blocks and ref in missing_asset_refs:
                    missing_refs[id(node)] = ref
                    missing_image_refs[node["image_id"]] = ref
                    first_missing_image_ids.setdefault(ref, node["image_id"])
            image_records[node["image_id"]] = deepcopy(node)
    for ref in refs:
        if ref not in positioned:
            local = localized.get(ref)
            node = {
                    "kind": "image",
                    "image_id": (
                        local["sha256"]
                        if local
                        else digest_json({"provider": provider, "ref": ref})
                    ),
                    "storage_key": local["object_key"] if local else None,
                    "content_sha256": local["sha256"] if local else None,
                    "media_type": local["media_type"] if local else None,
                    "fetch_failed": not bool(local),
                    "reason": failures.get(ref),
                    "status": "available" if local else "unavailable",
                    "evidence_ids": list(context.evidence_ids),
                }
            blocks.append(node)
            image_records[node["image_id"]] = deepcopy(node)
    evidence_ids = list(context.evidence_ids) or [
        "source:" + resources[0]["source_snapshot_id"]
    ]
    if html_figure_captions:
        for node in _walk(blocks):
            if not node.get("_ordered_html_table_cell") and not node.get("_preserve_cell_block_order"):
                continue
            _attach_figure_captions(node.get("blocks", []), "_html_figure_caption")
    if html_flow_figure_captions:
        _attach_figure_captions(blocks, "_html_flow_figure_caption")
        for node in _walk(blocks):
            if (node.get("kind") or node.get("type")) in ("ordered_list", "unordered_list"):
                for item in node.get("items", []):
                    if isinstance(item, dict) and isinstance(item.get("blocks"), list):
                        _attach_figure_captions(item["blocks"], "_html_flow_figure_caption")
    caption_layout = None

    def missing_caption_ids_for_table(table):
        nonlocal caption_layout
        caption_ids, single_caption_repaired = _retain_missing_table_captions(table, missing_refs, first_missing_image_ids)
        if single_caption_repaired:
            caption_layout = MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V2
        elif caption_ids and caption_layout is None:
            caption_layout = MISSING_TABLE_IMAGE_CAPTION_LAYOUT
        return caption_ids

    doc = build_ordered_document(
        {"article_id": str(article_id(context.key)), "evidence_ids": evidence_ids},
        blocks,
        preserve_marked_cells=(handled_pdf_embeds or positioned_html_table_images or structured_table_cell_order
                               or structured_table_column_order or html_nested_tables or html_media_table_headers),
        preserve_structured_columns=structured_table_columns or html_media_table_headers,
        step_parser=step_parser,
        table_caption_ids=missing_caption_ids_for_table if missing_refs else None,
    )
    if missing_image_refs and _drop_duplicate_missing_table_summaries(doc["blocks"], missing_image_refs):
        caption_layout = MISSING_TABLE_IMAGE_CAPTION_LAYOUT_V3
    if caption_layout:
        new_structure = True
        for record in (resources[0], provenance[0], manifest[0]):
            record["missing_table_image_caption_layout"] = caption_layout
    if (keep_inline_article_links and provider == "bankone"
        and body_payload.media_type == "text/html" and manifest[0].get("article_link_bindings")
        and body_digest != context.legacy_published_inline_article_link_body):
        from .retained_inline_article_links import INLINE_LINKS_FIELD, authored_inline_article_links

        try:
            references = authored_inline_article_links(
                body_payload.payload.decode("utf-8-sig"), manifest[0]["article_link_bindings"], doc, doc,
            )
        except ValueError as error:
            if str(error) != "INLINE_ARTICLE_LINK_LIMIT":
                raise
            references = []
        if references:
            doc[INLINE_LINKS_FIELD] = references
            new_structure = True
            for record in (resources[0], provenance[0], manifest[0]):
                record["html_inline_article_link_layout"] = HTML_INLINE_ARTICLE_LINK_LAYOUT
    for node in _image_nodes(doc["blocks"]):
        local = image_records.get(node.get("image_id"))
        document_evidence = [evidence for evidence in node.get("evidence_ids", []) if evidence in evidence_sources]
        node["evidence_ids"] = document_evidence or list(evidence_ids)
        if local:
            for name in ("status", "media_type", "content_sha256", "storage_key"):
                if local.get(name) is not None:
                    node[name] = local[name]
            node["unavailable_reason"] = (
                local.get("reason") if local["status"] == "unavailable" else None
            )
    body_text, steps, images = project_document(
        doc, include_cell_figure_captions=html_figure_captions, include_table_captions=html_table_captions,
        include_flow_figure_captions=html_flow_figure_captions,
    )
    projection_partial = bool(failures or any(image.get("status") == "unavailable" for image in images))
    if recover_legacy_bankone_svg:
        # The ordered projection must retain each authorized placement after normalization.
        placed_svg_digests = Counter(
            image["content_sha256"] for image in images
            if image.get("content_sha256") in recovered_svg_digests
            and image.get("status") == "available" and image.get("media_type") == "image/png"
        )
        if projection_partial or placed_svg_digests != recovered_svg_digests or validate_ordered_document(doc, strict=True):
            raise SourceConnectorError(_LEGACY_SVG_RECOVERY_INCOMPLETE)
    title = str(context.descriptor.get("title") or "").strip()
    image_only = not body_text.strip() or body_text.strip() == title
    if image_only:
        if not title or not any(
            image.get("status") == "available" and image.get("image_id") in authored_images
            for image in images
        ):
            raise SourceConnectorError("INVALID_ARTICLE_BODY")
        # Keep the descriptor title in the required legacy text field. The
        # ordered document still contains only the original source blocks.
        body_text = title
    if linked_decimal_preserved or (step_parser is not None and step_parser.preserved):
        new_structure = True
        for record in (resources[0], provenance[0], manifest[0]):
            record["leading_decimal_layout"] = LEADING_DECIMAL_LAYOUT
    fingerprint = digest_json(
        {
            "provider": provider,
            "body_ref": body_ref,
            "body_sha256": resources[0]["sha256"],
            "body_media_type": resources[0]["media_type"],
            "resource_manifest": manifest,
            **({"asset_bindings": sorted(body.body["asset_bindings"], key=lambda item: item["source_url"])}
               if body.body.get("asset_bindings") else {}),
        }
    )
    return CapturedSource(
        context,
        fingerprint,
        snapshot_id(resources[0]["sha256"]),
        tuple(resources),
        manifest,
        provenance,
        doc,
        images,
        body_text,
        steps,
        [
            {
                "evidence_id": e,
                "body_source_snapshot_id": resources[0]["source_snapshot_id"],
            }
            for e in evidence_ids
        ] + [
            {"evidence_id": evidence, "body_source_snapshot_id": resource["source_snapshot_id"]}
            for evidence, resource in evidence_sources.items()
        ],
        "partial" if projection_partial else "readable",
        datetime.now(timezone.utc),
        service_schedule=(
            banktwo_service_schedule(body_payload.payload)
            if provider == "banktwo" and context.descriptor.get("category") == "Service Intervals"
            else None
        ),
        projection_version=(
            "source-projection-v10" if retained_pdf_repeats
            else "source-projection-v9" if positioned_html_table_images
            else "source-projection-v8" if pdf_asset_orders
            else "source-projection-v7" if positioned_pdf_figures
            else "source-projection-v6" if handled_pdf_embeds
            else "source-projection-v5" if new_structure
            else "source-projection-v2"
        ),
        recovered_legacy_bankone_svg=recover_legacy_bankone_svg,
        image_only=image_only,
        raster_dimensions=raster_dimensions,
    )
