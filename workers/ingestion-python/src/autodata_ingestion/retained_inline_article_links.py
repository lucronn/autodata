"""Bind embedded Bankone references to immutable reader text."""

from collections import Counter
from hashlib import sha256

from .article_lifecycle_types import digest_json
from .bankone_first_draft_structure import _Markup, _compact
from .procedure_rewrite_full import _get, prose_slots
from .source_connector_client import _valid_article_link_bindings
from .source_job_persistence import bankone_archive_body_binding, source_bound_rewrite_source_allowed
from .source_media_replay import _MAX_OBJECT_BYTES


_MAX_LINKS = 128


def _sha(text):
    return sha256(text.encode()).hexdigest()


def _slots(document):
    by_location = {}
    for slot in prose_slots(document, include_cell_blocks=True):
        path, block, text = slot["path"], slot["block_id"], slot["text"]
        owner = path.removesuffix("/text")
        prefix, _, index = owner.rpartition("/items/")
        if prefix and index.isdecimal():
            location, tag = (block, int(index)), "li"
        elif path.endswith("/text") and _get(document, owner).get("type") == "paragraph":
            location, tag = (block, -1), "p"
        else:
            continue
        by_location[location] = None if location in by_location else (tag, text)
    return {location: value for location, value in by_location.items() if value is not None}


def _exact_label(text, label):
    if not label or text.count(label) != 1:
        return False
    before, _, after = text.partition(label)
    return not (before[-1:].isalnum() or after[:1].isalnum())


def authored_inline_article_links(html, connector_bindings, source_document, canonical_document):
    if not _valid_article_link_bindings(connector_bindings):
        return []
    targets = {link["source_id_sha256"]: link["target_ref_sha256"] for link in connector_bindings}
    source_slots, canonical_slots = _slots(source_document), _slots(canonical_document)
    spans = Counter((tag, _compact(text)) for tag, text in source_slots.values())
    markup = _Markup(html)
    links = []
    for (block, index), (tag, text) in source_slots.items():
        rendered = canonical_slots.get((block, index))
        if not rendered or rendered[0] != tag or spans[tag, _compact(text)] != 1:
            continue
        parent = markup.unique_span(tag, text)
        if parent is None:
            continue
        for node in parent.children:
            if node.hidden or node.tag != "mtr-doc-link" or not node.reference:
                continue
            label = markup.label(node)
            authored = _sha(node.reference)
            if (authored not in targets or len(label.encode()) > 384
                or not _exact_label(text, label) or not _exact_label(rendered[1], label)):
                continue
            links.append({
                "block_id": block, "item_index": index, "label": label, "label_sha256": _sha(label),
                "authored_id_sha256": authored, "target_ref_sha256": targets[authored],
            })
    if len(links) > _MAX_LINKS:
        raise ValueError("INLINE_ARTICLE_LINK_LIMIT")
    return sorted(links, key=lambda link: (link["block_id"], link["item_index"], link["label_sha256"]))


def retain_inline_article_links(repo, article_id, source_id, canonical_id, observation_id, *,
                                object_store, expected_digest=None):
    """Inspect the archived body and optionally publish its exact inline bindings."""
    apply = expected_digest is not None
    with repo.connect() as conn, conn.cursor() as cur:
        if not apply:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout='5s'")
        article = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s"
                              + (" FOR UPDATE" if apply else ""), (article_id,)).fetchone()
        if (
            not article or article["provider_slug"] != "bankone"
            or article["current_source_revision_id"] != source_id
            or article["current_canonical_revision_id"] != canonical_id
            or not source_bound_rewrite_source_allowed(cur, article, source_id)
        ):
            raise ValueError("INLINE_ARTICLE_LINK_SOURCE_CHANGED")
        stored = cur.execute("""
            SELECT source.source_document, source.resource_manifest, published.canonical_document,
                   published.rewrite_result_hash
            FROM canonical_article_source_revisions source
            JOIN canonical_article_revisions published USING (canonical_article_id, source_revision_id)
            JOIN catalog_article_current current USING (canonical_article_id)
            WHERE source.canonical_article_id=%s AND source.source_revision_id=%s
              AND published.canonical_article_revision_id=%s AND published.status='published'
              AND current.source_revision_id=source.source_revision_id
              AND current.canonical_revision_id=published.canonical_article_revision_id
              AND current.takedown_status='active'
        """, (article_id, source_id, canonical_id)).fetchone()
        if not stored or digest_json(stored["canonical_document"]) != stored["rewrite_result_hash"]:
            raise ValueError("INLINE_ARTICLE_LINK_PUBLICATION_CHANGED")
        body = bankone_archive_body_binding(cur, source_id, observation_id, lock=apply)
        raw = object_store.get_object(body.object_key, max_bytes=_MAX_OBJECT_BYTES)
        if sha256(raw).hexdigest() != body.digest:
            raise ValueError("INLINE_ARTICLE_LINK_BODY_CHANGED")
        [resource] = [value for value in stored["resource_manifest"] if value["role"] == "body"]
        bindings = authored_inline_article_links(
            raw.decode("utf-8-sig"), resource.get("article_link_bindings"),
            stored["source_document"], stored["canonical_document"],
        )
        proof = {
            "article": str(article_id), "source_revision": str(source_id), "canonical_revision": str(canonical_id),
            "observation": str(observation_id), "body_sha256": body.digest,
            "source_document_sha256": digest_json(stored["source_document"]),
            "canonical_document_sha256": stored["rewrite_result_hash"], "bindings_sha256": digest_json(bindings),
        }
        digest = digest_json(proof)
        inserted = 0
        if apply:
            if digest != expected_digest or not bindings:
                raise ValueError("INLINE_ARTICLE_LINK_PROOF_CHANGED")
            existing = cur.execute("""
                SELECT block_id,item_index,label,label_sha256,authored_id_sha256,target_ref_sha256,body_sha256
                FROM canonical_article_inline_link_bindings WHERE canonical_article_revision_id=%s
                ORDER BY block_id COLLATE "C",item_index,label_sha256 COLLATE "C"
            """, (canonical_id,)).fetchall()
            if existing and existing != [{**link, "body_sha256": body.digest} for link in bindings]:
                raise ValueError("INLINE_ARTICLE_LINK_BINDINGS_CONFLICT")
            if not existing:
                for binding in bindings:
                    cur.execute("""
                        INSERT INTO canonical_article_inline_link_bindings (canonical_article_id,source_revision_id,
                          canonical_article_revision_id,body_sha256,block_id,item_index,label,label_sha256,
                          authored_id_sha256,target_ref_sha256)
                        VALUES (%(article)s,%(source)s,%(canonical)s,%(body)s,%(block_id)s,%(item_index)s,
                                %(label)s,%(label_sha256)s,%(authored_id_sha256)s,%(target_ref_sha256)s)
                    """, {**binding, "article": article_id, "source": source_id, "canonical": canonical_id, "body": body.digest})
                inserted = len(bindings)
    return {
        **proof, "proof_sha256": digest, "verified_links": len(bindings), "inserted_links": inserted,
        "distinct_targets": len({link["target_ref_sha256"] for link in bindings}),
    }
