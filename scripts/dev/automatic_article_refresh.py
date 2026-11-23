#!/usr/bin/env python3
"""Preview or schedule a bounded explicit selection of stored articles for auto rewrite.

Selection JSON: [{"canonical_article_id":"UUID","expected_source_revision_id":"UUID"}].
Apply may call the configured source connector and model when the worker runs;
this command itself never contacts either. Published canonical articles are kept.
With --source-bound-from, select one unpublished article to draft from its existing
source revision and supply the UUID of its previous rejected job. Run
article_worker.py --job-id with the returned job ID to process that exact job.
Use --correct-from with a failed v2 job and a model-call budget for passage correction.
"""
import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers/ingestion-python/src"))
from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILES, MAX_CORRECTION_CALLS
from autodata_ingestion.procedure_rewrite_auto import PROFILE
from autodata_ingestion.source_job_persistence import (
    refresh_article_job, schedule_source_bound_correction, schedule_source_bound_rewrite,
)


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
        if row["target_rewrite_profile_version"] in AUTOMATIC_REWRITE_PROFILES:
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
    drafting = parser.add_mutually_exclusive_group()
    drafting.add_argument("--source-bound-from", type=UUID, metavar="PRIOR_JOB_ID",
                          help="schedule one new draft from the selected article's retained source")
    drafting.add_argument("--correct-from", type=UUID, metavar="FAILED_V2_JOB_ID",
                          help="correct a failed draft against the same retained source")
    parser.add_argument("--model-call-budget", type=int, metavar=f"1-{MAX_CORRECTION_CALLS}")
    args = parser.parse_args(argv)
    if args.selection.stat().st_size > 64 * 1024:
        raise ValueError("AUTOMATIC_SELECTION_LIMIT")
    targets = selection(json.loads(args.selection.read_text()))
    prior_job = args.source_bound_from or args.correct_from
    if prior_job is not None and (len(targets) != 1 or not args.apply):
        parser.error("retained-source drafting requires one selected article and --apply")
    if args.correct_from is not None and (
        args.model_call_budget is None or not 1 <= args.model_call_budget <= MAX_CORRECTION_CALLS
    ):
        parser.error(f"--correct-from requires --model-call-budget from 1 through {MAX_CORRECTION_CALLS}")
    if args.correct_from is None and args.model_call_budget is not None:
        parser.error("--model-call-budget requires --correct-from")
    if repo is None:
        from autodata_ingestion.worker import ArticleRepository
        repo = ArticleRepository()
    if prior_job is not None:
        target, = targets
        arguments = dict(
            expected_job_id=prior_job, expected_source_revision_id=UUID(target["expected_source_revision_id"]),
            actor=args.actor, reason=args.reason,
        )
        article_id = UUID(target["canonical_article_id"])
        if args.correct_from is not None:
            job = schedule_source_bound_correction(repo, article_id, model_call_budget=args.model_call_budget,
                                                   **arguments)
        else:
            job = schedule_source_bound_rewrite(repo, article_id, **arguments)
        results = [{**target, "job_id": str(job.job_id), "action": "scheduled" if job.created else "joined_existing"}]
    else:
        results = refresh_selected(repo, targets, actor=args.actor, reason=args.reason, apply=args.apply)
    print(json.dumps({"mode":"apply" if args.apply else "preview", "items":results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(json.dumps({"status":"error", "code":"AUTOMATIC_REFRESH_FAILED"}), file=sys.stderr)
        sys.exit(1)
