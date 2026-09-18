"""Provider-neutral vehicle identity resolution for AutoAPITwo/ACES records."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .vehicle_identity import CanonicalVehicleObservation, canonicalize_vehicle_observation


_ACES_NAME_KEYS = {
    "aces_vehicle": ("acesVehicleNames", "aces_vehicle_names"),
    "aces_engine": ("acesEngineConfigNames", "aces_engine_config_names"),
    "aces_vec": (
        "acesVehicleEngineConfigNames",
        "acesVehicleEngineConfigurationNames",
        "acesVecNames",
        "aces_vec_names",
    ),
}


@dataclass(frozen=True)
class AutoAPITwoResolution:
    status: str
    observation: CanonicalVehicleObservation
    candidates: tuple[dict[str, Any], ...]
    selected: dict[str, Any] | None
    reason: str | None = None


def normalize_autoapitwo_candidate(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Translate one provider row without discarding provider identifiers."""

    provider_car_id = str(raw.get("id") or raw.get("carid") or "").strip()
    if not provider_car_id.isdigit():
        raise ValueError("AutoAPITwo candidate requires a numeric car id")

    observation = _canonical_provider_observation(raw)
    mappings = [
        {
            "provider": "autoapitwo",
            "entity_type": "car",
            "provider_id": provider_car_id,
            "provider_label": _text(raw.get("description")) or provider_car_id,
            "raw_mapping": dict(raw),
        }
    ]
    for entity_type, keys in _ACES_NAME_KEYS.items():
        for value in _first_list(raw, keys):
            parsed = _parse_external_name(value)
            if parsed is None:
                continue
            provider_id, label = parsed
            mappings.append(
                {
                    "provider": "autoapitwo",
                    "entity_type": entity_type,
                    "provider_id": provider_id,
                    "provider_label": label,
                    "raw_mapping": {"source": value, "source_car_id": provider_car_id},
                }
            )

    return {
        "candidate_key": f"autoapitwo:car:{provider_car_id}",
        "provider": "autoapitwo",
        "provider_car_id": provider_car_id,
        "observation": observation,
        "vehicle": observation.to_dict(),
        "provider_mappings": _unique_mappings(mappings),
        "provider_label": _text(raw.get("description")) or provider_car_id,
        "raw": dict(raw),
    }


def resolve_autoapitwo_vehicle(
    requested: CanonicalVehicleObservation | Mapping[str, Any] | str,
    rows: list[Mapping[str, Any]],
) -> AutoAPITwoResolution:
    """Return a safe match, ambiguity, or miss for a bounded provider result set."""

    observation = (
        requested
        if isinstance(requested, CanonicalVehicleObservation)
        else canonicalize_vehicle_observation(requested)
    )
    candidates: list[dict[str, Any]] = []
    for raw in rows:
        try:
            candidate = normalize_autoapitwo_candidate(raw)
        except (TypeError, ValueError):
            continue
        score = _score(observation, candidate["observation"])
        if score is None:
            continue
        candidate["score"] = score
        candidates.append(candidate)

    candidates.sort(key=lambda item: (-item["score"], item["candidate_key"]))
    if not candidates:
        return AutoAPITwoResolution("unmatched", observation, (), None, "no_compatible_provider_candidate")
    top = candidates[0]
    tied = [candidate for candidate in candidates if candidate["score"] == top["score"]]
    if len(tied) > 1:
        return AutoAPITwoResolution("ambiguous", observation, tuple(candidates), None, "multiple_top_provider_candidates")
    if top["score"] < 80:
        return AutoAPITwoResolution("unmatched", observation, tuple(candidates), None, "provider_match_below_threshold")
    if len(candidates) > 1 and top["score"] - candidates[1]["score"] < 8:
        return AutoAPITwoResolution("ambiguous", observation, tuple(candidates), None, "provider_match_margin_too_small")
    return AutoAPITwoResolution("matched", observation, tuple(candidates), top)


