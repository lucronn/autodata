"""Bounded provider-bound capture; immutable public projection from actual bytes."""

from concurrent.futures import ThreadPoolExecutor, wait
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import time
import base64
from uuid import NAMESPACE_URL, uuid5
from .article_lifecycle_types import (
    CapturedSource,
    HTML_FIGURE_CAPTION_LAYOUT,
    HTML_FLOW_FIGURE_CAPTION_LAYOUT,
    HTML_MULTILINE_FIGURE_CAPTION_LAYOUT,
    HTML_TABLE_CAPTION_LAYOUT,
    PDF_BLANK_PAGE_LAYOUT,
    PDF_COMPACT_FIGURE_LAYOUT,
    PDF_LEGACY_FIGURE_LAYOUT,
    PDF_REPEAT_MARGIN_LAYOUT,
    PDF_SINGLE_LINE_FIGURE_LAYOUT,
    PDF_WORDLESS_FIGURE_LAYOUT,
    STRUCTURED_TABLE_CELL_ORDER_LAYOUT,
    STRUCTURED_TABLE_COLUMNS_LAYOUT,
    ResourceRef,
    article_id,
    digest_json,
)
from .source_adapters import adapt_bound_article, adapt_bound_pdf_embed
from .source_connector_client import SourceConnectorError
from .article_document import build_ordered_document, walk_ordered_list_items
from .svg_rasterization import rasterize_svg, SVGUnavailable, RASTERIZER_VERSION


_MAX_LINKED_PDFS = 4

# Keep in sync with the raster types accepted by the catalog image endpoint.
DISPLAYABLE_RASTER_MEDIA = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})


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


def _mark_json_table_cells(blocks):
    """Keep an authored cell sequence when a figure precedes procedure text."""
    textual = {"text", "paragraph", "callout", "warning", "caution", "note", "hint", "important"}
    ordered = []
    for node in _walk(blocks):
        # The connector document supplies the content, never private layout flags.
        for private in ("_ordered_html_table_cell", "_ordered_json_table_cell", "_preserve_cell_block_order"):
            node.pop(private, None)
        rows = node.get("rows")
        if not isinstance(rows, list) or str(node.get("type") or node.get("kind") or "").casefold() not in ("table", "grid"):
            continue
        for row in rows:
            if isinstance(row, dict):
                row = row.get("cells") or row.get("values") or row.get("blocks")
            if not isinstance(row, list):
                continue
            for cell in row:
                children = cell.get("blocks") if isinstance(cell, dict) else None
                if not isinstance(children, list) or any(not isinstance(child, dict) for child in children):
                    continue
                kinds = [str(child.get("type") or child.get("kind") or "text").casefold() for child in children]
                if ("image" in kinds and all(kind == "image" or kind in textual for kind in kinds)
                        and any(kind in textual for kind in kinds[kinds.index("image") + 1:])):
                    ordered.append(cell)
    for cell in ordered:
        cell["_ordered_json_table_cell"] = True
    return bool(ordered)


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
                          cell=cell or (node.get("type") == "table" and key == "rows"))

    visit(document.get("blocks", []))
    return "\n".join(texts), steps, images


def _replace_pdf_embeds(value, documents):
    """Expand signed connector document bindings in their original block positions."""
    if isinstance(value, dict):
        children = value.get("blocks")
        if isinstance(children, list) and any(
            isinstance(node, dict) and node.get("kind") == "document_embed" for node in children
        ):
            value["_preserve_cell_block_order"] = True
        for child in value.values():
            _replace_pdf_embeds(child, documents)
    elif isinstance(value, list):
        expanded = []
        for node in value:
            if isinstance(node, dict) and node.get("kind") == "document_embed":
                ref = node.get("asset_resource_ref")
                if ref in documents:
                    blocks, evidence, _ = documents[ref]
                    expanded.extend({**deepcopy(block), "evidence_ids": evidence} for block in blocks)
                else:
                    expanded.append({
                        "kind": "callout", "label": "Embedded document unavailable",
                        "text": "This document could not be prepared for Workshop.",
                    })
            else:
                _replace_pdf_embeds(node, documents)
                expanded.append(node)
        value[:] = expanded


