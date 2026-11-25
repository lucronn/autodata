"""Exact Banktwo archived-reply Note repair on isolated PostgreSQL."""

from copy import deepcopy
from io import BytesIO
import json
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, SOURCE_BOUND_REWRITE_PROFILE, digest_json,
)
from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
from autodata_ingestion.procedure_rewrite_full import _get, _set
from autodata_ingestion.published_media_publication import _publication_evidence
from autodata_ingestion.procedure_rewrite_sentence_correction import SENTENCE_CORRECTION_METHOD
from autodata_ingestion.retained_note_label_repair import (
    CHECKPOINT, PROFILE, ROTATION_REMOVAL_CHECKPOINT, ROTATION_REMOVAL_METHOD, ROTATION_REMOVAL_PROFILE,
    _restore_reply, repair_retained_note_labels, repair_retained_rotation_removal,
)
from autodata_ingestion.source_job_persistence import ProfileRefreshRequired, ensure_article_job, refresh_article_job, schedule_source_bound_rewrite
from lifecycle_support import fresh_database, runtime, seed_configuration, seed_snapshot
from test_source_bound_correction_recovery import recover
from test_source_bound_correction_worker import CopiedSource, CorrectedSource, schedule_correction
from test_source_bound_rewrite_worker import run_job
from test_source_revision_reprojection import all_rows


PARTS = ("filler cap", "panel", "shield", "sleeve", "retainer", "latch", "bracket")
SOURCE_NOTE = {f"Note: Remove the {part}.": f"Take the {part} off." for part in PARTS}


class ArchivedNotes:
    _model = "fixture-note-labels"

    def __init__(self, additional):
        self.wording = SOURCE_NOTE | additional

    def complete_json(self, prompt):
        payload = json.loads(prompt)
        candidate_count = len(payload["response_shape"]["rewrites"][0]["candidates"])
        rows = []
        for passage in payload["passages"]:
            source = passage["source"]
            old_rephrasing = self.wording.get(source, source)
            rows.append({"slot": passage["slot"], "candidates": [source, old_rephrasing, *([source] * (candidate_count - 2))]})
        return {"rewrites": rows}


def seed_banktwo_figure(runtime, raw):
    configuration = seed_configuration(runtime.repo, runtime.vehicle)
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicle_configurations SET trim='Touring' WHERE vehicle_configuration_id=%s", (configuration,))
    for job in ensure_article_catalog_jobs(runtime.repo, vehicle_id=runtime.vehicle, vehicle_configuration_id=configuration):
        assert run_job(runtime, job.job_id, None, registry=runtime.registry)
    with runtime.repo.connect() as conn:
        runtime.article_id = conn.execute("""SELECT canonical_article_id FROM canonical_articles
            WHERE vehicle_configuration_id=%s AND provider_slug='banktwo'""", (configuration,)).fetchone()["canonical_article_id"]

    connector = runtime.servers["banktwo"]
    connector.body(raw, assets=["diagram"], asset_bindings=[{"source_url": "/fixture/figure", "resource_ref": "diagram"}])
    picture = BytesIO()
    Image.new("RGB", (10, 8), (23, 89, 132)).save(picture, format="PNG")
    figure = picture.getvalue()
    connector.body(figure, media_type="image/png", ref="diagram", kind="asset")
    return figure


def seed_banktwo_correction_job(runtime, *, preserve_notes):
    def historical_prompt(document, *, context, profile_version=AUTOMATIC_REWRITE_PROFILE):
        if profile_version == AUTOMATIC_REWRITE_PROFILE:
            builder = auto._build_auto_prompt_v61 if preserve_notes else auto._build_auto_prompt_v60
            return builder(document, context=context)
        assert profile_version == SOURCE_BOUND_REWRITE_PROFILE
        return auto._build_source_bound_prompt(document, preserve_notes=preserve_notes)

    # Produce real legacy prompt and response hashes before testing current replay.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(auto, "build_auto_prompt", historical_prompt)
        captured = ensure_article_job(runtime.repo, runtime.article_id, normalization_version=NORMALIZATION_VERSION,
                                      rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE)
        assert run_job(runtime, captured.job_id, CopiedSource(), registry=runtime.registry)
        current = runtime.read_current()
        assert current["content_origin"] == "source", current["processing_error_code"]
        assert len(current["images"]) == 1 and current["images"][0]["status"] == "available"
        source_id = current["source_revision_id"]
        prior = schedule_source_bound_rewrite(
            runtime.repo, runtime.article_id, expected_job_id=captured.job_id, expected_source_revision_id=source_id,
            actor="fixture-editor", reason="Create a retained source draft.",
        )
        assert run_job(runtime, prior.job_id, CopiedSource())
    corrected = schedule_correction(runtime, prior.job_id, source_id, 2)
    return corrected.job_id, source_id


