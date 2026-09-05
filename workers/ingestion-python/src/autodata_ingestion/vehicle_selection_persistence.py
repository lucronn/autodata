"""Durable persistence for vehicle selector source lists."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping

from .bundle_persistence import (
    _persist_artifact_rows,
    _persist_extraction_evidence,
    _persist_snapshots,
    _stable_uuid,
    store_source_artifacts,
)
from .source_adapters import SourceArtifact, SourceResource, adapt_source_resource
from .source_bundle import SourceBundle
from .vehicle_identity import canonicalize_vehicle_observation
from .vehicle_identity_persistence import persist_vehicle_identity_resolution


def persist_vehicle_selection_list(
    values: Iterable[Mapping[str, Any] | str],
    *,
    source_uri: str = "input://vehicle-list",
    source_version: str = "vehicle-list-v1",
    region: str | None = None,
) -> dict[str, Any]:
    """Persist a vehicle list as source evidence and identity graph facts.

    The list itself is an immutable source snapshot. Each row becomes a
    separately addressable evidence record and identity observation, so a
    later richer row can add a configuration under the same base vehicle
    without creating a duplicate family. Persistence is intentionally
    explicit; callers must opt into it because source storage requires the
    configured object-store and database credentials.
    """

    raw_values = list(values)
    if not raw_values:
        raise ValueError("vehicle selection list cannot be empty")
    payload = json.dumps(raw_values, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    resource = SourceResource.from_bytes(
        source_uri,
        source_version,
        payload,
        "application/json",
        metadata={"source_kind": "vehicle_selection_list"},
    )
    artifact = adapt_source_resource(resource)
    artifacts: list[SourceArtifact] = [artifact]
    store_source_artifacts(artifacts)

    import psycopg
    from psycopg.types.json import Jsonb

    host, port_text = os.getenv("AUTODATA_DB_ADDRESS", "postgres:5432").rsplit(":", 1)
    conninfo = {
        "host": host,
        "port": int(port_text),
        "dbname": os.getenv("AUTODATA_POSTGRES_DB", "autodata"),
        "user": os.getenv("AUTODATA_POSTGRES_USER", "autodata"),
        "password": os.environ["AUTODATA_POSTGRES_PASSWORD"],
    }
    now = datetime.now(UTC).replace(microsecond=0)
    source_region = str(region).strip().upper() if region is not None else None
    observations = []
    evidence_items = []
    for index, raw_value in enumerate(raw_values):
        canonical_input = _with_default_region(raw_value, source_region)
        observation = canonicalize_vehicle_observation(canonical_input)
        if observation.region is None:
            raise ValueError(
                f"vehicle selection row {index} requires region or a default region"
            )
        evidence_items.append(
            {
                "evidence_id": _stable_uuid(
                    f"vehicle-list-evidence:{resource.content_sha256}:{index}"
                ),
                "content_sha256": resource.content_sha256,
                "locator": f"vehicle-list[{index}]",
                "extracted_text": json.dumps(
                    observation.to_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "confidence": 1.0,
                "reviewer_state": "pending",
            }
        )
        observations.append((raw_value, observation, evidence_items[-1]))

    bundle = SourceBundle(
        status="ready",
        vehicle=None,
        specifications=(),
        models=(),
        powertrains=(),
        parts=(),
        articles=(),
        documents=(),
        diagrams=(),
        evidence=tuple(evidence_items),
        quarantined=(),
        conflicts=(),
    )
    with psycopg.connect(**conninfo) as connection:
        with connection.cursor() as cursor:
            snapshot_ids = _persist_snapshots(
                cursor, artifacts, "vehicle-list", now, Jsonb
            )
            _persist_artifact_rows(cursor, artifacts, snapshot_ids, bundle, now, Jsonb)
            _persist_extraction_evidence(
                cursor,
                artifacts,
                snapshot_ids,
                {item["evidence_id"]: item for item in evidence_items},
                bundle.status,
                now,
            )
            results = []
            snapshot_id = snapshot_ids[resource.content_sha256]
            for raw_value, observation, evidence in observations:
                result = persist_vehicle_identity_resolution(
                    cursor,
                    observation,
                    source_snapshot_id=snapshot_id,
                    extraction_evidence_id=evidence["evidence_id"],
                    source_locator=evidence["locator"],
                    evidence_locator=evidence["locator"],
                    evidence_confidence=evidence["confidence"],
                    reviewer_state=evidence["reviewer_state"],
                    source_watermark=source_version,
                    raw_observation=raw_value,
                    jsonb=Jsonb,
                )
                results.append(
                    {
                        "vehicle_id": result.vehicle_id,
                        "vehicle_key": result.vehicle_key,
                        "vehicle_identity_base_id": result.vehicle_identity_base_id,
                        "vehicle_configuration_id": result.vehicle_configuration_id,
                        "configuration_key": result.configuration_key,
                        "observation_id": result.vehicle_identity_observation_id,
                        "resolution_status": result.resolution_status,
                    }
                )
            connection.commit()
    return {
        "status": "persisted",
        "source_snapshot_id": snapshot_ids[resource.content_sha256],
        "source_uri": source_uri,
        "source_version": source_version,
        "observations": results,
        "observation_count": len(results),
    }


def _with_default_region(value: Mapping[str, Any] | str, region: str | None) -> Mapping[str, Any] | str:
    if region is None or isinstance(value, str):
        return value
    result = dict(value)
    result.setdefault("region", region)
    return result


__all__ = ["persist_vehicle_selection_list"]