def _canonical_provider_observation(raw: Mapping[str, Any]) -> CanonicalVehicleObservation:
    description = _text(raw.get("description"))
    model_text = _text(raw.get("model"))
    aces_vehicle_labels = [
        parsed[1]
        for value in _first_list(raw, _ACES_NAME_KEYS["aces_vehicle"])
        if (parsed := _parse_external_name(value)) is not None
    ]
    model_source = " ".join((model_text, description, *aces_vehicle_labels))
    model = _canonical_model(model_source)
    make = _canonical_make(raw.get("make"), model_source)
    drivetrain = _match_drive(model_source)
    body_style = _match_body(model_source)
    engine = _text(raw.get("engine")) or description
    region = "US"
    if re.search(r"\bCAN(?:ADA)?\b", " ".join(aces_vehicle_labels), re.IGNORECASE) and not re.search(
        r"\bUSA\b", " ".join(aces_vehicle_labels), re.IGNORECASE
    ):
        region = "CA"
    return canonicalize_vehicle_observation(
        {
            "year": raw.get("year"),
            "make": make,
            "model": model,
            "region": region,
            "body_style": body_style,
            "drivetrain": drivetrain,
            "engine": engine,
        }
    )


def _score(
    requested: CanonicalVehicleObservation,
    candidate: CanonicalVehicleObservation,
) -> float | None:
    fields = (
        ("year", 30),
        ("make", 20),
        ("model", 25),
        ("drivetrain", 12),
        ("engine_displacement_l", 10),
        ("body_style", 3),
    )
    total = 0.0
    for name, weight in fields:
        expected = getattr(requested, name)
        actual = getattr(candidate, name)
        if expected is None:
            continue
        if actual is None or not _same_dimension(expected, actual):
            return None
        total += weight
    if requested.region and candidate.region and requested.region != candidate.region:
        return None
    return total


def _same_dimension(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) < 0.01
    return str(left).casefold() == str(right).casefold()


def _canonical_make(raw_make: Any, text: str) -> str:
    value = _text(raw_make)
    if re.search(r"\b(?:chevy|chevrolet)\b", value, re.IGNORECASE) or re.search(
        r"\b(?:chevy|chevrolet)\b", text, re.IGNORECASE
    ):
        return "Chevrolet"
    return value.removesuffix(" Truck").strip() or "Unknown"


def _canonical_model(text: str) -> str:
    silverado = re.search(r"\bSilverado\s+1500\b", text, re.IGNORECASE)
    if silverado:
        return "Silverado 1500"
    rav4 = re.search(r"\bRAV\s*4\b", text, re.IGNORECASE)
    if rav4:
        return "RAV4"
    model = re.split(r"\s+(?:(?:2|4)-Door|2WD|4WD)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    model = re.sub(r"^(?:\d{4}|\d{2})\s+", "", model).strip()
    model = re.sub(r"\b(?:For|A|An|The|Chevy|Chevrolet|Truck)\b", " ", model, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", model).strip() or "Unknown"


def _match_drive(text: str) -> str | None:
    match = re.search(r"\b(2WD|4WD|AWD|FWD|RWD)\b", text, re.IGNORECASE)
    return match.group(1).upper() if match else None


def _match_body(text: str) -> str | None:
    match = re.search(r"\b(2|4)-Door\b", text, re.IGNORECASE)
    return f"{match.group(1)}-door" if match else None


def _parse_external_name(value: Any) -> tuple[str, str] | None:
    match = re.match(r"\s*(\d+)\s*:\s*(.+?)\s*$", str(value or ""))
    return (match.group(1), match.group(2)) if match else None


def _first_list(raw: Mapping[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, list):
            return value
    return []


def _unique_mappings(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result = []
    for value in values:
        key = (value["entity_type"], value["provider_id"])
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


__all__ = [
    "AutoAPITwoResolution",
    "normalize_autoapitwo_candidate",
    "resolve_autoapitwo_vehicle",
]