def seed_archived_note_publication(runtime, *, additional=None):
    notes = list(SOURCE_NOTE)
    items = "".join(f"<li>{text}</li>" for text in notes[:6])
    additional = additional or {}
    appended = "".join(f"<p>{text}</p>" for text in additional)
    raw = (
        f"<h2>Service procedure</h2><ol start='3'>{items}</ol>"
        f"<img src='/fixture/figure' alt='Fixture component'><p>{notes[6]}</p><p>Remove the upper cover.</p>"
        f"{appended}"
    ).encode()
    seed_banktwo_figure(runtime, raw)
    correction_id, source_id = seed_banktwo_correction_job(runtime, preserve_notes=False)
    assert run_job(runtime, correction_id, ArchivedNotes(additional))
    assert runtime.read_current()["processing_error_code"] == "REWRITE_UNCHANGED"
    published = recover(runtime, correction_id, source_id)
    assert run_job(runtime, correction_id, None)
    assert runtime.read_current()["canonical_revision_id"] == published
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (runtime.article_id,)).fetchone()
        source = cur.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                             (source_id,)).fetchone()
        row, _, _, _, reply, version, _ = _publication_evidence(
            cur, article, SimpleNamespace(source_revision_id=source_id), fixture_mode=False, lock=False,
        )
    repaired, _, _, paths = _restore_reply(row["normalized_source_document"], source["source_document"],
                                          row["canonical_document"], reply, prompt_version=version)
    assert len(paths) == 7
    assert all("Note: " not in _get({"blocks": row["canonical_document"]["blocks"][1:]}, path) for path in paths)
    runtime.reset_counters()
    return dict(
        expected_job_id=correction_id, expected_source_revision_id=source_id,
        expected_descriptor_snapshot_id=article["descriptor_source_snapshot_id"], expected_published_revision_id=published,
        expected_published_hash=row["rewrite_result_hash"], expected_repaired_hash=digest_json(repaired),
        actor="fixture-editor", reason="Restore exact authored leading labels.",
    ), row, source, repaired, paths


@pytest.fixture
def archived_notes(runtime):
    return seed_archived_note_publication(runtime)


def _state(runtime):
    return all_rows(runtime.repo)


def test_retained_required_action_repair_publishes_same_source_and_rolls_back_atomically(runtime, monkeypatch):
    from autodata_ingestion.retained_required_action_repair import (
        CHECKPOINT as ACTION_CHECKPOINT, PROFILE as ACTION_PROFILE, _rebuild,
        repair_retained_required_actions,
    )

    draft = "The bracket's clamp should be tightened."
    with monkeypatch.context() as archived_release:
        # Reproduce the published archive from before the current guard.
        archived_release.setattr(auto, "require_required_procedure_actions", lambda *_a, **_k: None)
        args, _, source, _, _ = seed_archived_note_publication(runtime, additional={
            "Tighten the clamp on the existing bracket.": draft,
        })
        prior_id = repair_retained_note_labels(runtime.repo, runtime.article_id, **args)
    runtime.reset_counters()

    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        prior = cur.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                            (prior_id,)).fetchone()
        prior_job = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                                (article["current_job_id"],)).fetchone()
        plan = _rebuild(cur, article, prior_job, source["source_revision_id"], article["descriptor_source_snapshot_id"],
                        prior_id, prior["rewrite_result_hash"], lock=False)
    [path] = plan.evidence["restored_paths"]
    assert _get({"blocks": prior["canonical_document"]["blocks"][1:]}, path) == draft
    assert _get({"blocks": plan.document["blocks"][1:]}, path) == "The bracket's clamp must be tightened."
    pins = {
        **args, "expected_job_id": prior_job["source_fetch_job_id"], "expected_published_revision_id": prior_id,
        "expected_published_hash": prior["rewrite_result_hash"], "expected_repaired_hash": digest_json(plan.document),
    }
    before = _state(runtime)

    def abort_at_publication(point):
        assert point == "inside_publication"
        raise RuntimeError("fixture interrupted required wording publication")

    with pytest.raises(RuntimeError, match="fixture interrupted required wording publication"):
        repair_retained_required_actions(runtime.repo, runtime.article_id, **pins, hooks=abort_at_publication)
    assert _state(runtime) == before

    revision = repair_retained_required_actions(runtime.repo, runtime.article_id, **pins)
    current = runtime.read_current()
    assert current["content_origin"] == "canonical"
    assert current["source_revision_id"] == source["source_revision_id"]
    assert current["canonical_revision_id"] == revision
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        row, _, _, _, reply, version, _ = _publication_evidence(
            cur, article, SimpleNamespace(source_revision_id=source["source_revision_id"]), fixture_mode=False, lock=False,
        )
        assert cur.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                           (source["source_revision_id"],)).fetchone() == source
        assert cur.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                           (prior_id,)).fetchone() == prior
    assert row["rewrite_profile_version"] == ACTION_PROFILE
    assert row["canonical_document"] == plan.document
    assert row["canonical_images"] == prior["canonical_images"]
    assert row["model_metadata"][ACTION_CHECKPOINT]["evidence"] == plan.evidence
    assert reply == plan.reply and version == plan.evidence["guard_version"]
    reverted = deepcopy(row["canonical_document"])
    _set({"blocks": reverted["blocks"][1:]}, path, draft)
    assert reverted == prior["canonical_document"]
    after = _state(runtime)
    assert after["canonical_article_rewrite_attempts"] == before["canonical_article_rewrite_attempts"]
    assert len(after["publication_events"]) == len(before["publication_events"]) + 1
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 1}
    with pytest.raises(ValueError, match="^RETAINED_REQUIRED_ACTION_REPAIR_STALE$"):
        repair_retained_required_actions(runtime.repo, runtime.article_id, **pins)
    with pytest.raises(ProfileRefreshRequired):
        refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="Reject implicit operator profile.")


