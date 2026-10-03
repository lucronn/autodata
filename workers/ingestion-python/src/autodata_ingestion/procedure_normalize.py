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
        if isinstance(block, Mapping) and block_type == "ordered_list":
            items = block.get("items")
            if isinstance(items, list):
                try:
                    start = max(1, int(block.get("start") or 1))
                except (TypeError, ValueError):
                    start = 1
                for offset, item in enumerate(items):
                    text = _text(item.get("text") if isinstance(item, Mapping) else item)
                    if text:
                        expanded_blocks.append({
                            "kind": "text",
                            "text": f"{start + offset}. {text}",
                            "evidence_ids": block.get("evidence_ids", []),
                        })
                continue
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
        if not is_meaningful_procedure_text(text):
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
    """True only when the stored text contains meaningful procedure content.

    ``content_status`` is persisted metadata and may describe an older
    normalization revision. It cannot override the actual saved instructions.
    """

    steps = article.get("steps")
    if isinstance(steps, list) and steps:
        for step in steps:
            if isinstance(step, Mapping):
                candidates = [step.get("action"), *(step.get("instructions") or [])]
            else:
                candidates = [step]
            if any(is_meaningful_procedure_text(value) for value in candidates):
                return True
        return False
    body = str(article.get("body") or "")
    return any(
        is_meaningful_procedure_text(sentence)
        for sentence in re.split(r"[\n.!?]+", body)
    )


def is_meaningful_procedure_text(value: Any) -> bool:
    """Accept source text that reads like an instruction, not metadata or prose."""

    text = re.sub(r"\s+", " ", str(value or "")).strip()
    key = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    if not key or key in {
        "removal", "removals", "removal procedure", "removal procedures",
        "installation", "installations", "installation procedure",
        "installation procedures", "procedure", "procedures", "overview",
        "general information", "7l diesel",
    }:
        return False
    # Bare engine displacement labels (for example "7L" or "5.7L Diesel")
    # often arrive as the only extracted text when a provider page is missing
    # its procedure body. They identify an application, not an action.
    if re.fullmatch(
        r"\d+(?:\.\d+)?\s*(?:l|liter|liters|litre|litres)"
        r"(?:\s+(?:diesel|gas|gasoline|petrol|hybrid))?",
        text.casefold(),
    ):
        return False
    # A long descriptive paragraph can mention a component and still contain
    # no usable replacement instruction. Source procedures are normally
    # imperative steps; only accept an action verb at the start (optionally
    # following a short conditional or purpose clause).
    action = (
        r"disconnect|reconnect|remove|reinstall|install|replace|loosen|"
        r"tighten|torque|connect|raise|lower|support|drain|refill|clean|"
        r"inspect|align|apply|route|secure|attach|detach|turn|rotate|press|"
        r"pull|push|slide|lift|separate|release|depress|bleed|prime|check|"
        r"verify|measure|adjust|set|lubricate|transfer|mark|cut|grind|"
        r"solder|use|place|position|install|ensure|make|refer|depress"
    )
    prefix = (
        r"(?:\d+\s*[.)]\s*)?"
        r"(?:(?:if|when|before|after)\b[^,;]{1,100}[,;:]\s*)?"
        r"(?:(?:to|using)\b[^,;]{1,100}[,;:]\s*)?"
    )
    return re.match(prefix + rf"(?:{action})\b", text, flags=re.IGNORECASE) is not None


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
    return (
        CONTENT_STATUS_COMPLETE
        if article_is_content_complete(article)
        else CONTENT_STATUS_LIST_ONLY
    )


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
    "is_meaningful_procedure_text",
    "build_consumer_steps",
    "normalize_procedure_article",
]
