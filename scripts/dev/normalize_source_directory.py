"""Normalize a local heterogeneous source drop without uploading its raw files."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))

from autodata_ingestion.directory_connector import DirectorySourceConnector  # noqa: E402
from autodata_ingestion.source_adapters import SourceArtifact, adapt_source_resource  # noqa: E402
from autodata_ingestion.quality import evaluate_source_bundle  # noqa: E402
from autodata_ingestion.source_bundle import normalize_source_bundle  # noqa: E402


def summarize_source_artifacts(artifacts: Iterable[SourceArtifact]) -> list[dict[str, Any]]:
    """Return deterministic, payload-free inspection records for source artifacts."""

    report: list[dict[str, Any]] = []
    for artifact in artifacts:
        metadata = artifact.metadata
        if artifact.kind == "quarantine":
            extraction_status = "quarantined"
        else:
            extraction_status = str(
                metadata.get(
                    "extraction_status",
                    "candidate_ready" if artifact.candidates else "needs_review",
                )
            )
        reasons: set[str] = set()
        if artifact.kind == "quarantine":
            reasons.add(str(metadata.get("quarantine_reason", "unsupported_artifact")))
        if extraction_status == "needs_review":
            reasons.add("extraction_needs_review")
        if metadata.get("embedded_needs_review"):
            reasons.add("embedded_resource_needs_review")
        if metadata.get("page_errors"):
            reasons.add("page_extraction_error")
        candidate_kinds = dict(sorted(Counter(candidate.kind for candidate in artifact.candidates).items()))
        item: dict[str, Any] = {
            "source_uri": artifact.source_uri,
            "source_version": artifact.source_version,
            "media_type": artifact.media_type,
            "content_sha256": artifact.content_sha256,
            "object_key": artifact.object_key,
            "kind": artifact.kind,
            "candidate_count": len(artifact.candidates),
            "candidate_kinds": candidate_kinds,
            "extraction_status": extraction_status,
            "needs_review": bool(reasons),
            "review_reasons": sorted(reasons),
        }
        for field in ("extraction_mode", "embedded_resources", "page_count", "rasterized_page_count"):
            if field in metadata:
                value = metadata[field]
                if field == "embedded_resources":
                    value = [
                        {
                            key: record[key]
                            for key in ("locator", "media_type", "content_sha256", "candidate_count", "extraction_status")
                            if key in record
                        }
                        for record in value
                    ]
                item[field] = value
        report.append(item)
    return sorted(report, key=lambda item: (item["source_uri"], item["content_sha256"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--region", default="US")
    parser.add_argument("--source-version", default="local-directory-v1")
    parser.add_argument("--persist", action="store_true", help="persist local artifacts and normalized records to the configured local stack")
    parser.add_argument("--adapter-name", default="local-directory")
    args = parser.parse_args()
    if not args.directory.is_dir():
        raise SystemExit(f"source directory does not exist: {args.directory}")

    artifacts = []
    connector = DirectorySourceConnector(args.directory, args.source_version)
    for resource in connector.fetch({}):
        try:
            artifacts.append(adapt_source_resource(resource))
        except ValueError as error:
            print(f"source adapter failed for {resource.source_uri}: {error}", file=sys.stderr)
            raise SystemExit(1) from error

    bundle = normalize_source_bundle(artifacts, args.region)
    quality = evaluate_source_bundle(bundle)
    persistence = None
    if args.persist:
        from autodata_ingestion.bundle_persistence import persist_source_bundle

        persistence = persist_source_bundle(bundle, artifacts, adapter_name=args.adapter_name)
    print(
        json.dumps(
            {
                "status": bundle.status,
                "vehicle": bundle.vehicle,
                "counts": {
                    "models": len(bundle.models),
                    "powertrains": len(bundle.powertrains),
                    "parts": len(bundle.parts),
                    "articles": len(bundle.articles),
                    "documents": len(bundle.documents),
                    "diagrams": len(bundle.diagrams),
                    "evidence": len(bundle.evidence),
                    "quarantined": len(bundle.quarantined),
                    "conflicts": len(bundle.conflicts),
                },
                "quarantine_reasons": sorted({item.get("reason") for item in bundle.quarantined}),
                "conflict_fields": sorted({item.get("field") for item in bundle.conflicts}),
                "quality": quality.to_dict(),
                "persistence": persistence,
                "source_report": summarize_source_artifacts(artifacts),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
