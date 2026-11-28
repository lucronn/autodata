"""Register supplier-authored Banktwo documents through the article job queue."""

from hashlib import sha256
from time import monotonic

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .article_lifecycle_store import _upsert_descriptor, persist_resource
from .article_lifecycle_types import ArticleKey, article_id
from .banktwo_authored_article_links import (
    banktwo_article_markup, banktwo_authored_guid_paths, banktwo_inline_article_links,
)
from .source_article_capture import upload_envelope
from .source_connector_client import SourceConnectorError
from .source_job_persistence import _ensure_locked, source_bound_rewrite_source_allowed
from .source_media_replay import _MAX_OBJECT_BYTES, _source_replay_row


def _bound_parent(cur, parent_article_id, source_revision_id, *, lock=False):
    sql = "SELECT * FROM canonical_articles WHERE canonical_article_id=%s"
    parent = cur.execute(sql + (" FOR UPDATE" if lock else ""), (parent_article_id,)).fetchone()
    if (not parent or parent["provider_slug"] != "banktwo"
            or not source_bound_rewrite_source_allowed(cur, parent, source_revision_id)):
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_PARENT_CHANGED")
    observation = _source_replay_row(cur, source_revision_id)
    if not observation or observation["canonical_article_id"] != parent_article_id:
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_PARENT_CHANGED")
    bodies = [item for item in observation["resource_provenance"] if item.get("role") == "body"]
    if len(bodies) != 1:
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_BODY_INVALID")
    body, = bodies
    snapshot = cur.execute("""
        SELECT content_sha256::text AS digest, object_key FROM source_snapshots
        WHERE source_snapshot_id=%s AND takedown_status='active'
    """, (observation["body_source_snapshot_id"],)).fetchone()
    if (not snapshot or body.get("provider") != "banktwo" or body.get("sha256") != snapshot["digest"]
            or body.get("object_key") != snapshot["object_key"] or not body.get("opaque_ref")):
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_BODY_INVALID")
    return parent, body, observation["source_document"]


