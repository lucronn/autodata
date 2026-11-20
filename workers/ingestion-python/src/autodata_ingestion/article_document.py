"""Provider-neutral ordered article documents.

The source adapters produce small ordered blocks.  This module gives those
blocks one stable shape before they enter persistence.  The compatibility
``steps`` projection can still be generated for older consumers, but it is
never the authoritative representation of an article.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import re
from typing import Any, Mapping


SCHEMA_VERSION = 1
NORMALIZATION_VERSION = "ordered-article-v1"
_MIN_LIST_NUMBER = -(2**31)
_MAX_LIST_NUMBER = 2**31 - 1
DOCUMENT_TYPES = frozenset(
    {
        "heading",
        "paragraph",
        "ordered_list",
        "unordered_list",
        "step",
        "table",
        "callout",
        "image",
        "link",
        "break",
        "unknown",
    }
)
_PLAIN_MULTIWORD_SECTION_HEADERS = (
    "Technical Background",
    "Production Solution",
    "Required Parts and Tools",
    "Additional Information",
    "REVISION HISTORY",
    "Revision History",
)
_PLAIN_SINGLE_SECTION_HEADERS = (
    "Condition",
    "Service",
    "Warranty",
)
_PLAIN_SECTION_HEADERS = _PLAIN_MULTIWORD_SECTION_HEADERS + _PLAIN_SINGLE_SECTION_HEADERS
_PLAIN_SECTION_HEADER_KEYS = frozenset(
    re.sub(r"[^a-z0-9]+", " ", header.casefold()).strip()
    for header in _PLAIN_SECTION_HEADERS
)
_PLAIN_MULTIWORD_SECTION_SPLIT_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    + "|".join(re.escape(header) for header in _PLAIN_MULTIWORD_SECTION_HEADERS)
    + r")(?![A-Za-z0-9])"
)
# Single-word headers are common English words ("Service" appears in titles).
# Only split when they look like a new TSB section start.
_PLAIN_SINGLE_SECTION_SPLIT_RE = re.compile(
    r"(?:(?<=^)|(?<=[\.\?\!]\s)|(?<=\n)|(?<=Applicable\s))("
    + "|".join(re.escape(header) for header in _PLAIN_SINGLE_SECTION_HEADERS)
    + r")(?=\s+[A-Z0-9])"
)
# "Technical Service Bulletin Service 1." page headers: keep title intact, still
# open the Service section before the first numbered instruction.
_PLAIN_SERVICE_BEFORE_STEPS_RE = re.compile(
    r"(?<![A-Za-z0-9])(Service)(?=\s+\d{1,2}[.)]\s+)"
)
_PLAIN_CONDITION_BEFORE_SECTION_RE = re.compile(
    r"(?<![A-Za-z0-9])(Condition)(?=\s+(?:REVISION\b|The\s|When\s|If\s))"
)
_PLAIN_NOTE_SPLIT_RE = re.compile(r"(?<![A-Za-z0-9])(Note:)\s*", re.IGNORECASE)
_PLAIN_FIGURE_SPLIT_RE = re.compile(r"(?<![A-Za-z0-9])(Figure\s+\d+\.)\s*", re.IGNORECASE)
# Limit to 1-2 digit step numbers and ignore years like "2014. Supersedes".
_PLAIN_STEP_SPLIT_RE = re.compile(r"(?<![A-Za-z0-9.])(?<!Figure )(?<!Fig\. )(?<!\d)(\d{1,2}[.)]\s+)")
_PLAIN_SECTION_SPLIT_RE = re.compile(
    r"(?<![A-Za-z0-9])("
    + "|".join(re.escape(header) for header in _PLAIN_SECTION_HEADERS)
    + r")(?![A-Za-z0-9])"
)


def empty_document() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "blocks": [],
    }


def segment_plain_article_text(text: str) -> list[dict[str, Any]]:
    """Split PDF/TSB plain text into workshop-readable source blocks.

    Bankone bulletin PDFs often arrive as one whitespace-collapsed string.
    Insert structural boundaries, then classify lines as headings, notes,
    numbered steps, or paragraphs so the workshop does not render a wall of
    raw text.
    """

    cleaned = (
        str(text or "")
        .replace("\u0003", " ")
        .replace("\u00a0", " ")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )
    if not cleaned:
        return []
    if "\n" not in cleaned and _needs_plain_segmentation(cleaned):
        cleaned = _insert_plain_text_boundaries(cleaned)
    elif "\n" not in cleaned:
        return [{"kind": "text", "text": cleaned}]

    segments: list[dict[str, Any]] = []
    for raw_line in cleaned.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip(" -\t")
        if not line or _is_plain_boilerplate(line):
            continue
        note = re.match(r"^Note:\s*(.+)$", line, re.IGNORECASE)
        if note:
            segments.append({"kind": "note", "label": "Note", "text": note.group(1).strip()})
            continue
        if _is_plain_section_heading(line):
            segments.append({"kind": "heading", "text": line, "level": 2})
            continue
        if _looks_like_heading(line):
            segments.append({"kind": "heading", "text": line, "level": 2})
            continue
        numbered = _numbered_text(line)
        if numbered is not None:
            number, step_text = numbered
            segments.append({"kind": "text", "text": f"{number}. {step_text}"})
            continue
        segments.append({"kind": "text", "text": line})
    return segments or [{"kind": "text", "text": re.sub(r"\s+", " ", cleaned).strip()}]


def _image_identities(image: Mapping[str, Any]) -> set[str]:
    keys = (
        image.get("image_id"),
        image.get("id"),
        image.get("storage_key"),
        image.get("artifact_key"),
        image.get("asset_id"),
        image.get("content_sha256"),
        image.get("url"),
        image.get("source_url"),
        image.get("src"),
        image.get("href"),
        image.get("asset_resource_ref"),
        image.get("uri"),
        image.get("path"),
    )
    return {str(k).strip() for k in keys if k and str(k).strip()}


def _nested_image_keys(value, *, image=False):
    if isinstance(value, Mapping):
        if image or str(value.get("type") or value.get("kind") or "").casefold() == "image":
            yield from _image_identities(value)
        for key, child in value.items():
            yield from _nested_image_keys(child, image=key == "images")
    elif isinstance(value, list):
        for child in value:
            yield from _nested_image_keys(child, image=image)


def build_ordered_document(
    article: Mapping[str, Any],
    blocks: Any = None,
    *,
    preserve_marked_cells: bool = False,
) -> dict[str, Any]:
    """Convert adapter blocks into a deterministic, source-order document."""

    source_blocks = blocks
    if not isinstance(source_blocks, list):
        source_blocks = article.get("blocks")
    if not isinstance(source_blocks, list):
        source_blocks = _blocks_from_steps(article.get("steps"))
    if not isinstance(source_blocks, list) or not source_blocks:
        body = str(article.get("body") or "").strip()
        source_blocks = segment_plain_article_text(body) if body else []
    else:
        source_blocks = _expand_plain_source_blocks(source_blocks)

    seen_image_keys: set[str] = set()
    for block in source_blocks:
        if isinstance(block, Mapping):
            bkind = str(block.get("type") or block.get("kind") or "").casefold()
            if bkind == "image":
                seen_image_keys.update(_image_identities(block))
            elif bkind in {"table", "grid"}:
                for row in block.get("rows") or []:
                    if isinstance(row, Mapping):
                        for row_img in row.get("images") or []:
                            if isinstance(row_img, Mapping):
                                seen_image_keys.update(_image_identities(row_img))
                    cells = row if isinstance(row, list) else row.get("cells", []) if isinstance(row, Mapping) else []
                    for cell in cells:
                        if isinstance(cell, Mapping):
                            for cell_img in cell.get("images") or []:
                                if isinstance(cell_img, Mapping):
                                    seen_image_keys.update(_image_identities(cell_img))
                            for child in cell.get("blocks") or []:
                                if isinstance(child, Mapping) and str(child.get("kind") or child.get("type") or "").casefold() == "image":
                                    seen_image_keys.update(_image_identities(child))
            elif bkind in {"ordered_list", "unordered_list", "list"}:
                for item in _list_values(block):
                    if isinstance(item, Mapping):
                        seen_image_keys.update(_nested_image_keys(item))
            for block_img in block.get("images") or []:
                if isinstance(block_img, Mapping):
                    seen_image_keys.update(_image_identities(block_img))

    output: list[dict[str, Any]] = []
    figure_queue = [
        dict(image)
        for image in (article.get("images") or [])
        if isinstance(image, Mapping)
        and (
            str(image.get("storage_key") or "").strip()
            or str(image.get("url") or "").startswith("data:image/")
            or str(image.get("image_id") or "").strip()
        )
        and not (_image_identities(image) & seen_image_keys)
    ]
    for source_index, raw in enumerate(source_blocks, 1):
        if isinstance(raw, str):
            raw = {"kind": "text", "text": raw}
        if not isinstance(raw, Mapping):
            output.append(_unknown_block(article, source_index, raw))
            continue
        kind = str(raw.get("type") or raw.get("kind") or "text").casefold()
        evidence_ids = _evidence_ids(raw, article)
        if kind == "image":
            seen_image_keys.update(_image_identities(raw))
            output.append(_image_block(article, source_index, raw, evidence_ids))
            continue
        if kind in {"table", "grid"}:
            output.append(_table_block(article, source_index, raw, evidence_ids, preserve_marked_cells))
            continue
        if kind in {"ordered_list", "unordered_list", "list"}:
            output.append(_list_block(article, source_index, raw, evidence_ids, kind, preserve_marked_cells))
            continue
        if kind in {"callout", "note", "warning", "caution", "hint", "important"}:
            output.append(_callout_block(article, source_index, raw, evidence_ids, kind))
            continue
        if kind in {"step", "instruction"}:
            output.append(_step_block(article, source_index, raw, evidence_ids))
            continue
        if kind in {"break", "hr", "separator"}:
            output.append(_base_block(article, source_index, "break", evidence_ids=evidence_ids))
            continue

        images = _text_block_images(raw)
        extra_fields = {"images": images} if images else {}
        if kind in {"heading", "title", "section"}:
            text = _clean_text(
                raw.get("text")
                or raw.get("label")
                or raw.get("title")
                or raw.get("heading")
                or raw.get("value")
                or raw.get("content")
            )
            if text:
                output.append(_base_block(article, source_index, "heading", text=text, level=_level(raw), evidence_ids=evidence_ids, **extra_fields))
            continue
        if kind in {"link", "anchor"}:
            text = _clean_text(
                raw.get("text")
                or raw.get("label")
                or raw.get("title")
                or raw.get("name")
                or raw.get("value")
                or raw.get("content")
            )
            href = _safe_link(
                raw.get("href")
                or raw.get("url")
                or raw.get("link")
                or raw.get("target")
            )
            if text:
                output.append(
                    _base_block(
                        article,
                        source_index,
                        "link",
                        text=text,
                        href=href,
                        evidence_ids=evidence_ids,
                        **extra_fields,
                    )
                )
            continue

        text = _clean_text(
            raw.get("text")
            or raw.get("value")
            or raw.get("content")
            or raw.get("body")
        )
        if not text:
            output.append(_unknown_block(article, source_index, raw))
            continue
        explicit_number = _numbered_text(text)
        if explicit_number is not None:
            number, text = explicit_number
            output.append(
                _base_block(
                    article,
                    source_index,
                    "step",
                    text=text,
                    number=number,
                    evidence_ids=evidence_ids,
                    **extra_fields,
                )
            )
        elif _looks_like_heading(text):
            output.append(_base_block(article, source_index, "heading", text=text, level=2, evidence_ids=evidence_ids, **extra_fields))
        else:
            output.append(_base_block(article, source_index, "paragraph", text=text, evidence_ids=evidence_ids, **extra_fields))
        if figure_queue and re.search(r"\bFigure\s+\d+\b", text, re.IGNORECASE):
            fig = figure_queue.pop(0)
            seen_image_keys.update(_image_identities(fig))
            output.append(_image_block(article, source_index, fig, evidence_ids))

    # Append any remaining extracted PDF figures so the workshop still shows them.
    while figure_queue:
        fig = figure_queue.pop(0)
        if _image_identities(fig) & seen_image_keys:
            continue
        seen_image_keys.update(_image_identities(fig))
        output.append(_image_block(article, len(output) + 1, fig, []))

    # Source order and block IDs stay contiguous after figure insertion.
    _number_blocks(output, str(article.get("article_id") or "article"))

    return {
        "schema_version": SCHEMA_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "blocks": output,
    }


def _number_blocks(blocks, parent_id):
    for order, block in enumerate(blocks, start=1):
        block_id = f"{parent_id}:block:{order:04d}"
        block.update(source_order=order, block_id=block_id)
        if block["type"] in {"ordered_list", "unordered_list"}:
            for item_number, item in enumerate(block.get("items", []), start=1):
                if isinstance(item, dict) and item.get("blocks"):
                    _number_blocks(item["blocks"], f"{block_id}:item:{item_number:04d}")
        elif block["type"] == "table":
            for row_number, row in enumerate(block.get("rows", []), start=1):
                for column_number, cell in enumerate(row, start=1):
                    if isinstance(cell, dict) and cell.get("blocks"):
                        _number_blocks(cell["blocks"], f"{block_id}:row:{row_number:04d}:cell:{column_number:04d}")


def list_number(value: Any) -> int | None:
    """Return an exact signed 32-bit list ordinal, excluding Boolean values."""
    return value if type(value) is int and _MIN_LIST_NUMBER <= value <= _MAX_LIST_NUMBER else None


def _has_list_numbering(block: Mapping[str, Any]) -> bool:
    if block.get("type") != "ordered_list":
        return False
    if list_number(block.get("start")) is not None:
        return True
    items = block.get("items")
    return isinstance(items, list) and any(
        isinstance(item, Mapping) and list_number(item.get("number")) is not None for item in items
    )


def walk_ordered_list_items(block: Mapping[str, Any]):
    """Yield each item and its ordinal for a list with explicit numbering."""
    items = block.get("items", [])
    if not _has_list_numbering(block):
        for item in items:
            yield item, None
        return
    start = list_number(block.get("start"))
    ordinal = 1 if start is None else start
    for item in items:
        override = list_number(item.get("number")) if isinstance(item, Mapping) else None
        if override is not None:
            ordinal = override
        yield item, ordinal
        ordinal += 1


def has_only_list_ordinal_additions(before, after) -> bool:
    """Allow only source-authored ordinal additions to the same ordered document."""
    added = False

    def equivalent(old, new):
        if isinstance(old, dict) and isinstance(new, dict):
            if old.get("type") == new.get("type") == "ordered_list":
                return equivalent_list(old, new)
            return equivalent_fields(old, new)
        if isinstance(old, list) and isinstance(new, list):
            return len(old) == len(new) and all(equivalent(a, b) for a, b in zip(old, new, strict=True))
        return type(old) is type(new) and old == new

    def equivalent_fields(old, new, *, ignored=()):
        keys = old.keys() - set(ignored)
        return keys == new.keys() - set(ignored) and all(equivalent(old[key], new[key]) for key in keys)

    def equivalent_list(old, new):
        old_items, new_items = old.get("items"), new.get("items")
        if not (isinstance(old_items, list) and isinstance(new_items, list)
                and len(old_items) == len(new_items)
                and ordinal(old, new, "start")
                and equivalent_fields(old, new, ignored=("start", "items"))):
            return False
        for old_item, new_item in zip(old_items, new_items, strict=True):
            if isinstance(new_item, dict) and "number" in new_item:
                old_item = {"text": old_item} if isinstance(old_item, str) else old_item
                if (not isinstance(old_item, dict) or not ordinal(old_item, new_item, "number")
                        or not equivalent_fields(old_item, new_item, ignored=("number",))):
                    return False
            elif not equivalent(old_item, new_item):
                return False
        return True

    def ordinal(old, new, key):
        nonlocal added
        if key in old:
            return list_number(new.get(key)) is not None and type(old[key]) is int and old[key] == new[key]
        if key not in new:
            return True
        if list_number(new[key]) is None:
            return False
        added = True
        return True

    same_content = equivalent(before, after)
    return same_content and added


def has_ordered_list_numbering(document: Mapping[str, Any]) -> bool:
    """Detect persisted list ordinals, including lists nested inside items."""
    def visit(value):
        if isinstance(value, Mapping):
            return _has_list_numbering(value) or any(visit(child) for child in value.values())
        if isinstance(value, list):
            return any(visit(child) for child in value)
        return False

    return visit(document.get("blocks", []))


def has_structured_list_items(document: Mapping[str, Any]) -> bool:
    """Identify ordered documents that retain list item structure or numbering."""
    def visit(value):
        if isinstance(value, Mapping):
            if value.get("type") in ("ordered_list", "unordered_list") and (
                _has_list_numbering(value) or any(
                    isinstance(item, Mapping) and (item.get("images") or item.get("blocks"))
                    for item in value.get("items", [])
                )
            ):
                return True
            return any(visit(child) for child in value.values())
        if isinstance(value, list):
            return any(visit(child) for child in value)
        return False

    return visit(document.get("blocks", []))


def document_from_steps(article: Mapping[str, Any]) -> dict[str, Any]:
    """Build a readable compatibility document for legacy stored rows."""

    blocks: list[dict[str, Any]] = []
    for index, step in enumerate(article.get("steps") or [], 1):
        if not isinstance(step, Mapping):
            text = _clean_text(step)
            if text:
                blocks.append({"kind": "text", "text": text})
            continue
        heading = _clean_text(
            step.get("heading")
            or step.get("action")
            or step.get("title")
            or step.get("label")
            or step.get("name")
        )
        instructions = []
        for value in step.get("instructions") or []:
            if isinstance(value, Mapping):
                val_text = _clean_text(
                    value.get("text")
                    or value.get("action")
                    or value.get("instruction")
                    or value.get("value")
                    or value.get("content")
                    or value.get("body")
                )
            else:
                val_text = _clean_text(value)
            if val_text:
                instructions.append(val_text)
        if not heading and not instructions:
            step_text = _clean_text(
                step.get("text")
                or step.get("instruction")
                or step.get("content")
                or step.get("body")
            )
            if step_text:
                heading = step_text
        if heading:
            blocks.append({"kind": "text", "text": f"{step.get('number') or index}. {heading}"})
        for instruction in instructions:
            blocks.append({"kind": "text", "text": instruction})
        for image in step.get("images") or []:
            if isinstance(image, Mapping):
                blocks.append({"kind": "image", **dict(image)})
    return build_ordered_document(article, blocks)


def validate_ordered_document(document: Any, *, strict: bool = False) -> list[str]:
    """Return deterministic validation errors without dropping source data."""

    if not isinstance(document, Mapping):
        return ["document is not an object"]
    errors: list[str] = []
    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    if document.get("normalization_version") != NORMALIZATION_VERSION:
        errors.append("unsupported normalization_version")
    blocks = document.get("blocks")
    if not isinstance(blocks, list):
        return errors + ["blocks is not an array"]
    expected_order = 1
    for block in blocks:
        if not isinstance(block, Mapping):
            errors.append(f"block {expected_order} is not an object")
            expected_order += 1
            continue
        if block.get("source_order") != expected_order:
            errors.append(f"block {expected_order} has invalid source_order")
        if not str(block.get("block_id") or "").strip():
            errors.append(f"block {expected_order} has no block_id")
        block_type = str(block.get("type") or "")
        if block_type not in DOCUMENT_TYPES:
            errors.append(f"block {expected_order} has unknown type")
        if block_type in {"paragraph", "heading", "step", "callout", "link"} and not str(block.get("text") or "").strip():
            errors.append(f"block {expected_order} has no readable text")
        if block_type == "table" and not isinstance(block.get("rows"), list):
            errors.append(f"block {expected_order} has no table rows")
        if block_type in {"ordered_list", "unordered_list"} and not isinstance(block.get("items"), list):
            errors.append(f"block {expected_order} has no list items")
        if block_type == "image" and block.get("status") not in {"available", "unavailable"}:
            errors.append(f"block {expected_order} has no image status")
        expected_order += 1
    if strict:
        errors.extend(_validate_recursive_blocks(blocks))
        errors.extend(_validate_media_tree(document))
    return errors


def _validate_media_tree(value, *, image_container=False):
    errors=[]
    if isinstance(value,list):
        for child in value:errors.extend(_validate_media_tree(child,image_container=image_container))
    elif isinstance(value,dict):
        if image_container or value.get("type")=="image":
            evidence=value.get("evidence_ids")
            if not isinstance(evidence,list) or not evidence:errors.append("missing image evidence")
            if value.get("status")=="unavailable":
                if not value.get("unavailable_reason"):errors.append("missing image failure reason")
            elif (value.get("status")!="available" or not isinstance(value.get("storage_key"),str)
                  or not value["storage_key"] or not re.fullmatch(r"[a-f0-9]{64}",str(value.get("content_sha256","")))
                  or any(str(value.get(key,"")).lower().startswith(("http:","https:","javascript:")) for key in ("url","src","href"))):
                errors.append("image is not locally verified")
        for key,child in value.items():errors.extend(_validate_media_tree(child,image_container=key=="images"))
    elif image_container:
        errors.append("invalid image entry")
    return errors


def _validate_recursive_blocks(blocks, seen=None):
    seen = set() if seen is None else seen
    errors = []
    for order, block in enumerate(blocks, 1):
        if not isinstance(block, dict):
            errors.append("invalid nested block")
            continue
        identifier = block.get("block_id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            errors.append("missing or duplicate block id")
        else:
            seen.add(identifier)
        if type(block.get("source_order")) is not int or block["source_order"] != order:
            errors.append("invalid nested source order")
        kind = block.get("type")
        if kind not in DOCUMENT_TYPES or kind == "unknown":
            errors.append("unsupported block")
        evidence = block.get("evidence_ids")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(e, str) or not e for e in evidence):
            errors.append("missing block evidence")
        if kind in {"heading", "paragraph", "step", "callout", "link"} and (not isinstance(block.get("text"), str) or not block["text"].strip()):
            errors.append("missing readable text")
        if kind == "image":
            if block.get("status") == "unavailable":
                if not block.get("unavailable_reason"): errors.append("missing image failure reason")
            elif block.get("status") != "available" or not block.get("storage_key") or not block.get("content_sha256"):
                errors.append("image is not locally verified")
        if kind == "table":
            rows = block.get("rows")
            if not isinstance(rows, list) or not rows: errors.append("empty table")
            else:
                for row in rows:
                    cells = row if isinstance(row, list) else row.get("cells") if isinstance(row, dict) else None
                    if not isinstance(cells, list) or not cells: errors.append("invalid table cells"); continue
                    for cell in cells:
                        if isinstance(cell,str):
                            continue
                        if not isinstance(cell, dict): errors.append("invalid cell"); continue
                        if "blocks" in cell:
                            if not isinstance(cell["blocks"], list): errors.append("invalid cell blocks")
                            else: errors.extend(_validate_recursive_blocks(cell["blocks"], seen))
        if kind in {"ordered_list", "unordered_list"}:
            if "start" in block and (kind != "ordered_list" or list_number(block["start"]) is None):
                errors.append("invalid list start")
            items = block.get("items")
            if not isinstance(items, list) or not items: errors.append("empty list")
            else:
                for item in items:
                    if isinstance(item,str):
                        if not item.strip():errors.append("empty list item")
                        continue
                    if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                        errors.append("invalid list item")
                        continue
                    number = list_number(item.get("number")) if kind == "ordered_list" else None
                    if "number" in item and number is None:
                        errors.append("invalid list item number")
                    if not item["text"].strip() and number is None and not (item.get("images") or item.get("blocks")):
                        errors.append("empty list item")
                    if "images" in item and not isinstance(item["images"], list):
                        errors.append("invalid item images")
                    if "blocks" in item:
                        if not isinstance(item["blocks"], list):
                            errors.append("invalid item blocks")
                        else:
                            errors.extend(_validate_recursive_blocks(item["blocks"], seen))
    return errors


def _base_block(article: Mapping[str, Any], source_order: int, block_type: str, *, evidence_ids: list[str], **fields: Any) -> dict[str, Any]:
    block = {
        "block_id": f"{article.get('article_id') or 'article'}:block:{source_order:04d}",
        "source_order": source_order,
        "type": block_type,
        "evidence_ids": evidence_ids,
    }
    block.update({key: value for key, value in fields.items() if value not in (None, "", [])})
    return block


def _image_block(article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any], evidence_ids: list[str]) -> dict[str, Any]:
    source_url = _clean_text(raw.get("url") or raw.get("src") or raw.get("href"))
    image_id = _clean_text(raw.get("image_id") or raw.get("id"))
    storage_key = _clean_text(raw.get("storage_key") or raw.get("artifact_key"))
    asset_resource_ref = _clean_text(raw.get("asset_resource_ref"))
    uri = _clean_text(raw.get("uri"))
    path = _clean_text(raw.get("path"))
    asset_id = storage_key or image_id or asset_resource_ref or uri or path or (sha256(source_url.encode()).hexdigest() if source_url else "")
    is_available = raw.get("status") != "unavailable" and bool(
        source_url or storage_key or asset_resource_ref or uri or path
    )
    fields: dict[str, Any] = {
        "asset_id": asset_id or None,
        "image_id": image_id or asset_id or None,
        "alt": _clean_text(raw.get("alt") or raw.get("title") or raw.get("description") or raw.get("legend")) or "Article illustration",
        "caption": _clean_text(
            raw.get("caption")
            or raw.get("label")
            or raw.get("description")
            or raw.get("legend")
            or raw.get("title")
        ),
        "status": "available" if is_available else "unavailable",
        "unavailable_reason": None if is_available else (
            _clean_text(raw.get("unavailable_reason")) or "source image reference is missing"
        ),
        "media_type": _clean_text(raw.get("media_type")),
    }
    content_sha256 = _clean_text(raw.get("content_sha256"))
    if content_sha256:
        fields["content_sha256"] = content_sha256
    if storage_key:
        fields["storage_key"] = storage_key
    if source_url:
        fields["url"] = source_url
    if asset_resource_ref:
        fields["asset_resource_ref"] = asset_resource_ref
    if uri:
        fields["uri"] = uri
    if path:
        fields["path"] = path
    return _base_block(article, source_order, "image", evidence_ids=evidence_ids, **fields)


def _table_block(
    article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any],
    evidence_ids: list[str], preserve_marked_cells: bool,
) -> dict[str, Any]:
    rows = raw.get("rows")
    if not isinstance(rows, list):
        rows = []
    clean_rows = []
    row_images: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            values = row.get("cells") or row.get("values") or row.get("blocks") or []
            for img in row.get("images") or []:
                if isinstance(img, Mapping):
                    row_images.append(_normalize_cell_image(img))
        else:
            values = row
        if not isinstance(values, list):
            values = [values]
        clean_rows.append([_table_cell(value, evidence_ids=evidence_ids, preserve_marked_cells=preserve_marked_cells) for value in values])
    columns = raw.get("columns") if isinstance(raw.get("columns"), list) else []
    images_raw = raw.get("images")
    clean_images: list[dict[str, Any]] = []
    if isinstance(images_raw, list):
        clean_images.extend(
            _normalize_cell_image(image) for image in images_raw if isinstance(image, Mapping)
        )
    clean_images.extend(row_images)
    extra_fields: dict[str, Any] = {}
    if clean_images:
        seen_keys: set[str] = set()
        deduped_images: list[dict[str, Any]] = []
        for img in clean_images:
            keys = _image_identities(img)
            if keys and keys & seen_keys:
                continue
            seen_keys.update(keys)
            deduped_images.append(img)
        if deduped_images:
            extra_fields["images"] = deduped_images
    return _base_block(
        article,
        source_order,
        "table",
        label=_clean_text(
            raw.get("label")
            or raw.get("caption")
            or raw.get("title")
            or raw.get("heading")
        ),
        columns=[_clean_text(value) for value in columns],
        rows=clean_rows,
        evidence_ids=evidence_ids,
        **extra_fields,
    )


def _normalize_cell_image(raw: Mapping[str, Any]) -> dict[str, Any]:
    source_url = _clean_text(raw.get("url") or raw.get("src") or raw.get("href"))
    image_id = _clean_text(raw.get("image_id") or raw.get("id"))
    storage_key = _clean_text(raw.get("storage_key") or raw.get("artifact_key"))
    asset_resource_ref = _clean_text(raw.get("asset_resource_ref"))
    uri = _clean_text(raw.get("uri"))
    path = _clean_text(raw.get("path"))
    asset_id = storage_key or image_id or asset_resource_ref or uri or path or (sha256(source_url.encode()).hexdigest() if source_url else "")
    is_available = raw.get("status") != "unavailable" and bool(
        source_url or storage_key or asset_resource_ref or uri or path
    )
    out: dict[str, Any] = {
        "asset_id": asset_id or None,
        "image_id": image_id or asset_id or None,
        "alt": _clean_text(raw.get("alt") or raw.get("title") or raw.get("description") or raw.get("legend")) or "Article illustration",
        "status": "available" if is_available else "unavailable",
    }
    reason = _clean_text(raw.get("unavailable_reason"))
    if not is_available and reason:
        out["unavailable_reason"] = reason
    media_type = _clean_text(raw.get("media_type"))
    if media_type:
        out["media_type"] = media_type
    evidence_ids = _evidence_ids(raw, {})
    if evidence_ids:
        out["evidence_ids"] = evidence_ids
    content_sha256 = _clean_text(raw.get("content_sha256"))
    if content_sha256:
        out["content_sha256"] = content_sha256
    if storage_key:
        out["storage_key"] = storage_key
    if source_url:
        out["url"] = source_url
    if asset_resource_ref:
        out["asset_resource_ref"] = asset_resource_ref
    if uri:
        out["uri"] = uri
    if path:
        out["path"] = path
    caption = _clean_text(raw.get("caption") or raw.get("label") or raw.get("description") or raw.get("legend") or raw.get("title"))
    if caption:
        out["caption"] = caption
    return out


def _text_block_images(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    images = raw.get("images")
    if not isinstance(images, list):
        return []
    output = []
    seen = set()
    for image in images:
        if not isinstance(image, Mapping):
            continue
        normalized = _normalize_cell_image(image)
        keys = _image_identities(normalized)
        if keys & seen:
            continue
        seen.update(keys)
        output.append(normalized)
    return output


def _table_cell(value: Any, *, evidence_ids: list[str], preserve_marked_cells: bool) -> Any:
    if not isinstance(value, Mapping):
        return _clean_text(value)
    text_parts: list[str] = []
    direct_text = _clean_text(
        value.get("text")
        or value.get("value")
        or value.get("content")
        or value.get("body")
        or value.get("label")
    )
    if direct_text:
        text_parts.append(direct_text)
    images: list[dict[str, Any]] = []
    for direct_img in value.get("images") or []:
        if isinstance(direct_img, Mapping):
            images.append(_normalize_cell_image(direct_img))
    nested = value.get("blocks")
    if preserve_marked_cells and isinstance(nested, list) and value.get("_preserve_cell_block_order") is True:
        return {
            "text": direct_text,
            "blocks": build_ordered_document(
                {"evidence_ids": evidence_ids}, nested, preserve_marked_cells=preserve_marked_cells,
            )["blocks"],
            **({"images": images} if images else {}),
        }
    if isinstance(nested, list):
        for child in nested:
            if not isinstance(child, Mapping):
                continue
            child_kind = str(child.get("kind") or child.get("type") or "").casefold()
            if child_kind == "image":
                images.append(_normalize_cell_image(child))
            else:
                text = _clean_text(
                    child.get("text")
                    or child.get("value")
                    or child.get("content")
                    or child.get("body")
                    or child.get("label")
                )
                if text:
                    text_parts.append(text)
    combined_text = " ".join(part for part in text_parts if part).strip()
    if images:
        return {"text": combined_text, "images": images}
    return combined_text


def _list_values(raw):
    values = raw.get("items") or raw.get("values") or []
    return values if isinstance(values, list) else [values]


def _list_block(
    article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any],
    evidence_ids: list[str], kind: str, preserve_marked_cells: bool,
) -> dict[str, Any]:
    ordered = kind == "ordered_list"
    start = list_number(raw.get("start")) if ordered else None
    clean_items: list[str | dict[str, Any]] = []
    for value in _list_values(raw):
        if not isinstance(value, Mapping):
            text = _clean_text(value)
            if text:
                clean_items.append(text)
            continue
        text = _clean_text(
            value.get("text") or value.get("value") or value.get("label")
            or value.get("content") or value.get("body") or value.get("message")
        )
        item_images = value.get("images")
        images = [
            _normalize_cell_image(image) for image in item_images if isinstance(image, Mapping)
        ] if isinstance(item_images, list) else []
        child_blocks = value.get("blocks")
        children = []
        if isinstance(child_blocks, list) and child_blocks:
            item_evidence = _evidence_ids(value, {"evidence_ids": evidence_ids})
            children = build_ordered_document(
                {"evidence_ids": item_evidence}, child_blocks, preserve_marked_cells=preserve_marked_cells,
            )["blocks"]
        number = list_number(value.get("number")) if ordered else None
        if children or images or number is not None:
            item: dict[str, Any] = {"text": text}
            if number is not None:
                item["number"] = number
            if images:
                item["images"] = images
            if children:
                item["blocks"] = children
            clean_items.append(item)
        elif text:
            clean_items.append(text)
    return _base_block(
        article,
        source_order,
        "ordered_list" if ordered else "unordered_list",
        start=start,
        items=clean_items,
        label=_clean_text(raw.get("label") or raw.get("title") or raw.get("heading")),
        images=_text_block_images(raw),
        evidence_ids=evidence_ids,
    )


def _callout_block(article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any], evidence_ids: list[str], kind: str) -> dict[str, Any]:
    label = _clean_text(
        raw.get("label")
        or raw.get("title")
        or raw.get("heading")
    ) or kind.upper()
    text = _clean_text(
        raw.get("text")
        or raw.get("value")
        or raw.get("message")
        or raw.get("content")
        or raw.get("body")
    )
    item_images: list[dict[str, Any]] = []
    if not text and isinstance(raw.get("items"), list):
        item_parts: list[str] = []
        for item in raw["items"]:
            if isinstance(item, Mapping):
                it = _clean_text(
                    item.get("text")
                    or item.get("value")
                    or item.get("content")
                    or item.get("body")
                    or item.get("message")
                )
                for img in item.get("images") or []:
                    if isinstance(img, Mapping):
                        item_images.append(_normalize_cell_image(img))
            else:
                it = _clean_text(item)
            if it:
                item_parts.append(it)
        if item_parts:
            text = " ".join(item_parts)
    elif isinstance(raw.get("items"), list):
        for item in raw["items"]:
            if isinstance(item, Mapping):
                for img in item.get("images") or []:
                    if isinstance(img, Mapping):
                        item_images.append(_normalize_cell_image(img))
    images_raw = raw.get("images")
    clean_images: list[dict[str, Any]] = []
    if isinstance(images_raw, list):
        clean_images.extend(
            _normalize_cell_image(image) for image in images_raw if isinstance(image, Mapping)
        )
    clean_images.extend(item_images)
    extra_fields: dict[str, Any] = {}
    if clean_images:
        seen_keys: set[str] = set()
        deduped_images: list[dict[str, Any]] = []
        for img in clean_images:
            keys = _image_identities(img)
            if keys and keys & seen_keys:
                continue
            seen_keys.update(keys)
            deduped_images.append(img)
        if deduped_images:
            extra_fields["images"] = deduped_images
    return _base_block(article, source_order, "callout", label=label, text=text, evidence_ids=evidence_ids, **extra_fields)


def _step_block(article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any], evidence_ids: list[str]) -> dict[str, Any]:
    text_candidates = [
        raw.get("text"),
        raw.get("action"),
        raw.get("instruction"),
        raw.get("value"),
        raw.get("content"),
        raw.get("body"),
    ]
    instruction_images: list[dict[str, Any]] = []
    instruction_text = ""
    instructions = raw.get("instructions")
    if isinstance(instructions, list):
        cleaned_instructions: list[str] = []
        for item in instructions:
            if isinstance(item, Mapping):
                item_text = ""
                for candidate in (
                    item.get("text"), item.get("action"), item.get("instruction"),
                    item.get("value"), item.get("content"), item.get("body"),
                    item.get("description"),
                ):
                    item_text = _clean_text(candidate)
                    if item_text:
                        break
                for img in item.get("images") or []:
                    if isinstance(img, Mapping):
                        instruction_images.append(_normalize_cell_image(img))
            else:
                item_text = _clean_text(item)
            if item_text:
                cleaned_instructions.append(item_text)
        if cleaned_instructions:
            instruction_text = " ".join(cleaned_instructions)
    text_candidates.append(" ".join(part for part in (_clean_text(raw.get("description")), instruction_text) if part))

    text = ""
    for candidate in text_candidates:
        cleaned = _clean_text(candidate)
        if cleaned:
            text = cleaned
            break

    number = None
    raw_number = raw.get("number") if raw.get("number") is not None else raw.get("step_number") if raw.get("step_number") is not None else raw.get("index")
    if raw_number is not None:
        try:
            number = int(raw_number)
        except (ValueError, TypeError):
            number = None

    if number is None and text:
        parsed_num = _numbered_text(text)
        if parsed_num is not None:
            number, text = parsed_num

    label = _clean_text(raw.get("label") or raw.get("title") or raw.get("heading") or raw.get("action"))
    extra_fields: dict[str, Any] = {}
    if label and label != text:
        extra_fields["label"] = label
    if number is not None:
        extra_fields["number"] = number

    images_raw = raw.get("images")
    clean_images: list[dict[str, Any]] = []
    if isinstance(images_raw, list):
        clean_images.extend(
            _normalize_cell_image(image) for image in images_raw if isinstance(image, Mapping)
        )
    clean_images.extend(instruction_images)
    if clean_images:
        seen_keys: set[str] = set()
        deduped_images: list[dict[str, Any]] = []
        for img in clean_images:
            keys = _image_identities(img)
            if keys and keys & seen_keys:
                continue
            seen_keys.update(keys)
            deduped_images.append(img)
        if deduped_images:
            extra_fields["images"] = deduped_images

    if not text:
        text = label or (f"Step {number}" if number is not None else "Procedure step")

    return _base_block(article, source_order, "step", text=text, evidence_ids=evidence_ids, **extra_fields)


def _unknown_block(article: Mapping[str, Any], source_order: int, raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        text = _clean_text(raw.get("text") or raw.get("value"))
        locator = _clean_text(raw.get("locator") or raw.get("source_locator"))
    else:
        text, locator = _clean_text(raw), ""
    return _base_block(article, source_order, "unknown", text=text, source_locator=locator, review_reason="unrecognized source block", evidence_ids=[])


def _blocks_from_steps(steps: Any) -> list[dict[str, Any]] | None:
    if not isinstance(steps, list):
        return None
    result = []
    for step in steps:
        if isinstance(step, Mapping):
            ev_ids = step.get("evidence_ids", [])
            step_action = _clean_text(
                step.get("action")
                or step.get("heading")
                or step.get("title")
                or step.get("label")
                or step.get("name")
            )
            if step_action:
                result.append({"kind": "text", "text": step_action, "evidence_ids": ev_ids})
            has_instructions = False
            for value in step.get("instructions") or []:
                if isinstance(value, Mapping):
                    val_text = _clean_text(
                        value.get("text")
                        or value.get("action")
                        or value.get("instruction")
                        or value.get("value")
                        or value.get("content")
                        or value.get("body")
                    )
                else:
                    val_text = _clean_text(value)
                if val_text:
                    has_instructions = True
                    result.append({"kind": "text", "text": val_text, "evidence_ids": ev_ids})
            if not step_action and not has_instructions:
                step_text = _clean_text(
                    step.get("text")
                    or step.get("instruction")
                    or step.get("content")
                    or step.get("body")
                )
                if step_text:
                    result.append({"kind": "text", "text": step_text, "evidence_ids": ev_ids})
            result.extend({"kind": "image", **dict(image)} for image in step.get("images") or [] if isinstance(image, Mapping))
        elif str(step).strip():
            result.append({"kind": "text", "text": str(step)})
    return result


def _evidence_ids(raw: Mapping[str, Any], article: Mapping[str, Any]) -> list[str]:
    values = (
        raw.get("evidence_ids")
        or raw.get("evidence_id")
        or article.get("evidence_ids")
        or article.get("evidence_id")
        or []
    )
    if not isinstance(values, list):
        values = [values]
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _numbered_text(text: str) -> tuple[int, str] | None:
    match = re.match(r"^\s*(\d+)[.)]\s*(.+?)\s*$", text)
    return (int(match.group(1)), match.group(2).strip()) if match else None


def _looks_like_heading(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9/&'().,\- ]{2,119}", text) and re.search(r"[A-Z]", text))


def _clean_text(value: Any) -> str:
    text = str(value or "").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    # A pipe on a table edge is an extractor artifact, not article content.
    text = re.sub(r"^\|\s*", "", text)
    text = re.sub(r"\s*\|$", "", text)
    return text.strip()


def _safe_link(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("href") or value.get("url") or value.get("link") or value.get("target")
    href = _clean_text(value)
    if not href or href.startswith("#"):
        return ""
    scheme = href.split(":", 1)[0].lower() if ":" in href else ""
    if scheme in {"javascript", "vbscript", "data"}:
        return ""
    return href


def _level(raw: Mapping[str, Any]) -> int:
    try:
        return max(1, min(6, int(raw.get("level") or 2)))
    except (TypeError, ValueError):
        return 2


def _expand_plain_source_blocks(source_blocks: list[Any]) -> list[Any]:
    expanded: list[Any] = []
    for raw in source_blocks:
        if isinstance(raw, str):
            raw = {"kind": "text", "text": raw}
        if not isinstance(raw, Mapping):
            expanded.append(raw)
            continue
        kind = str(raw.get("type") or raw.get("kind") or "text").casefold()
        if kind not in {"text", "paragraph"}:
            expanded.append(raw)
            continue
        text = str(raw.get("text") or raw.get("value") or "")
        if not text.strip() or not _needs_plain_segmentation(text):
            expanded.append(raw)
            continue
        segments = segment_plain_article_text(text)
        if len(segments) <= 1:
            expanded.append(raw)
            continue
        for index, segment in enumerate(segments):
            block = {**raw, **segment}
            if index < len(segments) - 1:
                block.pop("images", None)
            expanded.append(block)
    return expanded


def _needs_plain_segmentation(text: str) -> bool:
    if "\n" in text:
        return True
    header_hits = len(_PLAIN_SECTION_SPLIT_RE.findall(text))
    step_hits = len(_PLAIN_STEP_SPLIT_RE.findall(text))
    note_hits = len(_PLAIN_NOTE_SPLIT_RE.findall(text))
    return header_hits >= 2 or step_hits >= 2 or (header_hits >= 1 and step_hits >= 1) or note_hits >= 1


def _insert_plain_text_boundaries(text: str) -> str:
    updated = _PLAIN_MULTIWORD_SECTION_SPLIT_RE.sub(r"\n\1\n", text)
    updated = _PLAIN_CONDITION_BEFORE_SECTION_RE.sub(r"\n\1\n", updated)
    updated = _PLAIN_SINGLE_SECTION_SPLIT_RE.sub(r"\n\1\n", updated)
    updated = _PLAIN_SERVICE_BEFORE_STEPS_RE.sub(r"\n\1\n", updated)
    updated = _PLAIN_NOTE_SPLIT_RE.sub(r"\n\1 ", updated)
    # Protect "Figure 1." captions before numbered-step splitting.
    updated = _PLAIN_FIGURE_SPLIT_RE.sub(r"\n\1 ", updated)
    updated = _PLAIN_STEP_SPLIT_RE.sub(r"\n\1", updated)
    updated = re.sub(r"\s*©\s*\d{4}[^\n]*", "\n", updated)
    updated = re.sub(r"\s*Page\s+\d+\s+of\s+\d+[^\n]*", "\n", updated, flags=re.IGNORECASE)
    # Drop repeated bulletin title lines that appear before the Service section.
    updated = re.sub(
        r"(?im)^Technical Service Bulletin\s*$",
        "",
        updated,
    )
    return updated


def _is_plain_section_heading(text: str) -> bool:
    key = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    return key in _PLAIN_SECTION_HEADER_KEYS


def _is_plain_boilerplate(text: str) -> bool:
    lowered = text.casefold()
    if re.match(r"^page\s+\d+\s+of\s+\d+\b", lowered):
        return True
    if lowered.startswith("©") or lowered.startswith("(c)"):
        return True
    if "all rights reserved" in lowered and len(text) > 80:
        return True
    if "information contained in this document is based on the latest information" in lowered:
        return True
    if "no part of this document may be reproduced" in lowered:
        return True
    return False


__all__ = [
    "DOCUMENT_TYPES",
    "NORMALIZATION_VERSION",
    "SCHEMA_VERSION",
    "build_ordered_document",
    "document_from_steps",
    "empty_document",
    "has_ordered_list_numbering",
    "has_structured_list_items",
    "segment_plain_article_text",
    "validate_ordered_document",
]


def project_ordered_document(document):
    """Derive compatibility content without replacing the ordered document.

    Tables and standalone illustrations contribute to body/images, never fake
    compatibility operations. Nested prose retains its source traversal order.
    """
    texts, steps, images = [], [], []
    current = None
    def visit(blocks, allow_steps=True):
        nonlocal current
        for block in blocks:
            kind = block.get("type")
            text = block.get("text")
            for label in (block.get("label"),block.get("caption")):
                if isinstance(label,str) and label.strip():texts.append(label)
            if isinstance(text, str) and text.strip():
                texts.append(text)
                if allow_steps and kind == "step":
                    current={"action":text,"instructions":[],"images":deepcopy(block.get("images",[])),
                             "evidence_ids":deepcopy(block.get("evidence_ids",[]))}
                    steps.append(current)
                elif allow_steps and kind == "paragraph" and current is not None:
                    current["instructions"].append(text)
            if kind == "image":
                images.append(deepcopy(block))
            if kind not in {"ordered_list", "unordered_list"}:
                images.extend(deepcopy(block.get("images", [])))
            if kind in {"ordered_list", "unordered_list"}:
                for item, ordinal in walk_ordered_list_items(block):
                    if isinstance(item, str):
                        item = {"text": item}
                    item_text = item.get("text")
                    previous_step = current
                    current = None
                    if isinstance(item_text, str) and item_text.strip():
                        texts.append(item_text)
                        if allow_steps:
                            current = {
                                "action": item_text, "instructions": [],
                                "images": deepcopy(item.get("images", [])),
                                "evidence_ids": deepcopy(block.get("evidence_ids", [])),
                            }
                            if ordinal is not None:
                                current["number"] = ordinal
                            steps.append(current)
                    images.extend(deepcopy(item.get("images", [])))
                    visit(item.get("blocks", []), allow_steps)
                    current = previous_step
                images.extend(deepcopy(block.get("images", [])))
            if kind == "table":
                for column in block.get("columns",[]):
                    if isinstance(column,str):texts.append(column)
                    elif isinstance(column,dict) and isinstance(column.get("text"),str):texts.append(column["text"])
                for row in block.get("rows",[]):
                    cells=row if isinstance(row,list) else row.get("cells",[])
                    for cell in cells:
                        if isinstance(cell,str):cell={"text":cell}
                        if isinstance(cell.get("text"),str): texts.append(cell["text"])
                        images.extend(deepcopy(cell.get("images",[])))
                        visit(cell.get("blocks",[]),False)
    visit(document["blocks"])
    return {"body":"\n".join(texts),"steps":steps,"images":images}
