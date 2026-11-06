#!/usr/bin/env python3
"""Privileged local full-article export/approve/reject/correct command.

--expected is a private JSON file containing every exported bindings field.
Corrections use the complete renderer response shape and require independent
approval after correction; the correct command appends a rejection/review wait.
"""
import argparse
import json
from pathlib import Path
import re
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers/ingestion-python/src"))
from autodata_ingestion.article_content_review import (
    PROFILE, _read_private_json, export_review, record_review, export_failed_review, record_failed_correction,
)


def _expected(path):
    value = _read_private_json(path)
    fields = {"job_id", "article_id", "source_revision_id", "candidate_revision_id", "request_generation",
        "profile_version", "normalization_version", "identity_key", "source_fingerprint", "source_hash", "candidate_hash"}
    if (not isinstance(value, dict) or set(value) != fields
        or type(value["request_generation"]) is not int or value["request_generation"] < 1
        or value["profile_version"] != PROFILE
        or not isinstance(value["normalization_version"], str) or not value["normalization_version"].strip()
        or not isinstance(value["identity_key"], str) or not value["identity_key"].strip()):
        raise ValueError("CONTENT_REVIEW_EXPECTED_INVALID")
    for key in ("job_id", "article_id", "source_revision_id", "candidate_revision_id"):
        if str(UUID(value[key])) != value[key]:
            raise ValueError("CONTENT_REVIEW_EXPECTED_INVALID")
    for key in ("source_fingerprint", "source_hash", "candidate_hash"):
        if not isinstance(value[key], str) or not re.fullmatch(r"[a-f0-9]{64}", value[key]):
            raise ValueError("CONTENT_REVIEW_EXPECTED_INVALID")
    return value


def main(argv=None, *, repo=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("export", "approve", "reject", "correct", "export-failed", "correct-failed"):
        sub = commands.add_parser(command)
        sub.add_argument("--expected", type=Path, required=True)
        if command.endswith("-failed"):
            sub.add_argument("--failed-attempt-id", required=True)
            sub.add_argument("--failed-response-hash", required=True)
        if command in ("export", "export-failed"):
            sub.add_argument("--output", type=Path, required=True)
        else:
            sub.add_argument("--reviewer", required=True)
            sub.add_argument("--allowlist", type=Path, required=True)
            sub.add_argument("--rationale", required=True)
            sub.add_argument("--full-content-reviewed", action="store_true")
            sub.add_argument("--retention-reviews", type=Path)
            sub.add_argument("--corrections", type=Path, required=command in ("correct", "correct-failed"))
            sub.add_argument("--fixture-mode", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "approve" and not args.full_content_reviewed:
        parser.error("approve requires --full-content-reviewed after complete independent source comparison")
    expected = _expected(args.expected)
    if repo is None:
        from autodata_ingestion.worker import ArticleRepository
        repo = ArticleRepository()
    failed = {}
    if args.command.endswith("-failed"):
        if (str(UUID(args.failed_attempt_id)) != args.failed_attempt_id
            or not re.fullmatch(r"[a-f0-9]{64}", args.failed_response_hash)):
            raise ValueError("CONTENT_REVIEW_ORIGIN_INVALID")
        failed = dict(failed_attempt_id=args.failed_attempt_id,failed_response_hash=args.failed_response_hash)
    if args.command in ("export", "export-failed"):
        export = export_failed_review if failed else export_review
        result = export(repo, expected=expected, destination=args.output, **failed)
    else:
        retention_reviews = _read_private_json(args.retention_reviews) if args.retention_reviews else {}
        correction = _read_private_json(args.corrections) if args.corrections else None
        record = record_failed_correction if failed else record_review
        decision = {} if failed else dict(decision="APPROVED" if args.command == "approve" else "REJECTED", full_content_reviewed=args.full_content_reviewed)
        result = record(repo, expected=expected, reviewer_id=args.reviewer, allowlist=args.allowlist,
            rationale=args.rationale, retention_reviews=retention_reviews, **decision, **failed,
            correction=correction, fixture_mode=args.fixture_mode)
    print(json.dumps(result, sort_keys=True))
    return 0


def run_safely(action):
    try:
        return action()
    except Exception:
        # Do not echo source text, reviewer input, database errors or credentials.
        print(json.dumps({"status": "error", "code": "CONTENT_REVIEW_FAILED"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run_safely(main))
