"""Plan and execute vehicle-scoped batches from split AutoAPI source drops."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .directory_connector import DirectorySourceConnector
from .quality import evaluate_source_bundle
from .source_adapters import SourceArtifact, adapt_source_resource
from .source_bundle import normalize_source_bundle
from .vehicle_identity import canonicalize_vehicle_observation
from .vehicle_selection import normalize_vehicle_list, normalize_vehicle_list_json


@dataclass(frozen=True)
class AutoAPIBatch:
    """One vehicle family and the source directory that owns its articles."""

    vehicle_key: str
    vehicle: dict[str, Any]
    source_directory: Path | None
    configurations: tuple[dict[str, Any], ...]


def discover_autoapi_source_directories(source_root: str | Path) -> tuple[Path, ...]:
    """Find one AutoAPI response bundle per vehicle under a source root.

    A directory containing ``name.json`` is itself a bundle. Otherwise each
    descendant directory containing ``name.json`` is treated as a bundle. The
    marker is deliberately provider-specific while the resources inside each
    bundle continue through the universal source adapter boundary.
    """

    root = Path(source_root)
    if not root.is_dir():
        raise ValueError(f"source root does not exist: {root}")
    if (root / "name.json").is_file():
        return (root,)
    return tuple(sorted({path.parent for path in root.rglob("name.json")}))


def derive_autoapi_vehicle_rows(
    source_directory: str | Path,
    *,
    default_region: str | None = None,
    source_version: str = "autoapi-local-v1",
) -> list[dict[str, Any]]:
    """Derive normalized selector rows from AutoAPI's split identity/model files."""

    directory = Path(source_directory)
    artifacts = _read_artifacts(directory, source_version)
    bundle = normalize_source_bundle(artifacts, default_region or "US")
    if bundle.vehicle is None:
        raise ValueError(f"AutoAPI bundle has no resolvable vehicle identity: {directory}")

    vehicle = dict(bundle.vehicle)
    identity_candidate = next(
        (
            candidate
            for artifact in artifacts
            for candidate in artifact.candidates
            if candidate.kind == "vehicle_identity"
        ),
        None,
    )
    if identity_candidate is not None:
        display_name = identity_candidate.data.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            parsed_identity = canonicalize_vehicle_observation(display_name)
            vehicle["drivetrain"] = parsed_identity.drivetrain
            vehicle["trim"] = parsed_identity.trim

    rows: list[dict[str, Any]] = []
    model_candidates = [
        candidate
        for artifact in artifacts
        for candidate in artifact.candidates
        if candidate.kind == "model"
    ]
    if not model_candidates:
        return [_base_row(vehicle)]

    for candidate in model_candidates:
        model_name = str(candidate.data.get("model") or "").strip()
        if not model_name:
            continue
        trim = _trim_from_model_name(vehicle["model"], model_name)
        engines = candidate.data.get("engines", [])
        if not isinstance(engines, list) or not engines:
            rows.append(_base_row(vehicle, trim=trim))
            continue
        for engine in engines:
            if not isinstance(engine, Mapping):
                continue
            engine_name = str(engine.get("name") or "").strip()
            row = _base_row(vehicle, trim=trim)
            if engine_name:
                row["engine"] = _engine_displacement_text(engine_name) or engine_name
                row["engine_name"] = engine_name
            rows.append(row)

    return rows or [_base_row(vehicle)]


