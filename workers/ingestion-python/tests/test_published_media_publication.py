"""Atomic retained-figure publication using synthetic data and the normal worker."""

from copy import deepcopy
import json
from uuid import uuid4

import pytest

from autodata_ingestion import article_content_review
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_auto import PROFILE as AUTO_PROFILE
from autodata_ingestion.published_media_publication import publish_retained_media_repair
from autodata_ingestion.source_job_persistence import refresh_article_job
from lifecycle_support import fresh_database, runtime
from test_source_revision_reprojection import all_rows, seed_historical_figure


class FixtureModel:
    _model = "fixture-publication-model"

    def __init__(self):
        self.calls = 0

    def complete_json(self, prompt):
        self.calls += 1
        paraphrases = {
            "Remove the pump.": "Take off the pump.",
            "Install the replacement.": "Fit the replacement unit.",
        }
        return {
            "introduction": "This procedure describes pump removal and replacement.",
            "replacements": [{
                "block_id": leaf["block_id"],
                "path": leaf["path"],
                "action": "rewrite",
                "text": paraphrases[leaf["text"]],
                "reason": "",
            } for leaf in json.loads(prompt)["slots"]],
        }


def _run(runtime, model):
    assert run_article_worker_once(runtime.repo, worker_id=uuid4(), registry=runtime.registry,
                                   object_store=runtime.objects, model_client=model)


def _allowlist(tmp_path):
    path = tmp_path / "reviewers.json"
    path.write_text(json.dumps({
        "version": 1, "drafting_identities": [FixtureModel._model],
        "reviewers": {"media-reviewer": {"kind": "synthetic"}, "content-reviewer": {"kind": "synthetic"}},
    }))
    path.chmod(0o600)
    return path


def _seed(runtime, monkeypatch, provider, profile, allowlist, *, body_fixture=None):
    source_id = seed_historical_figure(runtime, monkeypatch, provider, body_fixture=body_fixture)
    model = FixtureModel()
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture",
                        reason="publish historical projection", rewrite_profile_version=profile)
    _run(runtime, model)
    if profile == article_content_review.PROFILE:
        with runtime.repo.connect() as conn:
            article = conn.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                                   (runtime.article_id,)).fetchone()
            job = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                               (article["current_job_id"],)).fetchone()
            row = conn.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s",
                               (job["transformation_key"],)).fetchone()
            fingerprint = conn.execute("SELECT source_fingerprint FROM canonical_article_source_revisions WHERE source_revision_id=%s",
                                       (source_id,)).fetchone()["source_fingerprint"]
        article_content_review.record_review(
            runtime.repo, expected=article_content_review.bindings_for(job, article, row, fingerprint),
            reviewer_id="content-reviewer", allowlist=allowlist, decision="APPROVED",
            rationale="Compared every synthetic instruction with the original procedure.",
            full_content_reviewed=True, fixture_mode=True,
        )
        _run(runtime, model)
    state = runtime.read_current()
    assert state["source_revision_id"] == source_id
    assert state["canonical_revision_id"], runtime.diagnostics()
    assert state["document"]["blocks"][-1]["type"] == "image"
    assert model.calls == (0 if body_fixture else 1)
    return state, model


def _rows(repo):
    rows = all_rows(repo)
    with repo.connect() as conn:
        rows["canonical_article_reviews"] = conn.execute("SELECT * FROM canonical_article_reviews").fetchall()
    return rows


def _preview(runtime, original, tmp_path, capsys):
    from publish_article_media_repair import main

    destination = tmp_path / "approved-layout"
    assert main(["preview", "--article-id", str(runtime.article_id),
                 "--source-revision-id", str(original["source_revision_id"]), "--output", str(destination), "--fixture-mode"],
                repo=runtime.repo, object_store=runtime.objects) == 0
    output = json.loads(capsys.readouterr().out)
    assert set(output) == {"status", "article_id", "manifest_sha256"}
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in destination.iterdir())
    manifest = json.loads((destination / "manifest.json").read_text())
    assert output["manifest_sha256"] == digest_json(manifest)
    return destination, manifest


