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


def empty_document() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "blocks": [],
    }


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
        source_blocks = [{"kind": "text", "text": body}] if body else []

    output: list[dict[str, Any]] = []
    for source_index, raw in enumerate(source_blocks, 1):
        if isinstance(raw, str):
            raw = {"kind": "text", "text": raw}
        if not isinstance(raw, Mapping):
            output.append(_unknown_block(article, source_index, raw))
            continue
        kind = str(raw.get("type") or raw.get("kind") or "text").casefold()
        evidence_ids = _evidence_ids(raw, article)
        if kind == "image":
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
        if kind in {"heading", "title", "section"}:
            text = _clean_text(raw.get("text") or raw.get("label"))
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

        text = _clean_text(raw.get("text") or raw.get("value"))
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
            output.append(_base_block(article, source_index, "paragraph", text=text, evidence_ids=evidence_ids))

    # Source order is an invariant.  Do not sort or deduplicate this list.
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
    asset_id = storage_key or image_id or (sha256(source_url.encode()).hexdigest() if source_url else "")
    fields: dict[str, Any] = {
        "asset_id": asset_id or None,
        "image_id": image_id or asset_id or None,
        "alt": _clean_text(raw.get("alt") or raw.get("title")) or "Article illustration",
        "status": "available" if source_url or storage_key else "unavailable",
        "unavailable_reason": None if source_url or storage_key else "source image reference is missing",
    }
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


def _table_cell(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return _clean_text(value)
    nested = value.get("blocks")
    if not isinstance(nested, list):
        return _clean_text(value.get("text") or value.get("value"))
    text_parts: list[str] = []
    images: list[dict[str, Any]] = []
    for child in nested:
        if not isinstance(child, Mapping):
            continue
        if child.get("kind") == "image":
            source_url = _clean_text(child.get("url") or child.get("src"))
            image_id = _clean_text(child.get("image_id") or child.get("id"))
            storage_key = _clean_text(child.get("storage_key") or child.get("artifact_key"))
            asset_id = storage_key or image_id or (sha256(source_url.encode()).hexdigest() if source_url else "")
            images.append({
                "asset_id": asset_id,
                "image_id": image_id or asset_id,
                "alt": _clean_text(child.get("alt") or child.get("title")) or "Article illustration",
                "status": "available" if source_url or storage_key else "unavailable",
            })
        else:
            text = _clean_text(child.get("text") or child.get("value"))
            if text:
                text_parts.append(text)
    result: dict[str, Any] = {"text": " ".join(text_parts)}
    if images:
        result["images"] = images
    return result


def _list_block(article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any], evidence_ids: list[str], kind: str) -> dict[str, Any]:
    values = raw.get("items") or raw.get("values") or []
    if not isinstance(values, list):
        values = [values]
    return _base_block(
        article,
        source_order,
        "ordered_list" if kind == "ordered_list" else "unordered_list",
        items=[_clean_text(value) for value in values if _clean_text(value)],
        evidence_ids=evidence_ids,
    )


def _callout_block(article: Mapping[str, Any], source_order: int, raw: Mapping[str, Any], evidence_ids: list[str], kind: str) -> dict[str, Any]:
    label = _clean_text(raw.get("label")) or kind.upper()
    text = _clean_text(raw.get("text") or raw.get("value"))
    return _base_block(article, source_order, "callout", label=label, text=text, evidence_ids=evidence_ids)


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
    return "" if href.startswith("#") else href


def _level(raw: Mapping[str, Any]) -> int:
    try:
        return max(1, min(6, int(raw.get("level") or 2)))
    except (TypeError, ValueError):
        return 2


__all__ = [
    "DOCUMENT_TYPES",
    "NORMALIZATION_VERSION",
    "SCHEMA_VERSION",
    "build_ordered_document",
    "document_from_steps",
    "empty_document",
    "validate_ordered_document",
]
