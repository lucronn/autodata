"""Deterministic vehicle-list normalization for identity selection."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from .vehicle_identity import (
    CanonicalVehicleObservation,
    VehicleAlias,
    canonicalize_vehicle_observation,
)


@dataclass(frozen=True)
class VehicleSelectionRecord:
    """One stable vehicle family with its observed configurations."""

    vehicle_key: str
    year: int
    make: str
    model: str
    region: str | None
    body_style: str | None
    drivetrain: str | None
    configurations: tuple[dict[str, Any], ...]
    aliases: tuple[VehicleAlias, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "vehicle_id_key": self.vehicle_key,
            "year": self.year,
            "make": self.make,
            "model": self.model,
            "region": self.region,
            "body_style": self.body_style,
            "drivetrain": self.drivetrain,
            "configurations": [dict(item) for item in self.configurations],
            "aliases": [alias.to_dict() for alias in self.aliases],
        }


def normalize_vehicle_list(
    values: list[Mapping[str, Any] | str] | tuple[Mapping[str, Any] | str, ...],
    *,
    default_region: str | None = None,
) -> tuple[VehicleSelectionRecord, ...]:
    """Normalize and merge vehicle rows without creating duplicate families.

    Omitted optional dimensions are preserved as unknowns. A later row can
    add a configuration or fill an unknown body/drivetrain field, while a
    contradictory known base dimension is retained as a review conflict.
    """

    families: dict[str, dict[str, Any]] = {}
    normalized_default_region = _normalize_default_region(default_region)
    for raw in values:
        observation = canonicalize_vehicle_observation(_adapt_row(raw))
        if observation.region is None and normalized_default_region is not None:
            observation = replace(observation, region=normalized_default_region)
        vehicle_key = _stable_vehicle_key(observation)
        family = families.setdefault(vehicle_key, _new_family(observation, vehicle_key))
        _merge_family(family, observation)
    return tuple(
        _record_from_family(families[key]) for key in sorted(families)
    )


def normalize_vehicle_list_json(
    values: list[Mapping[str, Any] | str],
    *,
    default_region: str | None = None,
) -> list[dict[str, Any]]:
    """Return the normalized selection payload as JSON-compatible dictionaries."""

    return [
        record.to_dict()
        for record in normalize_vehicle_list(values, default_region=default_region)
    ]


def _adapt_row(raw: Mapping[str, Any] | str) -> Mapping[str, Any] | str:
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, Mapping):
        raise TypeError("vehicle list rows must be mappings or strings")
    aliases = dict(raw)
    if "year" not in aliases and "model_year" in aliases:
        aliases["year"] = aliases["model_year"]
    if "year" not in aliases and "modelYear" in aliases:
        aliases["year"] = aliases["modelYear"]
    if "make" not in aliases:
        aliases["make"] = aliases.get("makeName", aliases.get("vehicleMake"))
    if "model" not in aliases:
        aliases["model"] = aliases.get("modelName", aliases.get("vehicleModel"))
    if "engine" not in aliases and "engine_displacement_l" in aliases:
        raw_engine = aliases["engine_displacement_l"]
        aliases["engine"] = f"{raw_engine}L" if isinstance(raw_engine, (int, float)) else raw_engine
    if "engine" not in aliases and "engineDisplacementL" in aliases:
        raw_engine = aliases["engineDisplacementL"]
        aliases["engine"] = f"{raw_engine}L" if isinstance(raw_engine, (int, float)) else raw_engine
    if "engine" not in aliases and "engineName" in aliases:
        aliases["engine"] = aliases["engineName"]
    if "market" not in aliases and "region" in aliases:
        aliases["market"] = aliases["region"]
    return aliases


def _stable_vehicle_key(observation: CanonicalVehicleObservation) -> str:
    parts = [
        _slug(observation.make),
        _slug(observation.model),
        str(observation.year),
    ]
    if observation.region:
        parts.append(_slug(observation.region))
    return "-".join(parts)


def _new_family(observation: CanonicalVehicleObservation, vehicle_key: str) -> dict[str, Any]:
    return {
        "vehicle_key": vehicle_key,
        "year": observation.year,
        "make": observation.make,
        "model": observation.model,
        "region": observation.region,
        "body_style": observation.body_style,
        "drivetrain": observation.drivetrain,
        "configurations": {},
        "aliases": list(observation.aliases),
        "conflicts": [],
    }


def _merge_family(family: dict[str, Any], observation: CanonicalVehicleObservation) -> None:
    for field in ("body_style", "drivetrain"):
        incoming = getattr(observation, field)
        current = family[field]
        if current is None and incoming is not None:
            family[field] = incoming
        elif current is not None and incoming is not None and current != incoming:
            conflict = {"field": field, "existing": current, "incoming": incoming}
            if conflict not in family["conflicts"]:
                family["conflicts"].append(conflict)
    configuration_key = _configuration_key(family["vehicle_key"], observation)
    family["configurations"].setdefault(
        configuration_key,
        {
            "configuration_key": configuration_key,
            "trim": observation.trim,
            "engine_displacement_l": observation.engine_displacement_l,
            "drivetrain": family["drivetrain"],
        },
    )
    family["aliases"].extend(alias for alias in observation.aliases if alias not in family["aliases"])


def _record_from_family(family: dict[str, Any]) -> VehicleSelectionRecord:
    configurations = []
    for item in family["configurations"].values():
        configuration = dict(item)
        configuration["drivetrain"] = family["drivetrain"]
        configurations.append(configuration)
    if family["conflicts"]:
        configurations.append({"status": "needs_review", "conflicts": list(family["conflicts"])})
    return VehicleSelectionRecord(
        vehicle_key=family["vehicle_key"],
        year=family["year"],
        make=family["make"],
        model=family["model"],
        region=family["region"],
        body_style=family["body_style"],
        drivetrain=family["drivetrain"],
        configurations=tuple(configurations),
        aliases=tuple(family["aliases"]),
    )


def _configuration_key(vehicle_key: str, observation: CanonicalVehicleObservation) -> str:
    parts = [vehicle_key]
    if observation.trim:
        parts.extend(("trim", _slug(observation.trim)))
    if observation.engine_displacement_l is not None:
        engine_key = f"{observation.engine_displacement_l:.1f}".replace(".", "-") + "l"
        parts.extend(("engine", engine_key))
    return "-".join(parts)


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _normalize_default_region(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _slug(str(value)).upper()
    return normalized or None


__all__ = ["VehicleSelectionRecord", "normalize_vehicle_list", "normalize_vehicle_list_json"]
