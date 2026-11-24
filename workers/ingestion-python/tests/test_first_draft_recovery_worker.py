"""Recover one verbatim automatic draft through the ordinary article worker."""

from io import BytesIO
import json

from PIL import Image
import pytest

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, digest_json
from autodata_ingestion.procedure_rewrite_recovery import (
    FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    FIRST_DRAFT_RECOVERY_METHOD,
)
from autodata_ingestion.published_media_publication import _publication_evidence
from autodata_ingestion.source_job_persistence import ensure_article_job
from lifecycle_support import fresh_database, runtime
from test_source_bound_correction_worker import attempt_rows
from test_source_bound_rewrite_worker import run_job


COVER = "Remove the upper cover."
TORQUE = "Tighten the bolts to 18 N·m."


class EchoedDraft:
    _model = "fixture-auto"

    def __init__(self, variant="exact"):
        self.variant = variant
        self.responses = []

    def complete_json(self, prompt):
        request = json.loads(prompt)
        assert request["profile_version"] == AUTOMATIC_REWRITE_PROFILE
        slots = request["slots"]
        assert [(slot["text"], slot["required_action"]) for slot in slots] == [(COVER, "rewrite"), (TORQUE, "retain")]
        rows = [{
            "block_id": slot["block_id"], "path": slot["path"], "text": slot["text"],
            "action": slot["required_action"], "reason": "Preserve the exact specification." if slot["text"] == TORQUE else "",
        } for slot in slots]
        if self.variant == "retain":
            rows[0].update(action="retain", reason="Keep the source wording.")
        if self.variant == "near-copy":
            rows[0]["text"] = "First, remove the upper cover."
        if self.variant == "changed-torque":
            rows[1]["text"] = "Tighten the bolts to 8 N·m."
        result = {"introduction": "This article describes service information.", "replacements": rows}
        self.responses.append(result)
        return result


def queue_article(runtime, *, figure=False, instruction=COVER):
    connector = runtime.servers["bankone"]
    illustration = ""
    resource = {}
    if figure:
        illustration = "<img src='/fixture/diagram' alt='Cover locations'>"
        resource = {"assets": ["figure"], "asset_bindings": [{
            "source_url": "/fixture/diagram", "resource_ref": "figure",
        }]}
        image = BytesIO()
        Image.new("RGB", (10, 8), (23, 89, 132)).save(image, format="PNG")
        connector.body(image.getvalue(), media_type="image/png", ref="figure", kind="asset")
    connector.body((f"<h2>Upper Cover Service</h2><ol start='3'><li>{instruction}</li></ol>"
                    f"{illustration}<p>{TORQUE}</p>").encode(), **resource)
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE canonical_articles SET target_rewrite_profile_version=%s WHERE canonical_article_id=%s",
                     (AUTOMATIC_REWRITE_PROFILE, runtime.article_id))
    return ensure_article_job(
        runtime.repo, runtime.article_id, normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    ).job_id


def test_echoed_draft_reuses_one_delivery_and_preserves_retained_media(runtime):
    job_id = queue_article(runtime, figure=True)
    model = EchoedDraft()
    source_at_dispatch = []

    class WorkerStopped(Exception):
        pass

    def observe_then_interrupt(phase):
        if phase == "after_model_dispatch":
            source = runtime.read_current()
            assert source["content_origin"] == "source" and source["availability"] == "available"
            assert COVER in source["body"] and TORQUE in source["body"]
            assert source["images"][0]["status"] == "available"
            [sent] = attempt_rows(runtime, job_id)
            assert sent["status"] == "dispatched" and sent["response"] is None
            assert model.responses == []
            source_at_dispatch.append(source)
        if phase == "after_model_result_commit":
            raise WorkerStopped

    with pytest.raises(WorkerStopped):
        run_job(runtime, job_id, model, registry=runtime.registry, hooks=observe_then_interrupt)
    [source] = source_at_dispatch
    [archived] = attempt_rows(runtime, job_id)
    [raw] = model.responses
    assert raw["replacements"][0]["text"] == COVER
    assert archived["status"] == "succeeded" and archived["response"] == raw
    assert archived["response_hash"] == digest_json(raw)
    assert runtime.read_current()["content_origin"] == "source"
    assert runtime.counters() == {"source": 1, "asset": 1, "model": 0, "schedule": 1}
    runtime.reset_counters()
    runtime.expire_lease(job_id)
    assert run_job(runtime, None, None)
    assert not run_job(runtime, None, model)

    current = runtime.read_current()
    assert current["content_origin"] == "canonical"
    assert current["canonical_revision_id"] == archived["canonical_article_revision_id"]
    assert current["source_revision_id"] == source["source_revision_id"]
    assert "The upper cover must be removed." in current["body"] and TORQUE in current["body"]
    assert [block["start"] for block in current["document"]["blocks"] if block["type"] == "ordered_list"] == [3]
    assert current["images"] == [{**image, "source_order": image["source_order"] + 1} for image in source["images"]]
    assert attempt_rows(runtime, job_id) == [archived]
    assert model.responses == [raw]
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}

    binding = store.load_source_revision(runtime.repo, source["source_revision_id"])
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        revision, _, decision, attempt, effective, version, _ = _publication_evidence(
            cur, article, binding, fixture_mode=True, lock=False,
        )
        events = cur.execute("SELECT canonical_article_revision_id FROM publication_events").fetchall()
    assert events == [{"canonical_article_revision_id": current["canonical_revision_id"]}]
    assert decision == "UNREVIEWED" and attempt == archived
    assert revision["model_metadata"]["transformation_method"] == FIRST_DRAFT_RECOVERY_METHOD
    evidence = revision["model_metadata"]["first_draft_recovery"]
    assert evidence["raw_response_hash"] == archived["response_hash"]
    assert evidence["guard_version"] == version
    assert effective["replacements"][0]["text"] == "The upper cover must be removed."
    assert effective["replacements"][1] == raw["replacements"][1]