def build_autoapi_batch_plan(
    source_root: str | Path,
    *,
    selector_rows: Iterable[Mapping[str, Any] | str] | None = None,
    default_region: str | None = None,
    source_version: str = "autoapi-local-v1",
) -> tuple[AutoAPIBatch, ...]:
    """Build deterministic per-vehicle batches, merging duplicate selector rows."""

    directories = discover_autoapi_source_directories(source_root)

    supplied = (
        normalize_vehicle_list(list(selector_rows), default_region=default_region)
        if selector_rows is not None
        else ()
    )
    if not directories and not supplied:
        raise ValueError(f"no AutoAPI bundles or selector rows found under {source_root}")
    batches: list[AutoAPIBatch] = []
    matched_vehicle_keys: set[str] = set()
    for directory in directories:
        derived_rows = derive_autoapi_vehicle_rows(
            directory,
            default_region=default_region,
            source_version=source_version,
        )
        derived_selection = normalize_vehicle_list(derived_rows, default_region=default_region)
        if len(derived_selection) != 1:
            raise ValueError(f"AutoAPI bundle must resolve to one vehicle family: {directory}")
        derived = derived_selection[0]
        matching_supplied = [
            item for item in supplied if item.vehicle_key == derived.vehicle_key
        ]
        # A selector export may be coarser than the bundle's motorvehicles
        # response. Merge both observations so an identity refresh cannot
        # discard trim/engine configurations already proven by AutoAPI.
        selected = normalize_vehicle_list(
            [
                *derived_rows,
                *(
                    row
                    for item in matching_supplied
                    for row in _selection_record_rows(item)
                ),
            ],
            default_region=default_region,
        )[0]
        vehicle = {
            "year": selected.year,
            "make": selected.make,
            "model": selected.model,
            "region": selected.region or default_region,
            "drivetrain": selected.drivetrain,
        }
        if vehicle["region"] is None:
            raise ValueError(f"AutoAPI bundle vehicle has no region: {directory}")
        batches.append(
            AutoAPIBatch(
                vehicle_key=selected.vehicle_key,
                vehicle=vehicle,
                source_directory=directory,
                configurations=tuple(selected.configurations),
            )
        )
        matched_vehicle_keys.add(selected.vehicle_key)
    for selected in supplied:
        if selected.vehicle_key in matched_vehicle_keys:
            continue
        vehicle = {
            "year": selected.year,
            "make": selected.make,
            "model": selected.model,
            "region": selected.region or default_region,
            "drivetrain": selected.drivetrain,
        }
        if vehicle["region"] is None:
            raise ValueError(f"selector vehicle has no region: {selected.vehicle_key}")
        batches.append(
            AutoAPIBatch(
                vehicle_key=selected.vehicle_key,
                vehicle=vehicle,
                source_directory=None,
                configurations=tuple(selected.configurations),
            )
        )
    return tuple(sorted(batches, key=lambda item: item.vehicle_key))


def collect_autoapi_selection_rows(
    source_root: str | Path,
    *,
    default_region: str | None = None,
    source_version: str = "autoapi-local-v1",
) -> list[dict[str, Any]]:
    """Collect selector rows from every discovered AutoAPI bundle."""

    rows: list[dict[str, Any]] = []
    for directory in discover_autoapi_source_directories(source_root):
        rows.extend(
            derive_autoapi_vehicle_rows(
                directory,
                default_region=default_region,
                source_version=source_version,
            )
        )
    return rows


def execute_autoapi_batch(
    plan: Iterable[AutoAPIBatch],
    *,
    source_version: str,
    persist: bool = False,
    adapter_name: str = "autoapi-local",
    selector_rows: Iterable[Mapping[str, Any] | str] | None = None,
    selector_source_uri: str = "autoapi://local/selector-list",
) -> dict[str, Any]:
    """Normalize each vehicle bundle independently and continue after failures."""

    batches = tuple(plan)
    results: list[dict[str, Any]] = []
    selection_persistence = None
    if persist and selector_rows is not None:
        from .vehicle_selection_persistence import persist_vehicle_selection_list

        selection_persistence = persist_vehicle_selection_list(
            list(selector_rows),
            source_uri=selector_source_uri,
            source_version=source_version,
        )
    for batch in batches:
        if batch.source_directory is None:
            results.append(
                {
                    "vehicle_key": batch.vehicle_key,
                    "source_directory": None,
                    "status": "pending_source",
                    "error": "no AutoAPI source bundle matches the selector vehicle",
                }
            )
            continue
        try:
            artifacts = _read_artifacts(batch.source_directory, source_version)
            bundle = normalize_source_bundle(
                artifacts,
                str(batch.vehicle["region"]),
                expected_vehicle=batch.vehicle,
            )
            quality = evaluate_source_bundle(bundle)
            persistence = None
            if persist:
                from .bundle_persistence import persist_source_bundle

                persistence = persist_source_bundle(
                    bundle,
                    artifacts,
                    adapter_name=adapter_name,
                )
            result: dict[str, Any] = {
                "vehicle_key": batch.vehicle_key,
                "source_directory": str(batch.source_directory),
                "status": bundle.status,
                "quality_status": quality.status,
                "source_artifacts": len(artifacts),
                "articles": len(bundle.articles),
                "evidence": len(bundle.evidence),
                "quarantined": len(bundle.quarantined),
                "conflicts": len(bundle.conflicts),
            }
            if persistence is not None:
                result["persistence"] = persistence
        except Exception as error:  # noqa: BLE001 - one bad vehicle cannot stop the catalog batch
            result = {
                "vehicle_key": batch.vehicle_key,
                "source_directory": str(batch.source_directory),
                "status": "failed",
                "error": str(error),
            }
        results.append(result)
    output: dict[str, Any] = {
        "status": (
            "failed"
            if any(item["status"] == "failed" for item in results)
            else "pending_source"
            if any(item["status"] == "pending_source" for item in results)
            else "completed"
        ),
        "vehicle_count": len(results),
        "results": results,
    }
    if selection_persistence is not None:
        output["selection_persistence"] = selection_persistence
        from .autoapi_job_persistence import persist_autoapi_article_fetch_jobs

        output["article_fetch_jobs"] = persist_autoapi_article_fetch_jobs(
            batches,
            results,
            selector_persistence=selection_persistence,
            source_version=source_version,
            adapter_name=adapter_name,
        )
    return output


