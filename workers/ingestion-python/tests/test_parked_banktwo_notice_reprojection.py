"""Exercise the retained-source handoff and shared model lane in PostgreSQL."""

import json
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from autodata_ingestion import parked_banktwo_notice_reprojection, rollout_model_lane, source_article_capture
from autodata_ingestion.article_lifecycle import run_article_job, run_article_worker_once
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, SOURCE_BOUND_CORRECTION_PROFILE, digest_json,
)
from autodata_ingestion.parked_banktwo_notice_reprojection import reproject_parked_banktwo_notices
from autodata_ingestion.source_banktwo_notice_replay import preview_banktwo_notice_replay
from autodata_ingestion.source_job_persistence import claim_source_job, ensure_article_job
from lifecycle_support import fresh_database, runtime
from test_paid_catalog_api_integration import configure_scoped_runtime
from test_retained_banktwo_notice_publication import NoticeModel
from test_rollout_model_lane import CopiedFirstDraft, grant_scope, rollout
from test_source_revision_reprojection import all_rows


@pytest.mark.parametrize("reject_first_draft", [False, True])
def test_reproject_unspent_reserved_source(runtime, monkeypatch, reject_first_draft):
    config = configure_scoped_runtime(runtime, "banktwo")
    job = ensure_article_job(
        runtime.repo, runtime.article_id, normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    ).job_id
    snapshot = rollout()
    snapshot["reservations"].append({"job_id": str(job)})
    marker = {key: snapshot[key] for key in ("rollout_id", "source_sha", "cutoff")}
    marker["max_model_attempts"] = 1
    with runtime.repo.connect() as conn:
        conn.execute(
            "UPDATE source_fetch_jobs SET max_attempts=1,checkpoint=%s WHERE source_fetch_job_id=%s",
            (Jsonb({"new_article_rollout": marker}), job),
        )
    html = (
        '<ol><li>Remove the pump.<img data-resource-ref="figure" alt="Pump figure"></li>'
        '<div><b>Note:</b> Keep the pump seal in position.</div>'
        '<li>Install the replacement.</li></ol>'
    )
    runtime.servers["banktwo"].body(
        json.dumps({"_embedded": {"data": {"article": {"content": html}}}}).encode(),
        "application/hal+json", assets=["figure"],
    )
    capture = source_article_capture.capture_source_article

    def legacy_capture(*args, **kwargs):
        return capture(*args, **{**kwargs, "keep_banktwo_list_notices": False})

    with monkeypatch.context() as legacy:
        legacy.setattr(source_article_capture, "capture_source_article", legacy_capture)
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), registry=runtime.registry, object_store=runtime.objects,
            model_client=None, job_id=job,
        )
    before = runtime.read_current()
    rows = all_rows(runtime.repo)
    traffic = runtime.counters()
    binding, captured = preview_banktwo_notice_replay(runtime.repo, before["source_revision_id"],
                                                     object_store=runtime.objects)
    repair = {
        "object_store": runtime.objects, "expected_job_id": job, "expected_source_revision_id": binding.source_revision_id,
        "expected_observation_id": binding.source_observation_id, "expected_fingerprint": captured.source_fingerprint,
        "expected_document_sha256": digest_json(captured.source_document), "actor": "fixture",
        "reason": "Restore authored notice order using the original stored source.",
    }
    with pytest.raises(ValueError, match="PARKED_BANKTWO_NOTICE_REPROJECTION_STALE"):
        reproject_parked_banktwo_notices(runtime.repo, {**snapshot, "reservations": []}, **repair)
    with pytest.raises(ValueError, match="PARKED_BANKTWO_NOTICE_REPROJECTION_STALE"):
        reproject_parked_banktwo_notices(runtime.repo, snapshot, **{**repair, "expected_observation_id": uuid4()})
    # Force a failure after writing the successor and its observation.
    with monkeypatch.context() as interrupted:
        allowed = parked_banktwo_notice_reprojection._parked_rollout_source_allowed
        interrupted.setattr(parked_banktwo_notice_reprojection, "_parked_rollout_source_allowed",
                            lambda cur, row: row["request_generation"] == 0 and allowed(cur, row))
        with pytest.raises(ValueError, match="PARKED_BANKTWO_NOTICE_REPROJECTION_STALE"):
            reproject_parked_banktwo_notices(runtime.repo, snapshot, **repair)
    assert all_rows(runtime.repo) == rows
    assert runtime.read_current() == before

    result = reproject_parked_banktwo_notices(runtime.repo, snapshot, **repair)
    assert result["status"] == "applied"
    assert reproject_parked_banktwo_notices(runtime.repo, snapshot, **repair) == {**result, "status": "already_applied"}
    current = runtime.read_current()
    assert current["content_origin"] == "source" and str(current["source_revision_id"]) == result["source_revision_id"]
    assert claim_source_job(runtime.repo, worker_id=uuid4()) is None
    assert runtime.counters() == {**traffic, "schedule": traffic["schedule"] + 1}
    with monkeypatch.context() as quota:
        quota.setattr(rollout_model_lane, "MAX_MODEL_DISPATCHES_PER_WINDOW", 0)
        assert rollout_model_lane.claim_rollout_model_job(runtime.repo, snapshot, worker_id=uuid4()) is None
    assert rollout_model_lane.claim_rollout_model_job(
        runtime.repo, {**snapshot, "reservations": [{"job_id": result["job_id"]}]}, worker_id=uuid4(),
    ) is None
    lease = rollout_model_lane.claim_rollout_model_job(runtime.repo, snapshot, worker_id=uuid4())
    assert str(lease.job_id) == result["job_id"] and lease.generation == 1
    assert str(lease.source_revision_id) == result["source_revision_id"]
    model = CopiedFirstDraft() if reject_first_draft else NoticeModel()
    run_article_job(runtime.repo, lease, registry={}, object_store=None, model_client=model)
    if reject_first_draft:
        grant_scope(runtime.repo, config["configuration"], monkeypatch)
        correction = rollout_model_lane.claim_rollout_model_job(runtime.repo, snapshot, worker_id=uuid4())
        assert correction.rewrite_profile_version == SOURCE_BOUND_CORRECTION_PROFILE
        assert correction.source_revision_id == lease.source_revision_id and correction.generation == 2
    else:
        assert model.calls == 1
        assert runtime.read_current()["content_origin"] == "canonical", runtime.diagnostics()
    assert rollout_model_lane.claim_rollout_model_job(runtime.repo, snapshot, worker_id=uuid4()) is None
    assert runtime.counters() == {**traffic, "schedule": traffic["schedule"] + 1 + int(reject_first_draft)}
