"""Canonical vehicle identity helpers for ingestion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping


_MAKE_ALIASES = {
    "chevy": "Chevrolet",
    "chevrolet": "Chevrolet",
}
# Some source lists omit the make because the model is a recognizable branded
# name. Keep this deliberately small and high-confidence; unknown model-first
# strings must still provide a make or remain reviewable.
_MODEL_FIRST_MAKE_ALIASES = {
    "silverado": "Chevrolet",
}
_MODEL_ALIASES = {
    "rav 4": "RAV4",
    "rav4": "RAV4",
}
_DRIVETRAIN_ALIASES = {
    "2wd": "2WD",
    "4x2": "2WD",
    "4wd": "4WD",
    "4x4": "4WD",
    "awd": "AWD",
    "fwd": "FWD",
    "rwd": "RWD",
}
_KNOWN_TRIMS = {"lt", "ltz"}


@dataclass(frozen=True)
class VehicleAlias:
    kind: str
    raw: str
    canonical: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalVehicleObservation:
    year: int
    make: str
    model: str
    region: str | None
    body_style: str | None
    trim: str | None
    drivetrain: str | None
    engine_displacement_l: float | None
    aliases: tuple[VehicleAlias, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["aliases"] = [alias.to_dict() for alias in self.aliases]
        return output


@dataclass(frozen=True)
class VehicleBaseIdentity:
    vehicle_key: str
    year: int
    make: str
    model: str
    region: str | None
    body_style: str | None
    drivetrain: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VehicleConfiguration:
    configuration_key: str
    vehicle_key: str
    trim: str | None
    drivetrain: str | None
    engine_displacement_l: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VehicleMatchCandidate:
    candidate_key: str
    score: float
    vehicle_key: str
    configuration_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VehicleReviewState:
    status: str
    ambiguous: bool
    selected_candidate_key: str | None
    reason: str | None
    candidates: tuple[VehicleMatchCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return output


def canonicalize_vehicle_observation(value: Mapping[str, Any] | str) -> CanonicalVehicleObservation:
    if isinstance(value, str):
        return _canonicalize_text_observation(value)
    if isinstance(value, Mapping):
        return _canonicalize_mapping_observation(value)
    raise TypeError("vehicle observation must be a mapping or string")


def build_base_identity(observation: CanonicalVehicleObservation) -> VehicleBaseIdentity:
    return VehicleBaseIdentity(
        vehicle_key=_vehicle_key(
            observation.make,
            observation.model,
            observation.year,
            observation.region,
            observation.body_style,
            observation.drivetrain,
        ),
        year=observation.year,
        make=observation.make,
        model=observation.model,
        region=observation.region,
        body_style=observation.body_style,
        drivetrain=observation.drivetrain,
    )


def build_vehicle_configuration(observation: CanonicalVehicleObservation) -> VehicleConfiguration:
    base = build_base_identity(observation)
    return VehicleConfiguration(
        configuration_key=_configuration_key(
            base.vehicle_key,
            observation.trim,
            observation.engine_displacement_l,
        ),
        vehicle_key=base.vehicle_key,
        trim=observation.trim,
        drivetrain=observation.drivetrain,
        engine_displacement_l=observation.engine_displacement_l,
    )


def build_vehicle_aliases(observation: CanonicalVehicleObservation) -> tuple[VehicleAlias, ...]:
    return observation.aliases


def review_vehicle_candidates(
    observation: CanonicalVehicleObservation,
    candidates: list[Mapping[str, Any] | str],
) -> VehicleReviewState:
    scored: list[VehicleMatchCandidate] = []
    for candidate in candidates:
        candidate_observation = canonicalize_vehicle_observation(candidate)
        base = build_base_identity(candidate_observation)
        configuration = build_vehicle_configuration(candidate_observation)
        scored.append(
            VehicleMatchCandidate(
                candidate_key=configuration.configuration_key,
                score=_score_candidate(observation, candidate_observation),
                vehicle_key=base.vehicle_key,
                configuration_key=configuration.configuration_key,
            )
        )
    ranked = tuple(sorted(scored, key=lambda item: (-item.score, item.candidate_key)))
    if not ranked or ranked[0].score <= 0:
        return VehicleReviewState("unmatched", False, None, "no_candidate_match", ranked)
    top_score = ranked[0].score
    top_candidates = [candidate for candidate in ranked if candidate.score == top_score]
    if len(top_candidates) > 1:
        return VehicleReviewState("ambiguous", True, None, "multiple_top_candidates", ranked)
    return VehicleReviewState("matched", False, ranked[0].candidate_key, None, ranked)


def _canonicalize_mapping_observation(value: Mapping[str, Any]) -> CanonicalVehicleObservation:
    aliases: list[VehicleAlias] = []
    year = _normalize_year(_first_non_empty(value.get("year"), value.get("model_year"), value.get("modelYear")))
    make = _normalize_make(
        _first_non_empty(value.get("make"), value.get("makeName"), value.get("vehicleMake")),
        aliases,
    )
    model = _normalize_model(
        _first_non_empty(value.get("model"), value.get("modelName"), value.get("vehicleModel"))
    )
    region = _normalize_region(value.get("region", value.get("market")))
    body_style = _normalize_body_style(
        _first_non_empty(value.get("body_style"), value.get("bodyStyle"))
    )
    trim = _normalize_trim(value.get("trim"))
    drivetrain = _normalize_drivetrain(
        _first_non_empty(value.get("drivetrain"), value.get("driveType")), aliases
    )
    engine = _normalize_engine(
        _first_non_empty(
            value.get("engine"),
            value.get("engine_displacement_l"),
            value.get("engineDisplacementL"),
            value.get("engineName"),
        ),
        aliases,
    )
    return CanonicalVehicleObservation(
        year,
        make,
        model,
        region,
        body_style,
        trim,
        drivetrain,
        engine,
        tuple(aliases),
    )


def _canonicalize_text_observation(value: str) -> CanonicalVehicleObservation:
    normalized_value = value.casefold()
    for phrase, canonical in (
        (r"\b4\s*(?:-\s*)?wheel\s+drive\b", "4wd"),
        (r"\ball\s*(?:-\s*)?wheel\s+drive\b", "awd"),
        (r"\bfront\s*(?:-\s*)?wheel\s+drive\b", "fwd"),
        (r"\brear\s*(?:-\s*)?wheel\s+drive\b", "rwd"),
    ):
        normalized_value = re.sub(phrase, canonical, normalized_value)
    normalized_text = re.sub(
        r"(\d+(?:\.\d+)?)\s+(l(?:t|iter|itre)?)\b",
        r"\1\2",
        normalized_value,
    )
    tokens = re.findall(r"[a-z0-9.]+", normalized_text)
    year_indexes = [
        index for index, token in enumerate(tokens) if _is_valid_year_token(token)
    ]
    if len(year_indexes) != 1:
        raise ValueError("vehicle text observation requires exactly one year")
    year_index = year_indexes[0]
    year = _normalize_year(tokens[year_index])
    tokens.pop(year_index)
    if len(tokens) < 2:
        raise ValueError("vehicle text observation requires make and model")
    aliases: list[VehicleAlias] = []
    model_tokens: list[str] = []
    model_first_make = _MODEL_FIRST_MAKE_ALIASES.get(tokens[0])
    if model_first_make is not None:
        make = model_first_make
        model_tokens.append(tokens.pop(0))
        aliases.append(VehicleAlias("make", f"model:{model_tokens[0]}", make))
    else:
        make = _normalize_make(tokens.pop(0), aliases)
    trim = None
    drivetrain = None
    engine = None
    for token in tokens:
        if token in _KNOWN_TRIMS and trim is None:
            trim = token.upper()
            continue
        canonical_drivetrain = _DRIVETRAIN_ALIASES.get(token)
        if canonical_drivetrain is not None and drivetrain is None:
            if token != canonical_drivetrain.casefold():
                aliases.append(VehicleAlias("drivetrain", token.upper() if "x" not in token else token, canonical_drivetrain))
            drivetrain = canonical_drivetrain
            continue
        engine_value = _extract_engine_displacement(token)
        if engine_value is not None and engine is None:
            raw_engine = token.upper() if token.endswith("lt") else token.upper().replace("L", "L")
            canonical_engine = _format_engine_displacement(engine_value)
            if raw_engine != canonical_engine:
                aliases.append(VehicleAlias("engine_displacement", raw_engine, canonical_engine))
            engine = engine_value
            continue
        model_tokens.append(token)
    model = _normalize_model(" ".join(model_tokens))
    return CanonicalVehicleObservation(
        year,
        make,
        model,
        None,
        None,
        trim,
        drivetrain,
        engine,
        tuple(aliases),
    )


def _normalize_year(raw_year: Any) -> int:
    text = str(raw_year).strip()
    if not text:
        raise ValueError("vehicle year is required")
    year = int(text)
    if len(text) == 2:
        year += 2000 if year <= 30 else 1900
    if year < 1886 or year > 2100:
        raise ValueError("vehicle year is outside the supported range")
    return year


def _is_valid_year_token(token: str) -> bool:
    if not re.fullmatch(r"\d{2}|\d{4}", token):
        return False
    try:
        _normalize_year(token)
    except ValueError:
        return False
    return True


def _normalize_make(raw_make: Any, aliases: list[VehicleAlias]) -> str:
    text = str(raw_make).strip()
    if not text:
        raise ValueError("vehicle make is required")
    canonical = _MAKE_ALIASES.get(text.casefold(), _normalize_title_words(text))
    if text != canonical:
        aliases.append(VehicleAlias("make", text, canonical))
    return canonical


def _normalize_model(raw_model: Any) -> str:
    text = str(raw_model).strip()
    if not text:
        raise ValueError("vehicle model is required")
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", text).strip()
    if not normalized:
        raise ValueError("vehicle model is required")
    return _MODEL_ALIASES.get(normalized.casefold(), _normalize_title_words(normalized))


def _normalize_region(raw_region: Any) -> str | None:
    if raw_region is None:
        return None
    normalized = _slug(str(raw_region))
    return normalized.upper() or None


def _normalize_body_style(raw_body_style: Any) -> str | None:
    if raw_body_style is None:
        return None
    text = str(raw_body_style).strip()
    if not text:
        return None
    return _normalize_model(text)


def _normalize_trim(raw_trim: Any) -> str | None:
    if raw_trim is None:
        return None
    text = str(raw_trim).strip()
    if not text:
        return None
    return re.sub(r"[^A-Za-z0-9]+", "", text).upper() or None


def _normalize_drivetrain(raw_drivetrain: Any, aliases: list[VehicleAlias]) -> str | None:
    if raw_drivetrain is None:
        return None
    text = str(raw_drivetrain).strip()
    if not text:
        return None
    canonical = _DRIVETRAIN_ALIASES.get(text.casefold())
    if canonical is None:
        canonical = re.sub(r"[^A-Za-z0-9]+", "", text).upper() or None
    if canonical and text != canonical:
        aliases.append(VehicleAlias("drivetrain", text, canonical))
    return canonical


def _normalize_engine(raw_engine: Any, aliases: list[VehicleAlias]) -> float | None:
    if raw_engine is None:
        return None
    if isinstance(raw_engine, (int, float)) and not isinstance(raw_engine, bool):
        value = float(raw_engine)
        if value <= 0:
            raise ValueError("engine displacement must be positive")
        return value
    text = str(raw_engine).strip()
    if not text:
        return None
    value = _extract_engine_displacement(text)
    if value is None:
        raise ValueError("engine displacement could not be normalized")
    canonical = _format_engine_displacement(value)
    if text != canonical:
        aliases.append(VehicleAlias("engine_displacement", text, canonical))
    return value


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is not None and (not isinstance(value, str) or value.strip()):
            return value
    return None


def _extract_engine_displacement(text: str) -> float | None:
    match = re.search(
        r"(?<!\d)(\d+(?:\.\d+)?)\s*l(?:t|iter|itre)?\b",
        text.casefold(),
    )
    if match is None:
        return None
    return float(match.group(1))


def _format_engine_displacement(value: float) -> str:
    return f"{value:.1f}L"


def _normalize_title_words(text: str) -> str:
    words = re.split(r"\s+", text.strip())
    normalized_words = []
    for word in words:
        if word.isdigit():
            normalized_words.append(word)
        else:
            normalized_words.append(word[:1].upper() + word[1:].lower())
    return " ".join(normalized_words)


def _vehicle_key(
    make: str,
    model: str,
    year: int,
    region: str | None,
    body_style: str | None,
    drivetrain: str | None,
) -> str:
    parts = [_slug(make), _slug(model), str(year)]
    if region:
        parts.append(_slug(region))
    if body_style:
        parts.extend(("body", _slug(body_style)))
    if drivetrain:
        parts.extend(("drivetrain", _slug(drivetrain)))
    return "-".join(parts)


def _configuration_key(
    vehicle_key: str,
    trim: str | None,
    engine_displacement_l: float | None,
) -> str:
    parts = [vehicle_key]
    if trim:
        parts.extend(("trim", _slug(trim)))
    if engine_displacement_l is not None:
        parts.extend(("engine", _slug(_format_engine_displacement(engine_displacement_l))))
    return "-".join(parts)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _score_candidate(
    observation: CanonicalVehicleObservation,
    candidate: CanonicalVehicleObservation,
) -> float:
    if not _observations_are_compatible(observation, candidate):
        return 0.0
    score = 100.0
    score += _optional_match_score(observation.trim, candidate.trim, 10.0)
    score += _optional_match_score(observation.drivetrain, candidate.drivetrain, 5.0)
    score += _optional_engine_score(
        observation.engine_displacement_l,
        candidate.engine_displacement_l,
        5.0,
    )
    return score


def _observations_are_compatible(
    observation: CanonicalVehicleObservation,
    candidate: CanonicalVehicleObservation,
) -> bool:
    if (observation.year, observation.make, observation.model) != (
        candidate.year,
        candidate.make,
        candidate.model,
    ):
        return False
    return (
        _optional_values_are_compatible(observation.region, candidate.region)
        and _optional_values_are_compatible(observation.body_style, candidate.body_style)
        and _optional_values_are_compatible(observation.trim, candidate.trim)
        and _optional_values_are_compatible(observation.drivetrain, candidate.drivetrain)
        and _optional_engine_values_are_compatible(
            observation.engine_displacement_l,
            candidate.engine_displacement_l,
        )
    )


def _optional_values_are_compatible(left: str | None, right: str | None) -> bool:
    return left is None or right is None or left == right


def _optional_engine_values_are_compatible(left: float | None, right: float | None) -> bool:
    return left is None or right is None or abs(left - right) < 0.0001


def _optional_match_score(expected: str | None, actual: str | None, weight: float) -> float:
    if expected is None or actual is None:
        return 0.0
    return weight if expected == actual else -weight


def _optional_engine_score(expected: float | None, actual: float | None, weight: float) -> float:
    if expected is None or actual is None:
        return 0.0
    return weight if abs(expected - actual) < 0.0001 else -weight


__all__ = [
    "CanonicalVehicleObservation",
    "VehicleAlias",
    "VehicleBaseIdentity",
    "VehicleConfiguration",
    "VehicleMatchCandidate",
    "VehicleReviewState",
    "build_base_identity",
    "build_vehicle_aliases",
    "build_vehicle_configuration",
    "canonicalize_vehicle_observation",
    "review_vehicle_candidates",
]