def _read_artifacts(directory: Path, source_version: str) -> list[SourceArtifact]:
    connector = DirectorySourceConnector(directory, source_version)
    return [adapt_source_resource(resource) for resource in connector.fetch({})]


def _base_row(vehicle: Mapping[str, Any], *, trim: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "year": vehicle["model_year"],
        "make": vehicle["make"],
        "model": vehicle["model"],
        "region": vehicle["region"],
    }
    if vehicle.get("drivetrain"):
        row["drivetrain"] = vehicle["drivetrain"]
    if trim:
        row["trim"] = trim
    row["vehicle_key"] = vehicle["vehicle_key"]
    return row


def _trim_from_model_name(base_model: str, model_name: str) -> str | None:
    base = re.sub(r"\s+", " ", str(base_model).strip())
    candidate = re.sub(r"\s+", " ", model_name.strip())
    if candidate.casefold() == base.casefold():
        return None
    if candidate.casefold().startswith(base.casefold() + " "):
        return candidate[len(base):].strip() or None
    return candidate


def _engine_displacement_text(engine_name: str) -> str | None:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*L(?:T)?\b", engine_name, re.IGNORECASE)
    if match is None:
        return None
    return f"{float(match.group(1)):g}L"


def load_selector_rows(path: str | Path) -> list[Mapping[str, Any] | str]:
    """Load an array or an AutoAPI-style ``body`` array from JSON."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return _expand_selector_rows(payload)
    if isinstance(payload, dict) and isinstance(payload.get("body"), list):
        return _expand_selector_rows(payload["body"])
    if isinstance(payload, dict) and isinstance(payload.get("vehicles"), list):
        return _expand_selector_rows(payload["vehicles"])
    raise ValueError("selector JSON must contain an array, body array, or vehicles array")


def _expand_selector_rows(values: list[Any]) -> list[Mapping[str, Any] | str]:
    """Flatten common AutoAPI selector nesting into one row per configuration."""

    expanded: list[Mapping[str, Any] | str] = []
    for value in values:
        if isinstance(value, str):
            expanded.append(value)
            continue
        if not isinstance(value, Mapping):
            raise TypeError("selector JSON rows must be mappings or strings")
        base = dict(value)
        models = base.pop("models", None)
        if isinstance(models, list):
            for model in models:
                if not isinstance(model, Mapping):
                    raise TypeError("selector model rows must be mappings")
                expanded.extend(_expand_selector_rows([{**base, **dict(model)}]))
            continue
        engines = base.pop("engines", None)
        if isinstance(engines, list) and engines:
            for engine in engines:
                if not isinstance(engine, Mapping):
                    raise TypeError("selector engine rows must be mappings")
                expanded.append({**base, **dict(engine)})
            continue
        expanded.append(base)
    return expanded


def _selection_record_rows(record: Any) -> list[dict[str, Any]]:
    """Convert a normalized selector family back into mergeable observations."""

    rows: list[dict[str, Any]] = []
    for configuration in record.configurations:
        if configuration.get("status") == "needs_review":
            continue
        row: dict[str, Any] = {
            "year": record.year,
            "make": record.make,
            "model": record.model,
            "region": record.region,
        }
        for field in ("body_style", "drivetrain"):
            value = getattr(record, field)
            if value is not None:
                row[field] = value
        for field in ("trim", "engine_displacement_l"):
            value = configuration.get(field)
            if value is not None:
                row[field] = value
        rows.append(row)
    return rows


__all__ = [
    "AutoAPIBatch",
    "build_autoapi_batch_plan",
    "collect_autoapi_selection_rows",
    "derive_autoapi_vehicle_rows",
    "discover_autoapi_source_directories",
    "execute_autoapi_batch",
    "load_selector_rows",
    "normalize_vehicle_list_json",
]
