#!/usr/bin/env python3
"""Preview or schedule a bounded explicit selection of stored articles for auto rewrite.

Selection JSON: [{"canonical_article_id":"UUID","expected_source_revision_id":"UUID"}].
Apply may call the configured source connector and model when the worker runs;
this command itself never contacts either. Published canonical articles are kept.
With --source-bound-from, select one unpublished article to draft from its existing
source revision and supply the UUID of its previous rejected job. Run
article_worker.py --job-id with the returned job ID to process that exact job.
Use --correct-from with a failed v2 job and a model-call budget for passage correction.
Add --by-sentence to try a sentence pass on the remaining rejected prose.
Use --correct-first-draft-from with a failed v1 job to correct its saved reply
by sentence, without fetching the source again or requesting a full v2 draft.
Use --recover-first-draft-from with a failed v1 job, a registered recovery
method and the exact recovered document hash to publish from a saved reply.
Use --recover-from with a terminal v3 job to stage a correction from its saved replies.
Use --recover-staged-media-from with a failed positioned media refresh and its
expected published revision to replay the exact archived replies and publish.
Use --repair-retained-procedure-from with the exact served revision and both
document hashes to publish an audited correction from its saved reply.
Use --repair-retained-note-labels-from with the exact served descriptor and
revision and both document hashes to restore authored Note labels.
"""
import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers/ingestion-python/src"))
from autodata_ingestion.article_lifecycle_store import recover_source_bound_correction
from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILES, MAX_CORRECTION_CALLS
from autodata_ingestion.procedure_rewrite_auto import PROFILE
from autodata_ingestion.procedure_rewrite_recovery import (
    ARCHIVED_FIRST_DRAFT_RECOVERY_METHODS, BANKONE_ARCHIVE_STRUCTURE_VERSIONS,
)
from autodata_ingestion.procedure_rewrite_sentence_correction import MAX_SENTENCE_CORRECTION_CALLS
from autodata_ingestion.retained_note_label_repair import repair_retained_note_labels
from autodata_ingestion.retained_procedure_repair import repair_retained_procedure
from autodata_ingestion.source_job_persistence import (
    publish_source_bound_first_draft, refresh_article_job, schedule_source_bound_correction,
    schedule_source_bound_rewrite,
)
from autodata_ingestion.staged_media_reply_recovery import recover_staged_media_reply


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