@pytest.mark.parametrize(("variant", "error_code"), (
    ("retain", "REWRITE_UNCHANGED"),
    ("near-copy", "REWRITE_PROSE_TOO_SIMILAR"),
    ("changed-torque", "REWRITE_UNCHANGED"),
))
def test_echoed_draft_does_not_relax_other_rewrite_guards(runtime, variant, error_code):
    job_id = queue_article(runtime)
    model = EchoedDraft(variant)
    assert run_job(runtime, job_id, model, registry=runtime.registry)

    current = runtime.read_current()
    assert current["content_origin"] == "source" and current["canonical_revision_id"] is None
    assert current["processing_error_code"] == error_code
    assert COVER in current["body"] and TORQUE in current["body"]
    [archived] = attempt_rows(runtime, job_id)
    [raw] = model.responses
    assert archived["status"] == "failed" and archived["error_code"] == error_code
    assert archived["response"] == raw and archived["response_hash"] == digest_json(raw)
    assert not run_job(runtime, None, model)
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT 1 FROM publication_events").fetchone() is None


def test_worker_replays_recovery_with_its_original_response_and_media(runtime):
    instruction = "Install the guide plate. For additional information, refer to Section 410-07C ."
    job_id = queue_article(runtime, figure=True, instruction=instruction)

    class ChangedReference:
        _model = "fixture-auto"

        def complete_json(self, prompt):
            slots = json.loads(prompt)["slots"]
            assert [(s["text"], s["required_action"]) for s in slots] == [
                (instruction, "rewrite"), (TORQUE, "retain"),
            ]
            self.raw = {
                "introduction": "This article covers the service sequence for the cover.",
                "replacements": [
                    {
                        "block_id": s["block_id"], "path": s["path"],
                        "action": s["required_action"], "text": s["text"],
                        "reason": "Keep the technical value." if s["required_action"] == "retain" else "",
                    }
                    for s in slots
                ],
            }
            self.raw["replacements"][0]["text"] = "Put the guide plate in place. See Section 510-07C."
            return self.raw

    model = ChangedReference()
    assert run_job(runtime, job_id, model, registry=runtime.registry)
    current = runtime.read_current()
    assert current["content_origin"] == "canonical"
    assert "Fit the guide plate. Details are in Section 410-07C." in current["body"]
    assert "510-07C" not in current["body"]
    assert current["images"][0]["status"] == "available"

    [archived] = attempt_rows(runtime, job_id)
    binding = store.load_source_revision(runtime.repo, current["source_revision_id"])
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        revision, _, _, attempt, effective, _, _ = _publication_evidence(
            cur, article, binding, fixture_mode=True, lock=False,
        )
        assert conn.execute("SELECT count(*) AS n FROM publication_events").fetchone()["n"] == 1
    assert attempt == archived and archived["response"] == model.raw
    assert revision["model_metadata"]["transformation_method"] == FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD
    assert revision["model_metadata"]["first_draft_recovery"]["raw_response_hash"] == digest_json(model.raw)
    assert effective["replacements"][0]["text"] == "Fit the guide plate. Details are in Section 410-07C."
