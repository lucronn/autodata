"""Recover one verbatim automatic draft through the ordinary article worker."""

from io import BytesIO
import json

from PIL import Image
import pytest

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion import procedure_rewrite_recovery as recovery
from autodata_ingestion.article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION, SOURCE_BOUND_CORRECTION_PROFILE, digest_json,
)
from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
from autodata_ingestion.procedure_rewrite_correction import ARCHIVED_FIRST_DRAFT_METHOD
from autodata_ingestion.procedure_rewrite_recovery import (
    BANKONE_STRUCTURAL_RECOVERY_METHOD,
    FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD,
    FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD,
    FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD,
    FIRST_DRAFT_RECOVERY_METHOD,
    FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
)
from autodata_ingestion.published_media_publication import _publication_evidence
from autodata_ingestion.source_job_persistence import (
    ensure_article_job, publish_source_bound_first_draft, read_bankone_archive_structure,
    source_bound_correction_prior_attempt,
)
from lifecycle_support import fresh_database, runtime, seed_configuration
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


def scope_fixture_article(runtime):
    configuration = seed_configuration(runtime.repo, runtime.vehicle)
    with runtime.repo.connect() as conn:
        conn.execute("UPDATE vehicle_configurations SET trim='Touring' WHERE vehicle_configuration_id=%s",
                     (configuration,))
    for job in ensure_article_catalog_jobs(
        runtime.repo, vehicle_id=runtime.vehicle, vehicle_configuration_id=configuration,
    ):
        assert run_job(runtime, job.job_id, None, registry=runtime.registry)
    with runtime.repo.connect() as conn:
        runtime.article_id = conn.execute("""
            SELECT canonical_article_id FROM canonical_articles
            WHERE vehicle_configuration_id=%s AND provider_slug='bankone'
            """, (configuration,)).fetchone()["canonical_article_id"]


def test_publish_archived_first_draft_is_atomic_and_reuses_the_figure(runtime, monkeypatch):
    scope_fixture_article(runtime)
    prior_id = queue_article(runtime, figure=True)
    model = EchoedDraft()
    # Reproduce an older worker that stored the error and the model reply.
    with monkeypatch.context() as old_worker:
        old_worker.setattr(recovery, "recover_first_draft", lambda *_args, **_kwargs: None)
        assert run_job(runtime, prior_id, model, registry=runtime.registry)
    source = runtime.read_current()
    assert source["content_origin"] == "source" and source["availability"] == "available"
    assert source["processing_error_code"] == "REWRITE_UNCHANGED"
    assert source["job_id"] == prior_id and source["canonical_revision_id"] is None
    [archived] = attempt_rows(runtime, prior_id)
    assert archived["status"] == "failed" and archived["response"] == model.responses[0]
    assert len(source["images"]) == 1 and source["images"][0]["status"] == "available"
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        prior = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (prior_id,)).fetchone()
        [old_revision] = cur.execute("SELECT * FROM canonical_article_revisions").fetchall()
        attempt = source_bound_correction_prior_attempt(cur, prior, first_draft=True)
    assert prior["status"] == "dead_letter" and old_revision["status"] == "building"
    reviewed = recovery.recover_first_draft(
        prior["checkpoint"]["normalized_document"], archived["response"],
        prompt_version=attempt["guard_version"], method=FIRST_DRAFT_RECOVERY_METHOD,
    )
    assert reviewed.document is not None and reviewed.error_code is None
    output_hash = reviewed.evidence["output_hash"]
    assert output_hash == digest_json(reviewed.document)
    arguments = {
        "expected_job_id": prior_id, "expected_source_revision_id": source["source_revision_id"],
        "recovery_method": FIRST_DRAFT_RECOVERY_METHOD, "expected_recovery_hash": output_hash,
        "actor": "fixture-editor", "reason": "Publish a checked recovery of the archived draft.",
    }

    class PublicationInterrupted(Exception):
        pass

    def interrupt(phase):
        assert phase == "inside_publication"
        raise PublicationInterrupted

    runtime.reset_counters()
    with pytest.raises(ValueError, match="FIRST_DRAFT_ARCHIVE_RECOVERY_MISMATCH"):
        publish_source_bound_first_draft(runtime.repo, runtime.article_id, **{**arguments, "expected_recovery_hash": "0" * 64})
    with pytest.raises(PublicationInterrupted):
        publish_source_bound_first_draft(runtime.repo, runtime.article_id, **arguments, hooks=interrupt)

    assert runtime.read_current() == source
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
    with runtime.repo.connect() as conn:
        assert conn.execute("SELECT * FROM canonical_article_revisions").fetchall() == [old_revision]
        assert conn.execute("SELECT 1 FROM publication_events").fetchone() is None

    published = publish_source_bound_first_draft(runtime.repo, runtime.article_id, **arguments)
    joined = publish_source_bound_first_draft(runtime.repo, runtime.article_id, **arguments)
    assert published.created and not joined.created
    assert published.job_id != prior_id and published.job_id == joined.job_id
    assert published.state == joined.state == "completed"
    current = runtime.read_current()
    assert current["canonical_revision_id"] == published.published_revision_id == joined.published_revision_id
    assert current["source_revision_id"] == source["source_revision_id"]
    assert current["content_origin"] == "canonical"
    assert "The upper cover must be removed." in current["body"] and TORQUE in current["body"]
    assert [block["start"] for block in current["document"]["blocks"] if block["type"] == "ordered_list"] == [3]
    assert current["images"] == [{**image, "source_order": image["source_order"] + 1} for image in source["images"]]
    assert attempt_rows(runtime, published.job_id) == [] and attempt_rows(runtime, prior_id) == [archived]
    assert len(model.responses) == 1
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 1}

    binding = store.load_source_revision(runtime.repo, source["source_revision_id"])
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        revision, _, _, provenance, effective, guard, _ = _publication_evidence(
            cur, article, binding, fixture_mode=True, lock=False,
        )
        assert cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (prior_id,)).fetchone() == prior
        assert cur.execute("SELECT * FROM canonical_article_revisions WHERE canonical_article_revision_id=%s",
                           (old_revision["canonical_article_revision_id"],)).fetchone() == old_revision
        assert cur.execute("SELECT canonical_article_revision_id FROM publication_events").fetchall() == [
            {"canonical_article_revision_id": published.published_revision_id},
        ]
        assert cur.execute("SELECT count(*) AS n FROM canonical_article_source_observations").fetchone()["n"] == 1
    assert revision["rewrite_profile_version"] == SOURCE_BOUND_CORRECTION_PROFILE
    assert revision["model_metadata"]["transformation_method"] == ARCHIVED_FIRST_DRAFT_METHOD
    assert revision["rewrite_result_hash"] != output_hash
    assert provenance["rewrite_attempt_id"] == archived["rewrite_attempt_id"]
    assert provenance["response_hash"] == archived["response_hash"]
    assert effective == reviewed.response and guard == attempt["guard_version"]


