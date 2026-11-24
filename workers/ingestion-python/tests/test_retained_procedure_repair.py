"""Replay an archived draft and publish its checked correction on isolated PostgreSQL."""

import json
from uuid import uuid4

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_store import load_source_revision
from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION
from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
from autodata_ingestion.published_media_publication import _publication_evidence
from autodata_ingestion.retained_procedure_repair import CHECKPOINT, _correct_reply, repair_retained_procedure
from autodata_ingestion.source_job_persistence import ensure_article_job
from autodata_ingestion.source_table_replay import load_table_replay_binding
from lifecycle_support import fresh_database, runtime, seed_configuration, seed_snapshot
from test_procedure_rewrite_full import document, response
from test_source_revision_reprojection import all_rows


OLD_VERSION = "full-prose-auto-prompt-v2"
SOURCE = (
    "An access marker appears just inside the enclosure near upper mounting seam.",
    "Warning: Keep all bystanders clear of moving parts during service.",
    "30 seconds",
    "Remove the pump.",
)
DRAFT = (
    "There is a visible access marker just inside the enclosure close to the upper mounting groove.",
    "Warning: During service, keep everyone away from moving parts.",
    SOURCE[2],
    "Take off the pump.",
)
INTRODUCTION = "This procedure describes the 30 seconds used for pump service."


def _reply():
    result = response(*DRAFT, introduction=INTRODUCTION)
    result["replacements"][2].update(action="retain", reason="Keep the exact specified wait.")
    return result


def test_correct_reply_keeps_literal_warning_and_restores_exact_spatial_reference():
    source = document(*SOURCE)
    reply = _reply()
    prior = auto.render_auto(source, reply, prompt_version=OLD_VERSION)
    guard = json.loads(auto.build_auto_prompt(source, context={}))["prompt_version"]
    with pytest.raises(ValueError, match="^REWRITE_SPEC_SCOPE_MUTATION$"):
        auto.require_current_publication_checks(source, prior, saved_prompt_version=OLD_VERSION)
    corrected, candidate, validation, failures = _correct_reply(source, prior, reply, guard)
    assert failures == [
        {"path": "/blocks/0/text", "code": "REWRITE_DIRECTION_MUTATION"},
        {"path": "/blocks/1/text", "code": "REWRITE_SAFETY_MUTATION"},
    ]
    assert validation.passed and validation.report["changed_prose_slots"] == ["/blocks/0/text", "/blocks/3/text"]
    assert corrected["replacements"][0]["text"].endswith("near upper mounting seam.")
    assert corrected["replacements"][1]["text"] == SOURCE[1]
    assert corrected["replacements"][2:] == reply["replacements"][2:]
    assert reply == _reply()
    auto.require_current_publication_checks(source, candidate, saved_prompt_version=guard)

    bad = _reply()
    bad["replacements"][0]["text"] += " Move the cover."
    prior = auto.render_auto(source, bad, prompt_version=OLD_VERSION)
    with pytest.raises(ValueError, match="^RETAINED_PROCEDURE_REPAIR_INVALID$"):
        _correct_reply(source, prior, bad, guard)


def _seed_archived_reply(runtime, monkeypatch):
    config = seed_configuration(runtime.repo, runtime.vehicle)
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicle_configurations SET trim='Touring' WHERE vehicle_configuration_id=%s", (config,))

    def run(job_id, model=None):
        assert run_article_worker_once(
            runtime.repo, worker_id=uuid4(), job_id=job_id, registry=runtime.registry,
            object_store=runtime.objects, model_client=model,
        )

    for job in ensure_article_catalog_jobs(runtime.repo, vehicle_id=runtime.vehicle, vehicle_configuration_id=config):
        run(job.job_id)
    with runtime.repo.connect() as conn:
        runtime.article_id = conn.execute("""SELECT canonical_article_id FROM canonical_articles
            WHERE vehicle_configuration_id=%s AND provider_slug='bankone'""",
            (config,)).fetchone()["canonical_article_id"]
    runtime.servers["bankone"].body("".join(f"<p>{text}</p>" for text in SOURCE).encode())
    job = ensure_article_job(runtime.repo, runtime.article_id, normalization_version=NORMALIZATION_VERSION,
                             rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE)

    class SavedDraft:
        _model = "fixture-historical-model"

        def complete_json(self, raw):
            prompt = json.loads(raw)
            assert prompt["prompt_version"] == OLD_VERSION
            result = _reply()
            for slot, row in zip(prompt["slots"], result["replacements"], strict=True):
                row.update(path=slot["path"], block_id=slot["block_id"])
            return result

    render, validate = auto.render_auto, auto.validate_auto
    with monkeypatch.context() as historic:
        historic.setattr(auto, "build_auto_prompt", lambda source, *, context, profile_version:
                         auto._build_auto_prompt_v2(source, context=context))
        historic.setattr(auto, "render_auto", lambda *args, prompt_version=None, **kwargs:
                         render(*args, prompt_version=prompt_version or OLD_VERSION, **kwargs))
        historic.setattr(auto, "validate_auto", lambda *args, prompt_version=None, **kwargs:
                         validate(*args, prompt_version=prompt_version or OLD_VERSION, **kwargs))
        historic.setattr(auto, "require_current_publication_checks", lambda *args, **kwargs: None)
        run(job.job_id, SavedDraft())
    current = runtime.read_current()
    assert current["content_origin"] == "canonical", runtime.diagnostics()
    runtime.reset_counters()
    return current


