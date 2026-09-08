"""Cursor-testable persistence helpers for vehicle identity resolution."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
import uuid

from .vehicle_identity import (
    CanonicalVehicleObservation,
    VehicleReviewState,
    build_vehicle_aliases,
    canonicalize_vehicle_observation,
)


JsonAdapter = Callable[[Any], Any]


@dataclass(frozen=True)
class VehicleIdentityPersistenceResult:
    vehicle_id: str
    vehicle_key: str
    vehicle_identity_base_id: str
    canonical_base_key: str
    vehicle_configuration_id: str | None
    configuration_key: str | None
    vehicle_identity_observation_id: str
    observation_key: str
    resolution_status: str = "matched"
    resolution_reason: str | None = None


@dataclass(frozen=True)
class CatalogArticleReplayIdentity:
    vehicle_id: str
    article_id: str
    source_snapshot_id: str
    source_locator: str


@dataclass(frozen=True)
class VehicleIdentityObservationPersistenceResult:
    vehicle_identity_observation_id: str
    observation_key: str
    resolution_status: str


def persist_vehicle_identity_resolution(
    cursor: Any,
    observation: CanonicalVehicleObservation,
    *,
    source_snapshot_id: str,
    extraction_evidence_id: str,
    source_locator: str,
    evidence_locator: str,
    evidence_confidence: float,
    reviewer_state: str,
    source_watermark: str,
    raw_observation: Any | None = None,
    resolution: VehicleReviewState | None = None,
    jsonb: JsonAdapter = lambda value: value,
) -> VehicleIdentityPersistenceResult:
    """Persist one normalized vehicle identity observation and graph facts."""

    _validate_reviewer_state(reviewer_state)
    _validate_confidence(evidence_confidence)
    if observation.region is None:
        raise ValueError("vehicle identity persistence requires a non-null region")

    vehicle_key = _legacy_vehicle_key(observation)
    vehicle_id = _upsert_returning_id(
        cursor,
        """
        INSERT INTO vehicles
            (vehicle_id, vehicle_key, make, model, model_year, region,
             source_snapshot_id, source_watermark)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (vehicle_key)
        DO UPDATE SET source_snapshot_id = EXCLUDED.source_snapshot_id,
                      source_watermark = EXCLUDED.source_watermark,
                      updated_at = now()
        RETURNING vehicle_id
        """,
        (
            _stable_uuid(f"vehicle:{vehicle_key}"),
            vehicle_key,
            observation.make,
            observation.model,
            observation.year,
            observation.region,
            source_snapshot_id,
            source_watermark,
        ),
    )

    canonical_base_key = vehicle_key
    existing_base = _select_identity_base(cursor, canonical_base_key)
    conflict_reason = _base_dimension_conflict(existing_base, observation)
    if conflict_reason is not None:
        observation_payload = observation.to_dict()
        observation_key = _observation_key(
            source_snapshot_id,
            source_locator,
            observation_payload,
        )
        observation_id = _persist_identity_observation(
            cursor,
            observation_key=observation_key,
            vehicle_id=vehicle_id,
            vehicle_identity_base_id=existing_base["vehicle_identity_base_id"],
            vehicle_configuration_id=None,
            source_snapshot_id=source_snapshot_id,
            extraction_evidence_id=extraction_evidence_id,
            source_locator=source_locator,
            evidence_locator=evidence_locator,
            evidence_confidence=evidence_confidence,
            reviewer_state=reviewer_state,
            raw_observation=raw_observation if raw_observation is not None else observation_payload,
            canonical_observation=observation_payload,
            resolution_status="needs_review",
            resolution_reason=conflict_reason,
            selected_candidate_key=None,
            candidates=[],
            jsonb=jsonb,
        )
        return VehicleIdentityPersistenceResult(
            vehicle_id=vehicle_id,
            vehicle_key=vehicle_key,
            vehicle_identity_base_id=existing_base["vehicle_identity_base_id"],
            canonical_base_key=canonical_base_key,
            vehicle_configuration_id=None,
            configuration_key=None,
            vehicle_identity_observation_id=observation_id,
            observation_key=observation_key,
            resolution_status="needs_review",
            resolution_reason=conflict_reason,
        )

    base_id = _upsert_returning_id(
        cursor,
        """
        INSERT INTO vehicle_identity_bases
            (vehicle_identity_base_id, canonical_base_key, vehicle_id, make, model,
             model_year, region, body_style, drivetrain, source_snapshot_id,
             extraction_evidence_id, source_locator, evidence_locator,
             evidence_confidence, reviewer_state)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (canonical_base_key)
        DO UPDATE SET body_style = COALESCE(vehicle_identity_bases.body_style, EXCLUDED.body_style),
                      drivetrain = COALESCE(vehicle_identity_bases.drivetrain, EXCLUDED.drivetrain),
                      source_snapshot_id = EXCLUDED.source_snapshot_id,
                      extraction_evidence_id = EXCLUDED.extraction_evidence_id,
                      source_locator = EXCLUDED.source_locator,
                      evidence_locator = EXCLUDED.evidence_locator,
                      evidence_confidence = EXCLUDED.evidence_confidence,
                      reviewer_state = EXCLUDED.reviewer_state,
                      updated_at = now()
        WHERE (vehicle_identity_bases.body_style IS NULL
               OR EXCLUDED.body_style IS NULL
               OR vehicle_identity_bases.body_style = EXCLUDED.body_style)
          AND (vehicle_identity_bases.drivetrain IS NULL
               OR EXCLUDED.drivetrain IS NULL
               OR vehicle_identity_bases.drivetrain = EXCLUDED.drivetrain)
        RETURNING vehicle_identity_base_id
        """,
        (
            _stable_uuid(f"vehicle-identity-base:{canonical_base_key}"),
            canonical_base_key,
            vehicle_id,
            observation.make,
            observation.model,
            observation.year,
            observation.region,
            observation.body_style,
            observation.drivetrain,
            source_snapshot_id,
            extraction_evidence_id,
            source_locator,
            evidence_locator,
            evidence_confidence,
            reviewer_state,
        ),
    )

    configuration_key = _configuration_key(
        vehicle_key,
        observation.trim,
        observation.engine_displacement_l,
    )
    configuration_id = _upsert_returning_id(
        cursor,
        """
        INSERT INTO vehicle_configurations
            (vehicle_configuration_id, configuration_key, vehicle_identity_base_id,
             vehicle_id, trim, engine_displacement_l, source_snapshot_id,
             extraction_evidence_id, source_locator, evidence_locator,
             evidence_confidence, reviewer_state)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (configuration_key)
        DO UPDATE SET source_snapshot_id = EXCLUDED.source_snapshot_id,
                      extraction_evidence_id = EXCLUDED.extraction_evidence_id,
                      source_locator = EXCLUDED.source_locator,
                      evidence_locator = EXCLUDED.evidence_locator,
                      evidence_confidence = EXCLUDED.evidence_confidence,
                      reviewer_state = EXCLUDED.reviewer_state,
                      updated_at = now()
        RETURNING vehicle_configuration_id
        """,
        (
            _stable_uuid(f"vehicle-configuration:{configuration_key}"),
            configuration_key,
            base_id,
            vehicle_id,
            observation.trim,
            observation.engine_displacement_l,
            source_snapshot_id,
            extraction_evidence_id,
            source_locator,
            evidence_locator,
            evidence_confidence,
            reviewer_state,
        ),
    )

    for alias in build_vehicle_aliases(observation):
        cursor.execute(
            """
            INSERT INTO vehicle_aliases
                (vehicle_alias_id, vehicle_id, vehicle_configuration_id, alias_kind,
                 raw_value, canonical_value, source_snapshot_id,
                 extraction_evidence_id, source_locator, evidence_locator,
                 evidence_confidence, reviewer_state)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (vehicle_id, alias_kind, raw_value, canonical_value, source_snapshot_id, source_locator)
            DO UPDATE SET vehicle_configuration_id = EXCLUDED.vehicle_configuration_id,
                          extraction_evidence_id = EXCLUDED.extraction_evidence_id,
                          evidence_locator = EXCLUDED.evidence_locator,
                          evidence_confidence = EXCLUDED.evidence_confidence,
                          reviewer_state = EXCLUDED.reviewer_state,
                          updated_at = now()
            """,
            (
                _stable_uuid(
                    "vehicle-alias:"
                    f"{vehicle_id}:{alias.kind}:{alias.raw}:{alias.canonical}:"
                    f"{source_snapshot_id}:{source_locator}"
                ),
                vehicle_id,
                configuration_id,
                alias.kind,
                alias.raw,
                alias.canonical,
                source_snapshot_id,
                extraction_evidence_id,
                source_locator,
                evidence_locator,
                evidence_confidence,
                reviewer_state,
            ),
        )

    resolution_status = resolution.status if resolution is not None else "matched"
    resolution_reason = resolution.reason if resolution is not None else None
    selected_candidate_key = (
        resolution.selected_candidate_key
        if resolution is not None
        else configuration_key
    )
    candidates = (
        [candidate.to_dict() for candidate in resolution.candidates]
        if resolution is not None
        else []
    )
    observation_payload = observation.to_dict()
    observation_key = _observation_key(source_snapshot_id, source_locator, observation_payload)
    observation_id = _persist_identity_observation(
        cursor,
        observation_key=observation_key,
        vehicle_id=vehicle_id,
        vehicle_identity_base_id=base_id,
        vehicle_configuration_id=configuration_id,
        source_snapshot_id=source_snapshot_id,
        extraction_evidence_id=extraction_evidence_id,
        source_locator=source_locator,
        evidence_locator=evidence_locator,
        evidence_confidence=evidence_confidence,
        reviewer_state=reviewer_state,
        raw_observation=raw_observation if raw_observation is not None else observation_payload,
        canonical_observation=observation_payload,
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
        selected_candidate_key=selected_candidate_key,
        candidates=candidates,
        jsonb=jsonb,
    )

    return VehicleIdentityPersistenceResult(
        vehicle_id=vehicle_id,
        vehicle_key=vehicle_key,
        vehicle_identity_base_id=base_id,
        canonical_base_key=canonical_base_key,
        vehicle_configuration_id=configuration_id,
        configuration_key=configuration_key,
        vehicle_identity_observation_id=observation_id,
        observation_key=observation_key,
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
    )


def persist_unresolved_vehicle_identity_observation(
    cursor: Any,
    *,
    raw_observation: Any,
    source_snapshot_id: str,
    extraction_evidence_id: str,
    source_locator: str,
    evidence_locator: str,
    evidence_confidence: float,
    reviewer_state: str,
    resolution_status: str,
    resolution_reason: str | None = None,
    candidates: list[dict[str, Any]] | None = None,
    jsonb: JsonAdapter = lambda value: value,
) -> VehicleIdentityObservationPersistenceResult:
    """Persist reviewable raw identity evidence before a vehicle is resolved."""

    _validate_reviewer_state(reviewer_state)
    _validate_confidence(evidence_confidence)
    _validate_resolution_status(resolution_status)
    if resolution_status == "matched":
        raise ValueError("matched observations require resolved vehicle identity persistence")

    observation_key = _unresolved_observation_key(
        source_snapshot_id,
        source_locator,
        raw_observation,
    )
    observation_id = _persist_identity_observation(
        cursor,
        observation_key=observation_key,
        vehicle_id=None,
        vehicle_identity_base_id=None,
        vehicle_configuration_id=None,
        source_snapshot_id=source_snapshot_id,
        extraction_evidence_id=extraction_evidence_id,
        source_locator=source_locator,
        evidence_locator=evidence_locator,
        evidence_confidence=evidence_confidence,
        reviewer_state=reviewer_state,
        raw_observation=raw_observation,
        canonical_observation={},
        resolution_status=resolution_status,
        resolution_reason=resolution_reason,
        selected_candidate_key=None,
        candidates=candidates or [],
        jsonb=jsonb,
    )
    return VehicleIdentityObservationPersistenceResult(
        vehicle_identity_observation_id=observation_id,
        observation_key=observation_key,
        resolution_status=resolution_status,
    )


def persist_catalog_article_duplicate_link(
    cursor: Any,
    *,
    canonical: CatalogArticleReplayIdentity,
    duplicate: CatalogArticleReplayIdentity,
    source_snapshot_id: str,
    extraction_evidence_id: str,
    evidence_locator: str,
    evidence_confidence: float,
    reviewer_state: str,
) -> str:
    """Link duplicate articles after resolving each row by replay identity."""

    _validate_reviewer_state(reviewer_state)
    _validate_confidence(evidence_confidence)
    if canonical.vehicle_id != duplicate.vehicle_id:
        raise ValueError("canonical and duplicate article links must share a vehicle")

    canonical_article_id = _select_catalog_article_id(cursor, canonical)
    duplicate_article_id = _select_catalog_article_id(cursor, duplicate)
    link_id = _upsert_returning_id(
        cursor,
        """
        INSERT INTO catalog_article_vehicle_links
            (catalog_article_vehicle_link_id, vehicle_id, canonical_catalog_article_id,
             duplicate_catalog_article_id, source_snapshot_id, extraction_evidence_id,
             evidence_locator, evidence_confidence, reviewer_state, link_state)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'duplicate')
        ON CONFLICT (duplicate_catalog_article_id)
        DO UPDATE SET canonical_catalog_article_id = EXCLUDED.canonical_catalog_article_id,
                      source_snapshot_id = EXCLUDED.source_snapshot_id,
                      extraction_evidence_id = EXCLUDED.extraction_evidence_id,
                      evidence_locator = EXCLUDED.evidence_locator,
                      evidence_confidence = EXCLUDED.evidence_confidence,
                      reviewer_state = EXCLUDED.reviewer_state,
                      link_state = EXCLUDED.link_state,
                      updated_at = now()
        RETURNING catalog_article_vehicle_link_id
        """,
        (
            _stable_uuid(
                "catalog-article-vehicle-link:"
                f"{canonical_article_id}:{duplicate_article_id}"
            ),
            canonical.vehicle_id,
            canonical_article_id,
            duplicate_article_id,
            source_snapshot_id,
            extraction_evidence_id,
            evidence_locator,
            evidence_confidence,
            reviewer_state,
        ),
    )
    return link_id


def _select_catalog_article_id(cursor: Any, identity: CatalogArticleReplayIdentity) -> str:
    cursor.execute(
        """
        SELECT catalog_article_id
        FROM catalog_articles
        WHERE vehicle_id = %s
          AND article_id = %s
          AND source_snapshot_id = %s
          AND source_locator = %s
        """,
        (
            identity.vehicle_id,
            identity.article_id,
            identity.source_snapshot_id,
            identity.source_locator,
        ),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("catalog article replay identity was not found")
    return str(row[0])


def _select_identity_base(cursor: Any, canonical_base_key: str) -> dict[str, str | None] | None:
    cursor.execute(
        """
        SELECT vehicle_identity_base_id, body_style, drivetrain
        FROM vehicle_identity_bases
        WHERE canonical_base_key = %s
        """,
        (canonical_base_key,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "vehicle_identity_base_id": str(row[0]),
        "body_style": row[1],
        "drivetrain": row[2],
    }


def _base_dimension_conflict(
    existing_base: dict[str, str | None] | None,
    observation: CanonicalVehicleObservation,
) -> str | None:
    if existing_base is None:
        return None
    for field_name, incoming in (
        ("body_style", observation.body_style),
        ("drivetrain", observation.drivetrain),
    ):
        existing = existing_base[field_name]
        if existing is not None and incoming is not None and existing != incoming:
            return "conflicting_base_dimension"
    return None


def _legacy_vehicle_key(observation: CanonicalVehicleObservation) -> str:
    return "-".join(
        (
            _slug(observation.make),
            _slug(observation.model),
            str(observation.year),
            _slug(_require_region(observation.region)),
        )
    )


def _require_region(region: str | None) -> str:
    if region is None:
        raise ValueError("vehicle identity persistence requires a non-null region")
    return region


def _observation_key(
    source_snapshot_id: str,
    source_locator: str,
    canonical_observation: dict[str, Any],
) -> str:
    parts = [
        source_snapshot_id,
        source_locator,
        str(canonical_observation["year"]),
        str(canonical_observation["make"]),
        str(canonical_observation["model"]),
        str(canonical_observation.get("region") or ""),
        str(canonical_observation.get("body_style") or ""),
        str(canonical_observation.get("trim") or ""),
        str(canonical_observation.get("drivetrain") or ""),
        str(canonical_observation.get("engine_displacement_l") or ""),
    ]
    return "|".join(parts)


def _persist_identity_observation(
    cursor: Any,
    *,
    observation_key: str,
    vehicle_id: str | None,
    vehicle_identity_base_id: str | None,
    vehicle_configuration_id: str | None,
    source_snapshot_id: str,
    extraction_evidence_id: str,
    source_locator: str,
    evidence_locator: str,
    evidence_confidence: float,
    reviewer_state: str,
    raw_observation: Any,
    canonical_observation: Any,
    resolution_status: str,
    resolution_reason: str | None,
    selected_candidate_key: str | None,
    candidates: list[dict[str, Any]],
    jsonb: JsonAdapter,
) -> str:
    return _upsert_returning_id(
        cursor,
        """
        INSERT INTO vehicle_identity_observations
            (vehicle_identity_observation_id, observation_key, vehicle_id,
             vehicle_identity_base_id, vehicle_configuration_id, source_snapshot_id,
             extraction_evidence_id, source_locator, evidence_locator,
             evidence_confidence, reviewer_state, raw_observation,
             canonical_observation, resolution_status, resolution_reason,
             selected_candidate_key, candidates)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (observation_key)
        DO UPDATE SET vehicle_id = EXCLUDED.vehicle_id,
                      vehicle_identity_base_id = EXCLUDED.vehicle_identity_base_id,
                      vehicle_configuration_id = EXCLUDED.vehicle_configuration_id,
                      extraction_evidence_id = EXCLUDED.extraction_evidence_id,
                      evidence_locator = EXCLUDED.evidence_locator,
                      evidence_confidence = EXCLUDED.evidence_confidence,
                      reviewer_state = EXCLUDED.reviewer_state,
                      raw_observation = EXCLUDED.raw_observation,
                      canonical_observation = EXCLUDED.canonical_observation,
                      resolution_status = EXCLUDED.resolution_status,
                      resolution_reason = EXCLUDED.resolution_reason,
                      selected_candidate_key = EXCLUDED.selected_candidate_key,
                      candidates = EXCLUDED.candidates,
                      updated_at = now()
        RETURNING vehicle_identity_observation_id
        """,
        (
            _stable_uuid(f"vehicle-identity-observation:{observation_key}"),
            observation_key,
            vehicle_id,
            vehicle_identity_base_id,
            vehicle_configuration_id,
            source_snapshot_id,
            extraction_evidence_id,
            source_locator,
            evidence_locator,
            evidence_confidence,
            reviewer_state,
            jsonb(raw_observation),
            jsonb(canonical_observation),
            resolution_status,
            resolution_reason,
            selected_candidate_key,
            jsonb(candidates),
        ),
    )


def _unresolved_observation_key(
    source_snapshot_id: str,
    source_locator: str,
    raw_observation: Any,
) -> str:
    raw_identity = json.dumps(raw_observation, sort_keys=True, separators=(",", ":"), default=str)
    return f"{source_snapshot_id}|{source_locator}|unresolved|{raw_identity}"


def _validate_resolution_status(resolution_status: str) -> None:
    allowed = {"matched", "ambiguous", "unmatched", "rejected", "needs_review"}
    if resolution_status not in allowed:
        raise ValueError("resolution_status must be matched, ambiguous, unmatched, rejected, or needs_review")


def _validate_reviewer_state(reviewer_state: str) -> None:
    if reviewer_state not in {"pending", "approved", "rejected"}:
        raise ValueError("reviewer_state must be pending, approved, or rejected")


def _validate_confidence(confidence: float) -> None:
    if confidence < 0 or confidence > 1:
        raise ValueError("evidence_confidence must be between 0 and 1")


def _upsert_returning_id(cursor: Any, sql: str, params: tuple[Any, ...]) -> str:
    cursor.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        raise ValueError("upsert did not return an id")
    return str(row[0])


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autodata-vehicle-identity:{value}"))


def _configuration_key(
    vehicle_key: str,
    trim: str | None,
    engine_displacement_l: float | None,
) -> str:
    parts = [vehicle_key]
    if trim:
        parts.extend(("trim", _slug(trim)))
    if engine_displacement_l is not None:
        parts.extend(("engine", _slug(f"{engine_displacement_l:.1f}L")))
    return "-".join(parts)


def _slug(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


__all__ = [
    "CatalogArticleReplayIdentity",
    "VehicleIdentityObservationPersistenceResult",
    "VehicleIdentityPersistenceResult",
    "canonicalize_vehicle_observation",
    "persist_catalog_article_duplicate_link",
    "persist_unresolved_vehicle_identity_observation",
    "persist_vehicle_identity_resolution",
]
