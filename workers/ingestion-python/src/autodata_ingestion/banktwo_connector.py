"""Read-only, vehicle-scoped access to Banktwo repair content."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from itertools import accumulate, pairwise
import json
import re
import os
from typing import Any, Mapping

from .article_document import ConnectorBankoneGraphic, ConnectorDocumentEmbed, list_number
from .source_connector_client import (
    SourceConnectorClient,
    SourceConnectorError,
    SourceEnvelopeV1,
    source_connector_registry,
    source_connector_token,
)


_LIST_TAGS = {"ol": "ordered_list", "ul": "unordered_list"}
_HEADING_LEVELS = {f"h{level}": level for level in range(1, 7)}
_SECTION_TITLE_PARAGRAPH = re.compile(r"<p>\s*<(b|strong)>\s*([^<>]{1,80}?)\s*</\1>\s*</p>", re.IGNORECASE)
_SECTION_TITLE_LEVELS = {"removal": 2, "installation": 2, "all vehicles": 3}
_BANKONE_GRAPHIC_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_MAX_LIST_DEPTH = 32
_MAX_FIGURE_DEPTH = 32
_MAX_TABLE_DEPTH = 8
_TABLE_ROW_GROUPS = frozenset({"thead", "tbody", "tfoot"})
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr",
})
_HTML_SPACE = " \t\n\f\r"
_SRCSET_SPACE = re.compile(r"[ \t\n\f\r]*")
_SRCSET_URL = re.compile(r"[^ \t\n\f\r]+")
_SRCSET_WIDTH = re.compile(r"0*[1-9][0-9]*w")
_SRCSET_DENSITY = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?x")
_HTML_LIST_NUMBER = re.compile(r"([+-]?)0*([0-9]{1,10})")
_SUPERSCRIPT_NUMBER = re.compile(r"[+−⁺⁻-]?\s*[0-9⁰¹²³⁴⁵⁶⁷⁸⁹]+")
_FRACTIONAL_SUPERSCRIPT = re.compile(r"[+−-]?\s*(?:[0-9]*\.[0-9]+|[0-9]+\s*[/⁄]\s*[0-9]+)")
_SUPERSCRIPT_TRANSLATION = str.maketrans("0123456789+−-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻")


def _html_list_number(value):
    if not isinstance(value, str):
        return None
    match = _HTML_LIST_NUMBER.fullmatch(value.strip())
    return list_number(int(match[1] + match[2])) if match else None


def _bound_srcset_ref(value, bindings, ref):
    # A comma can be part of the URL. A comma after the URL or descriptor
    # separates candidates. Accept only the usual width and density forms.
    position = 0
    while position < len(value):
        position = _SRCSET_SPACE.match(value, position).end()
        if position == len(value):
            break
        match = _SRCSET_URL.match(value, position)
        url, position = match[0], match.end()
        if url.startswith(","):
            return None
        if url.endswith(","):
            url = url[:-1]
            if url.endswith(","):
                return None
        else:
            comma = value.find(",", position)
            end = len(value) if comma == -1 else comma
            descriptor = value[position:end].strip(_HTML_SPACE)
            if descriptor and not _SRCSET_WIDTH.fullmatch(descriptor):
                if not _SRCSET_DENSITY.fullmatch(descriptor) or not 0 < float(descriptor[:-1]) < float("inf"):
                    return None
            position = end + 1
        candidate = bindings.get(url)
        if not candidate or (ref and candidate != ref):
            return None
        ref = candidate
    return ref


def _table_spans(attrs):
    rowspan = _html_list_number(attrs.get("rowspan"))
    colspan = _html_list_number(attrs.get("colspan"))
    spans = {}
    if rowspan is not None and (rowspan == 0 or rowspan > 1):
        spans["rowspan"] = min(rowspan, 65_534)
    if colspan is not None and colspan > 1:
        spans["colspan"] = min(colspan, 1_000)
    return spans


def _resolve_table_rowspans(rows, boundaries):
    """Use finite spans scoped to the authored group and retained rows."""
    retained_rows = list(accumulate(map(bool, rows), initial=0))
    has_spans = False
    for start, stop in pairwise(boundaries):
        for index in range(start, stop):
            for cell in rows[index]:
                spans = cell.get("_html_table_cell_spans")
                if spans is None:
                    continue
                rowspan = spans.pop("rowspan", None)
                if rowspan is not None:
                    end = stop if rowspan == 0 else min(stop, index + rowspan)
                    length = retained_rows[end] - retained_rows[index]
                    if length > 1:
                        spans["rowspan"] = min(length, 65_534)
                has_spans |= bool(spans)
    return has_spans


@dataclass
class _ListItem:
    number: int | None = None
    lead: list[str] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _ListFrame:
    tag: str
    start: int
    authored_start: bool = False
    items: list[str | dict[str, Any]] = field(default_factory=list)
    item: _ListItem | None = None


@dataclass
class _FigureFrame:
    blocks: list[dict[str, Any]] | None
    in_table: bool = False
    image: dict[str, Any] | None = None
    caption: list[dict[str, Any]] | None = None
    open_caption: int | None = None
    invalid: bool = False
    lazy_images: dict[tuple[int, int], tuple[str, bool]] = field(default_factory=dict)
    noscript_images: dict[tuple[int, int], tuple[str, str]] = field(default_factory=dict)


@dataclass
class _TableCaption:
    text: str
    source: list[Any]
    start: int
    stop: int


@dataclass
class _EnclosingTable:
    rows: list
    row: list
    cell: list
    cell_spans: dict | None
    row_group_boundaries: list[int]
    has_candidate_spans: bool
    in_head: bool
    column_header: bool | None
    head_cells: list[tuple[dict, bool]]
    caption: _TableCaption | None
    figures: list[_FigureFrame]


class ArticleParser(HTMLParser):
    """Keep ordered text, figures and component links without executable HTML."""

    _DOCUMENT_LINK = "mtr-doc-link"
    _DOCUMENT_LINK_EXCLUSIONS = frozenset({
        "a", "button", "details", "form", "iframe", "label", "noscript", "object",
        "script", "select", "style", "summary", "template", "textarea",
    })
    _DOCUMENT_LINK_OPENING_TAG = re.compile(
        r"<(?:li|mtr-doc-link)(?:[ \t\n\r\f]+[^\x00-\x20\"'<>/=]+"
        r"(?:[ \t\n\r\f]*=[ \t\n\r\f]*(?:\"[^\"]*\"|'[^']*'|[^\x00-\x20\"'`=<>]+))?)*"
        r"[ \t\n\r\f]*>",
        re.IGNORECASE | re.ASCII,
    )
    _DOCUMENT_LINK_CLOSING_TAG = re.compile(r"</(?:li|mtr-doc-link)[ \t\n\r\f]*>", re.IGNORECASE | re.ASCII)
    _HIDDEN_LINK_STYLE = re.compile(
        r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse))"
        r"\s*(?:!important\s*)?(?:;|$)", re.IGNORECASE,
    )

    def __init__(
        self, *, asset_bindings=(), preserve_legacy_list_starts=True, keep_html_headings=False,
        keep_bound_pdf_iframes=False, keep_html_table_image_order=False, keep_html_figure_captions=False,
        keep_html_table_captions=False, keep_html_flow_figure_captions=False,
        keep_html_multiline_figure_captions=False,
        keep_html_table_spans=False, keep_html_media_table_headers=False,
        keep_html_nested_tables=False, keep_html_numeric_superscripts=False, resolved_pdf_refs=frozenset(),
        include_untyped_pdf_positions=False, keep_bound_html_images=False, skip_noscript_images=frozenset(),
        declared_image_refs=frozenset(), lazy_image_alts=None, keep_html_document_links=False,
        keep_html_section_titles=False, keep_bankone_graphic_positions=False,
    ):
        super().__init__(convert_charrefs=True)
        self._asset_bindings = {item["source_url"]: item["resource_ref"] for item in asset_bindings}
        self._keep_bound_html_images = keep_bound_html_images and bool(self._asset_bindings)
        self._skip_noscript_images = skip_noscript_images
        self._lazy_image_alts = lazy_image_alts or {}
        self._declared_image_refs = declared_image_refs
        self._hidden_image_scope = None
        self._hidden_image_depth = 0
        self.html_bound_images = False
        self.html_image_mirrors = set()
        self.html_lazy_image_alts = {}
        self.blocks = []
        self.links = []
        self._text = []
        self._skip = 0
        self._image_link = 0
        self._lists: list[_ListFrame] = []
        self._list_start = 1
        self._list_continuation_pending = False
        self._preserve_legacy_list_starts = preserve_legacy_list_starts
        self._keep_html_headings = keep_html_headings
        self._keep_html_section_titles = keep_html_section_titles
        self.html_section_titles = False
        self._keep_bankone_graphic_positions = keep_bankone_graphic_positions
        self.bankone_graphic_positions = False
        self._keep_html_document_links = keep_html_document_links
        self.html_document_links = False
        # Bounds are indexes into _text. A new list item awaits both bounds.
        self._document_link_bounds: tuple[int | None, int | None] | None = None
        self._document_link_scope: str | None = None
        self._document_link_depth = 0
        self._keep_bound_pdf_iframes = keep_bound_pdf_iframes
        self._keep_html_table_image_order = keep_html_table_image_order
        self._keep_html_figure_captions = keep_html_figure_captions
        self._keep_html_table_captions = keep_html_table_captions
        self._keep_html_flow_figure_captions = keep_html_flow_figure_captions
        self._keep_html_multiline_figure_captions = keep_html_multiline_figure_captions
        self._keep_html_table_spans = keep_html_table_spans
        self._keep_html_media_table_headers = keep_html_media_table_headers
        self._keep_html_nested_tables = keep_html_nested_tables
        self._keep_html_numeric_superscripts = keep_html_numeric_superscripts
        self._superscript_start = 0
        self._superscript_depth = 0
        self.handled_pdf_embeds = False
        self.untyped_pdf_embed_refs = {}
        self._resolved_pdf_refs = resolved_pdf_refs
        self._include_untyped_pdf_positions = include_untyped_pdf_positions
        self._hidden_html_tag = None
        self._hidden_html_depth = 0
        self.positioned_html_table_images = False
        self.html_figure_captions = False
        self.html_flow_figure_captions = False
        self.html_multiline_figure_captions = False
        self.html_table_captions = False
        self.html_table_spans = False
        self.html_media_table_headers = False
        self.html_nested_tables = False
        self.html_numeric_superscripts = False
        self._figures: list[_FigureFrame] = []
        self._hidden_embed_tags: list[str] = []
        self._heading: dict[str, Any] | None = None
        self._table_rows = None
        self._table_row = None
        self._table_cell = None
        self._table_cell_spans = None
        self._table_row_group_boundaries = [0]
        self._table_has_candidate_spans = False
        self._table_in_head = False
        self._table_column_header: bool | None = None
        self._table_head_cells: list[tuple[dict, bool]] = []
        self._table_caption_blocks: list[dict[str, Any]] | None = None
        self._table_caption: _TableCaption | None = None
        self._enclosing_tables: list[_EnclosingTable] = []

    @property
    def _in_table(self):
        return self._table_rows is not None

    def _current_list_item(self):
        return self._lists[-1].item if self._lists else None

    def _finish_superscript(self, start):
        text = "".join(self._text[start:])
        token = text.strip()
        if _SUPERSCRIPT_NUMBER.fullmatch(token):
            exponent = "".join(token.split()).translate(_SUPERSCRIPT_TRANSLATION)
        elif _FRACTIONAL_SUPERSCRIPT.fullmatch(token):
            # There is no superscript decimal point. Delimit the exponent so
            # the number cannot be mistaken for digits of the base value.
            exponent = "^(" + "".join(token.split()).replace("⁄", "/") + ")"
        else:
            return
        if exponent != token:
            before, _, after = text.partition(token)
            self._text[start:] = [before + exponent + after]
            self.html_numeric_superscripts = True

    def flush(self, *, inline=False):
        if self._superscript_depth:
            self._finish_superscript(self._superscript_start)
            if inline:
                self._superscript_start = 0
            else:
                self._superscript_depth = 0
        value = re.sub(r"\s+", " ", "".join(self._text)).strip()
        self._text = []
        if self._heading is not None:
            heading = self._heading
            self._heading = None
            if value:
                heading["text"] = value
                self._append_block(heading)
            else:
                for image in heading.get("images", []):
                    self._append_block(image)
            return
        if not value:
            return
        item = self._current_list_item()
        block = {"kind": "text", "text": value}
        if self._table_caption_blocks is not None:
            self._table_caption_blocks.append(block)
        elif self._table_cell is not None:
            self._table_cell.append(block)
        elif item is None:
            self.blocks.append(block)
            self._list_start = 1
            self._list_continuation_pending = False
        elif item.blocks:
            item.blocks.append(block)
        else:
            item.lead.append(value)

    def _append_block(self, block):
        item = self._current_list_item()
        if item is None:
            self.blocks.append(block)
        else:
            item.blocks.append(block)

    def _start_document_link_tag(self, tag, attrs):
        if self._document_link_scope is not None:
            if tag == self._document_link_scope:
                self._document_link_depth += 1
        else:
            style = attrs.get("style") or ""
            excluded = (
                tag in self._DOCUMENT_LINK_EXCLUSIONS or "hidden" in attrs
                or (attrs.get("aria-hidden") or "").strip().casefold() == "true"
                or bool(style and self._HIDDEN_LINK_STYLE.search(style))
            )
            if (excluded or tag == self._DOCUMENT_LINK) and tag not in _VOID_TAGS:
                self._document_link_scope = tag
                self._document_link_depth = 1
            if (tag == self._DOCUMENT_LINK and not excluded and self._document_link_bounds == (None, None)
                    and self._DOCUMENT_LINK_OPENING_TAG.fullmatch(self.get_starttag_text())
                    and not any(part.strip() for part in self._text)):
                self._document_link_bounds = (len(self._text), None)
                return
        self._document_link_bounds = None

    def _end_document_link_tag(self, tag):
        if tag == self._document_link_scope:
            self._document_link_depth -= 1
            if self._document_link_depth == 0:
                self._document_link_scope = None
        bounds = self._document_link_bounds
        self._document_link_bounds = None
        if bounds is None or bounds[0] is None or self._document_link_scope is not None:
            return
        start, end = bounds
        if tag == self._DOCUMENT_LINK and end is None:
            self._document_link_bounds = (start, len(self._text))
        elif tag == "li" and end is not None and not any(part.strip() for part in self._text[end:]):
            item = self._current_list_item()
            label = " ".join("".join(self._text[start:end]).split())
            if label and item is not None and not item.lead and not item.blocks:
                item.blocks.append({"kind": "link", "text": label})
                self._text = []
                self.html_document_links = True

    def _finish_list_item(self):
        frame = self._lists[-1]
        item = frame.item
        if item is None:
            return
        self.flush()
        if self._figures:
            self._figures[:] = [frame for frame in self._figures if frame.blocks is not item.blocks]
        text = " ".join(item.lead)
        if item.blocks or item.number is not None:
            entry = {"text": text}
            if item.number is not None:
                entry["number"] = item.number
            if item.blocks:
                entry["blocks"] = item.blocks
            frame.items.append(entry)
        elif text:
            frame.items.append(text)
        frame.item = None

    def _emit_list(self, frame, *, top_level):
        next_number = frame.start
        has_numbering = frame.authored_start
        if not frame.items:
            return next_number, has_numbering
        block = {"kind": _LIST_TAGS[frame.tag], "items": frame.items}
        if frame.tag == "ol":
            # The legacy facade still uses inferred starts to flatten HTML.
            # Bound capture stores only source-authored numbering or its continuation.
            if self._preserve_legacy_list_starts or frame.authored_start:
                block["start"] = frame.start
            for item in frame.items:
                if isinstance(item, dict) and "number" in item:
                    next_number = item["number"]
                    has_numbering = True
                next_number += 1
        else:
            next_number += len(frame.items)
        self._append_block(block)
        if top_level:
            self._list_start = next_number
            self._list_continuation_pending = True
        return next_number, has_numbering

    def _finish_list(self):
        self._finish_list_item()
        frame = self._lists.pop()
        self._emit_list(frame, top_level=not self._lists)

    def close(self):
        super().close()
        while self._in_table:
            self._finish_table()
        while self._lists:
            self._finish_list()

    def _flush_cell(self):
        self.flush()
        if self._figures:
            self._figures[:] = [frame for frame in self._figures if not frame.in_table]
        if self._table_cell is not None and self._table_row is not None:
            cell = {"blocks": self._table_cell}
            if self._table_column_header is not None:
                self._table_head_cells.append((cell, self._table_column_header))
            if self._table_cell_spans:
                cell["_html_table_cell_spans"] = self._table_cell_spans
                self._table_has_candidate_spans = True
            if self._keep_html_table_image_order or self.html_nested_tables:
                kinds = [block["kind"] for block in self._table_cell]
                has_nested_table = self.html_nested_tables and "table" in kinds
                if has_nested_table:
                    cell["_preserve_cell_block_order"] = True
                if self._enclosing_tables or has_nested_table:
                    for block in self._table_cell:
                        if block["kind"] == "text":
                            block["_html_literal_table_text"] = True
                # Cells with a linked document already have ordered blocks.
                if (self._keep_html_table_image_order and "document_embed" not in kinds and "image" in kinds
                        and "text" in kinds[kinds.index("image") + 1:]):
                    cell["_ordered_html_table_cell"] = True
                    self.positioned_html_table_images = True
            self._table_row.append(cell)
        self._table_cell = None
        self._table_cell_spans = None
        self._table_column_header = None

    def _flush_row(self):
        self._flush_cell()
        if self._table_row is not None and self._table_rows is not None:
            if self._table_row or self._keep_html_table_spans:
                self._table_rows.append(self._table_row)
        self._table_row = None

    def _mark_table_row_group_boundary(self):
        row_count = len(self._table_rows) + int(self._table_row is not None)
        if self._table_row_group_boundaries[-1] != row_count:
            self._table_row_group_boundaries.append(row_count)

    def _suspend_enclosing_table(self):
        if len(self._enclosing_tables) + 1 >= _MAX_TABLE_DEPTH:
            raise ValueError("HTML table nesting exceeds its limit")
        self._enclosing_tables.append(_EnclosingTable(
            rows=self._table_rows,
            row=self._table_row,
            cell=self._table_cell,
            cell_spans=self._table_cell_spans,
            row_group_boundaries=self._table_row_group_boundaries,
            has_candidate_spans=self._table_has_candidate_spans,
            in_head=self._table_in_head,
            column_header=self._table_column_header,
            head_cells=self._table_head_cells,
            caption=self._table_caption,
            figures=self._figures,
        ))
        self._figures = []
        self.html_nested_tables = True

    def _resume_enclosing_table(self):
        parent = self._enclosing_tables.pop()
        self._table_rows = parent.rows
        self._table_row = parent.row
        self._table_cell = parent.cell
        self._table_cell_spans = parent.cell_spans
        self._table_row_group_boundaries = parent.row_group_boundaries
        self._table_has_candidate_spans = parent.has_candidate_spans
        self._table_in_head = parent.in_head
        self._table_column_header = parent.column_header
        self._table_head_cells = parent.head_cells
        self._table_caption = parent.caption
        self._figures = parent.figures

    def _finish_table(self):
        self._finish_table_caption(closed=False)
        self._flush_row()
        rows = self._table_rows
        if rows and self._keep_html_table_spans:
            if self._table_has_candidate_spans:
                self._mark_table_row_group_boundary()
                self.html_table_spans |= _resolve_table_rowspans(rows, self._table_row_group_boundaries)
            rows = [row for row in rows if row]
        self._table_rows = None
        table = None
        if rows:
            # The ordered table contract has one row of column headers.
            # Only project an explicit leading all-TH row with media.
            first = rows[0]
            headers = self._table_head_cells
            if (headers and len(rows) > 1 and len(headers) == len(first)
                    and all(is_header and head is cell for (head, is_header), cell in zip(headers, first, strict=True))
                    and any(block["kind"] in {"image", "document_embed"} for cell in first for block in cell["blocks"])):
                table = {"kind": "table", "columns": first, "rows": rows[1:]}
                self.html_media_table_headers = True
            else:
                table = {"kind": "table", "rows": rows}
            caption = self._table_caption
            if caption is not None:
                del caption.source[caption.start:caption.stop]
                table["label"] = caption.text
                self.html_table_captions = True
        self._table_caption = None
        if self._enclosing_tables:
            self._resume_enclosing_table()
            if table is not None:
                self._table_cell.append(table)
        elif table is not None:
            self._append_block(table)

    def _finish_table_caption(self, *, closed):
        if self._table_caption_blocks is None:
            return
        self.flush()
        blocks, self._table_caption_blocks = self._table_caption_blocks, None
        # Keep the literal flow until a table with cells is ready. Mixed media,
        # malformed captions and empty tables retain their existing content.
        if self._enclosing_tables:
            source = self._enclosing_tables[-1].cell
            start = len(source)
            source.extend(blocks)
        else:
            item = self._current_list_item()
            source = self.blocks if item is None else (item.blocks if item.blocks else item.lead)
            start = len(source)
            for block in blocks:
                if block["kind"] == "text":
                    self._text.append(block["text"])
                    self.flush()
                else:
                    self._append_inline_media(block)
        if closed and blocks and all(block["kind"] == "text" for block in blocks):
            self._table_caption = _TableCaption(
                " ".join(block["text"] for block in blocks), source, start, len(source),
            )

    def _append_inline_media(self, block):
        self.flush(inline=True)
        if self._table_caption_blocks is not None:
            self._table_caption_blocks.append(block)
            return
        if self._table_cell is not None:
            self._table_cell.append(block)
            return
        if self._lists and self._lists[-1].item is None:
            # Emit media between sibling <li> tags in the enclosing item.
            frame = self._lists.pop()
            frame.start, frame.authored_start = self._emit_list(frame, top_level=not self._lists)
            if isinstance(block, ConnectorBankoneGraphic) and frame.tag == "ol" and frame.items:
                frame.authored_start = True
            frame.items = []
            self._append_block(block)
            self._lists.append(frame)
        else:
            self._append_block(block)

    def _start_figure(self):
        cell = self._table_cell is not None and self._keep_html_figure_captions
        item = self._current_list_item()
        blocks = None
        if cell:
            blocks = self._table_cell
        elif self._keep_html_flow_figure_captions and not self._in_table and (not self._lists or item is not None):
            blocks = item.blocks if item is not None else self.blocks
        if blocks is None and not self._figures:
            return
        if self._figures:
            self._figures[-1].invalid = True
        if len(self._figures) >= _MAX_FIGURE_DEPTH:
            raise ValueError("HTML figure nesting exceeds its limit")
        self._figures.append(_FigureFrame(blocks, in_table=self._in_table))

    def _start_figure_caption(self):
        self.flush()
        frame = self._figures[-1]
        if frame.in_table:
            self.html_figure_captions = True
        else:
            self.html_flow_figure_captions = True
        if frame.open_caption is not None or frame.caption is not None:
            frame.invalid = True
        blocks = frame.blocks
        if blocks is not None:
            frame.open_caption = len(blocks)

    def _finish_figure_caption(self):
        self.flush()
        frame = self._figures[-1]
        if frame.open_caption is None:
            return
        offset = frame.open_caption
        frame.open_caption = None
        # Only trailing text following this exact image is a safe caption.
        # Other content stays in the authored flow.
        blocks = frame.blocks
        caption = blocks[offset:] if blocks is not None else []
        if (blocks is not None and offset > 0 and caption and blocks[offset - 1] is frame.image
                and (len(caption) == 1 or self._keep_html_multiline_figure_captions)
                and all(part.get("kind") == "text" for part in caption)):
            frame.caption = caption
        else:
            frame.invalid = True

    def _bound_lazy_image(self, attrs):
        locator = (attrs.get("data-src") or "").strip(_HTML_SPACE)
        ref = self._asset_bindings.get(locator) if locator else None
        if locator and not ref:
            return None
        for name in ("srcset", "data-srcset"):
            value = (attrs.get(name) or "").strip(_HTML_SPACE)
            if value:
                ref = _bound_srcset_ref(value, self._asset_bindings, ref)
                if not ref:
                    return None
        return ref

    def handle_starttag(self, tag, attrs):
        duplicate_graphic_id = tag == "mtr-image" and sum(name == "id" for name, _ in attrs) != 1
        attrs = dict(attrs)
        if self._keep_html_document_links:
            self._start_document_link_tag(tag, attrs)
        if self._hidden_embed_tags:
            if tag in {"iframe", "object"}:
                self._hidden_embed_tags.append(tag)
            return
        if self._hidden_html_tag is not None:
            if tag == self._hidden_html_tag:
                self._hidden_html_depth += 1
            return
        if tag in {"script", "style"}:
            self._skip += 1
        if self._skip:
            return
        if self._include_untyped_pdf_positions and (tag == "template" or "hidden" in attrs):
            if tag not in _VOID_TAGS:
                self._hidden_html_tag = tag
                self._hidden_html_depth = 1
            return
        if self._keep_bound_html_images or self._keep_bankone_graphic_positions:
            if tag == self._hidden_image_scope:
                self._hidden_image_depth += 1
            elif self._hidden_image_scope is None and tag not in _VOID_TAGS and (
                tag in {"template", "noscript"} or "hidden" in attrs
            ):
                self._hidden_image_scope = tag
                self._hidden_image_depth = 1
        if tag == "figure" and (self._keep_html_figure_captions or self._keep_html_flow_figure_captions):
            self._start_figure()
        if tag == "figcaption" and self._figures and self._figures[-1].blocks is not None:
            self._start_figure_caption()
            return
        if self._keep_bound_pdf_iframes and tag in {"iframe", "object", "embed"}:
            locator = attrs.get("data" if tag == "object" else "src")
            ref = self._asset_bindings.get(locator)
            media_type = (attrs.get("type") or "").strip().casefold()
            is_document = tag == "iframe" or media_type == "application/pdf"
            untyped = tag != "iframe" and not media_type and bool(ref)
            if untyped:
                self.untyped_pdf_embed_refs[ref] = None
                is_document = self._include_untyped_pdf_positions or ref in self._resolved_pdf_refs
            if is_document:
                self.handled_pdf_embeds = True
                if ref and not (tag == "iframe" and "srcdoc" in attrs):
                    self._append_inline_media(ConnectorDocumentEmbed(ref, untyped=untyped))
                if tag != "embed":
                    self._hidden_embed_tags.append(tag)
                return
        if self._list_continuation_pending and tag not in {"ol", "ul", "li", "a", "img"}:
            self._list_start = 1
            self._list_continuation_pending = False
        if tag == "sup" and self._keep_html_numeric_superscripts:
            if not self._superscript_depth:
                self._superscript_start = len(self._text)
            self._superscript_depth += 1
            return
        # Table cells normalize to text and images, including any heading text.
        if self._keep_html_headings and tag in _HEADING_LEVELS and not self._in_table:
            self.flush()
            self._heading = {"kind": "heading", "level": _HEADING_LEVELS[tag]}
            return
        if tag == "br" and self._heading is not None:
            if self._superscript_depth:
                self._finish_superscript(self._superscript_start)
                self._superscript_start = len(self._text) + 1
            self._text.append(" ")
            return
        if tag == "table":
            self._finish_table_caption(closed=False)
            self.flush()
            if self._keep_html_nested_tables and self._table_cell is not None:
                self._suspend_enclosing_table()
            self._list_start = 1
            self._list_continuation_pending = False
            self._table_rows = []
            self._table_row = None
            self._table_cell = None
            self._table_cell_spans = None
            self._table_row_group_boundaries = [0]
            self._table_has_candidate_spans = False
            self._table_in_head = False
            self._table_column_header = None
            self._table_head_cells = []
            self._table_caption = None
            return
        if self._in_table:
            if tag in _TABLE_ROW_GROUPS and (self._keep_html_table_spans or self._keep_html_media_table_headers):
                if self._keep_html_table_spans:
                    self._mark_table_row_group_boundary()
                self._table_in_head = self._keep_html_media_table_headers and tag == "thead"
                return
            if (tag == "caption" and self._keep_html_table_captions
                    and not self._table_caption and self._table_caption_blocks is None
                    and not self._table_rows and self._table_row is None):
                self.flush()
                self._table_caption_blocks = []
                return
            if tag == "tr":
                self._finish_table_caption(closed=False)
                self._flush_row()
                self._table_row = []
                return
            if tag in {"td", "th"}:
                self._finish_table_caption(closed=False)
                self._flush_cell()
                if self._table_row is None:
                    self._table_row = []
                self._table_cell = []
                spans = _table_spans(attrs) if self._keep_html_table_spans or self._table_in_head else None
                if self._keep_html_table_spans:
                    self._table_cell_spans = spans
                if self._table_in_head:
                    scope = (attrs.get("scope") or "").strip().casefold()
                    # Columns can represent an explicit horizontal span with column scope.
                    supported_span = not spans or (
                        scope == "col" and self._keep_html_table_spans and spans.keys() == {"colspan"}
                    )
                    self._table_column_header = tag == "th" and scope in ("", "col") and supported_span
                return
            if tag == "br":
                self.flush(inline=True)
                return
        if tag in _LIST_TAGS and not self._in_table:
            self.flush()
            if len(self._lists) >= _MAX_LIST_DEPTH:
                raise ValueError("HTML list nesting exceeds its limit")
            if self._lists and self._lists[-1].item is None:
                self._lists[-1].item = _ListItem()
            # Separate <ol> elements have independent browser counters.
            # Only the compatibility facade reuses implicit top-level starts.
            continues = self._preserve_legacy_list_starts and not self._lists and self._list_continuation_pending
            start = self._list_start if continues else 1
            explicit = _html_list_number(attrs.get("start")) if tag == "ol" else None
            if explicit is not None:
                start = explicit
            self._lists.append(_ListFrame(tag, start, authored_start=explicit is not None))
            self._list_continuation_pending = False
            return
        if tag == "li" and self._lists and not self._in_table:
            self._finish_list_item()
            frame = self._lists[-1]
            number = _html_list_number(attrs.get("value")) if frame.tag == "ol" else None
            frame.item = _ListItem(number=number)
            if (self._keep_html_document_links and self._document_link_scope is None
                    and self._DOCUMENT_LINK_OPENING_TAG.fullmatch(self.get_starttag_text())):
                self._document_link_bounds = (None, None)
            return
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3"} or (
            tag in {"figure", "figcaption"} and self._current_list_item() is not None
        ):
            self.flush(inline=tag == "br")
        if tag == "a":
            if attrs.get("class") == "image":
                self._image_link += 1
            elif attrs.get("href"):
                self.links.append(attrs["href"])
        if tag in {"img", "mtr-image"}:
            if tag == "mtr-image" and (
                not self._keep_bankone_graphic_positions or duplicate_graphic_id
                or self._hidden_image_scope is not None or "hidden" in attrs
                or not _BANKONE_GRAPHIC_ID.fullmatch(attrs.get("id") or "")
            ):
                return
            if self._skip_noscript_images and self.getpos() in self._skip_noscript_images:
                return
            lazy_ref = None
            if tag == "mtr-image":
                # Bankone's source connector hashes the graphic kind and ID in its asset locator.
                locator_input = json.dumps({"kind": "graphic", "id": attrs["id"]}, separators=(",", ":"))
                locator = "bankone:asset:" + sha256(locator_input.encode()).hexdigest()[:24]
                image = ConnectorBankoneGraphic(locator, attrs.get("alt") or "")
                src = ref = ""
                self.bankone_graphic_positions = True
            else:
                src = attrs.get("src") or ""
                ref = self._asset_bindings.get(src) or attrs.get("data-resource-ref") or attrs.get("asset_resource_ref")
                if (self._keep_bound_html_images and not ref and src not in self._declared_image_refs
                        and not src.startswith("data:image/")
                        and self._hidden_image_scope is None and "hidden" not in attrs):
                    lazy_ref = self._bound_lazy_image(attrs)
                    if lazy_ref:
                        ref = lazy_ref
                        src = ""
                        self.html_bound_images = True
                if not src and not ref:
                    return
                image = {"kind": "image", "alt": attrs.get("alt", ""), "name": attrs.get("img_name", "")}
            if self._lazy_image_alts:
                image["alt"] = self._lazy_image_alts.get(self.getpos(), image["alt"])
            if src:
                image["url"] = src
            if ref:
                image["asset_resource_ref"] = ref
            if self._figures:
                frame = self._figures[-1]
                if lazy_ref:
                    frame.lazy_images[self.getpos()] = (lazy_ref, "alt" not in attrs and not attrs.get("img_name"))
                elif self._hidden_image_scope == "noscript":
                    mirror_ref = ref or (src if src in self._declared_image_refs else None)
                    if mirror_ref:
                        frame.noscript_images[self.getpos()] = (mirror_ref, (attrs.get("alt") or "").strip())
                if frame.image is not None or frame.open_caption is not None:
                    frame.invalid = True
                frame.image = image
            if self._heading is not None:
                self._heading.setdefault("images", []).append(image)
                return
            self._append_inline_media(image)

    def parse_starttag(self, offset):
        if (
            self._keep_html_section_titles and not self._in_table and not self._lists and not self._figures
            and not self._skip and not self._image_link and not self._hidden_embed_tags
            and self._hidden_html_tag is None and self._hidden_image_scope is None
            and self._heading is None and self._document_link_scope is None
        ):
            # A supplier can use an isolated bold paragraph as a section title.
            # The closed shape preserves bold instructions and mixed paragraphs.
            section = _SECTION_TITLE_PARAGRAPH.match(self.rawdata, offset)
            if section:
                title = " ".join(unescape(section[2]).split())
                level = _SECTION_TITLE_LEVELS.get(title.casefold())
                if level:
                    self.handle_starttag("p", [])
                    self._append_block({"kind": "heading", "level": level, "text": title})
                    self.html_section_titles = True
                    return section.end()
        return super().parse_starttag(offset)

    def parse_endtag(self, offset):
        # HTMLParser accepts attributes on end tags and only reports the name.
        if (self._document_link_bounds is not None
                and not self._DOCUMENT_LINK_CLOSING_TAG.match(self.rawdata, offset)
                and self.rawdata.find(">", offset + 2) != -1):
            self._document_link_bounds = None
        return super().parse_endtag(offset)

    def handle_endtag(self, tag):
        if self._keep_html_document_links:
            self._end_document_link_tag(tag)
        if self._hidden_embed_tags:
            if self._hidden_embed_tags[-1] == tag:
                self._hidden_embed_tags.pop()
            return
        if self._hidden_html_tag is not None:
            if tag == self._hidden_html_tag:
                self._hidden_html_depth -= 1
                if not self._hidden_html_depth:
                    self._hidden_html_tag = None
            return
        if self._skip:
            if tag in {"script", "style"}:
                self._skip -= 1
            return
        if tag == self._hidden_image_scope:
            self._hidden_image_depth -= 1
            if not self._hidden_image_depth:
                self._hidden_image_scope = None
        if tag == "sup" and self._superscript_depth:
            self._superscript_depth -= 1
            if not self._superscript_depth:
                self._finish_superscript(self._superscript_start)
            return
        if tag == "figcaption" and self._figures and self._figures[-1].blocks is not None:
            self._finish_figure_caption()
            return
        if tag == "figure" and self._figures:
            frame = self._figures.pop()
            if frame.lazy_images and frame.noscript_images:
                lazy_refs = {ref for ref, _ in frame.lazy_images.values()}
                labels = {}
                for position, (ref, alt) in frame.noscript_images.items():
                    if ref in lazy_refs:
                        self.html_image_mirrors.add(position)
                        if alt:
                            labels.setdefault(ref, set()).add(alt)
                for position, (ref, needs_alt) in frame.lazy_images.items():
                    alternatives = labels.get(ref, ())
                    # Keep an authored name when the visible copy has none.
                    if needs_alt and len(alternatives) == 1:
                        self.html_lazy_image_alts[position] = next(iter(alternatives))
            if frame.image is not None and frame.caption is not None and not frame.invalid:
                key = "_html_figure_caption" if frame.in_table else "_html_flow_figure_caption"
                text_parts = [part["text"] for part in frame.caption]
                frame.image[key] = text_parts[0] if len(text_parts) == 1 else text_parts
                for part in frame.caption:
                    part["_html_figure_caption_text"] = True
                if len(text_parts) > 1:
                    self.html_multiline_figure_captions = True
        if self._heading is not None and tag in _HEADING_LEVELS:
            self.flush()
            return
        if tag == "table" and self._in_table:
            self._finish_table()
            return
        if self._in_table:
            if tag in _TABLE_ROW_GROUPS and (self._keep_html_table_spans or self._keep_html_media_table_headers):
                if self._keep_html_table_spans:
                    self._mark_table_row_group_boundary()
                self._table_in_head = False
                return
            if tag == "caption" and self._table_caption_blocks is not None:
                self._finish_table_caption(closed=True)
                return
            if tag in {"td", "th"}:
                self._flush_cell()
                return
            if tag == "tr":
                self._flush_row()
                return
            if tag in {"br", "div", "p"}:
                self.flush(inline=tag == "br")
                return
        if self._lists and not self._in_table:
            if tag == "li":
                self._finish_list_item()
                return
            if tag in _LIST_TAGS:
                if self._lists[-1].tag == tag:
                    self._finish_list()
                return
        if tag == "a":
            self._image_link = 0
        if tag in {"p", "div", "li", "tr"} or (
            tag in {"figure", "figcaption"} and self._current_list_item() is not None
        ):
            self.flush()

    def handle_data(self, data):
        if not self._skip and not self._image_link and not self._hidden_embed_tags and self._hidden_html_tag is None:
            self._text.append(data)


class SourceUnavailable(RuntimeError):
    def __init__(self, message: str = "repair source is unavailable", *, code: str = "UPSTREAM_UNAVAILABLE"):
        self.code = code
        super().__init__(message)


class BanktwoConnector:
    """Compatibility facade for Banktwo's provider-neutral Source Connector v1."""

    def __init__(self, base_url: str | None = None, *, source_client: SourceConnectorClient | None = None,
                 opener: Any = None, timeout: float = 25, max_bytes: int = 8_000_000,
                 cache_entries: int = 128, cache_ttl: int = 300, retry_attempts: int = 3,
                 retry_delay: float = 0.25, retry_after_cap: float = 30.0):
        del cache_entries, cache_ttl, retry_attempts, retry_delay, retry_after_cap
        if source_client is not None:
            self.client = source_client
        elif opener is None and base_url is None:
            self.client = source_connector_registry(include_defaults=True)["banktwo"]
        else:
            configured = os.getenv("BANKTWO_BASE_URL", "https://banktwo.cars.tk")
            self.client = SourceConnectorClient(
                base_url or configured,
                token=source_connector_token("banktwo"),
                timeout=timeout,
                max_bytes=max_bytes,
                provider="banktwo",
                opener=opener,
            )

    def resolve_vehicle(self, selector: Mapping[str, Any]) -> SourceEnvelopeV1:
        return self._call(self.client.resolve_vehicle, selector)

    def list_articles(self, source_vehicle_ref: str, cursor: str | None = None) -> SourceEnvelopeV1:
        return self._call(self.client.list_articles, source_vehicle_ref, cursor)

    def search_articles(self, source_vehicle_ref: str, query: str, cursor: str | None = None) -> SourceEnvelopeV1:
        return self._call(self.client.search_articles, source_vehicle_ref, query, cursor)

    def read_resource(self, resource_ref: str) -> SourceEnvelopeV1:
        return self._call(self.client.read_resource, resource_ref)

    def _call(self, operation: Any, *args: Any) -> SourceEnvelopeV1:
        try:
            return operation(*args)
        except SourceConnectorError as error:
            raise SourceUnavailable(code=error.code) from None

    def fetch_article_catalog(self, source_vehicle_ref: str, *, max_index_reads: int = 512, on_progress=None):
        """Compatibility wrapper that lists v1 article descriptors in source order."""
        rows: list[dict[str, Any]] = []
        cursor = None
        reads = 0
        while True:
            if reads >= max_index_reads:
                raise SourceUnavailable("article catalog exceeds its page limit", code="INVALID_UPSTREAM_RESPONSE")
            envelope = self.list_articles(source_vehicle_ref, cursor)
            reads += 1
            page = envelope.body["articles"]
            rows.extend(dict(row) for row in page)
            if on_progress is not None:
                try:
                    on_progress({"phase": "indexing", "processed_units": reads,
                                 "total_units": reads if envelope.complete else None,
                                 "outcome": "succeeded", "result_count": len(page)})
                except Exception:
                    pass
            if envelope.complete:
                break
            cursor = envelope.next_cursor
        return {"articles": tuple(rows), "index_reads": reads,
                "component_reads": 0, "information_type_reads": 0}

    @staticmethod
    def descriptor_for_legacy_article_id(
        legacy_article_id: str,
        descriptors: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    ) -> Mapping[str, Any]:
        """Resolve an old persisted ``autoapitwo:<vehicle>:<article>`` ID.

        Source Connector v1 makes refs opaque and does not promise equality
        with Banktwo's historical IDs. Compatibility therefore uses only an
        exact suffix match and fails closed when it is absent or ambiguous.
        """
        parts = str(legacy_article_id or "").split(":", 2)
        if (len(parts) != 3 or parts[0] != "autoapitwo"
                or not parts[1].isdigit() or not parts[2]):
            raise SourceUnavailable(code="NOT_FOUND")
        matches = [
            descriptor for descriptor in descriptors
            if isinstance(descriptor, Mapping)
            and str(descriptor.get("opaque_ref") or "") == parts[2]
        ]
        if len(matches) != 1:
            raise SourceUnavailable(code="NOT_FOUND")
        return matches[0]

    def article_by_legacy_id(
        self,
        source_vehicle_ref: str,
        legacy_article_id: str,
        descriptors: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    ) -> dict[str, Any]:
        """Read a v1 resource while retaining the supplied persisted ID."""
        descriptor = self.descriptor_for_legacy_article_id(legacy_article_id, descriptors)
        return self.article_by_descriptor(
            source_vehicle_ref, descriptor, article_id=legacy_article_id
        )

    def article_by_descriptor(
        self,
        source_vehicle_ref: str,
        descriptor: Mapping[str, Any],
        *,
        article_id: str | None = None,
    ) -> dict[str, Any]:
        resource_ref = str(descriptor.get("resource_ref") or descriptor.get("opaque_ref") or "").strip()
        if not resource_ref:
            raise SourceUnavailable(code="INVALID_UPSTREAM_RESPONSE")
        envelope = self.read_resource(resource_ref)
        resource = envelope.to_source_resource()
        if resource.metadata.get("kind") not in {"article", "text"}:
            raise SourceUnavailable(code="INVALID_UPSTREAM_RESPONSE")
        html = resource.payload.decode("utf-8")
        article_id = article_id or f"autoapitwo:{source_vehicle_ref}:{descriptor.get('opaque_ref', resource_ref)}"
        digest = sha256(resource.payload).hexdigest()
        evidence_id = f"{article_id}:{digest}"
        parser = ArticleParser(asset_bindings=resource.metadata.get("asset_bindings", []))
        parser.feed(html)
        parser.close()
        parser.flush()
        asset_refs = []
        for value in (descriptor.get("asset_resource_refs"), envelope.body.get("asset_resource_refs")):
            if isinstance(value, list):
                asset_refs.extend(str(item) for item in value if isinstance(item, str))
        asset_refs = list(dict.fromkeys(asset_refs))
        image_blocks: list[dict[str, Any]] = []

        def annotate(block: Any, index: tuple[int, ...]) -> None:
            if not isinstance(block, dict):
                return
            suffix = ".".join(str(part) for part in index)
            block["evidence_ids"] = [evidence_id]
            block["block_id"] = f"{article_id}:block:{suffix}"
            if block.get("kind") == "image":
                url = block.pop("url", None)
                ref = block.get("asset_resource_ref") or (url if url in asset_refs else None)
                if not ref:
                    block["status"] = "unavailable"
                    block["unavailable_reason"] = "source asset reference was not provided"
                else:
                    block["asset_resource_ref"] = ref
                    block["image_id"] = sha256(ref.encode()).hexdigest()
                    image_blocks.append(block)
                return
            if block.get("kind") in _LIST_TAGS.values():
                for item_index, item in enumerate(block["items"]):
                    if isinstance(item, dict):
                        for child_index, child in enumerate(item.get("blocks", [])):
                            annotate(child, (*index, item_index, child_index))
            if block.get("kind") == "table":
                for row_index, row in enumerate(block.get("rows") or []):
                    cells = row.get("blocks") if isinstance(row, dict) else row
                    if isinstance(cells, list):
                        for cell_index, cell in enumerate(cells):
                            nested = cell.get("blocks") if isinstance(cell, dict) else None
                            if isinstance(nested, list):
                                for child_index, child in enumerate(nested):
                                    annotate(child, (*index, row_index, cell_index, child_index))
                            elif isinstance(cell, dict):
                                annotate(cell, (*index, row_index, cell_index))

        for block_index, block in enumerate(parser.blocks):
            annotate(block, (block_index,))
        article = {
            "article_id": article_id,
            "title": str(descriptor.get("title") or ""),
            "provider": "autoapitwo",
            "provider_vehicle_id": source_vehicle_ref,
            "source_uri": resource.locator,
            "source_resource_ref": resource_ref,
            "source_asset_refs": asset_refs,
            "source_watermark": digest,
            "raw_html": html,
            "body": "\n\n".join(_article_text_blocks(parser.blocks)),
            "blocks": parser.blocks,
            "images": image_blocks,
            "component_links": [],
            "evidence_ids": [evidence_id],
            "evidence": [{"evidence_id": evidence_id, "source_uri": resource.locator, "content_hash": digest}],
            "source_request_id": resource.metadata.get("request_id"),
            "source_revision": resource.source_version,
            "source_provider": "banktwo",
            "source_sha256": digest,
            "bucket": str(descriptor.get("category") or ""),
        }
        labor_ref = str(descriptor.get("labor_resource_ref") or "").strip()
        if labor_ref:
            labor_envelope = self.read_resource(labor_ref)
            labor_resource = labor_envelope.to_source_resource()
            labor_text = labor_resource.payload.decode("utf-8")
            article.update({
                "labor_body": labor_text,
                "labor_resource_ref": labor_ref,
                "labor_source_uri": labor_resource.locator,
                "labor_source_sha256": sha256(labor_resource.payload).hexdigest(),
                "labor_source_revision": labor_resource.source_version,
                "labor_source_request_id": labor_resource.metadata.get("request_id"),
                "labor_source_provider": "banktwo",
            })
        return article

    def search(self, source_vehicle_ref: str, term: str) -> list[dict[str, Any]]:
        envelope = self.search_articles(source_vehicle_ref, term)
        rows = [dict(row) for row in envelope.body["articles"]]
        cursor = envelope.next_cursor
        seen: set[str] = set()
        while not envelope.complete:
            if not cursor or cursor in seen or len(seen) >= 512:
                raise SourceUnavailable(code="INVALID_UPSTREAM_RESPONSE")
            seen.add(cursor)
            envelope = self.search_articles(source_vehicle_ref, term, cursor)
            rows.extend(dict(row) for row in envelope.body["articles"])
            cursor = envelope.next_cursor
        return rows

    def article(self, source_vehicle_ref: str, descriptor: Mapping[str, Any], *, title: str | None = None):
        value = dict(descriptor)
        if title and not value.get("title"):
            value["title"] = title
        return self.article_by_descriptor(source_vehicle_ref, value)


