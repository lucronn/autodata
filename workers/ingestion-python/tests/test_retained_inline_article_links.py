from hashlib import sha256

from autodata_ingestion.retained_inline_article_links import authored_inline_article_links


def digest(text):
    return sha256(text.encode()).hexdigest()


def test_references_match_source_paragraph_and_original_list_item_order():
    source = {"blocks": [
        {"block_id": "paragraph", "type": "paragraph", "text": "See Cover Removal."},
        {"block_id": "procedure", "type": "ordered_list", "items": [
            "Refer to Pump Service first.", "Then refit the cover.",
        ]},
    ]}
    draft = {"blocks": [
        {"block_id": "intro", "type": "paragraph", "text": "This procedure covers the pump."},
        {"block_id": "paragraph", "type": "paragraph", "text": "Follow Cover Removal."},
        {"block_id": "procedure", "type": "ordered_list", "items": [
            {"text": "Start with Pump Service."}, {"text": "Refit the cover next."},
        ]},
    ]}
    markup = ('<p>See <mtr-doc-link id="cover">Cover Removal</mtr-doc-link>.</p>'
              '<ol><li>Refer to <mtr-doc-link id="pump">Pump Service</mtr-doc-link> first.</li>'
              '<li>Then refit the cover.</li></ol>')
    connector = [{"source_id_sha256": digest(part), "target_ref_sha256": digest(part+"-document")}
                 for part in ("cover", "pump")]
    links = authored_inline_article_links(markup, connector, source, draft)
    assert [(link["block_id"], link["item_index"], link["label"], link["target_ref_sha256"])
            for link in links] == [
        ("paragraph", -1, "Cover Removal", digest("cover-document")),
        ("procedure", 0, "Pump Service", digest("pump-document")),
    ]


def test_hidden_unbound_ambiguous_or_reworded_link_titles_are_left_as_text():
    text = "Follow Cover Removal."
    source = {"blocks": [{"block_id": "p", "type": "paragraph", "text": text}]}
    connector = [{"source_id_sha256": digest("cover"), "target_ref_sha256": digest("cover-document")}]
    wrap = '<p>Follow <mtr-doc-link id="cover" {}>Cover Removal</mtr-doc-link>.</p>'
    assert authored_inline_article_links(wrap.format("hidden"), connector, source, source) == []
    assert authored_inline_article_links(wrap.format(""), [], source, source) == []
    assert authored_inline_article_links(wrap.format("") * 2, connector, source, source) == []
    for changed in ("Review removal of the cover.", "Cover Removal and Cover Removal."):
        draft = {"blocks": [{**source["blocks"][0], "text": changed}]}
        assert authored_inline_article_links(wrap.format(""), connector, source, draft) == []
