#!/usr/bin/env python3
"""Offline reviewed exact mappings. Dry-run is the default; no source/model IO."""
from pathlib import Path
import sys,json
from collections import Counter
from uuid import UUID,uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"workers/ingestion-python/src"))


def backfill(repo,mappings,*,apply=False):
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    from autodata_ingestion.article_lifecycle_types import ArticleKey,identity_payload,digest_json,transformation_key
    from autodata_ingestion.article_lifecycle_store import _upsert_descriptor
    from autodata_ingestion.source_job_persistence import _ensure_locked
    from autodata_ingestion.article_document import validate_ordered_document,project_ordered_document
    if not isinstance(mappings,list):raise ValueError("mapping file must be a JSON array")
    counts={"mapped":0,"already_mapped":0,"quarantined":0,"unresolved":0}
    duplicates=Counter(str(item.get("catalog_article_id")) for item in mappings if isinstance(item,dict))
    seen=set()
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        for mapping in mappings:
            legacy_id=str(mapping.get("catalog_article_id")) if isinstance(mapping,dict) else "invalid"
            if legacy_id in seen:continue
            seen.add(legacy_id)
            valid=False;legacy=None
            try:
                legacy_uuid=UUID(legacy_id)
                legacy=cur.execute("SELECT * FROM catalog_articles WHERE catalog_article_id=%s FOR UPDATE",(legacy_uuid,)).fetchone()
                if legacy is None:raise ValueError("unknown legacy row")
                key=ArticleKey(mapping["provider"],UUID(mapping["vehicle_id"]),UUID(mapping["vehicle_configuration_id"]) if mapping.get("vehicle_configuration_id") else None,mapping["source_vehicle_ref"],mapping["source_article_ref"])
                proof=mapping["proof"]
                if duplicates[legacy_id]!=1 or not proof.get("reviewer_id") or not proof.get("reason"):raise ValueError("missing explicit review")
                if legacy["vehicle_id"]!=key.vehicle_id or legacy.get("vehicle_configuration_id")!=key.vehicle_configuration_id:raise ValueError("scope mismatch")
                if legacy.get("provider") not in {key.provider,{"bankone":"autoapi","banktwo":"autoapitwo"}[key.provider]}:raise ValueError("bank mismatch")
                snapshot=legacy.get("content_source_snapshot_id") or legacy["source_snapshot_id"]
                if UUID(proof["source_snapshot_id"])!=snapshot:raise ValueError("snapshot mismatch")
                evidence=cur.execute("SELECT * FROM extraction_evidence WHERE extraction_evidence_id=%s AND source_snapshot_id=%s AND reviewer_state='approved'",(UUID(proof["extraction_evidence_id"]),snapshot)).fetchone()
                if evidence is None or json.loads(evidence["extracted_text"])!={**identity_payload(key),"body_resource_ref":mapping["body_resource_ref"]}:raise ValueError("binding proof mismatch")
                document=legacy["normalized_document"]
                if validate_ordered_document(document,strict=True):raise ValueError("legacy document needs review")
                if any(token in json.dumps(document).lower() for token in ("http://","https://","javascript:","<script")):raise ValueError("unsafe legacy projection")
                projected=project_ordered_document(document)
                if not projected["body"].strip():raise ValueError("missing source content")
                alias=cur.execute("SELECT canonical_article_id FROM canonical_article_aliases WHERE catalog_article_id=%s",(legacy_uuid,)).fetchone()
                from autodata_ingestion.article_lifecycle_types import article_id
                if alias:
                    if alias["canonical_article_id"]!=article_id(key):raise ValueError("conflicting alias")
                    counts["already_mapped"]+=1;continue
                valid=True
            except (ValueError,KeyError,TypeError,AttributeError):
                pass
            if not valid:
                counts["quarantined"]+=1
                if apply:
                    cur.execute("""INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,payload)
                        VALUES (%s,%s,'quarantine','ARTICLE_BINDING_REVIEW_REQUIRED',%s) ON CONFLICT(item_key) DO NOTHING""",
                        (uuid4(),"article-lifecycle-mapping:"+legacy_id,Jsonb({"catalog_article_id":legacy_id})))
                continue
            counts["mapped"]+=1
            if not apply:continue
            descriptor={"opaque_ref":key.source_article_ref,"title":legacy["title"],"resource_ref":mapping["body_resource_ref"]}
            canonical=_upsert_descriptor(conn,key,descriptor,legacy["source_snapshot_id"],0)
            article=cur.execute("SELECT * FROM canonical_articles WHERE canonical_article_id=%s FOR UPDATE",(canonical,)).fetchone()
            if article["current_job_id"] is not None:
                # An alias may bind to an existing exact identity; never replace
                # that identity's current source or transformation owner.
                cur.execute("INSERT INTO canonical_article_aliases(catalog_article_id,canonical_article_id,proof) VALUES (%s,%s,%s)",(legacy_uuid,canonical,Jsonb(proof)))
                cur.execute("UPDATE catalog_articles SET canonical_article_id=%s WHERE catalog_article_id=%s",(canonical,legacy_uuid))
                continue
            job=_ensure_locked(cur,article)
            blob=cur.execute("SELECT * FROM source_snapshots WHERE source_snapshot_id=%s",(snapshot,)).fetchone()
            fingerprint=digest_json({"source_snapshot_id":str(snapshot),"document":document,"projection":"offline-source-v1"})
            source=uuid4();evidence_ids=[str(evidence["extraction_evidence_id"])]
            manifest=[{"role":"body","provider":key.provider,"opaque_ref":key.source_article_ref,"source_snapshot_id":str(snapshot),"sha256":blob["content_sha256"],"object_key":blob["object_key"],"source_revision":blob["source_version"]}]
            cur.execute("""INSERT INTO canonical_article_source_revisions(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,source_document,source_images,source_body,source_steps,projection_status,evidence_manifest,captured_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'readable',%s,clock_timestamp())""",
                (source,canonical,fingerprint,snapshot,Jsonb(manifest),Jsonb(document),Jsonb(projected["images"]),projected["body"],Jsonb(projected["steps"]),Jsonb([{"evidence_id":evidence_ids[0],"body_source_snapshot_id":str(snapshot)}])))
            cur.execute("""UPDATE source_fetch_jobs SET source_revision_id=%s,transformation_key=%s,checkpoint=%s WHERE source_fetch_job_id=%s""",
                (source,transformation_key(canonical,fingerprint,article["target_normalization_version"],article["target_rewrite_profile_version"]),Jsonb({"offline_mapping":True,"legacy_catalog_article_id":legacy_id}),job.job_id))
            vehicle=cur.execute("SELECT make,model,model_year,region FROM vehicles WHERE vehicle_id=%s",(key.vehicle_id,)).fetchone()
            cur.execute("""INSERT INTO canonical_article_source_observations(source_observation_id,canonical_article_id,source_revision_id,source_fetch_job_id,request_generation,body_provider_revision,resource_provenance,captured_context,resolution_source_snapshot_id,descriptor_source_snapshot_id,captured_at)
                VALUES (%s,%s,%s,%s,0,%s,%s,%s,%s,%s,clock_timestamp())""",
                (uuid4(),canonical,source,job.job_id,blob["source_version"],Jsonb(manifest),Jsonb({"vehicle":vehicle,"descriptor":descriptor,"evidence_ids":evidence_ids}),snapshot,legacy["source_snapshot_id"]))
            cur.execute("UPDATE canonical_articles SET current_source_revision_id=%s WHERE canonical_article_id=%s",(source,canonical))
            cur.execute("INSERT INTO canonical_article_aliases(catalog_article_id,canonical_article_id,proof) VALUES (%s,%s,%s)",(legacy_uuid,canonical,Jsonb(proof)))
            cur.execute("UPDATE catalog_articles SET canonical_article_id=%s WHERE catalog_article_id=%s",(canonical,legacy_uuid))
        remaining=cur.execute("SELECT catalog_article_id FROM catalog_articles WHERE canonical_article_id IS NULL").fetchall()
        counts["unresolved"]=sum(str(row["catalog_article_id"]) not in seen for row in remaining)
        if not apply:conn.rollback()
    return counts


def main(argv=None):
    import argparse
    from autodata_ingestion.worker import ArticleRepository
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-file",required=True,type=Path)
    mode=parser.add_mutually_exclusive_group();mode.add_argument("--dry-run",action="store_true");mode.add_argument("--apply",action="store_true")
    args=parser.parse_args(argv)
    print(json.dumps(backfill(ArticleRepository(),json.loads(args.mapping_file.read_text()),apply=args.apply),sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
