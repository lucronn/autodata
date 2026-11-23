"""Place HTML-bound documents in the authoritative structured article."""

from collections import defaultdict
from itertools import groupby

from .article_document import (
    ConnectorDocumentEmbed, _clean_text, authored_image_caption, walk_ordered_list_items,
)


_BOUNDARY = object()
_PARAGRAPH_FIELDS = ("text", "value", "content", "body")
_LIST_ITEM_FIELDS = ("text", "value", "label", "content", "body", "message")
_TABLE_CELL_FIELDS = (*_PARAGRAPH_FIELDS, "label")
_CONTAINER_CAPTION_FIELDS = ("label", "caption", "title", "heading")
_TEXT_FIELDS = {
    **dict.fromkeys(("text", "paragraph"), _PARAGRAPH_FIELDS),
    **dict.fromkeys(("step", "instruction"), ("text", "action", "instruction", "value", "content", "body")),
    **dict.fromkeys(("heading", "title", "section"), ("text", "label", "title", "heading", "value", "content")),
    **dict.fromkeys(("callout", "note", "warning", "caution", "hint", "important"),
                    ("text", "value", "message", "content", "body")),
}
_CONTAINER_KINDS = {"ordered_list", "unordered_list", "list", "table", "grid"}
# HTML limits the nested list and table stacks to 32 and 8 respectively.
_MAX_CONTAINER_DEPTH = 40


def _kind(value):
    if isinstance(value, dict):
        return str(value.get("type") or value.get("kind") or "text").casefold()
    return "text" if isinstance(value, str) else ""


def _text(value, fields):
    if isinstance(value, dict):
        value = next((value[key] for key in fields if value.get(key)), "")
    if isinstance(value, str):
        return _clean_text(value) or None
    return None


def _anchor(value):
    fields = _TEXT_FIELDS.get(_kind(value))
    return _text(value, fields) if fields else None


def _parts(value, fields):
    children = value.get("blocks", []) if isinstance(value, dict) else []
    return _text(value, fields), children


def _layout(block):
    """Comparable ordered item contexts or the actual table cell grid."""
    kind = _kind(block)
    if kind in {"ordered_list", "unordered_list", "list"}:
        items = block.get("items") or block.get("values") or []
        if not isinstance(items, list):
            return None
        ordered = kind == "ordered_list"
        ordinals = ()
        if ordered:
            normalized = {"type": "ordered_list", "start": block.get("start"), "items": items}
            ordinals = tuple(
                index if number is None else number
                for index, (_, number) in enumerate(walk_ordered_list_items(normalized), 1)
            )
        return ("list", ordered, ordinals), [items]
    if kind in {"table", "grid"}:
        rows, columns = block.get("rows", []), block.get("columns", [])
        if not isinstance(rows, list) or not isinstance(columns, list):
            return None
        cells = [row.get("cells") or row.get("values") or row.get("blocks") or []
                 if isinstance(row, dict) else row for row in rows]
        if not all(isinstance(row, list) for row in cells):
            return None
        return ("table",), [columns, *cells]
    return None


def _shape(block, layouts, depth=0):
    """Use matching topology and full visible text, excluding parser embeds."""
    kind = _kind(block)
    if kind not in _CONTAINER_KINDS:
        text = _anchor(block)
        if text:
            return ("text", text)
        if kind == "image" and isinstance(block.get("asset_resource_ref"), str):
            return ("image", block["asset_resource_ref"], authored_image_caption(block))
        return None
    if depth >= _MAX_CONTAINER_DEPTH:
        return None
    if id(block) in layouts:
        return layouts[id(block)]
    layout = _layout(block)
    result = None
    if layout:
        identity, groups = layout
        fields = _LIST_ITEM_FIELDS if identity[0] == "list" else _TABLE_CELL_FIELDS
        shapes = [tuple(_part_shape(part, fields, layouts, depth + 1) for part in group) for group in groups]
        if all(all(part is not None for part in group) for group in shapes):
            result = (*identity, tuple(shapes))
    layouts[id(block)] = result
    return result


def _part_shape(part, fields, layouts, depth):
    """Each list item or table cell is its own placement context."""
    if not isinstance(part, (dict, str)):
        return None
    lead, children = _parts(part, fields)
    if not isinstance(children, list):
        return None
    shape = [("text", lead)] if lead else []
    shape.extend(_shape(child, layouts, depth) for child in children if not isinstance(child, ConnectorDocumentEmbed))
    if any(child is None for child in shape):
        return None
    spans = part.get("_html_table_cell_spans") if isinstance(part, dict) else None
    span_shape = None
    if isinstance(spans, dict):
        span_shape = (spans.get("rowspan", 1), spans.get("colspan", 1))
        if not all(type(span) is int for span in span_shape):
            return None
    return span_shape, tuple(shape)


def _gaps(blocks, lead):
    anchors = [_anchor(block) for block in blocks]
    bounded = [lead or _BOUNDARY, *anchors, _BOUNDARY]
    gaps = defaultdict(list)
    for index, (left, right) in enumerate(zip(bounded, bounded[1:])):
        if left is None or right is None or left is right is _BOUNDARY:
            continue
        gaps[left, right].append(index)
    return gaps


