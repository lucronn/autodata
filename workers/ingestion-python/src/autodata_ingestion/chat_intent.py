"""Deterministic natural-language chat intent extraction.

The chat boundary accepts one message, but downstream work needs structured
vehicle and operation data.  This module performs the cheap, repeatable first
pass and treats Mercury-2 as an advisory fallback only when the first pass
cannot resolve a value.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable, Mapping, TYPE_CHECKING

from .vehicle_identity import canonicalize_vehicle_observation

if TYPE_CHECKING:
    from .mercury2 import Mercury2Client


_ALLOWED_COMPONENTS = (
    "alternator",
    "battery",
    "brake_caliper",
    "brake_line",
    "brake_pads",
    "brake_rotor",
    "brakes",
    "oil_pump",
    "power_steering_pump",
    "starter",
    "timing_belt",
    "water_pump",
)

_COMPONENT_ALIASES = {
    "alternator": "alternator",
    "battery": "battery",
    "brake caliper": "brake_caliper",
    "brake line": "brake_line",
    "brakeline": "brake_line",
    "brake hose": "brake_line",
    "brake hoses": "brake_line",
    "brake pad": "brake_pads",
    "brake pads": "brake_pads",
    "brake rotor": "brake_rotor",
    "brake rotors": "brake_rotor",
    "brakes": "brakes",
    "oil pump": "oil_pump",
    "power steering pump": "power_steering_pump",
    "power-steering pump": "power_steering_pump",
    "starter": "starter",
    "timing belt": "timing_belt",
    "water pump": "water_pump",
}

_COMPONENT_PATTERN = re.compile(
    "|".join(
        re.escape(alias)
        for alias in sorted(_COMPONENT_ALIASES, key=len, reverse=True)
    ),
    re.IGNORECASE,
)
_VEHICLE_PATTERN = re.compile(
    r"\b(?P<year>\d{2}|(?:19|20)\d{2})\s+"
    r"(?P<make>[A-Za-z][A-Za-z-]*)\s+"
    r"(?P<model>RAV\s*[- ]?4|[A-Za-z][A-Za-z0-9-]*(?:\s+\d{2,4})?)",
    re.IGNORECASE,
)
_ACTION_PATTERN = re.compile(
    r"\b(replac(?:e|ement|ment)|r\s*&?\s*r|service|servicing|inspect(?:ion)?|bleed(?:ing)?)\b",
    re.IGNORECASE,
)
_INTENT_STOP_PATTERN = re.compile(
    r"\b(?:quote|procedure|procedures|repair\s+steps|how\s+to|please|need|help)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChatIntent:
    vehicle_observation: dict[str, Any]
    requested_operations: tuple[dict[str, Any], ...]
    quote_requested: bool
    procedure_requested: bool
    clarification: str | None


def interpret_chat_message(
    message: str,
    vehicle_candidates: tuple[Mapping[str, Any], ...],
    *,
    mercury_client: "Mercury2Client | None" = None,
) -> ChatIntent:
    """Interpret one chat message without allowing an LLM to become authoritative."""

    normalized_message = _require_message(message)
    deterministic_vehicle = _parse_vehicle(normalized_message)
    operations = _parse_operations(normalized_message)
    vehicle = _resolve_candidates(deterministic_vehicle, vehicle_candidates)

    needs_model = not operations or vehicle.get("status") in {"unmatched", "needs_review"}
    if needs_model and mercury_client is not None:
        proposal = _advisory_proposal(
            mercury_client,
            normalized_message,
            vehicle_candidates,
        )
        operations = operations or _operations_from_proposal(proposal)
        vehicle = _apply_advisory_vehicle_selection(vehicle, proposal, vehicle_candidates)

    if not operations:
        clarification = "Which component needs service?"
    elif vehicle.get("status") == "ambiguous":
        clarification = _vehicle_clarification(vehicle)
    elif vehicle.get("status") in {"unmatched", "needs_review"}:
        clarification = "Which vehicle configuration should I use?"
    else:
        clarification = None

    return ChatIntent(
        vehicle_observation=vehicle,
        requested_operations=tuple(operations),
        quote_requested=_contains_intent(normalized_message, ("quote", "price", "pricing")),
        procedure_requested=_contains_intent(
            normalized_message,
            ("procedure", "procedures", "repair steps", "how to"),
        ),
        clarification=clarification,
    )


def derive_supporting_operations(
    requested_operations: tuple[Mapping[str, Any], ...],
    articles: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Derive transparent support work from source/rule metadata.

    Model suggestions are deliberately preserved as ``needs_review``.  They
    cannot become required or recommended work without source or trusted-rule
    support.
    """

    requested_ids = {
        str(operation.get("operation_id", "")).strip()
        for operation in requested_operations
    }
    derived: list[dict[str, Any]] = []
    seen: set[str] = set(requested_ids)
    for article in articles:
        article_id = str(article.get("article_id", "")).strip()
        for field, category, basis in (
            ("supporting_operations", None, "source_article"),
            ("trusted_rules", None, "trusted_rule"),
            ("model_suggestions", "needs_review", "model_advisory"),
        ):
            values = article.get(field, ())
            if not isinstance(values, Iterable) or isinstance(values, (str, bytes, Mapping)):
                continue
            for raw_operation in values:
                if not isinstance(raw_operation, Mapping):
                    continue
                operation_id = str(raw_operation.get("operation_id", "")).strip()
                if not operation_id or operation_id in seen:
                    continue
                classification = category or str(raw_operation.get("classification", "")).strip().lower()
                if classification not in {"required", "recommended"}:
                    classification = "needs_review"
                derived.append(
                    {
                        "operation_id": operation_id,
                        "action": str(raw_operation.get("action", operation_id)).strip(),
                        "category": classification,
                        "basis": basis,
                        "source_article_ids": [article_id] if article_id else [],
                    }
                )
                seen.add(operation_id)
    return tuple(derived)