def _source_failure_reason(error: BaseException) -> str:
    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in chain and len(chain) < 8:
        chain.append(current)
        current = current.__cause__ or current.__context__
    status = next(
        (
            int(getattr(item, attribute))
            for item in chain
            for attribute in ("code", "status", "status_code")
            if str(getattr(item, attribute, "")).isdigit()
        ),
        None,
    )
    text = " ".join(str(getattr(item, "reason", "") or item).casefold() for item in chain)
    if "no matching" in text or "did not resolve" in text or "no vehicle" in text:
        return "returned no matching vehicle"
    codes = {str(getattr(item, "code", "")).upper() for item in chain}
    if "RATE_LIMITED" in codes:
        return "rate limited"
    if "UNAUTHORIZED" in codes:
        return "authentication expired or unauthorized"
    if "UPSTREAM_UNAVAILABLE" in codes:
        return "source server unavailable"
    if "AMBIGUOUS" in codes:
        return "vehicle resolution is ambiguous"
    if "NOT_FOUND" in codes:
        return "returned no matching vehicle"
    if status == 429 or "rate limit" in text or "too many requests" in text:
        return "rate limited"
    if status == 401 or "expired" in text or "authentication" in text or "unauthorized" in text:
        return "authentication expired or unauthorized"
    if status == 403 or "forbidden" in text:
        return "forbidden"
    if status in {408, 504} or "timed out" in text or "timeout" in text:
        return "server timed out"
    if status is not None and status >= 500:
        return f"source server unavailable (HTTP {status})"
    if "incomplete" in text and "article" in text:
        return "article index was incomplete"
    if "source read failed" in text:
        return "source read failed"
    return "request failed"


