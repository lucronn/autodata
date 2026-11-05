"""Privileged local human review boundary. No provider or model calls occur here.

The external allowlist is a private JSON file: version=1, drafting_identities=[...],
reviewers={reviewer_id: {kind: human|synthetic}}. Synthetic identities are permitted
only by explicitly isolated database fixtures. Database operators remain trusted.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .article_lifecycle_types import digest_json

PROFILE = "full-prose-review-v1"
REASON_SCHEMA = "autodata:article-content-review:v1"
_HASH = re.compile(r"[a-f0-9]{64}")
_LIMIT = 1048576


def bindings_for(job, article, candidate, source_fingerprint):
    return {
        "job_id": str(job["source_fetch_job_id"]),
        "article_id": str(job["canonical_article_id"]),
        "source_revision_id": str(job["source_revision_id"]),
        "candidate_revision_id": str(candidate["canonical_article_revision_id"]),
        "request_generation": job["request_generation"],
        "profile_version": job["rewrite_profile_version"],
        "normalization_version": job["normalization_version"],
        "identity_key": article["identity_key"],
        "source_fingerprint": source_fingerprint,
        "source_hash": digest_json(candidate["normalized_source_document"]),
        "candidate_hash": digest_json(candidate["canonical_document"]),
    }


def _reason(value):
    if isinstance(value, str):
        if len(value.encode()) > _LIMIT:
            raise ValueError("CONTENT_REVIEW_REASON_LIMIT")
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("CONTENT_REVIEW_REASON_INVALID")
    return value


def _substantive(value):
    return isinstance(value, str) and 20 <= len(value.strip()) <= 8000 and len(value.split()) >= 4


def correction_response(reason):
    reason = _reason(reason)
    correction = reason.get("correction")
    if correction is None:
        return None
    if (not isinstance(correction, dict)
        or set(correction) != {"original_candidate_hash", "final_candidate_hash", "response", "response_hash", "actor"}
        or not isinstance(correction["response"], dict)
        or correction["response_hash"] != digest_json(correction["response"])
        or not isinstance(correction["actor"], str) or not correction["actor"].strip()
        or any(not isinstance(correction[key], str) or not _HASH.fullmatch(correction[key])
               for key in ("original_candidate_hash", "final_candidate_hash", "response_hash"))):
        raise ValueError("CONTENT_REVIEW_CORRECTION_INVALID")
    return correction["response"]


def validate_review(reason, *, job, article, candidate, source_fingerprint, review, allow_synthetic=False):
    """Verify the latest decision's exact bindings; caller locks/checks DB ownership.

    Mechanical validation and original/corrected render reconstruction must also
    run inside the same transaction. This function does not prove human semantics.
    """
    reason = _reason(reason)
    expected = bindings_for(job, article, candidate, source_fingerprint)
    if (set(reason) != {"schema", "bindings", "full_content_reviewed", "retention_reviews", "rationale", "reviewer_kind", "correction"}
        or reason["schema"] != REASON_SCHEMA
        or reason["bindings"] != expected
        or type(reason["bindings"].get("request_generation")) is not int
        or job["rewrite_profile_version"] != PROFILE
        or reason["full_content_reviewed"] is not True
        or review["decision"] != "APPROVED"
        or not str(review.get("authorized_reviewer_id", "")).strip()
        or reason["reviewer_kind"] not in (("human", "synthetic") if allow_synthetic else ("human",))
        or not _substantive(reason["rationale"])
        or not isinstance(reason["retention_reviews"], dict)
        or any(not isinstance(key, str) or not _substantive(value) for key, value in reason["retention_reviews"].items())):
        raise ValueError("CONTENT_REVIEW_BINDING_INVALID")
    response = correction_response(reason)
    if response is not None and reason["correction"]["final_candidate_hash"] != expected["candidate_hash"]:
        raise ValueError("CONTENT_REVIEW_CORRECTION_INVALID")
    return reason


validate_review_reason = validate_review


def _outside_git(path):
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("CONTENT_REVIEW_PRIVATE_PATH_REQUIRED")


def _private_path(path, *, directory=False):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError("CONTENT_REVIEW_SYMLINK_FORBIDDEN")
    _outside_git(path)
    mode = path.stat()
    if mode.st_uid != os.getuid() or mode.st_mode & 0o077 or (directory and not stat.S_ISDIR(mode.st_mode)):
        raise ValueError("CONTENT_REVIEW_PRIVATE_PATH_REQUIRED")
    return path


def _read_private_json(path):
    path = _private_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        status = os.fstat(stream.fileno())
        if not stat.S_ISREG(status.st_mode) or status.st_uid != os.getuid() or status.st_mode & 0o077:
            raise ValueError("CONTENT_REVIEW_PRIVATE_PATH_REQUIRED")
        raw = stream.read(_LIMIT + 1)
    if len(raw.encode()) > _LIMIT:
        raise ValueError("CONTENT_REVIEW_INPUT_LIMIT")
    return json.loads(raw)


def authorize_reviewer(allowlist, reviewer_id, *, drafting_identities, fixture_mode=False):
    policy = _read_private_json(allowlist)
    if (not isinstance(policy, dict) or set(policy) != {"version", "drafting_identities", "reviewers"}
        or type(policy["version"]) is not int or policy["version"] != 1
        or not isinstance(policy["drafting_identities"], list)
        or any(not isinstance(item, str) or not item.strip() for item in policy["drafting_identities"])
        or not isinstance(policy["reviewers"], dict)):
        raise ValueError("CONTENT_REVIEW_ALLOWLIST_INVALID")
    reviewer = policy["reviewers"].get(reviewer_id)
    if (not isinstance(reviewer_id, str) or not reviewer_id.strip()
        or reviewer_id in set(policy["drafting_identities"]) | set(drafting_identities)
        or not isinstance(reviewer, dict) or set(reviewer) != {"kind"}
        or reviewer["kind"] not in (("human", "synthetic") if fixture_mode else ("human",))
        or (reviewer_id.lower().startswith(("synthetic", "fixture", "model:")) and not fixture_mode)):
        raise ValueError("CONTENT_REVIEW_REVIEWER_FORBIDDEN")
    return reviewer["kind"]


def write_private_export(destination, payloads):
    destination = Path(destination).absolute()
    _private_path(destination.parent, directory=True)
    _outside_git(destination)
    try:
        destination.mkdir(mode=0o700)
    except FileExistsError as error:
        raise ValueError("CONTENT_REVIEW_EXPORT_EXISTS") from error
    try:
        for name, payload in payloads.items():
            if name not in {"source", "candidate", "manifest", "reviews"}:
                raise ValueError("CONTENT_REVIEW_EXPORT_INVALID")
            descriptor = os.open(destination / (name + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2, default=str)
                stream.write("\n")
    except BaseException:
        for path in destination.iterdir():
            path.unlink()
        destination.rmdir()
        raise
    return destination


def _fixture_allowed(cur, fixture_mode):
    if fixture_mode and (os.environ.get("AUTODATA_LIFECYCLE_TEST") != "1"
        or not cur.execute("SELECT current_database() AS name").fetchone()["name"].startswith("lifecycle_test_")):
        raise ValueError("CONTENT_REVIEW_FIXTURE_FORBIDDEN")
    return fixture_mode


def _load_locked(cur, expected):
    """Match _lock_transform's job -> article -> candidate lock ordering."""
    job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s FOR UPDATE", (UUID(expected["job_id"]),)).fetchone()
    if job is None:
        raise ValueError("CONTENT_REVIEW_JOB_MISSING")
    article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE", (job["canonical_article_id"],)).fetchone()
    candidate = cur.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s FOR UPDATE", (UUID(expected["candidate_revision_id"]),)).fetchone()
    source = cur.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s", (job["source_revision_id"],)).fetchone()
    if (article is None or candidate is None or source is None
        or job["rewrite_profile_version"] != PROFILE
        or article["current_job_id"] != job["source_fetch_job_id"]
        or article["request_generation"] != job["request_generation"]
        or article["current_source_revision_id"] != job["source_revision_id"]
        or article["target_rewrite_profile_version"] != PROFILE
        or article["target_normalization_version"] != job["normalization_version"]
        or candidate["canonical_article_id"] != job["canonical_article_id"]
        or candidate["source_revision_id"] != job["source_revision_id"]
        or candidate["transformation_key"] != job["transformation_key"]
        or candidate["rewrite_profile_version"] != PROFILE
        or candidate["normalization_version"] != job["normalization_version"]
        or candidate["status"] != "validated"
        or article["current_canonical_revision_id"] == candidate["canonical_article_revision_id"]
        or job["status"] != "needs_review" or job["lease_owner"] is not None
        or job["lease_expires_at"] is not None
        or candidate["normalized_source_hash"] != digest_json(candidate["normalized_source_document"])
        or candidate["rewrite_result_hash"] != digest_json(candidate["canonical_document"])
        or expected != bindings_for(job, article, candidate, source["source_fingerprint"])):
        raise ValueError("CONTENT_REVIEW_STALE_BINDING")
    checkpoint = job["checkpoint"].get("content_review", {})
    if (checkpoint.get("version") != 1 or checkpoint.get("state") != "awaiting_review"
        or checkpoint.get("candidate_revision_id") != str(candidate["canonical_article_revision_id"])
        or checkpoint.get("candidate_hash") != candidate["rewrite_result_hash"]):
        raise ValueError("CONTENT_REVIEW_CHECKPOINT_INVALID")
    return job, article, candidate, source