def register_banktwo_authored_articles(
    repo, parent_article_id, source_revision_id, *, path_digests, connector, object_store, deadline_seconds=30,
):
    """Persist exact supplier descriptors and queue the ordinary scoped source jobs."""
    selected = frozenset(path_digests)
    if not selected or len(selected) > 128 or not 0 < deadline_seconds <= 30:
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_LOOKUP_INVALID")
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        parent, body, document = _bound_parent(cur, parent_article_id, source_revision_id)
        archived_paths = {row["authored_path_sha256"] for row in cur.execute("""
            SELECT authored_path_sha256 FROM banktwo_authored_article_referrals
            WHERE parent_article_id=%s AND parent_source_revision_id=%s
              AND authored_path_sha256=ANY(%s::text[])
        """, (parent_article_id, source_revision_id, list(selected)))}
    original = object_store.get_object(body["object_key"], max_bytes=_MAX_OBJECT_BYTES)
    if sha256(original).hexdigest() != body["sha256"]:
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_BODY_INVALID")
    markup = banktwo_article_markup(original, body["media_type"])
    markup_digest = sha256(markup.encode()).hexdigest()
    ordered = [sha256(path.encode()).hexdigest() for path in banktwo_authored_guid_paths(markup)]
    if not selected.issubset(ordered):
        raise ValueError("BANKTWO_AUTHORED_ARTICLE_LOOKUP_INVALID")

    deadline = monotonic() + deadline_seconds
    targets = []
    for authored in ordered:
        if authored not in selected:
            continue
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise SourceConnectorError("UPSTREAM_UNAVAILABLE", retryable=True)
        response = connector.resolve_authored_guid_article(
            parent["source_vehicle_ref"], body["opaque_ref"], markup_sha256=markup_digest,
            authored_path_sha256=authored, timeout=remaining,
        )
        descriptor, = response.body["articles"]
        key = ArticleKey(
            "banktwo", parent["vehicle_id"], parent["vehicle_configuration_id"],
            parent["source_vehicle_ref"], descriptor["opaque_ref"],
        )
        if article_id(key) == parent_article_id:
            raise ValueError("BANKTWO_AUTHORED_ARTICLE_LOOKUP_INVALID")
        resource = None if authored in archived_paths else upload_envelope(response, "authored_article", object_store)
        targets.append((authored, descriptor, key, resource))

    placements = banktwo_inline_article_links(markup, [
        {"source_id_sha256": authored, "target_ref_sha256": sha256(key.source_article_ref.encode()).hexdigest()}
        for authored, _, key, _ in targets
    ], document, document)
    registered = []
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        scope = cur.execute("""
            SELECT source_vehicle_ref FROM catalog_article_provider_scopes
            WHERE scope_key=%s AND provider_slug='banktwo' FOR UPDATE
        """, (parent["scope_key"],)).fetchone()
        if not scope or scope["source_vehicle_ref"] != parent["source_vehicle_ref"]:
            raise ValueError("BANKTWO_AUTHORED_ARTICLE_PARENT_CHANGED")
        _, retained_body, _ = _bound_parent(cur, parent_article_id, source_revision_id, lock=True)
        if retained_body != body:
            raise ValueError("BANKTWO_AUTHORED_ARTICLE_BODY_CHANGED")
        # Lock siblings in the same order for overlapping recovery requests.
        for authored, descriptor, key, resource in sorted(targets, key=lambda target: article_id(target[2])):
            target_id = article_id(key)
            inline_slots = [item for item in placements if item["authored_id_sha256"] == authored]
            known = cur.execute("""
                SELECT target_article_id, proof.takedown_status, inline_slots
                FROM banktwo_authored_article_referrals
                JOIN source_snapshots proof ON proof.source_snapshot_id=descriptor_source_snapshot_id
                WHERE parent_article_id=%s AND parent_source_revision_id=%s AND authored_path_sha256=%s
            """, (parent_article_id, source_revision_id, authored)).fetchone()
            if known and (known["target_article_id"] != target_id or known["takedown_status"] != "active"
                          or known["inline_slots"] != inline_slots):
                raise ValueError("BANKTWO_AUTHORED_ARTICLE_TARGET_CHANGED")
            target = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                                 (target_id,)).fetchone()
            if target and target["takedown_status"] != "active":
                raise ValueError("BANKTWO_AUTHORED_ARTICLE_TARGET_WITHDRAWN")
            if known is None:
                if resource is None:
                    raise ValueError("BANKTWO_AUTHORED_ARTICLE_TARGET_CHANGED")
                snapshot = persist_resource(cur, resource)
                if not cur.execute("SELECT 1 FROM source_snapshots WHERE source_snapshot_id=%s AND takedown_status='active'",
                                   (snapshot,)).fetchone():
                    raise ValueError("BANKTWO_AUTHORED_ARTICLE_TARGET_WITHDRAWN")
                if target is None:
                    _upsert_descriptor(conn, key, descriptor, snapshot, 0)
                cur.execute("""
                    INSERT INTO banktwo_authored_article_referrals (
                        parent_article_id,parent_source_revision_id,authored_path_sha256,
                        target_article_id,descriptor_source_snapshot_id,inline_slots
                    ) VALUES (%s,%s,%s,%s,%s,%s)
                """, (parent_article_id, source_revision_id, authored, target_id, snapshot, Jsonb(inline_slots)))
            if target is None:
                target = cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",
                                     (target_id,)).fetchone()
            if target is None:
                raise ValueError("BANKTWO_AUTHORED_ARTICLE_TARGET_CHANGED")
            if target["membership_status"] != "active":
                cur.execute("UPDATE canonical_articles SET membership_status='active',updated_at=clock_timestamp() "
                            "WHERE canonical_article_id=%s", (target_id,))
            if target["current_source_revision_id"] is None:
                _ensure_locked(cur, target)
            registered.append((authored, target_id))
    by_path = dict(registered)
    return [(authored, by_path[authored]) for authored in ordered if authored in by_path]