def test_retained_notes_publish_exact_successor_and_replay_after_descriptor_update(runtime, archived_notes, tmp_path, capsys):
    from automatic_article_refresh import main

    args, old, source, expected, paths = archived_notes
    before = _state(runtime)
    selection = tmp_path / "notes.json"
    selection.write_text(json.dumps([{
        "canonical_article_id": str(runtime.article_id), "expected_source_revision_id": str(source["source_revision_id"]),
    }]))
    assert main([
        "--selection", str(selection), "--apply", "--actor", args["actor"], "--reason", args["reason"],
        "--repair-retained-note-labels-from", str(args["expected_job_id"]),
        "--expected-descriptor-snapshot-id", str(args["expected_descriptor_snapshot_id"]),
        "--expected-published-revision-id", str(args["expected_published_revision_id"]),
        "--expected-published-hash", args["expected_published_hash"], "--expected-repaired-hash", args["expected_repaired_hash"],
    ], repo=runtime.repo) == 0
    receipt = json.loads(capsys.readouterr().out)["items"][0]
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (runtime.article_id,)).fetchone()
        row, _, _, _, reply, _, _ = _publication_evidence(
            cur, article, SimpleNamespace(source_revision_id=source["source_revision_id"]), fixture_mode=False, lock=False,
        )
        assert digest_json(reply) == row["model_metadata"][CHECKPOINT]["evidence"]["repaired_reply_hash"]
        assert cur.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                           (source["source_revision_id"],)).fetchone() == source
        assert cur.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                           (old["canonical_article_revision_id"],)).fetchone() == old
    assert article["current_source_revision_id"] == source["source_revision_id"]
    assert article["current_canonical_revision_id"] == row["canonical_article_revision_id"]
    assert receipt["revision_id"] == str(row["canonical_article_revision_id"])
    assert row["rewrite_profile_version"] == PROFILE
    assert row["canonical_document"] == expected
    assert row["canonical_images"] == old["canonical_images"]
    assert runtime.read_current()["content_origin"] == "canonical"
    restored = deepcopy(expected)
    for path in paths:
        canonical, prior = {"blocks": restored["blocks"][1:]}, {"blocks": old["canonical_document"]["blocks"][1:]}
        old_text = _get(prior, path)
        assert _get(canonical, path) == "Note: " + old_text
        _set(canonical, path, old_text)
    assert restored == old["canonical_document"]
    after = _state(runtime)
    assert after["canonical_article_rewrite_attempts"] == before["canonical_article_rewrite_attempts"]
    assert len(after["publication_events"]) == len(before["publication_events"]) + 1
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 1}
    with pytest.raises(ValueError, match="^RETAINED_NOTE_LABEL_REPAIR_STALE$"):
        repair_retained_note_labels(runtime.repo, runtime.article_id, **args)
    with pytest.raises(ProfileRefreshRequired):
        refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="Reject implicit operator profile.")

    replacement_descriptor = seed_snapshot(runtime.repo, b"new authorized descriptor")
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("""UPDATE canonical_articles SET descriptor_source_snapshot_id=%s
            WHERE canonical_article_id=%s RETURNING *""", (replacement_descriptor, runtime.article_id)).fetchone()
        current, *_ = _publication_evidence(cur, article, SimpleNamespace(source_revision_id=source["source_revision_id"]),
                                            fixture_mode=False, lock=False)
        assert current == row