def _original_and_effective(cur, job, candidate):
    from .procedure_rewrite_full import render_full
    attempt = cur.execute("SELECT * FROM canonical_article_rewrite_attempts WHERE canonical_article_revision_id=%s AND source_fetch_job_id=%s AND status='succeeded'", (candidate["canonical_article_revision_id"], job["source_fetch_job_id"])).fetchone()
    if (attempt is None or attempt["response_hash"] != digest_json(attempt["response"])
        or attempt["input_hash"] != candidate["normalized_source_hash"]
        or attempt["profile_version"] != PROFILE
        or attempt["prompt_hash"] != candidate["model_metadata"].get("prompt_hash")
        or attempt["model"] != candidate["model_metadata"].get("model")
        or candidate["model_metadata"].get("profile_version") != PROFILE):
        raise ValueError("CONTENT_REVIEW_ATTEMPT_INVALID")
    original = render_full(candidate["normalized_source_document"], attempt["response"])
    latest = cur.execute("SELECT * FROM canonical_article_reviews WHERE canonical_article_revision_id=%s ORDER BY reviewed_at DESC,canonical_article_review_id DESC LIMIT 1", (candidate["canonical_article_revision_id"],)).fetchone()
    correction = None
    response = attempt["response"]
    if latest:
        reason = _reason(latest["reason"])
        corrected = correction_response(reason)
        if corrected is not None:
            correction = reason["correction"]
            if (correction["original_candidate_hash"] != digest_json(original)
                or correction["final_candidate_hash"] != candidate["rewrite_result_hash"]):
                raise ValueError("CONTENT_REVIEW_CORRECTION_INVALID")
            response = corrected
    effective = render_full(candidate["normalized_source_document"], response)
    if effective != candidate["canonical_document"]:
        raise ValueError("CONTENT_REVIEW_RENDER_INVALID")
    return attempt, original, response, correction


