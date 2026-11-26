"""Recover a terminal sentence archive through the exact publication worker."""

from hashlib import sha256
import json

import pytest

from autodata_ingestion import article_lifecycle_store as store
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.procedure_rewrite_correction import _mask_literals
from autodata_ingestion.procedure_rewrite_sentence_correction import (
    SENTENCE_INSTRUCTION_RECOVERY_METHOD, SENTENCE_RECOVERY_METHOD, SENTENCE_TOOL_RECOVERY_METHOD,
)
from autodata_ingestion.published_media_publication import _publication_evidence
from lifecycle_support import fresh_database, runtime
from test_source_bound_correction_recovery import job_and_candidates, recover
from test_source_bound_correction_worker import attempt_rows, retained_media
from test_source_bound_rewrite_worker import run_job
from test_source_bound_sentence_worker import SENTENCE_METHOD, schedule


WIRING = (
    "The two receivers are not wired to the central controller, thus the monitor does not communicate directly "
    "on a service data network."
)
RECOVERED_WIRING = (
    "The two receivers lack wiring to the central controller, so the monitor has no direct communication "
    "on a service data network."
)
LINKED_REMOVAL = "Engine Coolant Supply Air Bleed Pipe(3)»Remove— Engine Coolant Supply Air Bleed Pipe Replacement"
RECOVERED_REMOVAL = (
    "Remove the component identified by (3) using the steps in Engine Coolant Supply Air Bleed Pipe Replacement."
)
INSTALL_SOCKET = "Install the drive socket (6) to the gear nut."
RECOVERED_SOCKET = "The drive socket (6) must be fitted to the gear nut."


class EchoedSentence:
    _model = "fixture-sentence-archive"

    def __init__(self, text):
        self.prompts = []
        self.responses = []
        self.statement = _mask_literals(text)[0] or text

    def complete_json(self, prompt):
        request = json.loads(prompt)
        assert request["method"] == SENTENCE_METHOD
        self.prompts.append(prompt)
        if "passages" in request:
            entries, field = request["passages"], "source"
        else:
            entries, field = request["statements"], "statement"
            assert [entry[field] for entry in entries] == [self.statement]
        response = {"rewrites": [{"slot": entry["slot"], "candidates": [entry[field]] * 3} for entry in entries]}
        self.responses.append(response)
        return response


@pytest.fixture(params=[
    (WIRING, RECOVERED_WIRING, SENTENCE_RECOVERY_METHOD),
    (LINKED_REMOVAL, RECOVERED_REMOVAL, SENTENCE_INSTRUCTION_RECOVERY_METHOD),
    (INSTALL_SOCKET, RECOVERED_SOCKET, SENTENCE_TOOL_RECOVERY_METHOD),
], ids=["wiring", "numbered-removal", "socket-installation"])
def terminal_sentence(runtime, request, monkeypatch):
    text, wording, method = request.param
    connector = runtime.servers["bankone"]
    write = connector.body

    def with_instruction(payload, *args, **kwargs):
        if "asset_bindings" in kwargs:
            payload += f"<p>{text}</p>".encode()
        return write(payload, *args, **kwargs)

    with monkeypatch.context() as fixture:
        fixture.setattr(connector, "body", with_instruction)
        prior_id, source, _ = request.getfixturevalue("retained_media")
    assert text in source["body"] and source["images"][0]["status"] == "available"
    job = schedule(runtime, prior_id, source["source_revision_id"])
    model = EchoedSentence(text)
    assert run_job(runtime, job.job_id, model, registry=runtime.registry)
    assert runtime.read_current()["processing_error_code"] == "REWRITE_UNCHANGED"
    terminal, candidates = job_and_candidates(runtime, job.job_id)
    assert (terminal["status"], terminal["phase"], terminal["retryable"]) == ("dead_letter", "rewriting", False)
    assert candidates == []
    archived = attempt_rows(runtime, job.job_id)
    assert [row["attempt_number"] for row in archived] == [1, 2]
    assert [row["prompt_hash"] for row in archived] == [sha256(prompt.encode()).hexdigest() for prompt in model.prompts]
    assert [row["response"] for row in archived] == model.responses
    assert all(row["status"] == "succeeded" and row["response_hash"] == digest_json(row["response"]) for row in archived)
    assert all(row["canonical_article_revision_id"] is None for row in archived)
    runtime.reset_counters()
    return job.job_id, prior_id, source, text, wording, method