@pytest.mark.parametrize(("change", "code"), [
    ("descriptor", "RETAINED_NOTE_LABEL_REPAIR_STALE"),
    ("published_hash", "RETAINED_NOTE_LABEL_REPAIR_STALE"),
    ("repaired_hash", "RETAINED_NOTE_LABEL_REPAIR_STALE"),
    ("body_rights", "RETAINED_NOTE_LABEL_REPAIR_SOURCE_UNAVAILABLE"),
    ("figure_rights", "RETAINED_NOTE_LABEL_REPAIR_SOURCE_UNAVAILABLE"),
])
def test_retained_notes_fail_closed_without_changing_article(runtime, archived_notes, change, code):
    args, _, source, _, _ = archived_notes
    if change == "descriptor":
        args["expected_descriptor_snapshot_id"] = uuid4()
    if change == "published_hash":
        args["expected_published_hash"] = "0" * 64
    if change == "repaired_hash":
        args["expected_repaired_hash"] = "0" * 64
    if change in ("body_rights", "figure_rights"):
        with runtime.repo.connect() as conn:
            snapshot = source["body_source_snapshot_id"]
            if change == "figure_rights":
                snapshot = conn.execute("SELECT source_snapshot_id FROM source_artifacts WHERE content_sha256=%s",
                                        (source["resource_manifest"][1]["sha256"],)).fetchone()["source_snapshot_id"]
            conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s", (snapshot,))
    before = _state(runtime)
    with pytest.raises(ValueError, match=f"^{code}$"):
        repair_retained_note_labels(runtime.repo, runtime.article_id, **args)
    assert _state(runtime) == before


def test_retained_notes_rolls_back_candidate_job_and_publication(runtime, archived_notes):
    args, _, _, _, _ = archived_notes
    before = _state(runtime)

    def force_rollback(point):
        assert point == "inside_publication"
        assert runtime.read_current()["canonical_revision_id"] == args["expected_published_revision_id"]
        raise RuntimeError("fixture interrupted publication")

    with pytest.raises(RuntimeError, match="fixture interrupted publication"):
        repair_retained_note_labels(runtime.repo, runtime.article_id, **args, hooks=force_rollback)
    assert _state(runtime) == before
    assert runtime.read_current()["canonical_revision_id"] == args["expected_published_revision_id"]


