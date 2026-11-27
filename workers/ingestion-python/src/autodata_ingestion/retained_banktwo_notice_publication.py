"""Publish exact source-layout corrections with their retained rewrites."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Callable
from uuid import UUID

from psycopg.rows import dict_row

from .article_lifecycle_store import resolve_source_bound_correction
from .article_lifecycle_types import digest_json, transformation_key
from .procedure_normalize import normalize_procedure_article
from .published_media_publication import _publication_evidence_for_revision, _publish, _RepairPlan, _result
from .retained_bankone_order_publication import _article, _captured_revision
from .retained_banktwo_notice_reply import (
    BANKONE_DEFINITION_METHOD, BANKONE_LIST_BOUNDARY_METHOD, BANKTWO_NOTICE_METHOD, repair_layout_reply,
)
from .retained_procedure_repair import _valid_audit
from .source_article_capture import _walk
from .source_bankone_definition_heading_replay import (
    load_bankone_definition_heading_binding, preview_bankone_definition_heading_replay,
    validate_bankone_definition_heading_capture,
)
from .source_bankone_list_boundary_replay import (
    load_bankone_list_boundary_binding, preview_bankone_list_boundary_replay, validate_bankone_list_boundary_capture,
)
from .source_bankone_order_replay import _without_generated_ids
from .source_banktwo_notice_replay import (
    load_banktwo_notice_binding, preview_banktwo_notice_replay, validate_banktwo_notice_capture,
)
from .source_job_persistence import source_bound_rewrite_source_allowed
from .source_revision_reprojection import _require_no_active_normal_job


SCHEMA = "autodata:published-banktwo-list-notices:v1"
BANKONE_DEFINITION_SCHEMA = "autodata:published-bankone-definition-headings:v1"
BANKONE_LIST_BOUNDARY_SCHEMA = "autodata:published-bankone-list-boundaries:v1"
_INVALID = "BANKTWO_NOTICE_PUBLICATION_INVALID"
_STALE = "BANKTWO_NOTICE_PUBLICATION_STALE"


@dataclass(frozen=True)
class _LayoutRepair:
    provider: str
    method: str
    load_binding: Callable
    preview_replay: Callable
    validate_capture: Callable


_LAYOUTS = {
    SCHEMA: _LayoutRepair(
        "banktwo", BANKTWO_NOTICE_METHOD, load_banktwo_notice_binding,
        preview_banktwo_notice_replay, validate_banktwo_notice_capture,
    ),
    BANKONE_DEFINITION_SCHEMA: _LayoutRepair(
        "bankone", BANKONE_DEFINITION_METHOD, load_bankone_definition_heading_binding,
        preview_bankone_definition_heading_replay, validate_bankone_definition_heading_capture,
    ),
    BANKONE_LIST_BOUNDARY_SCHEMA: _LayoutRepair(
        "bankone", BANKONE_LIST_BOUNDARY_METHOD, load_bankone_list_boundary_binding,
        preview_bankone_list_boundary_replay, validate_bankone_list_boundary_capture,
    ),
}


def _normalize(captured, article_id):
    return normalize_procedure_article({
        "article_id": str(article_id),
        "title": captured.context.descriptor.get("title"),
        "evidence_ids": list(captured.context.evidence_ids),
        "normalized_document": captured.source_document,
        "body": captured.source_body,
        "steps": captured.source_steps,
        "images": captured.source_images,
    }, resource_manifest=captured.resource_manifest)["normalized_document"]


def _retained_link_rows(cur, revision):
    return tuple(cur.execute("""SELECT block_id,label_sha256,authored_id_sha256,target_ref_sha256,body_sha256
        FROM canonical_article_link_bindings WHERE canonical_article_revision_id=%s
          AND canonical_article_id=%s AND source_revision_id=%s ORDER BY block_id COLLATE "C" LIMIT 129
        """, (revision["canonical_article_revision_id"], revision["canonical_article_id"],
              revision["source_revision_id"])).fetchall())


def _link_successors(links, previous, corrected, *, body_sha256):
    if len(links) > 128:
        raise ValueError(_INVALID)
    before = [node for node in _walk(previous["blocks"]) if node.get("type") == "link"]
    after = [node for node in _walk(corrected["blocks"]) if node.get("type") == "link"]
    result = []
    for link in links:
        old = [node for node in before if node.get("block_id") == link["block_id"]]
        if (len(old) != 1 or link["body_sha256"] != body_sha256 or "target_ref_sha256" in old[0]
                or sha256(old[0]["text"].encode()).hexdigest() != link["label_sha256"]):
            raise ValueError(_INVALID)
        target = _without_generated_ids(old[0])
        matches = [node for node in after if _without_generated_ids(node) == target]
        if len(matches) != 1:
            raise ValueError(_INVALID)
        result.append({**link, "block_id": matches[0]["block_id"]})
    if len({link["block_id"] for link in result}) != len(result):
        raise ValueError(_INVALID)
    return tuple(sorted(result, key=lambda link: link["block_id"]))


def _make_plan(cur, article, binding, captured, previous_id, *, schema, lock=False, expected_profile=None):
    layout = _LAYOUTS[schema]
    if binding.canonical_article_id != article["canonical_article_id"]:
        raise ValueError(_INVALID)
    layout.validate_capture(binding, captured)
    row, review, decision, attempt, response, prompt, authors = _publication_evidence_for_revision(
        cur, article, binding, previous_id, fixture_mode=False, lock=lock, expected_profile=expected_profile,
    )
    links = _retained_link_rows(cur, row)
    if (review is not None or decision != "UNREVIEWED" or attempt is None or not prompt
            or row["normalized_source_hash"] != binding.source_document_hash
            or links and schema != BANKONE_LIST_BOUNDARY_SCHEMA
            or cur.execute("""SELECT 1 FROM canonical_article_inline_link_bindings
                WHERE canonical_article_revision_id=%s LIMIT 1""", (previous_id,)).fetchone()):
        raise ValueError(_INVALID)

    owner = cur.execute("""SELECT * FROM source_fetch_jobs
        WHERE transformation_key=%s AND status='completed' AND phase='completed'
          AND canonical_article_id=%s AND source_revision_id=%s""",
        (row["transformation_key"], binding.canonical_article_id, binding.source_revision_id)).fetchone()
    if owner is None:
        raise ValueError(_INVALID)
    bankone_structure = None
    if schema == BANKONE_LIST_BOUNDARY_SCHEMA:
        original = resolve_source_bound_correction(cur, owner, row)
        if original.response != response or original.evidence["guard_version"] != prompt or original.bankone_structure is None:
            raise ValueError(_INVALID)
        bankone_structure = original.bankone_structure
    normalized = _normalize(captured, binding.canonical_article_id)
    repair = repair_layout_reply(
        row["normalized_source_document"], row["canonical_document"], normalized, response=response,
        prompt_version=prompt, profile=row["validation_report"]["profile_version"], method=layout.method,
        bankone_structure=bankone_structure,
    )
    retained_links = _link_successors(
        links, row["canonical_document"], repair.document, body_sha256=binding.body_sha256,
    ) if links else ()
    manifest = {
        "schema": schema,
        "article_id": str(binding.canonical_article_id),
        "source_revision_id": str(binding.source_revision_id),
        "source_observation_id": str(binding.source_observation_id),
        "canonical_revision_id": str(previous_id),
        "current_job_id": str(owner["source_fetch_job_id"]),
        "request_generation": owner["request_generation"],
        "descriptor_snapshot_id": str(binding.context.descriptor_snapshot_id),
        "body_sha256": binding.body_sha256,
        "source_fingerprint": binding.source_fingerprint,
        "repaired_source_fingerprint": captured.source_fingerprint,
        "repaired_source_document_hash": digest_json(captured.source_document),
        "repaired_provenance_hash": digest_json(captured.resource_provenance),
        "repaired_projection_version": captured.projection_version,
        "normalization_version": row["normalization_version"],
        "rewrite_profile_version": row["rewrite_profile_version"],
        "original_attempt_id": str(attempt["rewrite_attempt_id"]),
        "original_prompt_hash": attempt["prompt_hash"],
        "original_validation_hash": row["validation_hash"],
        "repaired_validation_hash": digest_json(repair.validation.report),
        **({"retained_link_count": len(retained_links), "retained_link_hash": digest_json(retained_links)}
           if schema == BANKONE_LIST_BOUNDARY_SCHEMA else {}),
        **repair.provenance,
    }
    return _RepairPlan(manifest, row, normalized, repair, decision, authors, retained_links), attempt


def _key(article_id, captured, manifest):
    return transformation_key(
        article_id, captured.source_fingerprint,
        manifest["normalization_version"], manifest["rewrite_profile_version"],
        projection_version=captured.projection_version,
    )


def _require_current(cur, article, manifest):
    if (article is None or article["provider_slug"] != _LAYOUTS[manifest["schema"]].provider
            or str(article["current_source_revision_id"]) != manifest["source_revision_id"]
            or str(article["current_canonical_revision_id"]) != manifest["canonical_revision_id"]
            or str(article["current_job_id"]) != manifest["current_job_id"]
            or str(article["descriptor_source_snapshot_id"]) != manifest["descriptor_snapshot_id"]
            or article["request_generation"] != manifest["request_generation"]
            or article["target_normalization_version"] != manifest["normalization_version"]
            or article["target_rewrite_profile_version"] != manifest["rewrite_profile_version"]
            or not source_bound_rewrite_source_allowed(cur, article, article["current_source_revision_id"])):
        raise ValueError(_STALE)


def _proof(approval, *, schema=SCHEMA):
    if (not isinstance(approval, dict) or set(approval) != {"manifest", "actor", "reason"}
            or not _valid_audit(approval["actor"], approval["reason"])):
        raise ValueError(_INVALID)
    manifest = approval["manifest"]
    if not isinstance(manifest, dict) or manifest.get("schema") != schema:
        raise ValueError(_INVALID)
    try:
        ids = tuple(UUID(manifest[name]) for name in ("article_id", "source_revision_id", "canonical_revision_id"))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError(_INVALID) from None
    return manifest, ids


def preview_banktwo_notice_publication(repo, source_revision_id, *, object_store):
    return _preview_layout_publication(repo, source_revision_id, object_store=object_store, schema=SCHEMA)


def preview_bankone_definition_heading_publication(repo, source_revision_id, *, object_store):
    return _preview_layout_publication(repo, source_revision_id, object_store=object_store, schema=BANKONE_DEFINITION_SCHEMA)


def preview_bankone_list_boundary_publication(repo, source_revision_id, *, object_store):
    return _preview_layout_publication(repo, source_revision_id, object_store=object_store, schema=BANKONE_LIST_BOUNDARY_SCHEMA)


def _preview_layout_publication(repo, source_revision_id, *, object_store, schema):
    layout = _LAYOUTS[schema]
    binding, captured = layout.preview_replay(repo, source_revision_id, object_store=object_store)
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='8s'")
        article = _article(cur, binding.canonical_article_id)
        if article is None or binding != layout.load_binding(cur, source_revision_id):
            raise ValueError(_STALE)
        plan, _ = _make_plan(cur, article, binding, captured, article["current_canonical_revision_id"], schema=schema)
        _require_current(cur, article, plan.manifest)
        return plan.manifest


def resolve_banktwo_notice_publication(cur, job, article, candidate, *, lock=False):
    return _resolve_layout_publication(cur, job, article, candidate, schema=SCHEMA, lock=lock)


def resolve_bankone_definition_heading_publication(cur, job, article, candidate, *, lock=False):
    return _resolve_layout_publication(cur, job, article, candidate, schema=BANKONE_DEFINITION_SCHEMA, lock=lock)


def resolve_bankone_list_boundary_publication(cur, job, article, candidate, *, lock=False):
    return _resolve_layout_publication(cur, job, article, candidate, schema=BANKONE_LIST_BOUNDARY_SCHEMA, lock=lock)


def _resolve_layout_publication(cur, job, article, candidate, *, schema, lock=False):
    layout = _LAYOUTS[schema]
    manifest, (article_id, source_id, previous_id) = _proof(job["checkpoint"].get("media_repair"), schema=schema)
    if (article_id != article["canonical_article_id"] or article_id != job["canonical_article_id"]
            or article_id != candidate["canonical_article_id"] or article["provider_slug"] != layout.provider
            or job["provider_slug"] != layout.provider or job["job_kind"] != "article"
            or job["source_version"] != layout.method or job["status"] != "completed"
            or job["phase"] != "completed" or job["source_revision_id"] != candidate["source_revision_id"]
            or candidate["source_revision_id"] == source_id or candidate["canonical_article_revision_id"] == previous_id
            or candidate["status"] != "published" or candidate["review_status"] != "UNREVIEWED"):
        raise ValueError(_INVALID)
    binding = layout.load_binding(cur, source_id, lock=lock)
    captured = _captured_revision(cur, candidate["source_revision_id"])
    # A successor can change the article target while the layout repair keeps its original rewrite profile.
    plan, attempt = _make_plan(cur, article, binding, captured, previous_id, schema=schema,
                               expected_profile=candidate["rewrite_profile_version"])
    key = _key(article_id, captured, plan.manifest)
    if schema == BANKONE_LIST_BOUNDARY_SCHEMA and _retained_link_rows(cur, candidate) != plan.retained_links:
        raise ValueError(_INVALID)
    if (manifest != plan.manifest or job["request_generation"] != manifest["request_generation"] + 1
            or job["transformation_key"] != key or candidate["transformation_key"] != key
            or not all(job[field] == candidate[field] == manifest[field]
                       for field in ("normalization_version", "rewrite_profile_version"))
            or candidate["normalized_source_document"] != plan.normalized
            or candidate["normalized_source_hash"] != digest_json(plan.normalized)
            or candidate["canonical_document"] != plan.repair.document
            or candidate["rewrite_result_hash"] != manifest["repaired_published_document_hash"]
            or candidate["validation_report"] != plan.repair.validation.report
            or candidate["validation_hash"] != manifest["repaired_validation_hash"]
            or plan.repair.projection != {"body": candidate["canonical_body"], "steps": candidate["canonical_steps"],
                                          "images": candidate["canonical_images"]}
            or candidate["model_metadata"] != {
                **plan.repair.provenance,
                "model": plan.previous["model_metadata"]["model"],
                "original_attempt_id": manifest["original_attempt_id"],
                "original_prompt_hash": manifest["original_prompt_hash"],
                "original_canonical_revision_id": manifest["canonical_revision_id"],
            }):
        raise ValueError(_INVALID)
    return plan.repair, attempt, manifest["original_prompt_version"]


def _current_candidate(cur, article):
    return cur.execute("""SELECT r.* FROM canonical_article_revisions r JOIN catalog_article_current visible
        ON visible.canonical_article_id=r.canonical_article_id AND visible.canonical_revision_id=r.canonical_article_revision_id
        WHERE visible.canonical_article_id=%s
          AND r.canonical_article_revision_id=%s AND r.source_revision_id=%s AND r.status='published'
          AND visible.availability='available' AND visible.takedown_status='active'""",
        (article["canonical_article_id"], article["current_canonical_revision_id"],
         article["current_source_revision_id"])).fetchone()


def _already_published(cur, article, approval, *, schema):
    candidate = _current_candidate(cur, article)
    if candidate is None or candidate["model_metadata"].get("transformation_method") != _LAYOUTS[schema].method:
        return None
    job = cur.execute("SELECT * FROM source_fetch_jobs WHERE transformation_key=%s",
                      (candidate["transformation_key"],)).fetchone()
    if job is None or job["checkpoint"].get("media_repair") != approval:
        raise ValueError(_STALE)
    _resolve_layout_publication(cur, job, article, candidate, schema=schema)
    return _result({**candidate, "source_fetch_job_id": job["source_fetch_job_id"]}, "already_published")


def publish_banktwo_notice(repo, *, expected, object_store, actor, reason, hooks=None):
    return _publish_layout_publication(repo, expected=expected, object_store=object_store, actor=actor, reason=reason,
                                       schema=SCHEMA, hooks=hooks)


def publish_bankone_definition_heading(repo, *, expected, object_store, actor, reason, hooks=None):
    return _publish_layout_publication(repo, expected=expected, object_store=object_store, actor=actor, reason=reason,
                                       schema=BANKONE_DEFINITION_SCHEMA, hooks=hooks)


def publish_bankone_list_boundary(repo, *, expected, object_store, actor, reason, hooks=None):
    return _publish_layout_publication(repo, expected=expected, object_store=object_store, actor=actor, reason=reason,
                                       schema=BANKONE_LIST_BOUNDARY_SCHEMA, hooks=hooks)


def _publish_layout_publication(repo, *, expected, object_store, actor, reason, schema, hooks):
    layout = _LAYOUTS[schema]
    approval = {"manifest": expected, "actor": actor, "reason": reason}
    manifest, (article_id, source_id, previous_id) = _proof(approval, schema=schema)
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SET LOCAL statement_timeout='8s'")
        article = _article(cur, article_id)
        if article is None:
            raise ValueError(_STALE)
        repeated = _already_published(cur, article, approval, schema=schema)
        if repeated is not None:
            return repeated
        _require_current(cur, article, manifest)

    binding, captured = layout.preview_replay(repo, source_id, object_store=object_store)
    with repo.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET LOCAL lock_timeout='5s'")
        article = _article(cur, article_id, lock=True)
        if article is None:
            raise ValueError(_STALE)
        repeated = _already_published(cur, article, approval, schema=schema)
        if repeated is not None:
            return repeated
        _require_current(cur, article, manifest)
        _require_no_active_normal_job(cur, article_id)
        locked = layout.load_binding(cur, source_id, lock=True)
        if binding != locked:
            raise ValueError(_STALE)
        plan, _ = _make_plan(cur, article, locked, captured, previous_id, schema=schema, lock=True)
        if plan.manifest != manifest:
            raise ValueError(_STALE)
        key = _key(article_id, captured, manifest)
        result = _publish(cur, article, captured, key, plan, approval, hooks=hooks)
        current = _article(cur, article_id)
        candidate = _current_candidate(cur, current)
        job = cur.execute("SELECT * FROM source_fetch_jobs WHERE transformation_key=%s", (key,)).fetchone()
        if candidate is None or job is None:
            raise ValueError(_INVALID)
        _resolve_layout_publication(cur, job, current, candidate, schema=schema)
        return result