@pytest.mark.parametrize(("provider", "profile", "review_status", "source_preserving"), [
    ("bankone", AUTO_PROFILE, "UNREVIEWED", False),
    ("banktwo", article_content_review.PROFILE, "APPROVED", False),
    ("banktwo", AUTO_PROFILE, "UNREVIEWED", True),
])
def test_publish_preserves_live_article_and_switches_layout_atomically(
    runtime, monkeypatch, tmp_path, capsys, provider, profile, review_status, source_preserving,
):
    allowlist = _allowlist(tmp_path)
    body_fixture = None
    if source_preserving:
        body_fixture = (json.dumps({"blocks": [
            {"type": "heading", "level": 2, "text": "Pump specifications"},
            {"type": "image", "asset_resource_ref": "figure", "alt": "Pump alignment"},
            {"type": "table", "columns": ["Component", "Torque"], "rows": [["Mounting bolts", "40 Nm"]]},
        ]}).encode(), "application/json")
    original, model = _seed(runtime, monkeypatch, provider, profile, allowlist, body_fixture=body_fixture)
    assert original["review_status"] == review_status
    before = _rows(runtime.repo)
    traffic = runtime.counters()
    destination, manifest = _preview(runtime, original, tmp_path, capsys)
    assert _rows(runtime.repo) == before
    candidate = json.loads((destination / "candidate.json").read_text())
    assert candidate["before"] == original["document"]
    expected_types = ["paragraph", "heading", "image", "table"] if source_preserving else ["paragraph", "paragraph", "image", "paragraph"]
    assert [block["type"] for block in candidate["after"]["blocks"]] == expected_types
    assert (manifest["original_attempt_id"] is None) == source_preserving

    def lose_transaction(point):
        assert point == "inside_publication"
        assert runtime.read_current() == original
        assert _rows(runtime.repo) == before
        raise RuntimeError("fixture transaction lost")

    rationale = "Compared archive placement with the exact published procedure and asset."
    kwargs = dict(expected=manifest, object_store=runtime.objects, reviewer_id="media-reviewer",
                  allowlist=allowlist, rationale=rationale, fixture_mode=True)
    with pytest.raises(RuntimeError, match="fixture transaction lost"):
        publish_retained_media_repair(runtime.repo, hooks=lose_transaction, **kwargs)
    assert _rows(runtime.repo) == before and runtime.read_current() == original

    from publish_article_media_repair import main
    assert main(["publish", "--expected", str(destination / "manifest.json"), "--reviewer", "media-reviewer",
                 "--allowlist", str(allowlist), "--rationale", rationale, "--fixture-mode"],
                repo=runtime.repo, object_store=runtime.objects) == 0
    published = json.loads(capsys.readouterr().out)
    state = runtime.read_current()
    assert published["status"] == "published"
    assert published["canonical_revision_id"] == str(state["canonical_revision_id"])
    assert published["source_revision_id"] == str(state["source_revision_id"])
    assert state["canonical_revision_id"] != original["canonical_revision_id"]
    assert state["source_revision_id"] != original["source_revision_id"]
    assert state["body"] == original["body"]
    assert state["review_status"] == review_status
    assert state["document"] == candidate["after"]
    assert state["document"]["blocks"][2]["alt"] == "Pump alignment"
    assert state["source_content_sha256"] == original["source_content_sha256"]
    after = _rows(runtime.repo)
    for table in ("canonical_article_rewrite_attempts", "source_snapshots", "source_artifacts"):
        assert after[table] == before[table]
    for table in ("canonical_article_source_revisions", "canonical_article_revisions", "publication_events",
                  "canonical_article_source_observations", "source_fetch_jobs"):
        assert len(after[table]) == len(before[table]) + 1
        assert all(row in after[table] for row in before[table])
    assert len(after["canonical_article_reviews"]) == len(before["canonical_article_reviews"]) + (review_status == "APPROVED")
    repeat = publish_retained_media_repair(runtime.repo, **kwargs)
    assert repeat == {**published, "status": "already_published"}
    assert _rows(runtime.repo) == after
    assert model.calls == (0 if source_preserving else 1)
    assert runtime.counters() == {**traffic, "schedule": traffic["schedule"] + 1}

    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="same source bytes refresh")
    _run(runtime, model)
    refreshed = runtime.read_current()
    assert refreshed["canonical_revision_id"] == state["canonical_revision_id"]
    assert refreshed["source_revision_id"] == state["source_revision_id"]
    assert refreshed["review_status"] == state["review_status"]
    assert model.calls == (0 if source_preserving else 1)
    assert _rows(runtime.repo)["publication_events"] == after["publication_events"]