def test_bankone_archive_requires_verified_body_and_retains_authored_alternatives(runtime):
    scope_fixture_article(runtime)
    authored = (
        'Fixture test adapter (2) » Remove <mtr-doc-link id="fixture-a">ordinary adapter</mtr-doc-link> '
        '(test scope), <mtr-doc-link id="fixture-b">adapter (top to middle)</mtr-doc-link>, '
        '<mtr-doc-link id="fixture-c">adapter (left to right)</mtr-doc-link>, or '
        '<mtr-doc-link id="fixture-d">adapter (front to rear)</mtr-doc-link>'
    )
    prior_id = queue_article(runtime, figure=True, instruction=authored)

    class CloseCopy:
        _model = "fixture-auto"

        def complete_json(self, prompt):
            slots = json.loads(prompt)["slots"]
            return {"introduction": "This article covers the service information that follows.", "replacements": [
                {"block_id": slot["block_id"], "path": slot["path"], "action": slot["required_action"],
                 "text": f"First, {slot['text']}" if slot["required_action"] == "rewrite" else slot["text"],
                 "reason": "Preserve the authored parameter." if slot["required_action"] == "retain" else ""}
                for slot in slots
            ]}

    assert run_job(runtime, prior_id, CloseCopy(), registry=runtime.registry)
    source = runtime.read_current()
    assert source["content_origin"] == "source" and source["availability"] == "available"
    assert source["processing_error_code"] == "REWRITE_PROSE_TOO_SIMILAR"
    source_id = source["source_revision_id"]
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        prior = cur.execute("SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (prior_id,)).fetchone()
        attempt = source_bound_correction_prior_attempt(cur, prior, first_draft=True)
    structure = read_bankone_archive_structure(
        runtime.repo, runtime.article_id, prior_id, source_id, object_store=runtime.objects,
    )
    [slot] = structure["proof"]["slots"].values()
    assert slot["kind"] == "alternatives" and len(slot["reference_hashes"]) == 4
    checked = recovery.recover_structured_bankone_first_draft(
        prior["checkpoint"]["normalized_document"], attempt, structure["proof"],
    )
    assert checked is not None and checked.error_code is None
    arguments = dict(
        expected_job_id=prior_id, expected_source_revision_id=source_id, recovery_method=BANKONE_STRUCTURAL_RECOVERY_METHOD,
        expected_recovery_hash=checked.evidence["output_hash"], actor="fixture-editor", reason="Check the retained choices.",
    )

    class WrongBody:
        def get_object(self, key, *, max_bytes):
            return b"<p>Changed fixture body.</p>"

    runtime.reset_counters()
    with pytest.raises(ValueError, match="FIRST_DRAFT_ARCHIVE_STRUCTURE_MISMATCH"):
        publish_source_bound_first_draft(runtime.repo, runtime.article_id, object_store=WrongBody(), **arguments)
    assert runtime.read_current() == source
    published = publish_source_bound_first_draft(runtime.repo, runtime.article_id, object_store=runtime.objects, **arguments)
    joined = publish_source_bound_first_draft(runtime.repo, runtime.article_id, object_store=runtime.objects, **arguments)
    assert published.created and not joined.created and published.published_revision_id == joined.published_revision_id
    current = runtime.read_current()
    assert current["canonical_revision_id"] == published.published_revision_id
    assert current["source_revision_id"] == source_id and current["content_origin"] == "canonical"
    assert "follow the applicable removal option" in current["body"]
    assert current["images"] == [{**image, "source_order": image["source_order"]+1} for image in source["images"]]
    assert not attempt_rows(runtime, published.job_id)
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 1}


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


