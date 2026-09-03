"""Normalize a local heterogeneous source drop without uploading its raw files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))

from autodata_ingestion.source_adapters import SourceResource, adapt_source_resource  # noqa: E402
from autodata_ingestion.quality import evaluate_source_bundle  # noqa: E402
from autodata_ingestion.source_bundle import normalize_source_bundle  # noqa: E402


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
    for path in sorted(item for item in args.directory.rglob("*") if item.is_file()):
        resource = SourceResource.from_bytes(
            source_uri=f"file://{path.relative_to(args.directory)}",
            source_version=args.source_version,
            payload=path.read_bytes(),
            media_type=None,
            locator=str(path.relative_to(args.directory)),
        )
        try:
            artifacts.append(adapt_source_resource(resource))
        except ValueError as error:
            print(f"source adapter failed for {path}: {error}", file=sys.stderr)
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
                },
                "quarantine_reasons": sorted({item.get("reason") for item in bundle.quarantined}),
                "quality": quality.to_dict(),
                "persistence": persistence,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
