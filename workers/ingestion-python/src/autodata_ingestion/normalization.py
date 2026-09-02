"""Normalize a source snapshot into stable, structured vehicle records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from autodata_contracts.fakes import SourceSnapshot


@dataclass(frozen=True)
class NormalizedSpecification:
    name: str
    value: Any
    unit: str | None


@dataclass(frozen=True)
class NormalizedVehicle:
    vehicle_key: str
    make: str
    model: str
    model_year: int
    region: str
    source_snapshot_id: str
    source_uri: str
    source_version: str
    source_sha256: str
    specifications: tuple[NormalizedSpecification, ...]

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["specifications"] = [asdict(specification) for specification in self.specifications]
        return output


def normalize_source_snapshot(snapshot: SourceSnapshot) -> NormalizedVehicle:
    vehicle = snapshot.content.get("vehicle")
    if not isinstance(vehicle, dict):
        raise ValueError("source snapshot is missing vehicle identity")
    required = ("make", "model", "year", "region")
    missing = [field for field in required if not str(vehicle.get(field, "")).strip()]
    if missing:
        raise ValueError(f"source snapshot is missing vehicle field: {missing[0]}")

    make = str(vehicle["make"]).strip()
    model = str(vehicle["model"]).strip()
    region = str(vehicle["region"]).strip().upper()
    try:
        model_year = int(vehicle["year"])
    except (TypeError, ValueError) as exc:
        raise ValueError("vehicle year must be an integer") from exc
    if model_year < 1886 or model_year > 2100:
        raise ValueError("vehicle year is outside the supported range")

    raw_specifications = snapshot.content.get("specifications", {})
    if not isinstance(raw_specifications, dict):
        raise ValueError("source specifications must be an object")
    specifications = tuple(
        NormalizedSpecification(name=name, value=value, unit=_unit_for(name))
        for name, value in raw_specifications.items()
    )
    return NormalizedVehicle(
        vehicle_key=f"{make.lower()}-{model.lower()}-{model_year}-{region.lower()}",
        make=make,
        model=model,
        model_year=model_year,
        region=region,
        source_snapshot_id=snapshot.source_snapshot_id,
        source_uri=snapshot.source_uri,
        source_version=snapshot.source_version,
        source_sha256=snapshot.content_sha256,
        specifications=specifications,
    )


def _unit_for(name: str) -> str | None:
    return {
        "engine_displacement_l": "L",
        "cylinders": "count",
    }.get(name)