@pytest.mark.parametrize(("instruction", "bad_wording", "introduction", "expected", "method"), [
    (
        "Install the guide plate. For additional information, refer to Section 410-07C .",
        "Put the guide plate in place. See Section 510-07C.",
        "This article covers the service sequence for the cover.",
        "Fit the guide plate. Details are in Section 410-07C.",
        FIRST_DRAFT_DIRECTIVE_RECOVERY_METHOD,
    ),
    (
        "Loosen the mounting plate bolts.",
        "Remove the mounting plate bolts.",
        "It is safe to service the cover while the engine is running.",
        "The mounting plate bolts must be loosened.",
        FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    ),
    (
        "Loosen the mounting plate bolts.",
        "The mounting plate bolts must be loosened.",
        "It is safe to service the cover while the engine is running.",
        "The mounting plate bolts must be loosened.",
        FIRST_DRAFT_COOLING_RECOVERY_METHOD,
    ),
    (
        "Place the gauge on the open part of the service tray.",
        "Position the gauge on the exposed section of the service tray.",
        "The article includes an 18 N·m torque specification.",
        "Position the gauge on the open section of the service tray.",
        FIRST_DRAFT_PLACEMENT_RECOVERY_METHOD,
    ),
    (
        "Install the protective cap over the port.",
        "The protective cap should be installed over the port.",
        "This article describes service information.",
        "The protective cap must be installed over the port.",
        FIRST_DRAFT_REQUIRED_ACTION_RECOVERY_METHOD,
    ),
    (
        "Remove the shield and the reservoir screen and return tube.",
        "Separate the shield from the reservoir screen and return tube.",
        "The article includes an 18 N·m torque specification.",
        "The shield and the reservoir screen and return tube must be removed.",
        FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD,
    ),
    (
        "Close the fixture valve.",
        "Open the fixture valve.",
        "This article covers the service sequence for the cover.",
        "The fixture valve must be closed.",
        FIRST_DRAFT_COOLING_SEQUENCE_RECOVERY_METHOD,
    ),
])
def test_worker_replays_recovery_with_its_original_response_and_media(
    runtime, instruction, bad_wording, introduction, expected, method,
):
    job_id = queue_article(runtime, figure=True, instruction=instruction)

    class ChangedReference:
        _model = "fixture-auto"

        def complete_json(self, prompt):
            slots = json.loads(prompt)["slots"]
            assert [(s["text"], s["required_action"]) for s in slots] == [
                (instruction, "rewrite"), (TORQUE, "retain"),
            ]
            self.raw = {
                "introduction": introduction,
                "replacements": [
                    {
                        "block_id": s["block_id"], "path": s["path"],
                        "action": s["required_action"], "text": s["text"],
                        "reason": "Keep the technical value." if s["required_action"] == "retain" else "",
                    }
                    for s in slots
                ],
            }
            self.raw["replacements"][0]["text"] = bad_wording
            return self.raw

    model = ChangedReference()
    assert run_job(runtime, job_id, model, registry=runtime.registry)
    current = runtime.read_current()
    assert current["content_origin"] == "canonical"
    assert expected in current["body"]
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
    assert revision["model_metadata"]["transformation_method"] == method
    evidence = revision["model_metadata"]["first_draft_recovery"]
    assert evidence["raw_response_hash"] == digest_json(model.raw)
    assert effective["replacements"][0]["text"] == expected
    if method in (FIRST_DRAFT_COOLING_RECOVERY_METHOD, FIRST_DRAFT_COMPOUND_REMOVAL_RECOVERY_METHOD):
        assert evidence["introduction_replaced"] is True
        assert effective["introduction"] != introduction
