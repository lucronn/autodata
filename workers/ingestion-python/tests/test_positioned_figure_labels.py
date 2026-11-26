import json
from uuid import UUID

import pytest

from autodata_ingestion.article_document import build_ordered_document
from autodata_ingestion.article_lifecycle_types import ArticleKey, SourceArticleContext
from autodata_ingestion.source_adapters import SourceResource, adapt_bound_article
from autodata_ingestion.procedure_rewrite_full import prose_slots


FRAME = """<div overlayedimage="true" style="position:relative;width:500px;height:250px">
<img overlayedimage="true" src="/fixture.png" style="position:absolute;left:0px;top:0px;width:500px;height:250px">
<p style="position:absolute;left:5px;top:10px;font-size:12pt;font-weight:normal;color:black">A</p>
<p style="position:absolute;left:250px;top:20px;font-size:12px;font-weight:normal;color:black">Cable marker<br>Second line</p>
</div>"""


def project(markup, *, enabled=True, provider="banktwo"):
    key = ArticleKey(provider, UUID(int=1), UUID(int=2), "vehicle", "article")
    context = SourceArticleContext(key, {}, {"title": "Fixture"}, UUID(int=3), UUID(int=4), ("source:fixture",))
    payload = json.dumps({"_embedded": {"data": {"article": {"content": markup}}}}).encode()
    source = SourceResource.from_bytes("https://example.test/article", "fixture", payload, "application/hal+json", "fixture")
    return adapt_bound_article(source, context, keep_positioned_figure_labels=enabled)


def test_labels_follow_their_figure_and_stay_out_of_prose_slots():
    markup = "<p>Procedure before the illustration.</p>" + FRAME + "<p>Procedure after the illustration.</p>"
    article = project(markup)
    assert article["positioned_figure_labels"]
    before, figure, after = article["blocks"]
    assert [before["text"], after["text"]] == ["Procedure before the illustration.", "Procedure after the illustration."]
    assert figure["figure_layout"] == {
        "width": 500, "height": 250, "labels": [
            {"left": 5, "top": 10, "font_size": 16, "lines": ["A"]},
            {"left": 250, "top": 20, "font_size": 12, "lines": ["Cable marker", "Second line"]},
        ],
    }
    document = build_ordered_document({**article, "article_id": "fixture", "evidence_ids": ["source:fixture"]})
    assert document["blocks"][1]["figure_layout"] == figure["figure_layout"]
    assert [slot["text"] for slot in prose_slots(document)] == [before["text"], after["text"]]
    assert len(project(markup, enabled=False)["blocks"]) == 6


@pytest.mark.parametrize("markup", [
    FRAME.replace("left:5px", "left:501px"),
    FRAME.replace("height:250px\">", "height:249px\">", 1),
    FRAME.replace("color:black", "color:black;display:none"),
    FRAME.replace("overlayedimage=\"true\"", "class=\"normal\"", 1),
    FRAME.replace("src=\"/fixture.png\"", "alt=\"No localized reference\""),
    FRAME.replace(">A</p>", "><strong>A</strong></p>"),
])
def test_unknown_or_unplaced_markup_leaves_its_readable_words(markup):
    article = project(markup)
    assert "positioned_figure_labels" not in article
    assert not any("figure_layout" in block for block in article["blocks"])
    assert "A" in [block.get("text") for block in article["blocks"]]