def export_review(repo, *, expected, destination):
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        job, article, candidate, source = _load_locked(cur, expected)
        _original_and_effective(cur, job, candidate)
        reviews = cur.execute("SELECT * FROM canonical_article_reviews WHERE canonical_article_revision_id=%s ORDER BY reviewed_at DESC,canonical_article_review_id DESC", (candidate["canonical_article_revision_id"],)).fetchall()
        payloads = {"source": {"document": source["source_document"], "normalized_document": candidate["normalized_source_document"], "images": source["source_images"]},
            "candidate": candidate["canonical_document"], "reviews": reviews,
            "manifest": {"schema": REASON_SCHEMA, "bindings": expected, "validation_report": candidate["validation_report"]}}
    write_private_export(destination, payloads)
    return {"status": "exported", "bindings": expected}


def record_review(repo, *, expected, reviewer_id, allowlist, decision, rationale,
                  full_content_reviewed=False, retention_reviews=None, correction=None, fixture_mode=False):
    """Append review and schedule saved-candidate resume in the same transaction."""
    if decision not in ("APPROVED", "REJECTED") or not _substantive(rationale):
        raise ValueError("CONTENT_REVIEW_DECISION_INVALID")
    from .procedure_rewrite_full import render_full, validate_full
    from .article_document import project_ordered_document
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        fixture_mode = _fixture_allowed(cur, fixture_mode)
        job, article, candidate, source = _load_locked(cur, expected)
        attempt, original, response, provenance = _original_and_effective(cur, job, candidate)
        kind = authorize_reviewer(allowlist, reviewer_id,
            drafting_identities=[attempt["provider"], attempt["model"], candidate["model_metadata"].get("drafting_actor", "")], fixture_mode=fixture_mode)
        if correction is not None:
            corrected = render_full(candidate["normalized_source_document"], correction)
            if corrected == candidate["canonical_document"]:
                raise ValueError("CONTENT_REVIEW_CORRECTION_UNCHANGED")
            response = correction
            provenance = {"original_candidate_hash": digest_json(original), "final_candidate_hash": digest_json(corrected),
                "response": correction, "response_hash": digest_json(correction), "actor": reviewer_id}
            candidate = {**candidate, "canonical_document": corrected, "rewrite_result_hash": digest_json(corrected)}
        validation = validate_full(candidate["normalized_source_document"], candidate["canonical_document"], response=response)
        if not validation.passed:
            raise ValueError("CONTENT_REVIEW_STRUCTURAL_INVALID")
        retentions = retention_reviews if retention_reviews is not None else {}
        if (not isinstance(retentions, dict) or set(retentions) != set(validation.report.get("retained_paths", []))
            or any(not _substantive(reason) for reason in retentions.values())):
            raise ValueError("CONTENT_REVIEW_RETENTION_REQUIRED")
        reason = {"schema": REASON_SCHEMA, "bindings": bindings_for(job, article, candidate, source["source_fingerprint"]),
            "full_content_reviewed": full_content_reviewed, "retention_reviews": retentions, "rationale": rationale,
            "reviewer_kind": kind, "correction": provenance}
        review_id = uuid4()
        if decision == "APPROVED":
            validate_review(reason, job=job, article=article, candidate=candidate, source_fingerprint=source["source_fingerprint"],
                review={"decision": decision, "authorized_reviewer_id": reviewer_id}, allow_synthetic=fixture_mode)
            # A correction author's changes require a later independent approval.
            if provenance is not None and provenance["actor"] == reviewer_id:
                raise ValueError("CONTENT_REVIEW_CORRECTION_REQUIRES_INDEPENDENT_APPROVAL")
        if len(json.dumps(reason).encode()) > _LIMIT:
            raise ValueError("CONTENT_REVIEW_REASON_LIMIT")
        if correction is not None:
            projection = project_ordered_document(candidate["canonical_document"])
            cur.execute("UPDATE canonical_article_revisions SET canonical_document=%s,canonical_body=%s,canonical_steps=%s,canonical_images=%s,rewrite_result_hash=%s,validation_report=%s,validation_hash=%s WHERE canonical_article_revision_id=%s",
                (Jsonb(candidate["canonical_document"]), projection["body"], Jsonb(projection["steps"]), Jsonb(projection["images"]), candidate["rewrite_result_hash"], Jsonb(validation.report), digest_json(validation.report), candidate["canonical_article_revision_id"]))
        cur.execute("INSERT INTO canonical_article_reviews(canonical_article_review_id,canonical_article_revision_id,authorized_reviewer_id,decision,reason,reviewed_at) VALUES (%s,%s,%s,%s,%s,clock_timestamp())",
            (review_id, candidate["canonical_article_revision_id"], reviewer_id, decision, json.dumps(reason, sort_keys=True)))
        checkpoint = {"version": 1, "state": "approved" if decision == "APPROVED" else "awaiting_review",
            "candidate_revision_id": str(candidate["canonical_article_revision_id"]), "candidate_hash": candidate["rewrite_result_hash"], "review_id": str(review_id)}
        if decision == "APPROVED":
            cur.execute("UPDATE source_fetch_jobs SET status='pending',phase='publishing',retryable=true,error_code=NULL,next_attempt_at=clock_timestamp(),checkpoint=checkpoint||%s,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s",
                (Jsonb({"content_review": checkpoint, "validation_hash": digest_json(validation.report)}), job["source_fetch_job_id"]))
        else:
            cur.execute("UPDATE source_fetch_jobs SET checkpoint=checkpoint||%s,updated_at=clock_timestamp() WHERE source_fetch_job_id=%s",
                (Jsonb({"content_review": checkpoint, "validation_hash": digest_json(validation.report)}), job["source_fetch_job_id"]))
        return {"status": decision.lower(), "review_id": str(review_id), "bindings": reason["bindings"]}
