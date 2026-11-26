"""Exercise the real publication-stage failure and its archived repair."""

from copy import deepcopy
import json

import pytest

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.published_media_publication import _publication_evidence
from autodata_ingestion.retained_introduction_repair import COPIED_INTRODUCTION, repair_retained_introduction
from lifecycle_support import fresh_database, runtime
from test_first_draft_recovery_worker import queue_article, scope_fixture_article
from test_source_bound_correction_worker import attempt_rows
from test_source_bound_rewrite_worker import run_job


SOURCE = "The acoustic insulation softens vibration from the ventilation system."
REWRITE = "Vibration from the ventilation unit is damped by the acoustic insulation."
INTRODUCTION = "This article describes the service information that follows."


class CopiedIntroduction:
    _model = "fixture-introduction"

    def complete_json(self, prompt):
        payload = json.loads(prompt)
        return {"introduction": SOURCE, "replacements": [
            {"block_id": slot["block_id"], "path": slot["path"], "action": "rewrite",
             "text": REWRITE, "reason": ""}
            if slot["text"] == SOURCE else
            {"block_id": slot["block_id"], "path": slot["path"], "action": "retain",
             "text": slot["text"], "reason": "Preserve the exact specification."}
            for slot in payload["slots"]
        ]}


def test_repair_copied_introduction_reuses_validated_body_and_rolls_back(runtime):
    scope_fixture_article(runtime)
    job_id = queue_article(runtime, figure=True, instruction=SOURCE)
    assert run_job(runtime, job_id, CopiedIntroduction(), registry=runtime.registry)
    before = runtime.read_current()
    assert before["processing_error_code"] == COPIED_INTRODUCTION
    assert before["content_origin"] == "source" and before["canonical_revision_id"] is None
    [archived] = attempt_rows(runtime, job_id)
    assert archived["status"] == "succeeded"
    draft_id = archived["canonical_article_revision_id"]
    with runtime.repo.connect() as conn:
        draft = conn.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                             (draft_id,)).fetchone()
    assert draft["status"] == "validated" and len(draft["canonical_images"]) == 1
    repaired_doc = deepcopy(draft["canonical_document"])
    repaired_doc["blocks"][0]["text"] = INTRODUCTION
    assert repaired_doc != draft["canonical_document"]

    kwargs = dict(
        expected_job_id=job_id, expected_source_revision_id=before["source_revision_id"],
        expected_draft_revision_id=draft_id, expected_reply_hash=archived["response_hash"],
        expected_repaired_hash=digest_json(repaired_doc), actor="fixture-editor",
        reason="Replace only the copied introduction in the verified archive.",
    )
    runtime.reset_counters()
    with pytest.raises(ValueError, match="^RETAINED_INTRODUCTION_REPAIR_STALE$"):
        repair_retained_introduction(runtime.repo, runtime.article_id, **{**kwargs, "expected_reply_hash": "0" * 64})
    assert runtime.read_current() == before

    def interrupt(event):
        assert event == "inside_publication"
        raise RuntimeError("interrupt publication transaction")

    with pytest.raises(RuntimeError, match="interrupt publication transaction"):
        repair_retained_introduction(runtime.repo, runtime.article_id, **kwargs, hooks=interrupt)
    assert runtime.read_current() == before
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 0

    revision = repair_retained_introduction(runtime.repo, runtime.article_id, **kwargs)
    after = runtime.read_current()
    assert (after["canonical_revision_id"], after["source_revision_id"], after["content_origin"]) == (
        revision, before["source_revision_id"], "canonical",
    )
    assert after["document"] == repaired_doc and after["images"] == draft["canonical_images"]
    assert attempt_rows(runtime, job_id) == [archived] and attempt_rows(runtime, after["job_id"]) == []
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 1}
    binding = store.load_source_revision(runtime.repo, before["source_revision_id"])
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        row, _, _, attempt, response, _, _ = _publication_evidence(cur, article, binding, fixture_mode=False, lock=False)
        assert row["canonical_article_revision_id"] == revision and attempt == archived
        assert response == {**archived["response"], "introduction": INTRODUCTION}
        assert cur.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 1
    with pytest.raises(ValueError, match="^RETAINED_INTRODUCTION_REPAIR_STALE$"):
        repair_retained_introduction(runtime.repo, runtime.article_id, **kwargs)
    assert runtime.read_current() == after
