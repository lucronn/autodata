"""Guard the exact archived tool-label edit and retained-body binding."""

from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest

from autodata_ingestion.article_lifecycle_types import SOURCE_BOUND_CORRECTION_PROFILE
from autodata_ingestion.procedure_rewrite_auto import render_auto
from autodata_ingestion.retained_note_label_repair import _restore_tool_label_reply, _tool_label_proof
from autodata_ingestion.source_job_persistence import load_bankone_structure
from test_procedure_rewrite_full import document, response


LABEL = "FW-730 Reservoir Alignment Gauge"
PATH = "/blocks/1/text"
HTML = b"<dl><dt>Tools Required</dt><dd><p><i>FW-730</i> Reservoir Alignment Gauge</p></dd></dl>"
OPTIONS = {"prompt_version": "full-prose-auto-prompt-v61", "profile_version": SOURCE_BOUND_CORRECTION_PROFILE}


@pytest.fixture
def archive():
    source = document("Remove the shield.", LABEL, "Drain the fixture reservoir.")
    raw = response("The shield must be removed.", "Reservoir gauge FW-730 for alignment",
                   "Empty the fixture reservoir.", introduction="This article covers fixture service.")
    prior = render_auto(source, raw, **OPTIONS)
    observation = uuid4()
    body = SimpleNamespace(digest=sha256(HTML).hexdigest(), object_key="fixture/body")
    captured = {"source_observation_id": observation, "resource_manifest": [{"sha256": body.digest}]}
    archive = load_bankone_structure(lambda *_args, **_kwargs: HTML, body, source, observation, structure_version=1)
    return source, raw, prior, captured, archive


def test_restore_only_the_authored_tool_label(archive):
    source, raw, prior, captured, evidence = archive
    original = deepcopy(raw)
    proof = _tool_label_proof(captured, source, evidence)
    assert proof["slots"] == {PATH: {"kind": "tool_label", "block_id": "p1"}}
    published, report, rebound, paths = _restore_tool_label_reply(
        source, source, prior, raw, **OPTIONS, bankone_structure=proof, path=PATH,
    )
    assert report.passed and paths == [PATH]
    assert raw == original and rebound["introduction"] == original["introduction"]
    assert rebound["replacements"][::2] == original["replacements"][::2]
    assert rebound["replacements"][1]["action"] == "retain"
    assert published["blocks"][2]["text"] == LABEL
    assert published["blocks"][:2] + published["blocks"][3:] == prior["blocks"][:2] + prior["blocks"][3:]


@pytest.mark.parametrize("pin", ["observation_id", "body_sha256"])
def test_reject_archive_bound_to_a_different_capture(archive, pin):
    source, _, _, captured, evidence = archive
    with pytest.raises(ValueError, match="RETAINED_TOOL_LABEL_REPAIR_INVALID"):
        _tool_label_proof(captured, source, {**evidence, pin: "wrong"})


def test_reject_changed_archived_reply_or_other_published_content(archive):
    source, raw, prior, captured, evidence = archive
    proof = _tool_label_proof(captured, source, evidence)
    changed_reply = deepcopy(raw)
    changed_reply["replacements"][1]["text"] = "FW-730 Reservoir Gauge"
    changed_prior = deepcopy(prior)
    changed_prior["blocks"][-1]["text"] = "Drain the tank."
    for document, reply in ((prior, changed_reply), (changed_prior, raw)):
        with pytest.raises(ValueError, match="RETAINED_TOOL_LABEL_REPAIR_INVALID"):
            _restore_tool_label_reply(
                source, source, document, reply, **OPTIONS, bankone_structure=proof, path=PATH,
            )


def test_reject_unbound_or_plain_tool_markup(archive):
    source, _, _, captured, evidence = archive
    plain = HTML.replace(b"<i>FW-730</i>", b"FW-730")
    with pytest.raises(ValueError, match="FIRST_DRAFT_ARCHIVE_STRUCTURE_MISMATCH"):
        load_bankone_structure(lambda *_args, **_kwargs: plain,
                               SimpleNamespace(object_key="fixture/body", digest=evidence["body_sha256"]),
                               source, captured["source_observation_id"], structure_version=1)
    plain_digest = sha256(plain).hexdigest()
    plain_archive = load_bankone_structure(
        lambda *_args, **_kwargs: plain, SimpleNamespace(object_key="fixture/body", digest=plain_digest),
        source, captured["source_observation_id"], structure_version=1,
    )
    with pytest.raises(ValueError, match="RETAINED_TOOL_LABEL_REPAIR_INVALID"):
        _tool_label_proof({**captured, "resource_manifest": [{"sha256": plain_digest}]}, source, plain_archive)