@pytest.mark.parametrize("condition", ["changed_hash", "not_allowlisted", "withdrawn", "refresh_pending", "generation_changed", "rejected"])
def test_publish_fences_bad_approval_and_stale_rights(runtime, monkeypatch, tmp_path, capsys, condition):
    allowlist = _allowlist(tmp_path)
    original, model = _seed(runtime, monkeypatch, "bankone", AUTO_PROFILE, allowlist)
    _, manifest = _preview(runtime, original, tmp_path, capsys)
    reviewer = "media-reviewer"
    if condition == "changed_hash":
        manifest = {**manifest, "repaired_published_document_hash": "0" * 64}
        error = "STALE"
    elif condition == "not_allowlisted":
        reviewer = "unlisted"
        error = "REVIEWER_FORBIDDEN"
    elif condition == "withdrawn":
        with runtime.repo.connect() as conn:
            conn.execute("""UPDATE source_snapshots SET takedown_status='takedown'
                WHERE content_sha256=(SELECT resource_manifest->1->>'sha256'
                FROM canonical_article_source_revisions WHERE source_revision_id=%s)""", (original["source_revision_id"],))
        error = "WITHDRAWN"
    elif condition in ("refresh_pending", "generation_changed"):
        refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="concurrent refresh")
        if condition == "generation_changed":
            _run(runtime, model)
            assert runtime.read_current()["canonical_revision_id"] == original["canonical_revision_id"]
        error = "ACTIVE_NORMAL_JOB" if condition == "refresh_pending" else "STALE"
    else:
        with runtime.repo.connect() as conn:
            conn.execute("""
                INSERT INTO canonical_article_reviews(canonical_article_review_id,canonical_article_revision_id,
                    authorized_reviewer_id,decision,reason) VALUES (%s,%s,'reviewer','REJECTED','Synthetic rejection')
                """, (uuid4(), original["canonical_revision_id"]))
        error = "REVIEW_REQUIRED"
    before = _rows(runtime.repo)
    with pytest.raises(ValueError, match=error):
        publish_retained_media_repair(
            runtime.repo, expected=deepcopy(manifest), object_store=runtime.objects,
            reviewer_id=reviewer, allowlist=allowlist, fixture_mode=True,
            rationale="Compared archive placement with the exact published procedure and asset.",
        )
    assert _rows(runtime.repo) == before


@pytest.mark.parametrize("profile", ["technical-prose-v1", "technical-prose-v2"])
def test_publish_historical_technical_profile(runtime, monkeypatch, tmp_path, capsys, profile):
    allowlist = _allowlist(tmp_path)
    if profile == "technical-prose-v1":
        source_id = seed_historical_figure(runtime, monkeypatch, "bankone", publish=True)
        model = FixtureModel()
    else:
        body = (
            b'<p>Remove the pump.</p><img data-resource-ref="figure" alt="Pump alignment">'
            b'<p>Install the cover.</p>'
        )
        source_id = seed_historical_figure(runtime, monkeypatch, "banktwo", body_fixture=(body, "text/html"))

        class SelectPlan(FixtureModel):
            def complete_json(self, prompt):
                self.calls += 1
                plan = json.loads(prompt)["plan"]
                return {"operations": [
                    {key: op[key] for key in ("block_id", "path", "operation_id")}
                    for op in plan["operations"]
                ]}

        model = SelectPlan()
        refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="historical grammar",
                            rewrite_profile_version=profile)
        _run(runtime, model)
        assert model.calls == 1
    original = runtime.read_current()
    assert original["source_revision_id"] == source_id
    assert original["canonical_revision_id"], runtime.diagnostics()
    assert original["document"]["blocks"][-1]["type"] == "image"
    before = _rows(runtime.repo)
    _, manifest = _preview(runtime, original, tmp_path, capsys)
    assert manifest["profile_version"] == profile
    assert _rows(runtime.repo) == before
    result = publish_retained_media_repair(
        runtime.repo, expected=manifest, object_store=runtime.objects,
        reviewer_id="media-reviewer", allowlist=allowlist, fixture_mode=True,
        rationale="Compared archive placement with the exact published procedure and asset.",
    )
    state = runtime.read_current()
    assert result["canonical_revision_id"] == str(state["canonical_revision_id"])
    assert state["body"] == original["body"] and state["review_status"] == original["review_status"]
    assert [block["type"] for block in state["document"]["blocks"]] == ["paragraph", "image", "paragraph"]
    assert _rows(runtime.repo)["canonical_article_rewrite_attempts"] == before["canonical_article_rewrite_attempts"]
    calls = model.calls
    refresh_article_job(runtime.repo, runtime.article_id, actor="fixture", reason="same bytes after history repair")
    _run(runtime, model)
    assert model.calls == calls
    assert runtime.read_current()["canonical_revision_id"] == state["canonical_revision_id"]


