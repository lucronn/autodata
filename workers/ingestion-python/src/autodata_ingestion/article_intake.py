"""Bounded HTTP intake for one vehicle-specific article."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .http_connector import HttpSourceConnector
from .source_adapters import SourceArtifact, adapt_source_resource
from .source_bundle import SourceBundle, normalize_source_bundle


@dataclass(frozen=True)
class VehicleTarget:
    """The vehicle identity an article is allowed to be associated with."""

    make: str
    model: str
    model_year: int
    region: str
    trim: str | None = None

    def __post_init__(self) -> None:
        make = str(self.make).strip()
        model = str(self.model).strip()
        region = str(self.region).strip().upper()
        trim = str(self.trim).strip() if self.trim is not None else None
        if not make or not model or not region:
            raise ValueError("vehicle target requires make, model, and region")
        try:
            model_year = int(self.model_year)
        except (TypeError, ValueError) as error:
            raise ValueError("vehicle target year must be an integer") from error
        if model_year < 1886 or model_year > 2100:
            raise ValueError("vehicle target year is outside the supported range")
        object.__setattr__(self, "make", make)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "model_year", model_year)
        object.__setattr__(self, "region", region)
        object.__setattr__(self, "trim", trim or None)

    @property
    def vehicle_key(self) -> str:
        return "-".join((_slug(self.make), _slug(self.model), str(self.model_year), _slug(self.region)))

    def as_dict(self) -> dict[str, Any]:
        result = {
            "make": self.make,
            "model": self.model,
            "year": self.model_year,
            "region": self.region,
        }
        if self.trim:
            result["trim"] = self.trim
        return result


@dataclass(frozen=True)
class VehicleArticleIntake:
    status: str
    source_uri: str
    target: VehicleTarget
    artifacts: tuple[SourceArtifact, ...]
    bundle: SourceBundle
    rejection_reason: str | None = None


def ingest_vehicle_article(
    source_uri: str,
    target: VehicleTarget,
    *,
    connector: Any | None = None,
    source_version: str | None = None,
    timeout_seconds: float = 30,
    max_bytes: int = 50 * 1024 * 1024,
    request_headers: dict[str, str] | None = None,
) -> VehicleArticleIntake:
    """Fetch, normalize, and safely associate one arbitrary HTTP article.

    The connector remains responsible only for bounded byte capture. The
    shared adapter/bundle path owns extraction, provenance, and review state.
    A source without a recognizable article or matching vehicle is never
    returned as an associated canonical article.
    """

    if connector is None:
        connector = HttpSourceConnector(
            source_uri,
            source_version,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
            request_headers=request_headers,
        )
    resources = tuple(connector.fetch({"source_uri": source_uri}))
    if not resources:
        raise ValueError("article source returned no resources")
    if len(resources) != 1:
        raise ValueError("article intake expects exactly one HTTP resource")
    artifacts = tuple(adapt_source_resource(resource) for resource in resources)
    bundle = normalize_source_bundle(
        artifacts,
        target.region,
        expected_vehicle=target.as_dict(),
    )
    if bundle.vehicle is None:
        reason = (
            "vehicle_identity_mismatch"
            if any(item.get("reason") == "vehicle_identity_mismatch" for item in bundle.quarantined)
            else "vehicle_identity_not_found"
        )
        return VehicleArticleIntake(
            "rejected", source_uri, target, artifacts, bundle, reason
        )
    if not bundle.articles:
        return VehicleArticleIntake(
            "rejected", source_uri, target, artifacts, bundle, "article_not_recognized"
        )
    return VehicleArticleIntake("ready", source_uri, target, artifacts, bundle)


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
