#!/usr/bin/env python3
"""Preview one bounded retained body projection; apply requires preview hash bindings."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers/ingestion-python/src"))
from autodata_ingestion.source_revision_reprojection import reproject_stored_source, apply_source_reprojection
from autodata_ingestion.article_lifecycle_types import article_id


def main(argv=None, *, repo=None, object_store=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-id", type=UUID, required=True)
    parser.add_argument("--source-revision-id", type=UUID, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    parser.add_argument("--actor")
    parser.add_argument("--reason")
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--expected-body-sha256")
    args = parser.parse_args(argv)
    if args.apply and not all((args.actor, args.reason, args.expected_fingerprint, args.expected_body_sha256)):
        parser.error("--apply requires --actor, --reason, --expected-fingerprint and --expected-body-sha256")
    if repo is None or object_store is None:
        from autodata_ingestion.worker import ArticleRepository, ArticleObjectStore
        if repo is None: repo = ArticleRepository()
        if object_store is None:
            endpoint = os.environ["AUTODATA_S3_ENDPOINT"]
            parsed = urlsplit(endpoint if "://" in endpoint else "http://" + endpoint)
            object_store = ArticleObjectStore(endpoint=parsed.netloc, secure=parsed.scheme == "https",
                access_key=os.environ["AUTODATA_S3_ACCESS_KEY"], secret_key=os.environ["AUTODATA_S3_SECRET_KEY"],
                bucket=os.environ["AUTODATA_SOURCE_BUCKET"])
    captured = reproject_stored_source(repo, args.source_revision_id, object_store=object_store)
    if article_id(captured.context.key) != args.article_id:
        raise ValueError("SOURCE_REPLAY_ARTICLE_MISMATCH")
    body_sha = captured.resource_manifest[0]["sha256"]
    result = {"status": "preview", "article_id": str(args.article_id), "source_revision_id": str(args.source_revision_id),
        "projection_version": captured.projection_version, "source_fingerprint": captured.source_fingerprint,
        "body_sha256": body_sha, "body_snapshot_id": str(captured.body_source_snapshot_id),
        "resource_count": len(captured.resource_manifest), "block_count": len(captured.source_document["blocks"]),
        "image_count": len(captured.source_images), "text_length": len(captured.source_body)}
    if args.apply:
        if (args.expected_fingerprint != captured.source_fingerprint or args.expected_body_sha256 != body_sha):
            raise ValueError("SOURCE_REPLAY_PREVIEW_BINDING_MISMATCH")
        result.update(apply_source_reprojection(repo, args.article_id, args.source_revision_id, captured,
                                               actor=args.actor, reason=args.reason))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception:
        # Never print provider refs, raw body, environment values or SDK exceptions.
        print(json.dumps({"status": "error", "code": "SOURCE_REPLAY_FAILED"}), file=sys.stderr)
        sys.exit(1)
