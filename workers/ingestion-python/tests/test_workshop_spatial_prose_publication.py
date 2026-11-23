"""Exercise scoped orientation in the worker's durable first-publication path."""

from hashlib import sha256
from io import BytesIO
import json
from uuid import uuid4

from PIL import Image
import pytest

from autodata_ingestion import procedure_rewrite_auto as auto
from autodata_ingestion.article_document import project_ordered_document
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_types import digest_json
from autodata_ingestion.source_job_persistence import refresh_article_job
from lifecycle_support import fresh_database, runtime


_SOURCE = "A painted spot on the inside guide face identifies the cover."
_REWRITE = "The cover is marked by a painted spot on its internal guide face."
_WARNING = "Do not pry on the cover."
_INTRODUCTION = "This article describes the cover identification mark."
_CAPTION = "Cover identification mark"
_ALT = "Painted identification spot"
_FIGURE_URL = "/fixture/cover.png"
_V55 = "full-prose-auto-prompt-v55"
_V59 = "full-prose-auto-prompt-v59"


def _install_article(connector, *, provider, prose):
    if provider == "bankone":
        article = {"blocks": [
            {"type": "paragraph", "text": prose},
            {"type": "image", "asset_resource_ref": "figure", "alt": _ALT, "caption": _CAPTION},
            {"type": "paragraph", "text": _WARNING},
        ]}
        connector.body(json.dumps(article).encode(), "application/json", assets=["figure"])
    else:
        html = (f'<p>{prose}</p><figure><img data-src="{_FIGURE_URL}" alt="{_ALT}">'
                f'<figcaption>{_CAPTION}</figcaption></figure><p>{_WARNING}</p>')
        hal = {"_embedded": {"data": {"article": {"content": html}}}}
        connector.body(json.dumps(hal).encode(), "application/hal+json", assets=["figure"],
                       asset_bindings=[{"source_url": _FIGURE_URL, "resource_ref": "figure"}])
    buffer = BytesIO()
    Image.new("RGB", (24, 16), "green").save(buffer, format="PNG")
    figure = buffer.getvalue()
    connector.body(figure, "image/png", ref="figure", kind="asset")
    return figure


class _Model:
    _model = "fixture-spatial-prose"

    def __init__(self, *, source, rewrite):
        self.source = source
        self.rewrite = rewrite
        self.versions = []

    def complete_json(self, prompt):
        payload = json.loads(prompt)
        self.versions.append(payload["prompt_version"])
        assert [(slot["text"], slot["required_action"]) for slot in payload["slots"]] == [
            (self.source, "rewrite"), (_WARNING, "retain"),
        ]
        return {"introduction": _INTRODUCTION, "replacements": [
            {"block_id": slot["block_id"], "path": slot["path"], "action": slot["required_action"],
             "text": _WARNING if slot["text"] == _WARNING else self.rewrite,
             "reason": "Preserve exact safety wording." if slot["text"] == _WARNING else ""}
            for slot in payload["slots"]
        ]}