def test_retained_rotation_removal_replays_exact_v61_archive_and_publishes_one_v64_leaf(runtime):
    original = "Rotate the retaining sleeve clockwise and remove the guide plate."
    replacement = "Turn the retaining sleeve in a clockwise direction and take the guide plate off."
    figure = seed_banktwo_figure(runtime, (
        f"<h2>Service procedure</h2><ol start='3'><li>{original}</li></ol>"
        "<img src='/fixture/figure' alt='Fixture component'><p>Note: Remove the upper cover.</p>"
    ).encode())
    job_id, source_id = seed_banktwo_correction_job(runtime, preserve_notes=True)
    assert run_job(runtime, job_id, CorrectedSource())
    current = runtime.read_current()
    assert current["content_origin"] == "canonical", current["processing_error_code"]
    binding = SimpleNamespace(source_revision_id=source_id)
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        prior, review, decision, attempt, archived_reply, archived_guard, _ = _publication_evidence(
            cur, article, binding, fixture_mode=False, lock=False,
        )
        source = cur.execute("SELECT * FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                             (source_id,)).fetchone()
        owner = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (job_id,)).fetchone()
    assert prior["model_metadata"]["transformation_method"] == SENTENCE_CORRECTION_METHOD
    assert owner["request_generation"] == 1
    assert review is None and decision == "UNREVIEWED"
    assert archived_guard == "full-prose-auto-prompt-v61"
    [image] = prior["canonical_images"]
    assert runtime.objects.get_object(image["storage_key"], max_bytes=1024 * 1024) == figure
    [retained] = [row for row in archived_reply["replacements"] if row["text"] == original]
    assert retained["action"] == "retain"
    path = retained["path"]
    expected = deepcopy(prior["canonical_document"])
    expected_body = {"blocks": expected["blocks"][1:]}
    assert _get(expected_body, path) == original
    _set(expected_body, path, replacement)
    pins = dict(
        expected_job_id=job_id, expected_source_revision_id=source_id,
        expected_descriptor_snapshot_id=article["descriptor_source_snapshot_id"],
        expected_published_revision_id=prior["canonical_article_revision_id"],
        expected_published_hash=prior["rewrite_result_hash"], expected_repaired_hash=digest_json(expected),
        actor="fixture-editor", reason="Reword the exact authored rotation and removal.",
    )
    runtime.reset_counters()
    before = _state(runtime)
    for key, value in (
        ("expected_job_id", uuid4()), ("expected_source_revision_id", uuid4()),
        ("expected_descriptor_snapshot_id", uuid4()), ("expected_published_revision_id", uuid4()),
        ("expected_published_hash", "0" * 64), ("expected_repaired_hash", "0" * 64),
    ):
        with pytest.raises(ValueError, match="^RETAINED_ROTATION_REMOVAL_REPAIR_STALE$"):
            repair_retained_rotation_removal(runtime.repo, runtime.article_id, **(pins | {key: value}))
        assert _state(runtime) == before

    body_snapshot, figure_snapshot = (item["source_snapshot_id"] for item in source["resource_provenance"])
    for snapshot in (body_snapshot, figure_snapshot):
        with runtime.repo.connect() as conn:
            conn.execute("UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=%s",
                         (snapshot,))
        restricted = _state(runtime)
        with pytest.raises(ValueError, match="^RETAINED_NOTE_LABEL_REPAIR_SOURCE_UNAVAILABLE$"):
            repair_retained_rotation_removal(runtime.repo, runtime.article_id, **pins)
        assert _state(runtime) == restricted
        with runtime.repo.connect() as conn:
            conn.execute("UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=%s",
                         (snapshot,))
    before = _state(runtime)

    def force_rollback(point):
        assert point == "inside_publication"
        assert runtime.read_current()["canonical_revision_id"] == pins["expected_published_revision_id"]
        raise RuntimeError("fixture interrupted rotation removal publication")

    with pytest.raises(RuntimeError, match="fixture interrupted rotation removal publication"):
        repair_retained_rotation_removal(runtime.repo, runtime.article_id, **pins, hooks=force_rollback)
    assert _state(runtime) == before

    revision_id = repair_retained_rotation_removal(runtime.repo, runtime.article_id, **pins)
    current = runtime.read_current()
    assert current["canonical_revision_id"] == revision_id != pins["expected_published_revision_id"]
    assert current["source_revision_id"] == source_id
    assert runtime.objects.get_object(image["storage_key"], max_bytes=1024 * 1024) == figure
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        successor, _, _, replay_attempt, reply, guard, _ = _publication_evidence(
            cur, article, binding, fixture_mode=False, lock=False,
        )
        assert cur.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                           (pins["expected_published_revision_id"],)).fetchone() == prior
    assert successor["rewrite_profile_version"] == ROTATION_REMOVAL_PROFILE
    assert successor["model_metadata"]["transformation_method"] == ROTATION_REMOVAL_METHOD
    assert successor["canonical_document"] == expected
    assert successor["canonical_images"] == prior["canonical_images"]
    evidence = successor["model_metadata"][ROTATION_REMOVAL_CHECKPOINT]["evidence"]
    assert evidence["archived_guard_version"] == archived_guard
    assert evidence["guard_version"] == guard == "full-prose-auto-prompt-v64"
    assert evidence["archived_final_reply_hash"] == digest_json(archived_reply)
    assert evidence["repaired_reply_hash"] == digest_json(reply)
    assert evidence["restored_paths"] == [path]
    assert replay_attempt == attempt
    expected_reply = deepcopy(archived_reply)
    [row] = [row for row in expected_reply["replacements"] if row["path"] == path]
    row.update(action="rewrite", text=replacement, reason="")
    assert reply == expected_reply
    after = _state(runtime)
    for table in ("canonical_article_source_revisions", "canonical_article_source_observations",
                  "canonical_article_rewrite_attempts", "source_snapshots", "source_artifacts"):
        assert after[table] == before[table]
    assert len(after["publication_events"]) == len(before["publication_events"]) + 1
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 1}
    with pytest.raises(ValueError, match="^RETAINED_ROTATION_REMOVAL_REPAIR_STALE$"):
        repair_retained_rotation_removal(runtime.repo, runtime.article_id, **pins)
