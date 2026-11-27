#!/usr/bin/env python3
"""Privileged local preview and publication of a retained article correction."""
import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

from reproject_article_source import article_archive
from autodata_ingestion.article_content_review import _read_private_json
from autodata_ingestion.published_media_publication import (
    preview_published_media_repair,
    publish_retained_media_repair,
)
from autodata_ingestion.source_svg_archive import stage_svg_archive


def main(argv=None, *, repo=None, object_store=None, registry=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preview = commands.add_parser("preview")
    preview.add_argument("--article-id", type=UUID, required=True)
    preview.add_argument("--source-revision-id", type=UUID, required=True)
    preview.add_argument("--output", type=Path, required=True)
    repairs = preview.add_mutually_exclusive_group()
    repairs.add_argument("--ordinals", action="store_true",
                         help="Recover authored ordered-list numbers from the retained source")
    repairs.add_argument("--table-spans", action="store_true",
                         help="Recover authored table spans from the retained source")
    repairs.add_argument("--table-geometry", action="store_true",
                         help="Recover authored table headers and spans from the retained source")
    repairs.add_argument("--svg-archive", type=Path, help="Private SVG input directory from stage-svg")
    stage = commands.add_parser("stage-svg")
    stage.add_argument("--article-id", type=UUID, required=True)
    stage.add_argument("--source-revision-id", type=UUID, required=True)
    stage.add_argument("--output", type=Path, required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("--expected", type=Path, required=True, help="Private manifest.json from preview")
    publish.add_argument("--reviewer", required=True)
    publish.add_argument("--allowlist", type=Path, required=True)
    publish.add_argument("--rationale", required=True)
    publish.add_argument("--svg-archive", type=Path, help="The same private SVG inputs used for preview")
    for command in (preview, publish):
        command.add_argument("--fixture-mode", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "stage-svg":
        from autodata_ingestion.source_connector_client import source_connector_registry
        from autodata_ingestion.worker import ArticleRepository

        result = stage_svg_archive(
            repo if repo is not None else ArticleRepository(), args.article_id, args.source_revision_id,
            registry=registry if registry is not None else source_connector_registry(include_defaults=False),
            destination=args.output,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    repo, object_store = article_archive(repo, object_store)
    if args.command == "preview":
        result = preview_published_media_repair(
            repo, args.article_id, args.source_revision_id, object_store=object_store,
            destination=args.output, fixture_mode=args.fixture_mode, ordinals=args.ordinals,
            table_spans=args.table_spans, table_geometry=args.table_geometry, svg_archive=args.svg_archive,
        )
    else:
        result = publish_retained_media_repair(
            repo, expected=_read_private_json(args.expected), object_store=object_store,
            reviewer_id=args.reviewer, allowlist=args.allowlist, rationale=args.rationale,
            fixture_mode=args.fixture_mode, svg_archive=args.svg_archive,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(json.dumps({"status": "error", "code": "PUBLISHED_MEDIA_REPAIR_FAILED"}), file=sys.stderr)
        sys.exit(1)
