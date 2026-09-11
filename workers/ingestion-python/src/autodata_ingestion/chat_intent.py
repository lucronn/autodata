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
from typing import Any, Iterable, Mapping

from .mercury2 import Mercury2Client
from .vehicle_identity import canonicalize_vehicle_observation


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
    r"(?P<model>RAV\s*[- ]?4|[A-Za-z0-9][A-Za-z0-9-]*(?:\s+\d{2,4})?)",
    re.IGNORECASE,
)
_ACTION_PATTERN = re.compile(
    r"\b(replac(?:e|ement|ment)|r\s*&?\s*r|service|servicing|inspect(?:ion)?|bleed(?:ing)?|flush(?:ing)?|install(?:ation)?|repair|fix|adjust(?:ment)?|diagnos(?:e|is|tic)?|check)\b",
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
    mercury_client: Mercury2Client | None = None,
) -> ChatIntent:
    """Interpret one chat message without allowing an LLM to become authoritative."""

    normalized_message = _require_message(message)
    deterministic_vehicle = _parse_vehicle(normalized_message)
    operations = _parse_operations(normalized_message)
    vehicle = _resolve_candidates(deterministic_vehicle, vehicle_candidates)

    advisory_error = False
    needs_model = not operations or vehicle.get("status") in {"unmatched", "needs_review"}
    if needs_model and mercury_client is not None:
        try:
            proposal = _advisory_proposal(
                mercury_client,
                normalized_message,
                vehicle_candidates,
            )
        except Exception:
            proposal = {}
            advisory_error = True
        if not operations:
            operations = (
                [_advisory_review_operation()]
                if advisory_error
                else _operations_from_proposal(proposal)
            )
        vehicle = _apply_advisory_vehicle_selection(vehicle, proposal, vehicle_candidates)
        if _proposal_has_unknown_component(proposal):
            vehicle = {**vehicle, "status": "needs_review"}

    if vehicle.get("status") == "ambiguous":
        clarification = _vehicle_clarification(vehicle)
    elif not operations:
        clarification = "Which component needs service?"
    elif vehicle.get("status") in {"unmatched", "needs_review"}:
        clarification = "Which vehicle configuration should I use?"
    else:
        clarification = None

    return ChatIntent(
        vehicle_observation=vehicle,
        requested_operations=tuple(operations),
        quote_requested=_contains_intent(
            normalized_message,
            ("quote", "estimate", "price", "pricing", "cost", "how much"),
        ),
        procedure_requested=_contains_intent(
            normalized_message,
            ("procedure", "procedures", "repair steps", "steps", "instructions", "how to"),
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
    by_operation_id: dict[str, dict[str, Any]] = {}
    for article in articles:
        article_id = str(
            article.get("article_id")
            or article.get("articleId")
            or article.get("source_article_id")
            or article.get("id")
            or ""
        ).strip()
        for field, category, basis in (
            ("supporting_operations", None, "source_article"),
            ("trusted_rules", None, "trusted_rule"),
            ("model_suggestions", "needs_review", "model_advisory"),
            ("supportingOperations", None, "source_article"),
            ("trustedRules", None, "trusted_rule"),
        ):
            values = article.get(field, ())
            if not isinstance(values, Iterable) or isinstance(values, (str, bytes, Mapping)):
                continue
            for raw_operation in values:
                if not isinstance(raw_operation, Mapping):
                    continue
                operation_id = str(
                    raw_operation.get("operation_id")
                    or raw_operation.get("operationId")
                    or raw_operation.get("id")
                    or ""
                ).strip()
                if not operation_id or operation_id in requested_ids:
                    continue
                classification = category or str(
                    raw_operation.get("classification")
                    or raw_operation.get("category")
                    or raw_operation.get("operation_category")
                    or ""
                ).strip().lower()
                if classification not in {"required", "recommended"}:
                    if raw_operation.get("required") is True:
                        classification = "required"
                    elif raw_operation.get("recommended") is True:
                        classification = "recommended"
                if classification not in {"required", "recommended"}:
                    classification = "needs_review"
                operation_basis = basis
                source_metadata = article.get("source_metadata")
                if (
                    classification == "required"
                    and operation_basis == "source_article"
                    and isinstance(source_metadata, Mapping)
                    and source_metadata.get("trusted") is False
                ):
                    classification = "recommended"
                origin = str(
                    raw_operation.get("origin")
                    or raw_operation.get("source")
                    or ""
                ).casefold()
                if origin in {"mercury2", "mercury-2", "model", "llm"}:
                    classification = "needs_review"
                    operation_basis = "model_advisory"
                output = {
                    "operation_id": operation_id,
                    "action": str(
                        raw_operation.get("action")
                        or raw_operation.get("name")
                        or raw_operation.get("title")
                        or operation_id
                    ).strip(),
                    "category": classification,
                    "basis": operation_basis,
                    "source_article_ids": [article_id] if article_id else [],
                }
                evidence_ids = raw_operation.get("evidence_ids") or raw_operation.get("evidenceIds")
                if isinstance(evidence_ids, str):
                    evidence_ids = [evidence_ids]
                if isinstance(evidence_ids, (list, tuple, set)):
                    output["evidence_ids"] = sorted(
                        {str(evidence_id) for evidence_id in evidence_ids if str(evidence_id).strip()}
                    )
                existing = by_operation_id.get(operation_id)
                if existing is None:
                    by_operation_id[operation_id] = output
                    derived.append(output)
                    continue
                existing["source_article_ids"] = sorted(
                    set(existing.get("source_article_ids", ()))
                    | set(output.get("source_article_ids", ()))
                )
                existing["evidence_ids"] = sorted(
                    set(existing.get("evidence_ids", ()))
                    | set(output.get("evidence_ids", ()))
                )
                if _classification_rank(output["category"]) > _classification_rank(existing["category"]):
                    existing["category"] = output["category"]
                    existing["basis"] = output["basis"]
    return tuple(derived)


def _require_message(message: str) -> str:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("chat message must be a non-empty string")
    return re.sub(r"\s+", " ", message.strip())


def _parse_vehicle(message: str) -> dict[str, Any]:
    match = _VEHICLE_PATTERN.search(message)
    later_year_match = re.search(
        r"(?P<make>[A-Za-z][A-Za-z-]*)\s+"
        r"(?P<model>RAV\s*[- ]?4|[A-Za-z0-9][A-Za-z0-9-]*(?:\s+\d{2,4})?)\s+"
        r"(?P<year>\d{2}|(?:19|20)\d{2})\b",
        message,
        re.IGNORECASE,
    )
    if later_year_match is not None and (match is None or later_year_match.start() < match.start()):
        match = None
    if match is None:
        # ``vehicle_identity`` already supports a later year.  This bounded
        # fallback lets the chat form use that canonicalization too.
        later_year = later_year_match
        if later_year is None:
            return {"status": "unmatched", "candidates": []}
        vehicle_text = message[later_year.start():]
        stop = _first_operation_or_intent(vehicle_text)
        observation_text = vehicle_text[:stop] if stop is not None else vehicle_text
        try:
            observation = canonicalize_vehicle_observation(observation_text)
        except (TypeError, ValueError):
            return {"status": "needs_review", "raw": observation_text, "candidates": []}
        parsed = observation.to_dict()
        parsed.update(_dimensions_from_message(message, parsed))
        parsed["engine"] = parsed.get("engine_displacement_l")
        return {**parsed, "status": "unresolved", "raw": observation_text}
    vehicle_text = message[match.start() :]
    stop = _first_operation_or_intent(vehicle_text)
    observation_text = vehicle_text[:stop] if stop is not None else vehicle_text
    try:
        observation = canonicalize_vehicle_observation(observation_text)
    except (TypeError, ValueError):
        return {"status": "needs_review", "raw": observation_text, "candidates": []}
    parsed = observation.to_dict()
    parsed.update(_dimensions_from_message(message, parsed))
    parsed["engine"] = parsed.get("engine_displacement_l")
    return {
        **parsed,
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
        if not candidates and all(
            observation.get(key) is not None for key in ("year", "make", "model")
        ):
            return {
                **dict(observation),
                "status": "matched",
                "selected_vehicle_id": None,
                "selected_candidate_key": None,
                "candidates": [],
            }
        return {**dict(observation), "status": "unmatched", "candidates": []}
    ranked.sort(key=lambda item: _candidate_sort_key(item[1], item[2]))
    options = [
        _candidate_option(candidate, candidate_observation, option_number=index)
        for index, (_, candidate, candidate_observation) in enumerate(ranked, start=1)
    ]
    if len(ranked) > 1:
        return {
            **dict(observation),
            "status": "ambiguous",
            "candidates": options,
        }
    selected = _candidate_option(ranked[0][1], ranked[0][2], option_number=1)
    return {
        **dict(observation),
        "status": "matched",
        "selected_vehicle_id": selected.get("vehicle_id"),
        "selected_candidate_key": selected.get("candidate_key", selected.get("vehicle_id")),
        "candidates": options,
    }


def _dimensions_from_message(
    message: str,
    parsed: Mapping[str, Any],
) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    if parsed.get("engine_displacement_l") is None:
        engine = re.search(
            r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:l|lt|liter|litre)\b",
            message,
            re.IGNORECASE,
        )
        if engine is not None:
            dimensions["engine_displacement_l"] = float(engine.group(1))
    if parsed.get("drivetrain") is None:
        for pattern, drivetrain in (
            (r"\b4\s*(?:-\s*)?wheel\s+drive\b", "4WD"),
            (r"\ball\s*(?:-\s*)?wheel\s+drive\b", "AWD"),
            (r"\bfront\s*(?:-\s*)?wheel\s+drive\b", "FWD"),
            (r"\brear\s*(?:-\s*)?wheel\s+drive\b", "RWD"),
        ):
            if re.search(pattern, message, re.IGNORECASE):
                dimensions["drivetrain"] = drivetrain
                break
    return dimensions


def _candidate_option(
    candidate: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    option_number: int,
) -> dict[str, Any]:
    vehicle_id = str(candidate.get("vehicle_id", candidate.get("vehicle_key", ""))).strip()
    dimensions = (
        ("region", observation.get("region")),
        ("body", observation.get("body_style")),
        ("trim", observation.get("trim")),
        ("drive", observation.get("drivetrain")),
        (
            "engine",
            f"{observation['engine_displacement_l']:.1f}L"
            if observation.get("engine_displacement_l") is not None
            else None,
        ),
    )
    identity = " ".join(
        str(value)
        for value in (observation.get("year"), observation.get("make"), observation.get("model"))
        if value
    )
    qualifiers = " ".join(f"{name}={value}" for name, value in dimensions if value)
    return {
        "option_number": option_number,
        "vehicle_id": vehicle_id,
        "candidate_key": str(candidate.get("candidate_key", vehicle_id)),
        "confidence": float(candidate.get("confidence", 0.0)),
        "label": f"{identity} {qualifiers}".strip(),
        "year": observation.get("year"),
        "make": observation.get("make"),
        "model": observation.get("model"),
        "region": observation.get("region"),
        "body_style": observation.get("body_style"),
        "trim": observation.get("trim"),
        "drivetrain": observation.get("drivetrain"),
        "engine_displacement_l": observation.get("engine_displacement_l"),
    }


def _candidate_sort_key(
    candidate: Mapping[str, Any], observation: Mapping[str, Any]
) -> tuple[str, ...]:
    return tuple(
        str(observation.get(key) or "").casefold()
        for key in (
            "year",
            "make",
            "model",
            "region",
            "body_style",
            "trim",
            "drivetrain",
            "engine_displacement_l",
        )
    ) + (str(candidate.get("vehicle_id") or candidate.get("vehicle_key") or "").casefold(),)


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
    # Keep offsets stable while accepting hyphenated component spellings.
    searchable = re.sub(r"[-_/]", " ", message)
    matches = list(_COMPONENT_PATTERN.finditer(searchable))
    operations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, match in enumerate(matches):
        alias = match.group(0).casefold()
        component = _COMPONENT_ALIASES[alias]
        previous_end = matches[index - 1].end() if index else 0
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(message)
        action = _action_for_component(
            message,
            match.start(),
            match.end(),
            left_boundary=previous_end,
            right_boundary=next_start,
        )
        if (action, component) in seen:
            continue
        operations.append(
            {
                "operation_id": f"{action}-{component.replace('_', '-')}",
                "action": action,
                "component": component,
                "status": "matched",
                "source": "deterministic",
            }
        )
        seen.add((action, component))
    return operations


def _action_for_component(
    message: str,
    start: int,
    end: int,
    *,
    left_boundary: int = 0,
    right_boundary: int | None = None,
) -> str:
    left = max(0, start - 36, left_boundary)
    right = min(len(message), end + 36)
    if right_boundary is not None:
        right = min(right, right_boundary)
    window = message[left:right]
    component_offset = start - left
    action_matches = list(_ACTION_PATTERN.finditer(window))
    if not action_matches:
        return "replace"
    nearest = min(
        action_matches,
        key=lambda match: abs(((match.start() + match.end()) / 2) - component_offset),
    )
    return _canonical_action(nearest.group(0))


def _canonical_action(value: str) -> str:
    lowered = value.casefold()
    if re.search(r"inspect|check|diagnos", lowered):
        return "inspect"
    if "bleed" in lowered:
        return "bleed"
    if "flush" in lowered:
        return "flush"
    if "install" in lowered:
        return "install"
    if re.search(r"repair|fix", lowered):
        return "repair"
    if "adjust" in lowered:
        return "adjust"
    if "service" in lowered:
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
            "vehicle_candidates": [_candidate_prompt(candidate) for candidate in candidates],
            "allowed_components": list(_ALLOWED_COMPONENTS),
            "allowed_candidate_keys": _allowed_candidate_keys(candidates),
            "response_format": "json_object",
            "output": {
                "components": "array of allowed component names",
                "selected_candidate_key": "one supplied candidate key or null",
            },
        },
        sort_keys=True,
    )
    response = client.complete_json(prompt)
    if not isinstance(response, Mapping):
        raise ValueError("Mercury-2 chat response must be an object")
    if not isinstance(response.get("components"), list):
        raise ValueError("Mercury-2 chat response components must be an array")
    selected_key = response.get("selected_candidate_key")
    if selected_key is not None and not isinstance(selected_key, str):
        raise ValueError("Mercury-2 selected candidate key must be a string or null")
    return response


