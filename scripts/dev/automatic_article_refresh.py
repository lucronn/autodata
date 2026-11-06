#!/usr/bin/env python3
"""Preview or schedule a bounded explicit selection of stored articles for auto rewrite.

Selection JSON: [{"canonical_article_id":"UUID","expected_source_revision_id":"UUID"}].
Apply may call the configured source connector and model when the worker runs;
this command itself never contacts either. Published canonical articles are kept.
"""
import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers/ingestion-python/src"))
from autodata_ingestion.source_job_persistence import refresh_article_job
from autodata_ingestion.procedure_rewrite_auto import PROFILE


def selection(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 100:
        raise ValueError("AUTOMATIC_SELECTION_INVALID")
    seen = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != {"canonical_article_id", "expected_source_revision_id"}:
            raise ValueError("AUTOMATIC_SELECTION_INVALID")
        for key in row:
            if not isinstance(row[key], str) or str(UUID(row[key])) != row[key]:
                raise ValueError("AUTOMATIC_SELECTION_INVALID")
        if row["canonical_article_id"] in seen:
            raise ValueError("AUTOMATIC_SELECTION_DUPLICATE")
        seen.add(row["canonical_article_id"])
    return value


def refresh_selected(repo, targets, *, actor, reason, apply=False):
    targets = selection(targets)
    if not actor.strip() or not reason.strip():
        raise ValueError("AUTOMATIC_REFRESH_REASON_REQUIRED")
    results = []
    for target in targets:
        with repo.connect() as conn:
            row = conn.execute("""SELECT a.current_source_revision_id,a.current_canonical_revision_id,
                a.target_rewrite_profile_version,j.status FROM canonical_articles a
                LEFT JOIN source_fetch_jobs j ON j.source_fetch_job_id=a.current_job_id
                WHERE a.canonical_article_id=%s""", (target["canonical_article_id"],)).fetchone()
        if row is None or str(row["current_source_revision_id"]) != target["expected_source_revision_id"]:
            raise ValueError("AUTOMATIC_SOURCE_CHANGED")
        if row["target_rewrite_profile_version"] == PROFILE:
            action = "already_automatic"
        elif row["current_canonical_revision_id"] is not None:
            action = "keep_published"
        elif row["status"] in {"pending", "processing", "failed"}:
            raise ValueError("AUTOMATIC_SOURCE_BUSY")
        elif apply:
            job = refresh_article_job(repo, target["canonical_article_id"], actor=actor, reason=reason,
                rewrite_profile_version=PROFILE, expected_source_revision_id=target["expected_source_revision_id"])
            action = "scheduled" if job.created else "joined_existing"
        else:
            action = "would_refresh"
        results.append({**target, "action":action})
    return results


def main(argv=None, *, repo=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.selection.stat().st_size > 64 * 1024:
        raise ValueError("AUTOMATIC_SELECTION_LIMIT")
    targets = selection(json.loads(args.selection.read_text()))
    if repo is None:
        from autodata_ingestion.worker import ArticleRepository
        repo = ArticleRepository()
    results = refresh_selected(repo, targets, actor=args.actor, reason=args.reason, apply=args.apply)
    print(json.dumps({"mode":"apply" if args.apply else "preview", "items":results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(json.dumps({"status":"error", "code":"AUTOMATIC_REFRESH_FAILED"}), file=sys.stderr)
        sys.exit(1)