@pytest.mark.parametrize("provider", ["bankone", "banktwo"])
@pytest.mark.parametrize("historical_swap", [False, True], ids=["current-rewrite", "v55-bound-swap"])
def test_spatial_prose_first_publication(runtime, monkeypatch, provider, historical_swap):
    runtime.article_id = runtime.articles[provider]
    source = _SOURCE.replace("inside", "internal") if historical_swap else _SOURCE
    draft = _REWRITE.replace("internal", "external") if historical_swap else _REWRITE
    png = _install_article(runtime.servers[provider], provider=provider, prose=source)
    if historical_swap:
        # Create and store the candidate under the saved rules. The worker must
        # still check the candidate against today's rules in the transaction.
        render = auto.render_auto
        validate = auto.validate_auto

        def historical_render(source, response, *, prompt_version=None):
            return render(source, response, prompt_version=prompt_version or _V55)

        def historical_validate(source, candidate, *, response=None, prompt_version=None):
            return validate(source, candidate, response=response, prompt_version=prompt_version or _V55)

        monkeypatch.setattr(auto, "build_auto_prompt", auto._build_auto_prompt_v55)
        monkeypatch.setattr(auto, "render_auto", historical_render)
        monkeypatch.setattr(auto, "validate_auto", historical_validate)

    model = _Model(source=source, rewrite=draft)
    phases = []
    job = refresh_article_job(
        runtime.repo, runtime.article_id, actor="fixture", reason="verify physical orientation",
        rewrite_profile_version=auto.PROFILE,
    )
    assert run_article_worker_once(
        runtime.repo, worker_id=uuid4(), registry=runtime.registry, object_store=runtime.objects,
        model_client=model, job_id=job.job_id, hooks=phases.append,
    )
    view = runtime.read_current()
    assert view["source_revision_id"] is not None
    with runtime.repo.connect() as conn:
        source_row = conn.execute(
            "SELECT source_document, source_body, source_images FROM canonical_article_source_revisions "
            "WHERE source_revision_id=%s", (view["source_revision_id"],),
        ).fetchone()
        attempt = conn.execute(
            "SELECT response, response_hash FROM canonical_article_rewrite_attempts WHERE source_fetch_job_id=%s",
            (job.job_id,),
        ).fetchone()
        publication = conn.execute(
            "SELECT canonical_article_revision_id, source_revision_id, canonical_document, canonical_body, "
            "canonical_steps, canonical_images, validation_report FROM canonical_article_revisions "
            "WHERE canonical_article_id=%s AND status='published'", (runtime.article_id,),
        ).fetchone()

    source_blocks = source_row["source_document"]["blocks"]
    assert [block["type"] for block in source_blocks] == ["paragraph", "image", "paragraph"]
    expected_source_body = [source, _WARNING] if provider == "bankone" else [source, _CAPTION, _WARNING]
    assert source_row["source_body"].splitlines() == expected_source_body
    image = source_blocks[1]
    assert source_row["source_images"] == [image]
    assert (image["caption"], image["alt"], image["status"]) == (_CAPTION, _ALT, "available")
    assert image["content_sha256"] == sha256(png).hexdigest()
    assert image["evidence_ids"]
    assert runtime.objects.get_object(image["storage_key"], max_bytes=1 << 20) == png
    assert attempt["response_hash"] == digest_json(attempt["response"])
    assert attempt["response"]["replacements"][0]["text"] == draft
    assert "after_model_result_commit" in phases and "before_publication" in phases
    if historical_swap:
        assert model.versions == [_V55]
        assert view["content_origin"] == "source" and view["canonical_revision_id"] is None
        assert view["processing_error_code"] == "REWRITE_DIRECTION_MUTATION"
        assert view["document"] == source_row["source_document"]
        assert publication is None and "after_publication_commit" not in phases
        return

    assert model.versions == [_V59]
    assert "after_publication_commit" in phases
    assert view["content_origin"] == "canonical"
    assert view["canonical_revision_id"] == publication["canonical_article_revision_id"]
    assert view["source_revision_id"] == publication["source_revision_id"]
    assert view["document"] == publication["canonical_document"]
    assert view["body"].splitlines() == [_INTRODUCTION, draft, _CAPTION, _WARNING]
    projected = project_ordered_document(view["document"])
    assert (projected["body"], projected["steps"], projected["images"]) == (
        publication["canonical_body"], publication["canonical_steps"], publication["canonical_images"],
    )
    blocks = view["document"]["blocks"]
    assert [block["type"] for block in blocks] == ["paragraph", "paragraph", "image", "paragraph"]
    assert blocks[2] == {**image, "source_order": image["source_order"] + 1}
    assert blocks[3]["text"] == _WARNING and blocks[3]["evidence_ids"] == source_blocks[2]["evidence_ids"]
    assert publication["validation_report"]["validator_version"] == "full-prose-auto-validator-v57"
    assert publication["validation_report"]["changed_prose_slots"] == ["/blocks/0/text"]
    assert publication["validation_report"]["retained_paths"] == ["/blocks/2/text"]
