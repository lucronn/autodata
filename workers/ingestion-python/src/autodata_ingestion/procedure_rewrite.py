"""Phrase-only DIY rewrite of ordered procedure steps."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from typing import Any, Mapping


REWRITE_STATUS_PENDING = "pending"
REWRITE_STATUS_REWRITTEN = "rewritten"
REWRITE_STATUS_SKIPPED = "skipped"
REWRITE_STATUS_FAILED = "failed"


def rewrite_steps_for_diy(
    steps: list[Mapping[str, Any]],
    *,
    client: Any | None = None,
    vehicle: Mapping[str, Any] | None = None,
    title: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """Rewrite action/instruction phrasing only; keep count and order fixed.

    Returns ``(steps, rewrite_status)``. On missing credentials, transport
    failure, or validation failure, returns the original steps with
    ``skipped`` or ``failed``.
    """

    baseline = deepcopy(steps)
    if any(not isinstance(step, Mapping) for step in baseline):
        return baseline, REWRITE_STATUS_FAILED
    if not baseline:
        return [], REWRITE_STATUS_SKIPPED
    if os.getenv("AUTODATA_PROCEDURE_DIY_REWRITE", "1") == "0":
        return baseline, REWRITE_STATUS_SKIPPED

    try:
        mercury = client or _configured_client()
    except Exception:  # noqa: BLE001
        return baseline, REWRITE_STATUS_SKIPPED
    if mercury is None:
        return baseline, REWRITE_STATUS_SKIPPED

    prompt = _build_prompt(baseline, vehicle=vehicle or {}, title=title)
    try:
        payload = mercury.complete_json(prompt)
    except Exception:  # noqa: BLE001
        return baseline, REWRITE_STATUS_FAILED

    try:
        rewritten = _validate_phrase_only_rewrite(baseline, payload)
    except ValueError:
        return baseline, REWRITE_STATUS_FAILED
    return rewritten, REWRITE_STATUS_REWRITTEN


def rewrite_procedure_article(
    article: Mapping[str, Any],
    *,
    vehicle: Mapping[str, Any] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Rewrite an ingested article while preserving its ordered document.

    The rewrite validator constrains changes to safe phrase substitutions. The
    matching pass updates only the existing step/paragraph blocks; every other
    block, image, identifier, and source-order value is retained verbatim.
    """

    from .article_document import document_from_steps

    result = deepcopy(dict(article))
    original_steps = result.get("steps")
    if not isinstance(original_steps, list) or not original_steps:
        result["rewrite_status"] = REWRITE_STATUS_SKIPPED
        return result
    rewritten_steps, status = rewrite_steps_for_diy(
        original_steps,
        client=client,
        vehicle=vehicle,
        title=str(result.get("title") or ""),
    )
    if status != REWRITE_STATUS_REWRITTEN:
        result["rewrite_status"] = status
        return result

    document = result.get("normalized_document")
    if not isinstance(document, Mapping) or not isinstance(document.get("blocks"), list):
        document = document_from_steps({**result, "steps": original_steps})
    updated_document = deepcopy(dict(document))
    blocks = updated_document.get("blocks")
    if not isinstance(blocks, list):
        result["rewrite_status"] = REWRITE_STATUS_FAILED
        return result

    cursor = 0
    for step_index, (original, rewritten) in enumerate(zip(original_steps, rewritten_steps)):
        if not isinstance(original, Mapping) or not isinstance(rewritten, Mapping):
            result["rewrite_status"] = REWRITE_STATUS_FAILED
            return result
        action = str(original.get("action") or "").strip()
        next_action = ""
        for later in original_steps[step_index + 1 :]:
            if isinstance(later, Mapping) and str(later.get("action") or "").strip():
                next_action = str(later["action"]).strip()
                break
        action_index = next(
            (
                index
                for index in range(cursor, len(blocks))
                if isinstance(blocks[index], dict)
                and blocks[index].get("type") in {"step", "paragraph"}
                and str(blocks[index].get("text") or "").strip() == action
                and blocks[index].get("type") == "step"
            ),
            None,
        )
        if action_index is None:
            result["rewrite_status"] = REWRITE_STATUS_FAILED
            return result
        blocks[action_index]["text"] = str(rewritten.get("action") or "").strip()
        cursor = action_index + 1

        old_instructions = list(original.get("instructions") or [])
        new_instructions = list(rewritten.get("instructions") or [])
        for old_value, new_value in zip(old_instructions, new_instructions):
            old_text = str(old_value or "").strip()
            instruction_index = next(
                (
                    index
                    for index in range(cursor, len(blocks))
                    if isinstance(blocks[index], dict)
                    and blocks[index].get("type") == "paragraph"
                    and str(blocks[index].get("text") or "").strip() == old_text
                    and (not next_action or str(blocks[index].get("text") or "").strip() != next_action)
                ),
                None,
            )
            if instruction_index is None:
                result["rewrite_status"] = REWRITE_STATUS_FAILED
                return result
            blocks[instruction_index]["text"] = str(new_value or "").strip()
            cursor = instruction_index + 1

    result["steps"] = rewritten_steps
    result["normalized_document"] = updated_document
    result["body"] = "\n".join(
        text
        for step in rewritten_steps
        for text in [
            str(step.get("action") or "").strip(),
            *(str(value or "").strip() for value in step.get("instructions") or []),
        ]
        if text
    )
    result["rewrite_status"] = REWRITE_STATUS_REWRITTEN
    return result