def _operations_from_proposal(proposal: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(proposal, Mapping):
        raise ValueError("Mercury-2 chat proposal must be an object")
    proposed = proposal.get("components")
    if not isinstance(proposed, list):
        raise ValueError("Mercury-2 chat proposal components must be an array")
    operations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw_component in enumerate(proposed):
        raw_action = "replace"
        if isinstance(raw_component, Mapping):
            raw_action = str(raw_component.get("action") or raw_component.get("verb") or "replace")
            raw_component = raw_component.get("component") or raw_component.get("component_id") or ""
        elif not isinstance(raw_component, str):
            raise ValueError(f"Mercury-2 component {index} must be a string or object")
        raw_component_text = str(raw_component).strip()
        if not raw_component_text:
            raise ValueError(f"Mercury-2 component {index} must not be empty")
        component_lookup = raw_component_text.casefold().replace("-", " ").replace("_", " ")
        component = _COMPONENT_ALIASES.get(component_lookup, component_lookup.replace(" ", "_"))
        action = _canonical_action(raw_action)
        if component not in _ALLOWED_COMPONENTS:
            slug = re.sub(r"[^a-z0-9]+", "-", raw_component_text.casefold()).strip("-") or str(index + 1)
            operations.append(
                {
                    "operation_id": f"review-unknown-{slug}",
                    "action": "review",
                    "component": raw_component_text,
                    "status": "needs_review",
                    "source": "mercury2_advisory",
                    "reason": "component_not_allowlisted",
                    "raw_component": raw_component_text,
                }
            )
            continue
        if (action, component) in seen:
            continue
        operations.append(
            {
                "operation_id": f"{action}-{component.replace('_', '-')}",
                "action": action,
                "component": component,
                "status": "needs_review",
                "source": "mercury2_advisory",
            }
        )
        seen.add((action, component))
    return operations


def _advisory_review_operation() -> dict[str, Any]:
    return {
        "operation_id": "review-chat-intent",
        "action": "review",
        "component": None,
        "status": "needs_review",
        "source": "mercury2_unavailable",
        "reason": "advisory_response_unavailable_or_invalid",
    }


def _apply_advisory_vehicle_selection(
    vehicle: Mapping[str, Any],
    proposal: Mapping[str, Any],
    candidates: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    selected_key = str(
        proposal.get("selected_candidate_key")
        or proposal.get("vehicle_candidate")
        or ""
    ).strip()
    if not selected_key:
        return dict(vehicle)
    valid: dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        for key in (
            candidate.get("candidate_key"),
            candidate.get("vehicle_id"),
            candidate.get("vehicle_key"),
        ):
            if key:
                valid[str(key).strip()] = candidate
        try:
            identity = canonicalize_vehicle_observation(candidate)
            from .vehicle_identity import build_vehicle_configuration
            valid[build_vehicle_configuration(identity).configuration_key] = candidate
        except (TypeError, ValueError):
            continue
    selected = valid.get(selected_key)
    if selected is None:
        return {**dict(vehicle), "status": "needs_review"}
    if vehicle.get("status") == "ambiguous":
        # Mercury may point at an option for UI ranking, but a user must still
        # make the selection when more than one compatible vehicle remains.
        return {**dict(vehicle), "advisory_candidate_key": selected_key}
    selected_id = str(selected.get("vehicle_id", selected.get("vehicle_key", ""))).strip()
    canonical = canonicalize_vehicle_observation(selected).to_dict()
    return {
        **dict(vehicle),
        **canonical,
        "status": "matched",
        "selected_vehicle_id": selected_id,
        "selected_candidate_key": selected_key,
    }


def _candidate_prompt(candidate: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(candidate)
    output.setdefault("candidate_key", _candidate_key(candidate))
    return output


def _candidate_key(candidate: Mapping[str, Any]) -> str:
    explicit = candidate.get("candidate_key")
    if explicit:
        return str(explicit).strip()
    for key in ("vehicle_id", "vehicle_key"):
        if candidate.get(key):
            return str(candidate[key]).strip()
    try:
        identity = canonicalize_vehicle_observation(candidate)
        from .vehicle_identity import build_vehicle_configuration
        return build_vehicle_configuration(identity).configuration_key
    except (TypeError, ValueError):
        return ""


def _first_operation_or_intent(value: str) -> int | None:
    searchable = re.sub(r"[-_/]", " ", value)
    positions = [match.start() for match in _COMPONENT_PATTERN.finditer(searchable)]
    positions.extend(match.start() for match in _ACTION_PATTERN.finditer(value))
    positions.extend(match.start() for match in _INTENT_STOP_PATTERN.finditer(value))
    return min(positions) if positions else None


def _vehicle_clarification(vehicle: Mapping[str, Any]) -> str:
    model = str(vehicle.get("model", "vehicle")).strip()
    return f"Which {model} configuration should I use?"


def _contains_intent(value: str, phrases: tuple[str, ...]) -> bool:
    lowered = value.casefold()
    for phrase in phrases:
        if phrase not in lowered:
            continue
        if phrase in {"quote", "estimate", "price", "pricing", "cost"} and re.search(
            rf"\bno\s+(?:a\s+)?{re.escape(phrase)}\b", lowered
        ):
            continue
        return True
    return False


def _allowed_candidate_keys(candidates: tuple[Mapping[str, Any], ...]) -> list[str]:
    keys: set[str] = set()
    for candidate in candidates:
        for key in (
            candidate.get("candidate_key"),
            candidate.get("vehicle_id"),
            candidate.get("vehicle_key"),
        ):
            if key:
                keys.add(str(key).strip())
        try:
            identity = canonicalize_vehicle_observation(candidate)
            from .vehicle_identity import build_vehicle_configuration
            keys.add(build_vehicle_configuration(identity).configuration_key)
        except (TypeError, ValueError):
            continue
    return sorted(keys)


def _proposal_has_unknown_component(proposal: Mapping[str, Any]) -> bool:
    proposed = proposal.get("components", ())
    if not isinstance(proposed, list):
        return True
    for raw_component in proposed:
        if isinstance(raw_component, Mapping):
            raw_component = raw_component.get("component") or raw_component.get("component_id")
        component_text = str(raw_component or "").strip().casefold()
        component_lookup = component_text.replace("-", " ").replace("_", " ")
        component = _COMPONENT_ALIASES.get(component_lookup, component_lookup.replace(" ", "_"))
        if component_text and component not in _ALLOWED_COMPONENTS:
            return True
    return False


def _classification_rank(value: str) -> int:
    return {"needs_review": 0, "recommended": 1, "required": 2}.get(value, 0)


__all__ = [
    "ChatIntent",
    "derive_supporting_operations",
    "interpret_chat_message",
]
