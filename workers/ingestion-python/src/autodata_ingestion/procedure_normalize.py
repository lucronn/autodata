"""Normalize provider procedure pages into the catalog consumer shape."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping

from .article_document import (
    build_ordered_document,
    document_from_steps,
    validate_ordered_document,
)


_COMPONENT_TERMS = {
    "oil_pump": "oil pump",
    "water_pump": "water pump",
    "timing_belt": "timing belt",
    "power_steering_pump": "power steering pump",
    "alternator": "alternator",
    "starter": "starter",
    "brakes": "brake",
    "brake_pads": "brake pad",
    "brake_rotor": "brake rotor",
    "brake_caliper": "brake caliper",
}

CONTENT_STATUS_LIST_ONLY = "list_only"
CONTENT_STATUS_COMPLETE = "content_complete"


def normalize_procedure_article(article: Mapping[str, Any]) -> dict[str, Any]:
    """Return one source-agnostic procedure article for catalog persistence.

    Provider HTML/blocks are converted into ordered consumer steps once. The
    returned record is safe to store in ``catalog_articles.steps`` and to serve
    directly to compose/display without title guessing.
    """

    out = deepcopy(dict(article))
    _ensure_classification(out)
    if _steps_are_consumer_shaped(out.get("steps")):
        document = out.get("normalized_document")
        blocks = document.get("blocks") if isinstance(document, Mapping) else None
        if (
            not isinstance(document, Mapping)
            or not isinstance(blocks, list)
            or not blocks
            or validate_ordered_document(document)
        ):
            out["normalized_document"] = document_from_steps(out)
        out.pop("blocks", None)
        out["content_status"] = _content_status_for(out)
        return out

    blocks = out.get("blocks")
    if not isinstance(blocks, list):
        steps_field = out.get("steps")
        if _steps_are_provider_blocks(steps_field):
            blocks = steps_field
        elif isinstance(steps_field, list) and steps_field and _steps_are_consumer_shaped(steps_field):
            out["steps"] = list(steps_field)
            out.pop("blocks", None)
            out["content_status"] = _content_status_for(out)
            return out
        elif isinstance(steps_field, list) and all(isinstance(step, str) for step in steps_field):
            blocks = [{"kind": "text", "text": f"{index}. {step}"} for index, step in enumerate(steps_field, 1)]
        else:
            body = str(out.get("body") or "").strip()
            blocks = [{"kind": "text", "text": body}] if body else []
    elif blocks and all(isinstance(step, str) for step in blocks):
        # AutoAPI detail pages expose ordered <li> items as strings. Keep each
        # item as an independent block so normalization preserves source order.
        blocks = [{"kind": "text", "text": f"{index}. {step}"} for index, step in enumerate(blocks, 1)]

    out["normalized_document"] = build_ordered_document(out, blocks)
    out["steps"] = build_consumer_steps(out, blocks)
    out.pop("blocks", None)
    if not str(out.get("body") or "").strip() and out["steps"]:
        out["body"] = _body_from_steps(out["steps"])
    out["content_status"] = _content_status_for(out)
    return out


def build_consumer_steps(
    article: Mapping[str, Any],
    blocks: Any,
) -> list[dict[str, Any]]:
    """Convert interleaved provider blocks into ordered consumer steps."""

    component = str(article.get("component") or "service")
    kind = str(article.get("procedure_kind") or "procedure")
    article_title = _text(article.get("title"))
    heading_keys = {
        re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
        for value in (
            article_title,
            article_title.split(">>", 1)[0],
            component.replace("_", " "),
            _COMPONENT_TERMS.get(component, ""),
        )
        if value
    }
    if not isinstance(blocks, list):
        blocks = [{"kind": "text", "text": article.get("body", "")}]
    pending_images: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    current_phase = "removal" if kind == "removal_and_installation" else kind
    section_start = True
    # Body-only sources and provider blocks may contain several numbered lines.
    # Split before whitespace normalization erases their boundaries.
    expanded_blocks = []
    for block in blocks:
        block_type = str(block.get("kind") or block.get("type") or "").casefold() if isinstance(block, Mapping) else ""
        if isinstance(block, Mapping) and block_type != "image":
            lines = str(block.get("text") or "").splitlines()
            expanded_blocks.extend({**block, "text": line} for line in lines)
        else:
            expanded_blocks.append(block)
    for block in expanded_blocks:
        if not isinstance(block, Mapping):
            continue
        if str(block.get("kind") or block.get("type") or "").casefold() == "image":
            image = {
                key: block[key]
                for key in ("url", "alt", "image_id", "evidence_ids", "storage_key", "source_article_ids")
                if block.get(key)
            }
            if article.get("article_id"):
                image["source_article_ids"] = [str(article["article_id"])]
            if image.get("url") or image.get("storage_key"):
                pending_images.append(image)
            continue
        text = _text(block.get("text"))
        if not text:
            continue
        heading_key = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
        if heading_key in {"removal", "removals", "removal procedure", "removal procedures"}:
            current_phase = "removal"
            section_start = True
            continue
        if heading_key in {
            "installation",
            "installations",
            "installation procedure",
            "installation procedures",
        }:
            current_phase = "installation"
            section_start = True
            continue
        if heading_key in heading_keys:
            continue
        evidence_ids = [
            str(value)
            for value in block.get("evidence_ids", article.get("evidence_ids", []))
            if str(value).strip()
        ]
        starts_step = bool(re.match(r"^\d+[.)]\s", text)) or not steps or section_start
        if starts_step:
            # Headings alone set phase. Do not flip phase from verbs such as
            # "Remove residual gasket" inside an INSTALLATION section — that
            # mis-tags steps and later compose sorts would shuffle them.
            steps.append(
                {
                    "action": _step_action(text, component, kind),
                    "instructions": [],
                    "components": [component],
                    "source_article_ids": [str(article.get("article_id"))],
                    "evidence_ids": sorted(set(evidence_ids)),
                    "images": pending_images,
                    "phase": current_phase,
                }
            )
            pending_images = []
            section_start = False
        else:
            current = steps[-1]
            current["instructions"].append(text)
            current["evidence_ids"] = sorted(
                set(current.get("evidence_ids", [])) | set(evidence_ids)
            )
    if pending_images and steps:
        steps[-1]["images"].extend(pending_images)
    return steps


def article_is_content_complete(article: Mapping[str, Any]) -> bool:
    """True when the article may be served from catalog without re-fetch."""

    status = str(article.get("content_status") or "").casefold()
    if status == CONTENT_STATUS_COMPLETE:
        return True
    if status == CONTENT_STATUS_LIST_ONLY:
        return False
    steps = article.get("steps")
    if _steps_are_consumer_shaped(steps) and steps:
        return True
    body = str(article.get("body") or "").strip()
    return len(body) >= 80


def _ensure_classification(article: dict[str, Any]) -> None:
    title = str(article.get("title") or "")
    title_key = title.casefold()
    if not str(article.get("component") or "").strip():
        for component, term in _COMPONENT_TERMS.items():
            if term in title_key or component.replace("_", " ") in title_key:
                article["component"] = component
                break
    if not str(article.get("procedure_kind") or "").strip():
        if "removal and installation" in title_key:
            article["procedure_kind"] = "removal_and_installation"
        elif "removal" in title_key:
            article["procedure_kind"] = "removal"
        elif "installation" in title_key:
            article["procedure_kind"] = "installation"
    article_id = str(article.get("article_id") or "")
    if not str(article.get("provider") or "").strip() and (
        article_id.startswith("merged:autoapitwo")
        or article_id.startswith("autoapitwo:")
        or "autoapitwo.vercel.app" in str(article.get("source_uri") or "")
    ):
        article["provider"] = "autoapitwo"
    if not str(article.get("content_kind") or "").strip():
        article["content_kind"] = "procedure"


def _content_status_for(article: Mapping[str, Any]) -> str:
    document = article.get("normalized_document")
    if isinstance(document, Mapping):
        errors = validate_ordered_document(document)
        blocks = document.get("blocks")
        if errors or not isinstance(blocks, list):
            return CONTENT_STATUS_LIST_ONLY
        readable = any(
            isinstance(block, Mapping)
            and (
                str(block.get("text") or "").strip()
                or str(block.get("type") or "") in {"image", "table", "ordered_list", "unordered_list"}
            )
            for block in blocks
        )
        structural_content = any(
            isinstance(block, Mapping)
            and str(block.get("type") or "") in {"step", "table", "image", "ordered_list", "unordered_list", "callout"}
            for block in blocks
        )
        if readable and (structural_content or len(str(article.get("body") or "").strip()) >= 80):
            return CONTENT_STATUS_COMPLETE
    steps = article.get("steps")
    if _steps_are_consumer_shaped(steps) and steps:
        return CONTENT_STATUS_COMPLETE
    body = str(article.get("body") or "").strip()
    if len(body) >= 80:
        return CONTENT_STATUS_COMPLETE
    return CONTENT_STATUS_LIST_ONLY


def _steps_are_consumer_shaped(steps: Any) -> bool:
    if not isinstance(steps, list) or not steps:
        return False
    first = steps[0]
    if not isinstance(first, Mapping):
        return False
    if str(first.get("kind") or "").strip():
        return False
    return bool(str(first.get("action") or "").strip() or first.get("instructions"))


def _steps_are_provider_blocks(steps: Any) -> bool:
    if not isinstance(steps, list) or not steps:
        return False
    first = steps[0]
    return isinstance(first, Mapping) and bool(str(first.get("kind") or "").strip())


def _body_from_steps(steps: list[Mapping[str, Any]]) -> str:
    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        action = _text(step.get("action"))
        if action:
            lines.append(f"{index}. {action}")
        for instruction in step.get("instructions") or []:
            text = _text(instruction)
            if text:
                lines.append(text)
    return "\n".join(lines)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _step_action(text: str, component: str, kind: str) -> str:
    cleaned = re.sub(r"^\d+[.)]\s*", "", text).strip()
    if cleaned:
        return cleaned
    verb = "Install" if kind == "installation" else "Remove"
    return f"{verb} {_COMPONENT_TERMS.get(component, component.replace('_', ' '))}."


__all__ = [
    "CONTENT_STATUS_COMPLETE",
    "CONTENT_STATUS_LIST_ONLY",
    "article_is_content_complete",
    "build_consumer_steps",
    "normalize_procedure_article",
]