def test_terminal_sentence_recovers_with_only_the_archived_calls(runtime, terminal_sentence):
    job_id, prior_id, source, text, wording, method = terminal_sentence
    source_id = source["source_revision_id"]
    archived = attempt_rows(runtime, job_id)
    prior_attempts = attempt_rows(runtime, prior_id)
    terminal, _ = job_and_candidates(runtime, job_id)
    figure_key = source["images"][0]["storage_key"]
    figure_bytes = runtime.objects.get_object(figure_key, max_bytes=1024 * 1024)

    revision_id = recover(runtime, job_id, source_id)

    pending, (candidate,) = job_and_candidates(runtime, job_id)
    assert (pending["status"], pending["phase"]) == ("pending", "publishing")
    assert pending["lease_token"] == terminal["lease_token"]
    assert candidate["canonical_article_revision_id"] == revision_id and candidate["source_revision_id"] == source_id
    assert candidate["status"] == "validated" and candidate["validation_report"]["passed"]
    assert candidate["model_metadata"]["transformation_method"] == method
    audit = pending["checkpoint"]["correction_recovery"]
    assert audit == candidate["model_metadata"]["correction_recovery"]
    assert audit["terminal_error"] == "REWRITE_UNCHANGED"
    assert audit["attempts"] == [{
        "attempt_id": str(row["rewrite_attempt_id"]),
        "prompt_hash": row["prompt_hash"], "response_hash": row["response_hash"],
    } for row in archived]
    current = runtime.read_current()
    assert current["content_origin"] == "source" and current["availability"] == "available"
    assert current["document"] == source["document"] and current["images"] == source["images"]
    with pytest.raises(ValueError, match="SOURCE_BOUND_CORRECTION_RECOVERY_STALE"):
        recover(runtime, job_id, source_id)
    assert not run_job(runtime, None, None)
    assert run_job(runtime, job_id, None, registry=runtime.registry)
    assert not run_job(runtime, job_id, None)

    current = runtime.read_current()
    assert current["content_origin"] == "canonical" and current["canonical_revision_id"] == revision_id
    assert current["source_revision_id"] == source_id
    assert current["images"] == [
        {**image, "source_order": image["source_order"] + 1} for image in source["images"]
    ]
    assert runtime.objects.get_object(figure_key, max_bytes=1024 * 1024) == figure_bytes
    assert attempt_rows(runtime, prior_id) == prior_attempts
    assert attempt_rows(runtime, job_id) == [archived[0], {**archived[1], "canonical_article_revision_id": revision_id}]
    binding = store.load_source_revision(runtime.repo, source_id)
    with runtime.repo.connect() as conn, conn.cursor() as cur:
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s",
                              (runtime.article_id,)).fetchone()
        revision, _, _, attempt, effective, _, _ = _publication_evidence(
            cur, article, binding, fixture_mode=True, lock=False,
        )
        events = cur.execute("SELECT canonical_article_revision_id FROM publication_events").fetchall()
    assert effective["replacements"][-1]["text"] == wording
    assert wording in current["body"] and text not in current["body"]
    evidence = revision["model_metadata"]["correction_evidence"]
    assert evidence["original_error_code"] == "REWRITE_UNCHANGED"
    assert evidence["base_draft_hash"] != evidence["draft_hash"] == digest_json(effective)
    assert revision["canonical_article_revision_id"] == revision_id
    assert attempt["rewrite_attempt_id"] == archived[-1]["rewrite_attempt_id"]
    assert events == [{"canonical_article_revision_id": revision_id}]
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}


def test_terminal_sentence_recovery_rejects_a_changed_archive(runtime, terminal_sentence):
    job_id, _, source, *_ = terminal_sentence
    with runtime.repo.connect() as conn:
        conn.execute("""UPDATE canonical_article_rewrite_attempts SET response='{"rewrites":[]}'::jsonb
            WHERE source_fetch_job_id=%s AND attempt_number=2""", (job_id,))
    before = job_and_candidates(runtime, job_id)
    archived = attempt_rows(runtime, job_id)
    with pytest.raises(ValueError, match="REWRITE_CORRECTION_EVIDENCE_INVALID"):
        recover(runtime, job_id, source["source_revision_id"])
    assert job_and_candidates(runtime, job_id) == before
    assert attempt_rows(runtime, job_id) == archived
    assert runtime.read_current()["content_origin"] == "source"
    assert runtime.counters() == {"source": 0, "asset": 0, "model": 0, "schedule": 0}
