"""Bounded HTTP intake for one vehicle-specific article."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .http_connector import HttpSourceConnector
from .source_adapters import SourceArtifact, adapt_source_resource
from .source_bundle import SourceBundle, normalize_source_bundle
from .vehicle_identity import canonicalize_vehicle_observation


@dataclass(frozen=True)
class VehicleTarget:
    """The vehicle identity an article is allowed to be associated with."""

    make: str
    model: str
    model_year: int
    region: str
    trim: str | None = None
    body_style: str | None = None
    drivetrain: str | None = None
    engine_displacement_l: float | str | None = None

    def __post_init__(self) -> None:
        raw_engine = self.engine_displacement_l
        if isinstance(raw_engine, (int, float)):
            raw_engine = f"{raw_engine}L"
        try:
            canonical = canonicalize_vehicle_observation(
                {
                    "year": self.model_year,
                    "make": self.make,
                    "model": self.model,
                    "region": self.region,
                    "body_style": self.body_style,
                    "trim": self.trim,
                    "drivetrain": self.drivetrain,
                    "engine": raw_engine,
                }
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "vehicle target requires valid make, model, year, and region"
            ) from error
        if canonical.region is None:
            raise ValueError("vehicle target requires make, model, and region")
        object.__setattr__(self, "make", canonical.make)
        object.__setattr__(self, "model", canonical.model)
        object.__setattr__(self, "model_year", canonical.year)
        object.__setattr__(self, "region", canonical.region)
        object.__setattr__(self, "trim", canonical.trim)
        object.__setattr__(self, "body_style", canonical.body_style)
        object.__setattr__(self, "drivetrain", canonical.drivetrain)
        object.__setattr__(self, "engine_displacement_l", canonical.engine_displacement_l)

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
        if self.body_style:
            result["body_style"] = self.body_style
        if self.drivetrain:
            result["drivetrain"] = self.drivetrain
        if self.engine_displacement_l is not None:
            result["engine_displacement_l"] = self.engine_displacement_l
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
    artifacts = tuple(
        _augment_unrecognized_resource(resource, adapt_source_resource(resource))
        for resource in resources
    )
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


def _augment_unrecognized_resource(resource: Any, artifact: SourceArtifact) -> SourceArtifact:
    """Optionally ask Mercury-2 for typed candidates from an unknown JSON shape."""

    if artifact.kind != "structured" or artifact.candidates:
        return artifact
    from .mercury2 import configured_source_extractor

    extractor, extractor_error = configured_source_extractor()
    if extractor is None and extractor_error is None:
        return artifact
    if extractor_error is not None:
        return replace(
            artifact,
            metadata={
                **artifact.metadata,
                "extraction_mode": "mercury-2",
                "extraction_status": "needs_review",
                "extraction_error": extractor_error,
            },
        )
    try:
        candidates = tuple(extractor.extract(resource))
    except Exception as error:  # noqa: BLE001 - source review must survive advisory failures
        return replace(
            artifact,
            metadata={
                **artifact.metadata,
                "extraction_mode": "mercury-2",
                "extraction_status": "needs_review",
                "extraction_error": str(error),
            },
        )
    return replace(
        artifact,
        candidates=candidates,
        metadata={
            **artifact.metadata,
            "extraction_mode": "mercury-2",
            "candidate_count": len(candidates),
            "extraction_status": "candidate_ready" if candidates else "needs_review",
        },
    )


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