def _article_text_blocks(blocks: Any, *, include_flat_lists=False):
    """Yield readable text from structured HTML content."""

    for block in blocks or []:
        if not isinstance(block, Mapping):
            continue
        if block.get("kind") == "text" and str(block.get("text") or "").strip():
            yield str(block["text"]).strip()
        elif block.get("kind") in _LIST_TAGS.values():
            items = block.get("items") or []
            if include_flat_lists or any(isinstance(item, Mapping) for item in items):
                for item in items:
                    text = item.get("text") if isinstance(item, Mapping) else item
                    if isinstance(text, str) and text:
                        yield text
                    if isinstance(item, Mapping):
                        yield from _article_text_blocks(item.get("blocks"), include_flat_lists=True)
        elif block.get("kind") == "table":
            for row in block.get("rows") or []:
                cells = row.get("blocks") if isinstance(row, Mapping) else row
                if not isinstance(cells, list):
                    continue
                for cell in cells:
                    cell_blocks = cell.get("blocks") if isinstance(cell, Mapping) else None
                    if not isinstance(cell_blocks, list):
                        cell_blocks = [cell]
                    for cell_block in cell_blocks:
                        if not isinstance(cell_block, Mapping) or cell_block.get("kind") != "text":
                            continue
                        text = str(cell_block.get("text") or "").strip()
                        if text:
                            yield text
