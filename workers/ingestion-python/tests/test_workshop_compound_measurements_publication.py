"""Exercise retained compound measurements at the durable first-publication gate."""

import json
from uuid import uuid4

import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.source_job_persistence import refresh_article_job
from lifecycle_support import fresh_database, runtime


_OPENING = "Remove the cover."
_WARNING = "Do not start the pump dry."


class _Model:
    _model = "fixture-compound-measurements"

    def __init__(self, *, historical, rate, wrong_rate):
        self.historical = historical
        self.rate = rate
        self.wrong_rate = wrong_rate
        self.versions = []

    def complete_json(self, prompt):
        payload = json.loads(prompt)
        self.versions.append(payload["prompt_version"])
        replacements = []
        for slot in payload["slots"]:
            source = slot["text"]
            verb = slot["required_action"]
            if source == _OPENING:
                assert verb == "rewrite"
                output = "Take the cover off."
            elif source == self.rate and self.historical:
                assert verb == "rewrite"
                output = self.wrong_rate
            else:
                assert verb == "retain"
                output = source
            replacements.append({
                "block_id": slot["block_id"], "path": slot["path"], "action": verb, "text": output,
                "reason": "Preserve the authored specification or warning." if verb == "retain" else "",
            })
        return {"introduction": "This procedure covers access to the pump.", "replacements": replacements}


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("historical", [False, True], ids=["v57", "v55-first-publication"])
@pytest.mark.parametrize("rate,wrong_rate", [
    pytest.param("Set the return line flow rate to a maximum of 14 L/min.",
                 "Set the return line flow rate to a maximum of 14 L/s.", id="abbreviated"),
    pytest.param("The pump moves 14 US gal of water every minute.",
                 "The pump moves 14 US gal of water every second.", id="written"),
])
def test_compound_measurement_first_publication(runtime, monkeypatch, provider, historical, rate, wrong_rate):
    runtime.article_id = runtime.articles[provider]
    values = (_OPENING, rate, _WARNING)
    if provider == "bankone":
        source = json.dumps({"blocks": [{"type": "paragraph", "text": value} for value in values]}).encode()
        media_type = "application/json"
    else:
        source = "".join(f"<p>{value}</p>" for value in values).encode()
        media_type = "text/html"
    runtime.servers[provider].body(source, media_type)
    if historical:
        # Use the saved v55 rules through candidate construction. The real
        # publication transaction still applies the current first-publish gate.
        render = auto.render_auto
        validate = auto.validate_auto
        version = "full-prose-auto-prompt-v55"

        def historical_render(source, response, *, prompt_version=None):
            return render(source, response, prompt_version=prompt_version or version)

        def historical_validate(source, candidate, *, response=None, prompt_version=None):
            return validate(source, candidate, response=response, prompt_version=prompt_version or version)

        monkeypatch.setattr(auto, "build_auto_prompt", auto._build_auto_prompt_v55)
        monkeypatch.setattr(auto, "render_auto", historical_render)
        monkeypatch.setattr(auto, "validate_auto", historical_validate)
    model = _Model(historical=historical, rate=rate, wrong_rate=wrong_rate)
    phases = []
    job = refresh_article_job(
        runtime.repo, runtime.article_id, actor="fixture", reason="verify compound measurement publication",
        rewrite_profile_version=auto.PROFILE,
    )
    assert run_article_worker_once(
        runtime.repo, worker_id=uuid4(), registry=runtime.registry, object_store=runtime.objects,
        model_client=model, job_id=job.job_id, hooks=phases.append,
    )
    read = runtime.read_current()
    assert read["source_revision_id"] is not None
    with runtime.repo.connect() as conn:
        source_row = conn.execute(
            "SELECT source_body FROM canonical_article_source_revisions WHERE source_revision_id=%s",
            (read["source_revision_id"],),
        ).fetchone()
        publication = conn.execute(
            "SELECT canonical_body, validation_report FROM canonical_article_revisions "
            "WHERE canonical_article_id=%s AND status='published'",
            (runtime.article_id,),
        ).fetchone()
    assert source_row["source_body"].splitlines() == list(values)
    assert "after_model_result_commit" in phases and "before_publication" in phases
    if historical:
        assert model.versions == ["full-prose-auto-prompt-v55"]
        assert read["content_origin"] == "source" and read["canonical_revision_id"] is None
        assert read["processing_error_code"] == "REWRITE_SPEC_SCOPE_MUTATION"
        assert publication is None
    else:
        assert model.versions == ["full-prose-auto-prompt-v57"]
        assert read["content_origin"] == "canonical"
        assert publication["canonical_body"].splitlines() == [
            "This procedure covers access to the pump.", "Take the cover off.", rate, _WARNING,
        ]
        assert publication["validation_report"]["validator_version"] == "full-prose-auto-validator-v55"