@pytest.mark.parametrize(("provider", "profile", "numbered_only", "legacy_projection"), [
    ("bankone", AUTO_PROFILE, True, "source-projection-v2"),
    ("banktwo", article_content_review.PROFILE, False, "source-projection-v3"),
    ("banktwo", "technical-prose-v1", False, "source-projection-v2"),
    ("bankone", "technical-prose-v2", False, "source-projection-v2"),
])
def test_publish_retained_ordinals_preserves_prose_and_visibility(
    runtime, monkeypatch, tmp_path, capsys, provider, profile, numbered_only, legacy_projection,
):
    from dataclasses import replace
    from io import BytesIO
    from PIL import Image
    from autodata_ingestion import source_article_capture as capture
    from autodata_ingestion.article_lifecycle_store import load_source_revision
    from autodata_ingestion.published_media_publication import ORDINAL_SCHEMA
    from publish_article_media_repair import main

    runtime.article_id = runtime.articles[provider]
    server = runtime.servers[provider]
    procedure = (
        b'<ol start="4"><li>Remove the pump.</li><li value="9">Install the cover.</li></ol>'
    )
    if numbered_only:
        # Four historical blocks also satisfy the original authoritative layout
        # check. Test ordinal repair on a retained article with only a body.
        body = json.dumps({"blocks": [
            {"type": "heading", "level": 2, "text": "Service procedure"},
            {"type": "heading", "level": 3, "text": "Pump"},
            {"type": "ordered_list", "start": 4, "items": [
                "Remove the pump.", {"number": 9, "text": "Install the cover."},
            ]},
            {"type": "heading", "level": 3, "text": "End of procedure"},
        ]}).encode()
        server.body(body, "application/json")
    else:
        body = procedure + b'<img data-resource-ref="figure" alt="Reference marks">'
        if profile == article_content_review.PROFILE:
            drawing = (b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
                       b'<rect width="24" height="24" fill="green"/></svg>')
            server.body(drawing, "image/svg+xml", ref="figure", kind="asset")
        else:
            figure = BytesIO()
            Image.new("RGB", (24, 24), "green").save(figure, format="PNG")
            server.body(figure.getvalue(), "image/png", ref="figure", kind="asset")
        server.body(body, "text/html", assets=["figure"])

    capture_current = capture.capture_source_article

    def before_ordinals(*args, **kwargs):
        result = capture_current(*args, **kwargs)
        document = deepcopy(result.source_document)
        ordered = next(block for block in document["blocks"] if block["type"] == "ordered_list")
        assert ordered.pop("start") == 4
        ordered["items"][1] = ordered["items"][1]["text"]
        body, steps, images = capture.project_document(document)
        return replace(result, source_document=document, source_body=body, source_steps=steps,
                       source_images=images, projection_version=legacy_projection)

    class SavedRewrite(FixtureModel):
        def complete_json(self, prompt):
            self.calls += 1
            value = json.loads(prompt)
            if profile == "technical-prose-v2":
                return {"operations": [{key: operation[key] for key in ("block_id", "path", "operation_id")}
                                       for operation in value["plan"]["operations"]]}
            phrases = {"Remove the pump.": "Take off the pump.", "Install the cover.": "Fit the cover."}
            replacements = [
                {"block_id": slot["block_id"], "path": slot["path"], "text": phrases[slot["text"]]}
                for slot in value["slots"]
            ]
            if profile == "technical-prose-v1":
                return {"replacements": replacements}
            return {"introduction": "This procedure covers pump removal.",
                    "replacements": [{**entry, "action": "rewrite", "reason": ""} for entry in replacements]}

    allowlist = _allowlist(tmp_path)
    model = SavedRewrite()
    with runtime.repo.connect() as conn:
        conn.execute(
            "UPDATE canonical_articles SET target_rewrite_profile_version=%s WHERE canonical_article_id=%s",
            (profile, runtime.article_id),
        )
    from autodata_ingestion.source_job_persistence import ensure_article_job

    with monkeypatch.context() as legacy:
        legacy.setattr(capture, "capture_source_article", before_ordinals)
        ensure_article_job(runtime.repo, runtime.article_id, normalization_version="ordered-article-v1",
                           rewrite_profile_version=profile)
        _run(runtime, model)
    if profile == article_content_review.PROFILE:
        with runtime.repo.connect() as conn:
            article = conn.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                                   (runtime.article_id,)).fetchone()
            job = conn.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s",
                               (article["current_job_id"],)).fetchone()
            row = conn.execute("SELECT * FROM canonical_article_revisions WHERE transformation_key=%s",
                               (job["transformation_key"],)).fetchone()
        source = load_source_revision(runtime.repo, row["source_revision_id"])
        article_content_review.record_review(
            runtime.repo, expected=article_content_review.bindings_for(job, article, row, source.source_fingerprint),
            reviewer_id="content-reviewer", allowlist=allowlist, decision="APPROVED",
            rationale="Compared every synthetic instruction with the original procedure.",
            full_content_reviewed=True, fixture_mode=True,
        )
        _run(runtime, model)

    original = runtime.read_current()
    assert original["canonical_revision_id"], runtime.diagnostics()
    assert model.calls == 1
    before = _rows(runtime.repo)
    destination = tmp_path / "ordinal-preview"
    assert main(["preview", "--ordinals", "--article-id", str(runtime.article_id),
                 "--source-revision-id", str(original["source_revision_id"]), "--output", str(destination),
                 "--fixture-mode"], repo=runtime.repo, object_store=runtime.objects) == 0
    output = json.loads(capsys.readouterr().out)
    manifest = json.loads((destination / "manifest.json").read_text())
    assert manifest["schema"] == ORDINAL_SCHEMA
    assert manifest["repaired_projection_version"] == "source-projection-v4"
    assert output["manifest_sha256"] == digest_json(manifest)
    assert _rows(runtime.repo) == before

    args = dict(expected=manifest, object_store=runtime.objects, reviewer_id="media-reviewer",
                allowlist=allowlist, rationale="Compared original procedure numbering against the retained source.",
                fixture_mode=True)
    with pytest.raises(ValueError, match="PUBLISHED_MEDIA_REPAIR_STALE"):
        publish_retained_media_repair(runtime.repo, **{**args, "expected": {
            **manifest, "repaired_published_document_hash": "0" * 64,
        }})
    assert runtime.read_current() == original and _rows(runtime.repo) == before

    result = publish_retained_media_repair(runtime.repo, **args)
    assert result["status"] == "published"
    assert publish_retained_media_repair(runtime.repo, **args) == {**result, "status": "already_published"}
    updated = runtime.read_current()
    assert updated["canonical_revision_id"] != original["canonical_revision_id"]
    assert updated["review_status"] == original["review_status"]
    assert updated["body"] == original["body"] and updated["images"] == original["images"]
    if profile == article_content_review.PROFILE:
        assert updated["images"][0]["media_type"] == "image/png"
    source = load_source_revision(runtime.repo, updated["source_revision_id"])
    assert source.projection_version == "source-projection-v4"
    assert [step["number"] for step in source.source_steps] == [4, 9]
    assert [step["number"] for step in updated["steps"]] == [4, 9]
    assert _rows(runtime.repo)["canonical_article_rewrite_attempts"] == before["canonical_article_rewrite_attempts"]

    runtime.refresh()
    _run(runtime, model)
    assert model.calls == 1
    assert runtime.read_current()["canonical_revision_id"] == updated["canonical_revision_id"]
