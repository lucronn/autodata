"""Canonical vehicle identity helpers for ingestion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping


_MAKE_ALIASES = {
    "chevy": "Chevrolet",
    "chevrolet": "Chevrolet",
}
_DRIVETRAIN_ALIASES = {
    "2wd": "2WD",
    "4x2": "2WD",
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
        vehicle_key=_vehicle_key(observation.make, observation.model, observation.year),
        year=observation.year,
        make=observation.make,
        model=observation.model,
    )


def build_vehicle_configuration(observation: CanonicalVehicleObservation) -> VehicleConfiguration:
    base = build_base_identity(observation)
    return VehicleConfiguration(
        configuration_key=_configuration_key(
            base.vehicle_key,
            observation.trim,
            observation.drivetrain,
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
    year = _normalize_year(value.get("year"))
    make = _normalize_make(value.get("make"), aliases)
    model = _normalize_model(value.get("model"))
    trim = _normalize_trim(value.get("trim"))
    drivetrain = _normalize_drivetrain(value.get("drivetrain"), aliases)
    engine = _normalize_engine(value.get("engine"), aliases)
    return CanonicalVehicleObservation(year, make, model, trim, drivetrain, engine, tuple(aliases))


def _canonicalize_text_observation(value: str) -> CanonicalVehicleObservation:
    normalized_text = re.sub(
        r"(\d+(?:\.\d+)?)\s+(l(?:t)?)\b",
        r"\1\2",
        value.casefold(),
    )
    tokens = re.findall(r"[a-z0-9.]+", normalized_text)
    if len(tokens) < 3:
        raise ValueError("vehicle text observation requires year, make, and model")
    aliases: list[VehicleAlias] = []
    year = _normalize_year(tokens[0])
    make = _normalize_make(tokens[1], aliases)
    trim = None
    drivetrain = None
    engine = None
    model_tokens: list[str] = []
    for token in tokens[2:]:
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
    return CanonicalVehicleObservation(year, make, model, trim, drivetrain, engine, tuple(aliases))


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
    return _normalize_title_words(normalized)


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


def _extract_engine_displacement(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*l(?:t)?$", text.casefold())
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


def _vehicle_key(make: str, model: str, year: int) -> str:
    return "-".join((_slug(make), _slug(model), str(year)))


def _configuration_key(
    vehicle_key: str,
    trim: str | None,
    drivetrain: str | None,
    engine_displacement_l: float | None,
) -> str:
    parts = [vehicle_key]
    if trim:
        parts.append(_slug(trim))
    if drivetrain:
        parts.append(_slug(drivetrain))
    if engine_displacement_l is not None:
        parts.append(_slug(_format_engine_displacement(engine_displacement_l)))
    return "-".join(parts)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _score_candidate(
    observation: CanonicalVehicleObservation,
    candidate: CanonicalVehicleObservation,
) -> float:
    if observation.year != candidate.year:
        return 0.0
    if observation.make != candidate.make:
        return 0.0
    if observation.model != candidate.model:
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
