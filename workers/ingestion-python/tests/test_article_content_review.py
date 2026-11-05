"""Local content-review security and exact binding regressions; synthetic content only."""
import json
import os
from copy import deepcopy
from uuid import uuid4
import pytest
from autodata_ingestion import article_content_review as review
from autodata_ingestion.article_lifecycle_types import digest_json


def rows():
    article_id, job_id, source_id, candidate_id = [uuid4() for _ in range(4)]
    source = {"blocks": [{"text": "Remove the pump."}]}
    candidate = {"blocks": [{"text": "Take off the pump."}]}
    job = dict(source_fetch_job_id=job_id, canonical_article_id=article_id,
        source_revision_id=source_id, request_generation=3,
        normalization_version="ordered-article-v1", rewrite_profile_version=review.PROFILE)
    article = dict(identity_key="bankone:synthetic", canonical_article_id=article_id)
    revision = dict(canonical_article_revision_id=candidate_id, canonical_article_id=article_id,
        source_revision_id=source_id, normalized_source_document=source, canonical_document=candidate,
        normalized_source_hash=digest_json(source), rewrite_result_hash=digest_json(candidate))
    return job, article, revision


def reason_and_rows():
    job, article, candidate = rows()
    reason = dict(schema=review.REASON_SCHEMA, bindings=review.bindings_for(job, article, candidate, "a"*64),
        full_content_reviewed=True, retention_reviews={}, rationale="Compared every instruction and all source context.",
        reviewer_kind="human", correction=None)
    row = dict(decision="APPROVED", authorized_reviewer_id="qualified-human")
    return reason, job, article, candidate, row


def test_exact_review_bindings_reject_every_changed_field():
    reason, job, article, candidate, row = reason_and_rows()
    assert review.validate_review(reason, job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)==reason
    for key in reason["bindings"]:
        changed=deepcopy(reason);changed["bindings"][key]="foreign"
        with pytest.raises(ValueError):
            review.validate_review(changed,job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)


@pytest.mark.parametrize("field,value",[("full_content_reviewed",1),("rationale","short"),("reviewer_kind","synthetic"),("retention_reviews",[])])
def test_approval_requires_human_full_review(field,value):
    reason,job,article,candidate,row=reason_and_rows();reason[field]=value
    with pytest.raises(ValueError):
        review.validate_review(reason,job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)


def test_json_reason_is_parsed_and_rejection_cannot_approve():
    reason,job,article,candidate,row=reason_and_rows()
    assert review.validate_review(json.dumps(reason),job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)==reason
    row["decision"]="REJECTED"
    with pytest.raises(ValueError):review.validate_review(reason,job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)


def test_external_allowlist_requires_private_file_and_independent_human(tmp_path):
    policy=tmp_path/'reviewers.json'
    policy.write_text(json.dumps({"version":1,"drafting_identities":["drafter"],"reviewers":{"alice":{"kind":"human"},"drafter":{"kind":"human"},"synthetic:test":{"kind":"synthetic"}}}))
    policy.chmod(0o600)
    assert review.authorize_reviewer(policy,"alice",drafting_identities=["model"])=="human"
    for actor in ("drafter","synthetic:test","model","unknown"):
        with pytest.raises(ValueError):review.authorize_reviewer(policy,actor,drafting_identities=["model"])
    policy.chmod(0o644)
    with pytest.raises(ValueError):review.authorize_reviewer(policy,"alice",drafting_identities=[])


def test_private_export_is_exclusive_and_rejects_public_parent(tmp_path):
    destination=tmp_path/'export'
    review.write_private_export(destination,{"source":{"private":"source"},"candidate":{"private":"draft"},"manifest":{"hash":"a"*64}})
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in destination.iterdir())
    assert json.loads((destination/'source.json').read_text())=={"private":"source"}
    with pytest.raises(ValueError):review.write_private_export(destination,{"source":{}})
    public=tmp_path/'public';public.mkdir(mode=0o755)
    with pytest.raises(ValueError):review.write_private_export(public/'export',{"source":{}})


def test_correction_provenance_requires_exact_response_hash():
    reason,job,article,candidate,row=reason_and_rows()
    correction={"original_candidate_hash":"b"*64,"final_candidate_hash":reason['bindings']['candidate_hash'],"response":{"introduction":"source"},"response_hash":"c"*64,"actor":"alice"}
    reason['correction']=correction
    with pytest.raises(ValueError):review.validate_review(reason,job=job,article=article,candidate=candidate,source_fingerprint="a"*64,review=row)
    correction['response_hash']=digest_json(correction['response'])
    assert review.correction_response(reason)==correction['response']