def main(argv=None, *, repo=None, object_store=None):
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
    drafting.add_argument("--correct-first-draft-from", type=UUID, metavar="FAILED_V1_JOB_ID",
                          help="correct the original failed draft by sentence using the exact stored source")
    drafting.add_argument("--recover-first-draft-from", type=UUID, metavar="FAILED_V1_JOB_ID",
                          help="publish a checked recovery of this job's saved reply")
    drafting.add_argument("--recover-from", type=UUID, metavar="FAILED_V3_JOB_ID",
                          help="stage a correction using this job's archived model replies")
    drafting.add_argument("--recover-staged-media-from", type=UUID, metavar="FAILED_REFRESH_JOB_ID",
                          help="publish a positioned-media revision using the exact archived replies")
    drafting.add_argument("--repair-retained-procedure-from", type=UUID, metavar="PUBLISHED_JOB_ID",
                          help="publish a checked procedure correction using its exact archived reply")
    drafting.add_argument("--repair-retained-note-labels-from", type=UUID, metavar="PUBLISHED_V3_JOB_ID",
                          help="restore leading authored Note labels using the exact archived reply")
    parser.add_argument("--expected-published-revision-id", type=UUID,
                        help="bind archived-reply replay to the exact served canonical revision")
    parser.add_argument("--expected-published-hash", metavar="SHA256")
    parser.add_argument("--expected-repaired-hash", metavar="SHA256")
    parser.add_argument("--expected-descriptor-snapshot-id", type=UUID,
                        help="bind a Note label repair to the exact active descriptor")
    parser.add_argument("--first-draft-recovery-method", choices=ARCHIVED_FIRST_DRAFT_RECOVERY_METHODS)
    parser.add_argument("--expected-first-draft-recovery-hash", metavar="SHA256",
                        help="bind the recovery to the checked v1 document")
    parser.add_argument("--model-call-budget", type=int, metavar=f"1-{MAX_CORRECTION_CALLS}")
    parser.add_argument("--by-sentence", action="store_true", help="use sentence correction for the selected failed draft")
    args = parser.parse_args(argv)
    if args.selection.stat().st_size > 64 * 1024:
        raise ValueError("AUTOMATIC_SELECTION_LIMIT")
    targets = selection(json.loads(args.selection.read_text()))
    repair = args.repair_retained_procedure_from or args.repair_retained_note_labels_from
    correction_job = args.correct_from or args.correct_first_draft_from
    retained_job = (args.source_bound_from or correction_job or args.recover_first_draft_from or args.recover_from
                    or args.recover_staged_media_from or repair)
    if retained_job is not None and (len(targets) != 1 or not args.apply):
        parser.error("retained-source drafting requires one selected article and --apply")
    if args.correct_from is not None and (
        args.model_call_budget is None or not 1 <= args.model_call_budget <= MAX_CORRECTION_CALLS
    ):
        parser.error(f"--correct-from requires --model-call-budget from 1 through {MAX_CORRECTION_CALLS}")
    if args.correct_first_draft_from is not None and (
        args.model_call_budget is None or not 1 <= args.model_call_budget <= MAX_SENTENCE_CORRECTION_CALLS
    ):
        parser.error(f"--correct-first-draft-from requires --model-call-budget from 1 through {MAX_SENTENCE_CORRECTION_CALLS}")
    if correction_job is None and args.model_call_budget is not None:
        parser.error("--model-call-budget requires a correction job")
    if args.by_sentence and (args.correct_from is None or args.model_call_budget > MAX_SENTENCE_CORRECTION_CALLS):
        parser.error(f"--by-sentence requires --correct-from and a budget of 1 through {MAX_SENTENCE_CORRECTION_CALLS}")
    if args.recover_first_draft_from is not None:
        if not (args.first_draft_recovery_method and args.expected_first_draft_recovery_hash):
            parser.error("first-draft publication requires --first-draft-recovery-method and --expected-first-draft-recovery-hash")
    elif args.first_draft_recovery_method or args.expected_first_draft_recovery_hash:
        parser.error("first-draft recovery options require --recover-first-draft-from")
    if bool(args.recover_staged_media_from or repair) != bool(args.expected_published_revision_id):
        parser.error("archived-reply publication requires --expected-published-revision-id")
    if repair and not (args.expected_published_hash and args.expected_repaired_hash):
        parser.error("retained publication repairs require both document hashes")
    if not repair and (args.expected_published_hash or args.expected_repaired_hash):
        parser.error("document hashes require a retained publication repair")
    if bool(args.repair_retained_note_labels_from) != bool(args.expected_descriptor_snapshot_id):
        parser.error("Note label repair requires --expected-descriptor-snapshot-id")
    if repo is None:
        from autodata_ingestion.worker import ArticleRepository
        repo = ArticleRepository()
    if retained_job is not None:
        target, = targets
        arguments = dict(
            expected_job_id=retained_job, expected_source_revision_id=UUID(target["expected_source_revision_id"]),
            actor=args.actor, reason=args.reason,
        )
        article_id = UUID(target["canonical_article_id"])
        if args.repair_retained_note_labels_from is not None:
            revision = repair_retained_note_labels(
                repo, article_id, expected_published_revision_id=args.expected_published_revision_id,
                expected_published_hash=args.expected_published_hash, expected_repaired_hash=args.expected_repaired_hash,
                expected_descriptor_snapshot_id=args.expected_descriptor_snapshot_id, **arguments,
            )
            results = [{**target, "prior_job_id": str(retained_job), "revision_id": str(revision), "action": "published"}]
        elif args.repair_retained_procedure_from is not None:
            revision = repair_retained_procedure(
                repo, article_id, expected_published_revision_id=args.expected_published_revision_id,
                expected_published_hash=args.expected_published_hash, expected_repaired_hash=args.expected_repaired_hash,
                **arguments,
            )
            results = [{**target, "prior_job_id": str(retained_job), "revision_id": str(revision), "action": "published"}]
        elif args.recover_staged_media_from is not None:
            revision = recover_staged_media_reply(
                repo, article_id, expected_published_revision_id=args.expected_published_revision_id, **arguments,
            )
            results = [{**target, "job_id": str(retained_job), "revision_id": str(revision), "action": "published"}]
        elif args.recover_first_draft_from is not None:
            if args.first_draft_recovery_method in BANKONE_ARCHIVE_STRUCTURE_VERSIONS:
                from reproject_article_source import article_archive

                _, objects = article_archive(repo=repo, object_store=object_store)
                arguments["object_store"] = objects
            job = publish_source_bound_first_draft(
                repo, article_id, recovery_method=args.first_draft_recovery_method,
                expected_recovery_hash=args.expected_first_draft_recovery_hash, **arguments,
            )
            results = [{
                **target, "prior_job_id": str(retained_job), "job_id": str(job.job_id),
                "revision_id": str(job.published_revision_id),
                "action": "published" if job.created else "joined_existing",
            }]
        elif args.recover_from is not None:
            revision = recover_source_bound_correction(repo, article_id, **arguments)
            results = [{**target, "job_id": str(retained_job), "revision_id": str(revision), "action": "recovered"}]
        else:
            if args.correct_first_draft_from is not None:
                job = schedule_source_bound_correction(repo, article_id, model_call_budget=args.model_call_budget,
                                                       by_sentence=True, first_draft=True, **arguments)
            elif args.correct_from is not None:
                job = schedule_source_bound_correction(repo, article_id, model_call_budget=args.model_call_budget,
                                                       by_sentence=args.by_sentence,
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