def _configured_client() -> Any | None:
    api_key = os.getenv("INCEPTION_API_KEY", "").strip()
    if not api_key:
        return None
    from .mercury2 import Mercury2Client

    return Mercury2Client.from_environment()


def _build_prompt(
    steps: list[Mapping[str, Any]],
    *,
    vehicle: Mapping[str, Any],
    title: str,
) -> str:
    slim_steps = []
    for index, step in enumerate(steps):
        slim_steps.append(
            {
                "index": index,
                "action": step.get("action"),
                "instructions": list(step.get("instructions") or []),
                "phase": step.get("phase"),
                "components": list(step.get("components") or []),
                "source_article_ids": list(step.get("source_article_ids") or []),
                "evidence_ids": list(step.get("evidence_ids") or []),
                "image_ids": [
                    str(image.get("image_id"))
                    for image in (step.get("images") or [])
                    if isinstance(image, Mapping) and str(image.get("image_id") or "").strip()
                ],
            }
        )
    contract = {
        "task": "diy_phrase_rewrite",
        "rules": [
            "Return JSON with key steps: an array of the same length and order as input.",
            "Each output step must include index, action, and instructions only.",
            "Rewrite action and instructions for DIY-friendly, unique phrasing.",
            "Do not add, drop, or reorder steps.",
            "Do not invent torque values, specs, warnings, parts, or tools.",
            "Preserve every factual constraint present in the source wording.",
            "Keep instruction array length equal to the source instruction array length.",
            "Keep numeric specifications and warning/caution/note text verbatim.",
            "Only change opening imperative phrases: Remove / Take off / Lift off; "
            "Install / Fit / Seat; Discard / Toss. Keep all remaining wording identical.",
        ],
        "vehicle": {
            "year": vehicle.get("year") or vehicle.get("model_year"),
            "make": vehicle.get("make"),
            "model": vehicle.get("model"),
        },
        "title": title,
        "steps": slim_steps,
    }
    return (
        "Rewrite the supplied procedure steps for DIY readability and unique phrasing. "
        "Keep step order and count identical. Return only JSON.\n"
        + json.dumps(contract, sort_keys=True, default=str)
    )


def _validate_phrase_only_rewrite(
    baseline: list[Mapping[str, Any]],
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping) or set(payload) != {"steps"}:
        raise ValueError("rewrite must contain only steps")
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or len(raw_steps) != len(baseline):
        raise ValueError("rewrite step count mismatch")
    rewritten: list[dict[str, Any]] = []
    for index, source in enumerate(baseline):
        candidate = raw_steps[index]
        if not isinstance(candidate, Mapping):
            raise ValueError("rewrite step must be an object")
        if set(candidate) != {"index", "action", "instructions"}:
            raise ValueError("rewrite must contain only index, action and instructions")
        reported_index = candidate["index"]
        if type(reported_index) is not int or reported_index != index:
            raise ValueError("rewrite step index mismatch")
        action = candidate.get("action")
        if not isinstance(action, str) or not action.strip():
            raise ValueError("rewrite action missing")
        instructions = candidate.get("instructions")
        if not isinstance(instructions, list):
            raise ValueError("rewrite instructions must be an array")
        source_instructions = list(source.get("instructions") or [])
        if len(instructions) != len(source_instructions):
            raise ValueError("rewrite instruction count mismatch")
        if any(not isinstance(item, str) or not item.strip() for item in instructions):
            raise ValueError("rewrite instruction must be a non-empty string")
        action = action.strip()
        cleaned_instructions = [item.strip() for item in instructions]
        _validate_wording(source.get("action"), action)
        for original, replacement in zip(source_instructions, cleaned_instructions):
            _validate_wording(original, replacement)
        out = deepcopy(dict(source))
        out["action"] = action
        out["instructions"] = cleaned_instructions
        rewritten.append(out)
    return rewritten


# Deliberately bounded equivalences: free paraphrasing cannot be proved safe by
# matching numbers or keywords. Compare each position separately, including the
# entire remainder, so renamed components, negation, clause swaps and new tools
# fail closed. Unknown but valid paraphrases also fall back to source wording.
_OPENING_PHRASES = (
    (re.compile(r"^(?:remove|take off|lift off)\b", re.I), "Remove"),
    (re.compile(r"^(?:install|fit|seat)\b", re.I), "Install"),
    (re.compile(r"^(?:discard|toss)\b", re.I), "Discard"),
)
_PROTECTED_WORDING = re.compile(
    r"\d|\b(?:warning|caution|danger|note|notice|never|not|must|always)\b", re.I
)


def _validate_wording(source: Any, candidate: str) -> None:
    if not isinstance(source, str):
        raise ValueError("source wording must be a string")
    source = source.strip()
    if source == candidate:
        return
    if _PROTECTED_WORDING.search(source) or _PROTECTED_WORDING.search(candidate):
        raise ValueError("rewrite changed protected wording")
    for pattern, canonical in _OPENING_PHRASES:
        if pattern.match(source) and pattern.match(candidate):
            if pattern.sub(canonical, source, count=1) == pattern.sub(canonical, candidate, count=1):
                return
    raise ValueError("rewrite wording equivalence cannot be verified")


__all__ = [
    "REWRITE_STATUS_FAILED",
    "REWRITE_STATUS_PENDING",
    "REWRITE_STATUS_REWRITTEN",
    "REWRITE_STATUS_SKIPPED",
    "rewrite_procedure_article",
    "rewrite_steps_for_diy",
]