def capture_source_article(
    context, *, registry, object_store, deadline_seconds=30.0,
    keep_embedded_pdf=False, keep_html_headings=False, keep_bound_pdf_iframes=False,
    keep_pdf_figure_order=False, keep_multiple_pdf_figures=False, keep_html_table_image_order=False,
    keep_repeated_pdf_figures=False, keep_pdf_figures_with_margins=False, keep_compact_pdf_figures=False,
    keep_html_figure_captions=False, keep_html_table_captions=False, keep_html_flow_figure_captions=False,
    keep_html_multiline_figure_captions=False,
    skip_blank_linked_pdf_pages=False,
    keep_wordless_linked_pdf_figures=False,
    keep_single_line_pdf_figures=False,
    keep_structured_table_columns=False,
    keep_structured_table_cell_order=False,
    keep_ordered_step_instructions=False,
    keep_image_only_step_instructions=False,
):
    if not 0 < deadline_seconds <= 30:
        raise ValueError("capture deadline must be within 30 seconds")
    provider = context.key.provider
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

    class BoundedObjects:
        """Bound caller latency, not an adapter's already-running network request.

        Runtime adapters must configure their own socket timeouts. On timeout the
        only possible late effect is a content-addressed blob upload; no worker
        thread can commit lifecycle observations or publish an article.
        """

        def put_object(self, *args):
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True)
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                pool.submit(object_store.put_object, *args).result(timeout=timeout)
            except TimeoutError:
                raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True) from None
            except Exception:
                # SDK and transport exceptions have no shared OSError base.
                raise SourceConnectorError(
                    "ASSET_STORAGE_UNAVAILABLE", retryable=True
                ) from None
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

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

    def retain_compact_figures(digest):
        return keep_compact_pdf_figures and digest not in context.legacy_published_pdf_compact_roots

    parser_pool = ThreadPoolExecutor(max_workers=1)
    try:
        parsing = parser_pool.submit(
            adapt_bound_article, body.to_source_resource(), context,
            keep_embedded_pdf=keep_embedded_pdf, keep_html_headings=keep_html_headings,
            keep_bound_pdf_iframes=keep_bound_pdf_iframes,
            keep_pdf_figure_order=keep_pdf_figure_order,
            keep_multiple_pdf_figures=keep_multiple_pdf_figures,
            keep_html_table_image_order=keep_html_table_image_order,
            keep_repeated_pdf_figures=retain_repeats(body.body["sha256"]),
            keep_pdf_figures_with_margins=retain_repeats_with_margins(body.body["sha256"]),
            keep_compact_pdf_figures=retain_compact_figures(body.body["sha256"]),
            keep_html_figure_captions=(
                keep_html_figure_captions and body.body["sha256"] != context.legacy_published_html_figure_body
            ),
            keep_html_table_captions=(
                keep_html_table_captions and body.body["sha256"] != context.legacy_published_html_table_caption_body
            ),
            keep_html_flow_figure_captions=(
                keep_html_flow_figure_captions and body.body["sha256"] != context.legacy_published_html_flow_figure_body
            ),
            keep_html_multiline_figure_captions=(
                keep_html_multiline_figure_captions
                and body.body["sha256"] != context.legacy_published_html_multiline_figure_body
            ),
            keep_structured_table_cell_order=keep_structured_table_cell_order,
            keep_ordered_step_instructions=keep_ordered_step_instructions,
            keep_image_only_step_instructions=keep_image_only_step_instructions,
        )
        article = parsing.result(timeout=remaining())
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        code = (
            "WRONG_APPLICABILITY"
            if "applicability" in str(error)
            else "INVALID_ARTICLE_BODY"
        )
        raise SourceConnectorError(code) from None
    except TimeoutError:
        raise SourceConnectorError("CAPTURE_DEADLINE", retryable=True) from None
    finally:
        parser_pool.shutdown(wait=False, cancel_futures=True)
    blocks = deepcopy(article["blocks"])
    html_figure_captions = article.get("html_figure_captions") is True
    html_flow_figure_captions = article.get("html_flow_figure_captions") is True
    html_multiline_figure_captions = article.get("html_multiline_figure_captions") is True
    html_table_captions = article.get("html_table_captions") is True
    handled_pdf_embeds = article.get("handled_pdf_embeds") is True
    positioned_html_table_images = article.get("positioned_html_table_images") is True
    positioned_pdf_figures = article.get("positioned_pdf_figures") is True
    retained_pdf_repeats = article.get("retained_repeated_pdf_figures") is True
    pdf_asset_order = article.get("pdf_legacy_asset_order", [])
    structured_table_cell_order = article.get("authored_json_blocks") is True and _mark_json_table_cells(blocks)
    step_layout = article.get("ordered_step_instructions_layout")
    structured_table_columns = keep_structured_table_columns and any(
        str(node.get("type") or node.get("kind") or "").casefold() in {"table", "grid"}
        and isinstance(node.get("columns"), list) and any(isinstance(column, dict) for column in node["columns"])
        for node in _walk(blocks)
    )
    new_structure = (
        structured_table_columns or structured_table_cell_order or step_layout or html_table_captions or html_flow_figure_captions
        or article.get("embedded_pdf")
        or (article.get("authored_html_headings") and any(block.get("kind") == "heading" for block in _walk(blocks)))
    )
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
        if handled_pdf_embeds and node.get("kind") == "document_embed"
        and isinstance(node.get("asset_resource_ref"), str)
        and node["asset_resource_ref"] in (body.body.get("asset_resource_refs") or [])
        and node["asset_resource_ref"] != body_ref
    )
    selected_documents = set(list(linked_refs)[:_MAX_LINKED_PDFS])
    # Stable dedupe retains the first source position; opaque refs are never normalized.
    refs = list(dict.fromkeys(ref for ref in refs if ref not in linked_refs))
    for node in _walk(blocks):
        if (
            (node.get("kind") or node.get("type")) == "image"
            and not node.get("asset_resource_ref")
            and node.get("url") in refs
        ):
            node["asset_resource_ref"] = node["url"]
    labor_ref = context.descriptor.get("labor_resource_ref")
    optional = [(ref, "asset") for ref in refs]
    optional += [(ref, "document_asset") for ref in linked_refs if ref in selected_documents]
    if labor_ref and labor_ref not in refs and labor_ref not in linked_refs and labor_ref != body_ref:
        optional.append((labor_ref, "labor"))
    resources = [upload_resource(body, body_ref, "body", bounded_objects)]
    manifest = [
        {k: resources[0][k] for k in ("role", "opaque_ref", "sha256", "media_type")}
    ]
    if article.get("retained_pdf_figures_with_margins") is True:
        resources[0]["pdf_figure_layout"] = manifest[0]["pdf_figure_layout"] = PDF_REPEAT_MARGIN_LAYOUT
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
    if structured_table_columns:
        resources[0]["structured_table_columns_layout"] = manifest[0]["structured_table_columns_layout"] = STRUCTURED_TABLE_COLUMNS_LAYOUT
    if structured_table_cell_order:
        resources[0]["structured_table_cell_order_layout"] = manifest[0]["structured_table_cell_order_layout"] = STRUCTURED_TABLE_CELL_ORDER_LAYOUT
    if step_layout:
        resources[0]["ordered_step_instructions_layout"] = manifest[0]["ordered_step_instructions_layout"] = step_layout
    provenance = [deepcopy(resources[0])]
    failures = {}
    localized = {}
    documents = {}

    # All requests share one deadline; no more than four can run concurrently.
    def fetch(pair):
        ref, role = pair
        originals = []
        try:
            envelope = read(ref)
            if role == "document_asset":
                payload = envelope.to_source_resource()
                if payload.media_type != "application/pdf":
                    return ref, role, None, "UNSUPPORTED_DOCUMENT_MEDIA", originals, None
                resource = upload_resource(envelope, ref, role, bounded_objects)
                try:
                    adapted = adapt_bound_pdf_embed(
                        payload, require_complete_ocr=True, keep_pdf_figure_order=keep_pdf_figure_order,
                        keep_multiple_pdf_figures=keep_multiple_pdf_figures,
                        keep_repeated_pdf_figures=retain_repeats(payload.content_sha256),
                        keep_pdf_figures_with_margins=retain_repeats_with_margins(payload.content_sha256),
                        keep_compact_pdf_figures=retain_compact_figures(payload.content_sha256),
                        keep_single_line_compact_figures=keep_single_line_pdf_figures,
                        keep_wordless_pdf_figures=keep_wordless_linked_pdf_figures,
                        skip_blank_pages=(
                            skip_blank_linked_pdf_pages
                            and payload.content_sha256 not in context.legacy_published_pdf_blank_roots
                        ),
                    )
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

    pool = ThreadPoolExecutor(max_workers=4)
    futures = [pool.submit(fetch, pair) for pair in optional]
    done, _ = wait(futures, timeout=max(0, deadline - time.monotonic()))
    for pair, future in zip(optional, futures):
        ref, role = pair
        if future not in done:
            future.cancel()
            resource = None
            failure = "CAPTURE_DEADLINE"
        else:
            _, _, resource, failure, originals, adapted = future.result()
            if adapted is not None:
                documents[ref] = (adapted["blocks"], ["source:" + resource["source_snapshot_id"]],
                                  adapted.get("pdf_legacy_asset_order", []))
                positioned_pdf_figures |= adapted.get("positioned_pdf_figures") is True
                retained_pdf_repeats |= adapted.get("retained_repeated_pdf_figures") is True
                if adapted.get("retained_pdf_figures_with_margins") is True:
                    resource["pdf_figure_layout"] = PDF_REPEAT_MARGIN_LAYOUT
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
                    "pdf_figure_layout", "pdf_compact_figure_layout", "pdf_blank_page_layout", "pdf_single_line_figure_layout",
                    "pdf_wordless_figure_layout",
                ) if key in resource}
            )
            if role == "asset":
                localized[ref] = resource
        else:
            failures[ref] = failure
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

    # Embedded figures are derived only from verified bytes and never fetched by URL.
    evidence_sources = {
        "source:" + resource["source_snapshot_id"]: resource
        for resource in resources if resource["role"] == "document_asset"
    }
    embedded_nodes = [
        node for node in _walk(blocks)
        if (node.get("kind") or node.get("type")) == "image"
        and not node.get("asset_resource_ref") and node.get("url", "").startswith("data:image/")
    ]
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
            header, encoded = uri.split(",", 1)
            media = header[5:].split(";", 1)[0].strip().lower()
            if ";base64" not in header or media == "image/svg+xml":
                raise ValueError("unsupported embedded figure")
            payload = base64.b64decode(encoded, validate=True)
            digest = sha256(payload).hexdigest()
            key = "sources/" + digest[:16] + "/" + digest
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
            if not retained_pdf_repeats or (key, media) not in uploaded_embedded_images:
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
    for node in _walk(blocks):
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
    doc = build_ordered_document(
        {"article_id": str(article_id(context.key)), "evidence_ids": evidence_ids},
        blocks,
        preserve_marked_cells=handled_pdf_embeds or positioned_html_table_images or structured_table_cell_order,
        preserve_structured_columns=structured_table_columns,
    )
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
    if (
        not body_text.strip()
        or body_text.strip() == str(context.descriptor.get("title", "")).strip()
    ):
        raise SourceConnectorError("INVALID_ARTICLE_BODY")
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
        (
            "partial"
            if failures or any(i.get("status") == "unavailable" for i in images)
            else "readable"
        ),
        datetime.now(timezone.utc),
        projection_version=(
            "source-projection-v10" if retained_pdf_repeats
            else "source-projection-v9" if positioned_html_table_images
            else "source-projection-v8" if pdf_asset_orders
            else "source-projection-v7" if positioned_pdf_figures
            else "source-projection-v6" if handled_pdf_embeds
            else "source-projection-v5" if new_structure
            else "source-projection-v2"
        ),
    )