def _direct_placements(blocks, html_blocks, lead, html_lead):
    html_siblings = []
    runs = {}
    for is_embed, members in groupby(html_blocks, key=lambda node: isinstance(node, ConnectorDocumentEmbed)):
        if is_embed:
            runs[len(html_siblings)] = list(members)
        else:
            html_siblings.extend(members)
    if not runs:
        return []
    structured_gaps = _gaps(blocks, lead)
    html_gaps = _gaps(html_siblings, html_lead)
    placements = []
    for signature, html_indices in html_gaps.items():
        structured_indices = structured_gaps.get(signature, ())
        if len(html_indices) == len(structured_indices) == 1:
            html_index = html_indices[0]
            if html_index in runs:
                placements.append((html_index, structured_indices[0], runs[html_index]))
    return placements


def _nested_placements(blocks, html_blocks, layouts):
    with_documents = {
        index for index, block in enumerate(html_blocks)
        if _kind(block) in _CONTAINER_KINDS and next(_html_embeds([block]), None) is not None
    }
    if not with_documents:
        return []
    structured = defaultdict(list)
    html = defaultdict(list)
    for candidates, grouped in ((html_blocks, html), (blocks, structured)):
        for index, block in enumerate(candidates):
            if _kind(block) in _CONTAINER_KINDS:
                shape = _shape(block, layouts)
                if shape is not None:
                    grouped[shape].append(index)
        if not html:
            return []
    return [
        (indices[0], structured[shape][0])
        for shape, indices in html.items()
        if len(indices) == len(structured.get(shape, ())) == 1 and indices[0] in with_documents
    ]


def _place(blocks, html_blocks, lead, html_lead, accepted, layouts, resolved_pdf_refs):
    # Drop provisional nodes only for evaluating sibling positions. Their HTML
    # runs still supply the placement and whether a resource needs confirmation.
    direct = _direct_placements(blocks, html_blocks, lead, html_lead)
    html_siblings = [block for block in html_blocks if not isinstance(block, ConnectorDocumentEmbed)]
    nested = _nested_placements(blocks, html_siblings, layouts)
    positions = [(2 * html_index, 2 * index) for html_index, index, _ in direct]
    positions.extend((2 * html_index + 1, 2 * index + 1) for html_index, index in nested)
    order = [index for _, index in sorted(positions)]
    if order != sorted(set(order)):
        return 0

    placed = 0
    for html_index, index in nested:
        structured, html = blocks[index], html_siblings[html_index]
        caption = _text(structured, _CONTAINER_CAPTION_FIELDS)
        html_caption = _text(html, _CONTAINER_CAPTION_FIELDS)
        if caption and html_caption and caption != html_caption:
            continue
        identity, structured_groups = _layout(structured)
        _, html_groups = _layout(html)
        fields = _LIST_ITEM_FIELDS if identity[0] == "list" else _TABLE_CELL_FIELDS
        for structured_group, html_group in zip(structured_groups, html_groups):
            for offset, (part, html_part) in enumerate(zip(structured_group, html_group)):
                text, children = _parts(part, fields)
                other_text, html_children = _parts(html_part, fields)
                count = _place(children, html_children, text, other_text, accepted, layouts, resolved_pdf_refs)
                if count:
                    if isinstance(part, dict):
                        part["blocks"] = children
                    else:
                        structured_group[offset] = {"text": part, "blocks": children}
                    placed += count

    for _, index, run in sorted(direct, key=lambda placement: placement[1], reverse=True):
        accepted.update(map(id, run))
        ready = [node for node in run if not node.untyped or node["asset_resource_ref"] in resolved_pdf_refs]
        blocks[index:index] = ready
        placed += len(ready)
    return placed


def _html_embeds(blocks):
    # Reading the untouched HTML order keeps the capture's document quota in
    # authored order, including markers in nested cells and list items.
    for block in blocks:
        if isinstance(block, ConnectorDocumentEmbed):
            yield block
        elif isinstance(block, dict):
            layout = _layout(block)
            if layout:
                for group in layout[1]:
                    for part in group:
                        children = part.get("blocks") if isinstance(part, dict) else None
                        if isinstance(children, list):
                            yield from _html_embeds(children)


def _fold_html_captions(value):
    """Compare figures by their captions instead of the parser's fallback text."""
    if isinstance(value, list):
        value[:] = [
            node for node in value
            if not (isinstance(node, dict) and node.get("_html_figure_caption_text") is True)
        ]
        for node in value:
            _fold_html_captions(node)
    elif isinstance(value, dict) and not isinstance(value, ConnectorDocumentEmbed):
        if _kind(value) == "image":
            caption = value.get("_html_figure_caption") or value.get("_html_flow_figure_caption")
            if isinstance(caption, list):
                caption = " ".join(caption)
            if isinstance(caption, str):
                value["caption"] = caption
        for child in value.values():
            if isinstance(child, (list, dict)):
                _fold_html_captions(child)


def place_bound_documents(blocks, html_blocks, *, resolved_pdf_refs):
    """Insert only exact-position HTML bindings, keeping structured content intact."""
    if next(_html_embeds(html_blocks), None) is None:
        return (), 0
    _fold_html_captions(html_blocks)
    accepted = set()
    placed = _place(blocks, html_blocks, None, None, accepted, {}, resolved_pdf_refs)
    untyped = (node["asset_resource_ref"] for node in _html_embeds(html_blocks)
               if node.untyped and id(node) in accepted)
    return tuple(dict.fromkeys(untyped)), placed