def test_atomic_archived_repair_keeps_history_and_replays_without_calls(runtime, monkeypatch, tmp_path, capsys):
    from automatic_article_refresh import main
    from autodata_ingestion.retained_procedure_repair import _rebuild

    current = _seed_archived_reply(runtime, monkeypatch)
    article_id = runtime.article_id
    source_id = current["source_revision_id"]
    old_id = current["canonical_revision_id"]
    before = all_rows(runtime.repo)
    old, = before["canonical_article_revisions"]
    saved, = before["canonical_article_rewrite_attempts"]
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (article_id,)).fetchone()
        binding = load_table_replay_binding(cur, source_id)
        correct = _rebuild(cur, article, binding, old_id, old_hash=old["rewrite_result_hash"])
    args = {"expected_job_id": current["job_id"], "expected_source_revision_id": source_id,
            "expected_published_revision_id": old_id, "expected_published_hash": old["rewrite_result_hash"],
            "expected_repaired_hash": correct.evidence["repaired_document_hash"],
            "actor": "fixture-editor", "reason": "Restore the proven spatial reference and warning."}
    with pytest.raises(ValueError, match="^RETAINED_PROCEDURE_REPAIR_STALE$"):
        repair_retained_procedure(runtime.repo, article_id, **{**args, "expected_repaired_hash": "0" * 64})
    assert all_rows(runtime.repo) == before

    class Interrupted(Exception):
        pass

    def stopped(point):
        assert point == "inside_publication"
        assert runtime.read_current() == current
        raise Interrupted

    with pytest.raises(Interrupted):
        repair_retained_procedure(runtime.repo, article_id, **args, hooks=stopped)
    assert all_rows(runtime.repo) == before

    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps([{"canonical_article_id": str(article_id), "expected_source_revision_id": str(source_id)}]))
    assert main([
        "--selection", str(selection), "--apply", "--actor", args["actor"], "--reason", args["reason"],
        "--repair-retained-procedure-from", str(args["expected_job_id"]),
        "--expected-published-revision-id", str(old_id), "--expected-published-hash", args["expected_published_hash"],
        "--expected-repaired-hash", args["expected_repaired_hash"],
    ], repo=runtime.repo) == 0
    published = runtime.read_current()
    new_id = published["canonical_revision_id"]
    assert json.loads(capsys.readouterr().out)["items"][0]["revision_id"] == str(new_id)
    assert published["source_revision_id"] == source_id and new_id != old_id
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (article_id,)).fetchone()
        row, _, _, archive, reply, version, _ = _publication_evidence(cur, article, binding, fixture_mode=False, lock=False)
        assert archive == saved and reply == correct.response and version == correct.prompt_version
        assert row["model_metadata"][CHECKPOINT] == {"actor": args["actor"], "reason": args["reason"],
                                                     "evidence": correct.evidence}
    after = all_rows(runtime.repo)
    for table in ("canonical_article_source_revisions", "canonical_article_source_observations",
                  "canonical_article_rewrite_attempts", "source_snapshots", "source_artifacts"):
        assert after[table] == before[table]
    assert old in after["canonical_article_revisions"]
    assert len(after["publication_events"]) == len(before["publication_events"]) + 1
    assert sum(event["canonical_article_revision_id"] == new_id for event in after["publication_events"]) == 1
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 1}

    refreshed = seed_snapshot(runtime.repo, b"active replacement descriptor")
    assert refreshed != binding.context.descriptor_snapshot_id
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET descriptor_source_snapshot_id=%s WHERE canonical_article_id=%s",
                     (refreshed, article_id))
    assert runtime.read_current()["canonical_revision_id"] == new_id
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (article_id,)).fetchone()
        retained = load_table_replay_binding(cur, source_id)
        stored = load_source_revision(runtime.repo, source_id)
        row, _, _, archive, reply, _, _ = _publication_evidence(cur, article, stored, fixture_mode=False, lock=False)
        assert retained.source_observation_id == binding.source_observation_id
        assert row["canonical_article_revision_id"] == new_id and archive == saved and reply == correct.response
