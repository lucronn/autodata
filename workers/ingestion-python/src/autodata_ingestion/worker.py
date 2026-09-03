"""Deterministic process boundary for the fast-lane worker."""

from __future__ import annotations

import json
import os
import time


def run_once() -> dict[str, object]:
    """Run one explicitly configured local source-drop job or return a heartbeat."""

    source_directory = os.getenv("AUTODATA_SOURCE_DIRECTORY", "").strip()
    if source_directory:
        return run_source_directory(source_directory)
    source_uri = os.getenv("AUTODATA_SOURCE_URI", "").strip()
    if source_uri:
        return run_source_uri(source_uri)

    return {"worker": "ingestion", "lane": "fast", "status": "idle"}


def run_source_directory(directory: str) -> dict[str, str | int | list[str]]:
    """Normalize one local source drop and optionally persist its records."""

    from .directory_connector import DirectorySourceConnector

    connector = DirectorySourceConnector(
        directory,
        os.getenv("AUTODATA_SOURCE_VERSION", "local-directory-v1"),
    )
    return _run_connector(connector)


def run_source_uri(source_uri: str) -> dict[str, str | int | list[str]]:
    """Fetch one HTTP(S) source URI and run the shared intake pipeline."""

    from .http_connector import HttpSourceConnector

    connector = HttpSourceConnector(
        source_uri,
        os.getenv("AUTODATA_SOURCE_VERSION", "") or None,
        timeout_seconds=float(os.getenv("AUTODATA_SOURCE_HTTP_TIMEOUT_SECONDS", "30")),
        max_bytes=int(os.getenv("AUTODATA_SOURCE_MAX_BYTES", str(50 * 1024 * 1024))),
        request_headers=_source_request_headers(),
    )
    return _run_connector(connector)


def _source_request_headers() -> dict[str, str]:
    raw_headers = os.getenv("AUTODATA_SOURCE_REQUEST_HEADERS_JSON", "").strip()
    if not raw_headers:
        return {}
    try:
        headers = json.loads(raw_headers)
    except json.JSONDecodeError as error:
        raise ValueError("AUTODATA_SOURCE_REQUEST_HEADERS_JSON must be valid JSON") from error
    if not isinstance(headers, dict) or any(not isinstance(value, str) for value in headers.values()):
        raise ValueError("AUTODATA_SOURCE_REQUEST_HEADERS_JSON must be an object of string values")
    return {str(key): value for key, value in headers.items()}


def _run_connector(connector: object) -> dict[str, str | int | list[str]]:
    from .quality import evaluate_source_bundle
    from .source_adapters import adapt_source_resource
    from .source_bundle import normalize_source_bundle

    resources = connector.fetch({})
    artifacts = [adapt_source_resource(resource) for resource in resources]
    bundle = normalize_source_bundle(
        artifacts,
        os.getenv("AUTODATA_SOURCE_REGION", "US"),
    )
    quality = evaluate_source_bundle(bundle)
    persistence = None
    if os.getenv("AUTODATA_SOURCE_PERSIST") == "1":
        from .bundle_persistence import persist_source_bundle

        persistence = persist_source_bundle(bundle, artifacts, adapter_name=connector.name)

    result: dict[str, str | int | list[str]] = {
        "worker": "ingestion",
        "lane": "fast",
        "status": bundle.status if quality.status == "pass" else quality.status,
        "bundle_status": bundle.status,
        "quality_status": quality.status,
        "source_artifacts": len(artifacts),
        "evidence": len(bundle.evidence),
        "quarantined": len(bundle.quarantined),
        "conflicts": len(bundle.conflicts),
        "quarantine_reasons": sorted({str(item.get("reason")) for item in bundle.quarantined}),
    }
    if bundle.vehicle is not None:
        result["vehicle_key"] = bundle.vehicle["vehicle_key"]
    if persistence is not None:
        result["persistence_status"] = str(persistence.get("status", "unknown"))
    return result


def main() -> None:
    interval = float(os.getenv("AUTODATA_WORKER_HEARTBEAT_SECONDS", "30"))
    if os.getenv("AUTODATA_WORKER_ONCE") == "1":
        print(json.dumps(run_once(), sort_keys=True))
        return
    while True:
        print(json.dumps(run_once(), sort_keys=True), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
