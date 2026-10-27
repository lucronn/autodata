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
        image.get("src"),
        image.get("href"),
        image.get("asset_resource_ref"),
    )
    return {str(k).strip() for k in keys if k and str(k).strip()}


def build_ordered_document(
    article: Mapping[str, Any],
    blocks: Any = None,
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
                    cells = row if isinstance(row, list) else row.get("cells", []) if isinstance(row, Mapping) else []
                    for cell in cells:
                        if isinstance(cell, Mapping):
                            for cell_img in cell.get("images") or []:
                                if isinstance(cell_img, Mapping):
                                    seen_image_keys.update(_image_identities(cell_img))
                            for child in cell.get("blocks") or []:
                                if isinstance(child, Mapping) and str(child.get("kind") or child.get("type") or "").casefold() == "image":
                                    seen_image_keys.update(_image_identities(child))

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
            output.append(_table_block(article, source_index, raw, evidence_ids))
            continue
        if kind in {"ordered_list", "unordered_list", "list"}:
            output.append(_list_block(article, source_index, raw, evidence_ids, kind))
            continue
        if kind in {"callout", "note", "warning", "caution", "hint", "important"}:
            output.append(_callout_block(article, source_index, raw, evidence_ids, kind))
            continue
        if kind in {"step", "instruction"}:
            output.append(_step_block(article, source_index, raw, evidence_ids))
            continue
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
                output.append(_base_block(article, source_index, "heading", text=text, level=_level(raw), evidence_ids=evidence_ids))
            continue
        if kind in {"break", "hr", "separator"}:
            output.append(_base_block(article, source_index, "break", evidence_ids=evidence_ids))
            continue
        if kind in {"link", "anchor"}:
            text = _clean_text(raw.get("text") or raw.get("label"))
            if text:
                output.append(
                    _base_block(
                        article,
                        source_index,
                        "link",
                        text=text,
                        href=_safe_link(raw.get("href")),
                        evidence_ids=evidence_ids,
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
                )
            )
        elif _looks_like_heading(text):
            output.append(_base_block(article, source_index, "heading", text=text, level=2, evidence_ids=evidence_ids))
        else:
            images_raw = raw.get("images")
            extra_fields: dict[str, Any] = {}
            if isinstance(images_raw, list):
                clean_images = [
                    _normalize_cell_image(image) for image in images_raw if isinstance(image, Mapping)
                ]
                if clean_images:
                    extra_fields["images"] = clean_images
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

    # Source order / block ids must stay contiguous after figure insertion.
    for order, block in enumerate(output, start=1):
        block["source_order"] = order
        block["block_id"] = f"{article.get('article_id') or 'article'}:block:{order:04d}"

    return {
        "schema_version": SCHEMA_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "blocks": output,
    }


def document_from_steps(article: Mapping[str, Any]) -> dict[str, Any]:
    """Build a readable compatibility document for legacy stored rows."""

    blocks: list[dict[str, Any]] = []
    for index, step in enumerate(article.get("steps") or [], 1):
        if not isinstance(step, Mapping):
            text = _clean_text(step)
            if text:
                blocks.append({"kind": "text", "text": text})
            continue
        heading = _clean_text(step.get("heading") or step.get("action"))
        instructions = [
            _clean_text(value)
            for value in step.get("instructions") or []
            if _clean_text(value)
        ]
        if heading:
            blocks.append({"kind": "text", "text": f"{step.get('number') or index}. {heading}"})
        for instruction in instructions:
            blocks.append({"kind": "text", "text": instruction})
        for image in step.get("images") or []:
            if isinstance(image, Mapping):
                blocks.append({"kind": "image", **dict(image)})
    return build_ordered_document(article, blocks)


def validate_ordered_document(document: Any) -> list[str]:
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
    asset_id = storage_key or image_id or asset_resource_ref or (sha256(source_url.encode()).hexdigest() if source_url else "")
    is_available = bool(source_url or storage_key or asset_resource_ref)
    fields: dict[str, Any] = {
        "asset_id": asset_id or None,
        "image_id": image_id or asset_id or None,
        "alt": _clean_text(raw.get("alt") or raw.get("title")) or "Article illustration",
        "status": "available" if is_available else "unavailable",
        "unavailable_reason": None if is_available else "source image reference is missing",
    }
    if storage_key:
        fields["storage_key"] = storage_key
    if source_url:
        fields["url"] = source_url
    if asset_resource_ref:
        fields["asset_resource_ref"] = asset_resource_ref
    return _base_block(article, source_order, "image", evidence_ids=evidence_ids, **fields)


def _table_block(article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any], evidence_ids: list[str]) -> dict[str, Any]:
    rows = raw.get("rows")
    if not isinstance(rows, list):
        rows = []
    clean_rows = []
    for row in rows:
        if isinstance(row, Mapping):
            values = row.get("cells") or row.get("values") or row.get("blocks") or []
        else:
            values = row
        if not isinstance(values, list):
            values = [values]
        clean_rows.append([_table_cell(value) for value in values])
    columns = raw.get("columns") if isinstance(raw.get("columns"), list) else []
    return _base_block(
        article,
        source_order,
        "table",
        label=_clean_text(raw.get("label") or raw.get("caption")),
        columns=[_clean_text(value) for value in columns],
        rows=clean_rows,
        evidence_ids=evidence_ids,
    )