def _require_message(message: str) -> str:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("chat message must be a non-empty string")
    return re.sub(r"\s+", " ", message.strip())


def _parse_vehicle(message: str) -> dict[str, Any]:
    match = _VEHICLE_PATTERN.search(message)
    if match is None:
        return {"status": "unmatched", "candidates": []}
    vehicle_text = message[match.start() :]
    stop = _first_operation_or_intent(vehicle_text)
    observation_text = vehicle_text[:stop] if stop is not None else vehicle_text
    try:
        observation = canonicalize_vehicle_observation(observation_text)
    except (TypeError, ValueError):
        return {"status": "needs_review", "raw": observation_text, "candidates": []}
    return {
        **observation.to_dict(),
        "status": "unresolved",
        "raw": observation_text,
    }


def _resolve_candidates(
    observation: Mapping[str, Any],
    candidates: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    if observation.get("status") in {"unmatched", "needs_review"}:
        return dict(observation)
    ranked: list[tuple[float, Mapping[str, Any], dict[str, Any]]] = []
    for candidate in candidates:
        try:
            candidate_observation = canonicalize_vehicle_observation(candidate).to_dict()
        except (TypeError, ValueError):
            continue
        if not _vehicle_compatible(observation, candidate_observation):
            continue
        score = float(candidate.get("confidence", 0.0))
        score += _specificity_score(observation, candidate_observation)
        ranked.append((score, candidate, candidate_observation))
    if not ranked:
        return {**dict(observation), "status": "unmatched", "candidates": []}
    ranked.sort(key=lambda item: (item[0], str(item[1].get("vehicle_id", ""))))
    options = [_candidate_option(candidate, candidate_observation) for _, candidate, candidate_observation in ranked]
    if len(ranked) > 1:
        return {
            **dict(observation),
            "status": "ambiguous",
            "candidates": options,
        }
    selected = _candidate_option(ranked[0][1], ranked[0][2])
    return {
        **dict(observation),
        "status": "matched",
        "selected_vehicle_id": selected.get("vehicle_id"),
        "selected_candidate_key": selected.get("candidate_key", selected.get("vehicle_id")),
        "candidates": options,
    }


def _candidate_option(candidate: Mapping[str, Any], observation: Mapping[str, Any]) -> dict[str, Any]:
    vehicle_id = str(candidate.get("vehicle_id", candidate.get("vehicle_key", ""))).strip()
    label = " ".join(
        str(value)
        for value in (
            observation.get("year"),
            observation.get("make"),
            observation.get("model"),
            observation.get("drivetrain"),
            f"{observation['engine_displacement_l']:.1f}L"
            if observation.get("engine_displacement_l") is not None
            else None,
        )
        if value
    )
    return {
        "vehicle_id": vehicle_id,
        "candidate_key": str(candidate.get("candidate_key", vehicle_id)),
        "confidence": float(candidate.get("confidence", 0.0)),
        "label": label,
    }


def _vehicle_compatible(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    for key in ("year", "make", "model", "region", "body_style", "trim", "drivetrain"):
        expected = left.get(key)
        actual = right.get(key)
        if expected is not None and actual is not None and str(expected).casefold() != str(actual).casefold():
            return False
    expected_engine = left.get("engine_displacement_l")
    actual_engine = right.get("engine_displacement_l")
    return (
        expected_engine is None
        or actual_engine is None
        or abs(float(expected_engine) - float(actual_engine)) < 0.0001
    )


def _specificity_score(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    score = 0.0
    for key in ("drivetrain", "engine_displacement_l", "trim"):
        if left.get(key) is not None and right.get(key) is not None:
            score += 1.0
    return score


def _parse_operations(message: str) -> list[dict[str, Any]]:
    matches = list(_COMPONENT_PATTERN.finditer(message))
    operations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in matches:
        alias = match.group(0).casefold()
        component = _COMPONENT_ALIASES[alias]
        if component in seen:
            continue
        action = _action_for_component(message, match.start(), match.end())
        operations.append(
            {
                "operation_id": f"{action}-{component.replace('_', '-')}",
                "action": action,
                "component": component,
                "status": "matched",
                "source": "deterministic",
            }
        )
        seen.add(component)
    return operations


def _action_for_component(message: str, start: int, end: int) -> str:
    window = message[max(0, start - 36) : min(len(message), end + 36)]
    if re.search(r"\b(inspect(?:ion)?|check|diagnos)\w*\b", window, re.IGNORECASE):
        return "inspect"
    if re.search(r"\b(bleed(?:ing)?|flush(?:ing)?|service|servicing)\b", window, re.IGNORECASE):
        return "service"
    return "replace"


def _advisory_proposal(
    client: "Mercury2Client",
    message: str,
    candidates: tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any]:
    prompt = json.dumps(
        {
            "message": message,
            "vehicle_candidates": [dict(candidate) for candidate in candidates],
            "allowed_components": list(_ALLOWED_COMPONENTS),
            "output": {
                "components": "array of allowed component names",
                "selected_candidate_key": "one supplied candidate key or null",
            },
        },
        sort_keys=True,
    )
    response = client.complete_json(prompt)
    return response if isinstance(response, Mapping) else {}


def _operations_from_proposal(proposal: Mapping[str, Any]) -> list[dict[str, Any]]:
    proposed = proposal.get("components", ())
    if not isinstance(proposed, Iterable) or isinstance(proposed, (str, bytes, Mapping)):
        return []
    operations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_component in proposed:
        component = str(raw_component).strip().casefold()
        if component not in _ALLOWED_COMPONENTS or component in seen:
            continue
        operations.append(
            {
                "operation_id": f"replace-{component.replace('_', '-')}",
                "action": "replace",
                "component": component,
                "status": "needs_review",
                "source": "mercury2_advisory",
            }
        )
        seen.add(component)
    return operations


def _apply_advisory_vehicle_selection(
    vehicle: Mapping[str, Any],
    proposal: Mapping[str, Any],
    candidates: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    selected_key = str(proposal.get("selected_candidate_key", "")).strip()
    if not selected_key:
        return dict(vehicle)
    valid = {
        str(candidate.get("candidate_key", candidate.get("vehicle_id", ""))).strip(): candidate
        for candidate in candidates
    }
    selected = valid.get(selected_key)
    if selected is None:
        return {**dict(vehicle), "status": "needs_review"}
    selected_id = str(selected.get("vehicle_id", selected.get("vehicle_key", ""))).strip()
    return {
        **dict(vehicle),
        "status": "matched",
        "selected_vehicle_id": selected_id,
        "selected_candidate_key": selected_key,
    }


def _first_operation_or_intent(value: str) -> int | None:
    positions = [match.start() for match in _COMPONENT_PATTERN.finditer(value)]
    positions.extend(match.start() for match in _ACTION_PATTERN.finditer(value))
    positions.extend(match.start() for match in _INTENT_STOP_PATTERN.finditer(value))
    return min(positions) if positions else None


def _vehicle_clarification(vehicle: Mapping[str, Any]) -> str:
    model = str(vehicle.get("model", "vehicle")).strip()
    return f"Which {model} configuration should I use?"


def _contains_intent(value: str, phrases: tuple[str, ...]) -> bool:
    lowered = value.casefold()
    return any(phrase in lowered for phrase in phrases)


__all__ = [
    "ChatIntent",
    "derive_supporting_operations",
    "interpret_chat_message",
]