def _normalize_cell_image(raw: Mapping[str, Any]) -> dict[str, Any]:
    source_url = _clean_text(raw.get("url") or raw.get("src") or raw.get("href"))
    image_id = _clean_text(raw.get("image_id") or raw.get("id"))
    storage_key = _clean_text(raw.get("storage_key") or raw.get("artifact_key"))
    asset_resource_ref = _clean_text(raw.get("asset_resource_ref"))
    asset_id = storage_key or image_id or asset_resource_ref or (sha256(source_url.encode()).hexdigest() if source_url else "")
    out: dict[str, Any] = {
        "asset_id": asset_id or None,
        "image_id": image_id or asset_id or None,
        "alt": _clean_text(raw.get("alt") or raw.get("title")) or "Article illustration",
        "status": "available" if (source_url or storage_key or asset_resource_ref) else "unavailable",
    }
    if storage_key:
        out["storage_key"] = storage_key
    if source_url:
        out["url"] = source_url
    if asset_resource_ref:
        out["asset_resource_ref"] = asset_resource_ref
    return out


def _table_cell(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return _clean_text(value)
    text_parts: list[str] = []
    direct_text = _clean_text(value.get("text") or value.get("value"))
    if direct_text:
        text_parts.append(direct_text)
    images: list[dict[str, Any]] = []
    for direct_img in value.get("images") or []:
        if isinstance(direct_img, Mapping):
            images.append(_normalize_cell_image(direct_img))
    nested = value.get("blocks")
    if isinstance(nested, list):
        for child in nested:
            if not isinstance(child, Mapping):
                continue
            child_kind = str(child.get("kind") or child.get("type") or "").casefold()
            if child_kind == "image":
                images.append(_normalize_cell_image(child))
            else:
                text = _clean_text(child.get("text") or child.get("value"))
                if text:
                    text_parts.append(text)
    combined_text = " ".join(part for part in text_parts if part).strip()
    if images:
        return {"text": combined_text, "images": images}
    return combined_text


def _list_block(article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any], evidence_ids: list[str], kind: str) -> dict[str, Any]:
    values = raw.get("items") or raw.get("values") or []
    if not isinstance(values, list):
        values = [values]
    clean_items: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            item_text = _clean_text(
                value.get("text")
                or value.get("value")
                or value.get("label")
                or value.get("content")
                or value.get("body")
                or value.get("message")
            )
        else:
            item_text = _clean_text(value)
        if item_text:
            clean_items.append(item_text)
    return _base_block(
        article,
        source_order,
        "ordered_list" if kind == "ordered_list" else "unordered_list",
        items=clean_items,
        evidence_ids=evidence_ids,
    )


def _callout_block(article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any], evidence_ids: list[str], kind: str) -> dict[str, Any]:
    label = _clean_text(raw.get("label")) or kind.upper()
    text = _clean_text(
        raw.get("text")
        or raw.get("value")
        or raw.get("message")
        or raw.get("content")
        or raw.get("body")
    )
    images_raw = raw.get("images")
    extra_fields: dict[str, Any] = {}
    if isinstance(images_raw, list):
        clean_images = [
            _normalize_cell_image(image) for image in images_raw if isinstance(image, Mapping)
        ]
        if clean_images:
            extra_fields["images"] = clean_images
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
    instructions = raw.get("instructions")
    if isinstance(instructions, list):
        joined_instructions = " ".join(_clean_text(item) for item in instructions if _clean_text(item))
        if joined_instructions:
            text_candidates.append(joined_instructions)

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
    if isinstance(images_raw, list):
        clean_images = [
            _normalize_cell_image(image) for image in images_raw if isinstance(image, Mapping)
        ]
        if clean_images:
            extra_fields["images"] = clean_images

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
            if step.get("action"):
                result.append({"kind": "text", "text": step.get("action"), "evidence_ids": step.get("evidence_ids", [])})
            result.extend({"kind": "text", "text": value, "evidence_ids": step.get("evidence_ids", [])} for value in step.get("instructions") or [])
            result.extend({"kind": "image", **dict(image)} for image in step.get("images") or [] if isinstance(image, Mapping))
        elif str(step).strip():
            result.append({"kind": "text", "text": str(step)})
    return result


def _evidence_ids(raw: Mapping[str, Any], article: Mapping[str, Any]) -> list[str]:
    values = raw.get("evidence_ids", article.get("evidence_ids", []))
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
        for segment in segments:
            expanded.append({**dict(raw), **segment})
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
    "segment_plain_article_text",
    "validate_ordered_document",
]
