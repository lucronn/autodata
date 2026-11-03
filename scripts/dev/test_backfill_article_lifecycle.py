"""Offline mappings require exact persisted evidence and retain source state."""
from pathlib import Path
import sys,json
from uuid import uuid4
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle_support import fresh_database,seed_vehicle,seed_snapshot
from backfill_article_lifecycle import backfill


def seed(repo,provider="bankone"):
    from psycopg.types.json import Jsonb
    vehicle=seed_vehicle(repo);snapshot=seed_snapshot(repo,provider.encode());legacy=uuid4()
    identity={"provider":provider,"source_vehicle_ref":"opaque:v","source_article_ref":"same/a","vehicle_id":str(vehicle),"vehicle_configuration_id":None,"body_resource_ref":"opaque:body"}
    with repo.connect() as conn:
        evidence=conn.execute("INSERT INTO extraction_evidence(source_snapshot_id,locator,artifact_key,extracted_text,confidence,reviewer_state) VALUES (%s,'fixture','fixture',%s,1,'approved') RETURNING extraction_evidence_id",(snapshot,json.dumps(identity))).fetchone()["extraction_evidence_id"]
        document={"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[{"block_id":"p","source_order":1,"type":"paragraph","text":"Remove the pump.","evidence_ids":[str(evidence)]}]}
        conn.execute("INSERT INTO catalog_articles(catalog_article_id,vehicle_id,article_id,title,source_snapshot_id,evidence_locator,evidence_confidence,provider,body,normalized_document) VALUES (%s,%s,'legacy','Same title',%s,'fixture',1,%s,'Remove the pump.',%s)",(legacy,vehicle,snapshot,provider,Jsonb(document)))
    return {"catalog_article_id":str(legacy),**identity,"proof":{"source_snapshot_id":str(snapshot),"extraction_evidence_id":str(evidence),"reviewer_id":"fixture-operator","reason":"reviewed exact identity"}}


def test_dry_run_has_no_writes_and_apply_projects_source_and_queues_atomically(fresh_database):
    repo=fresh_database();mapping=seed(repo)
    assert backfill(repo,[mapping])["mapped"]==1
    with repo.connect() as conn:assert conn.execute("SELECT count(*) AS n FROM canonical_articles").fetchone()["n"]==0
    assert backfill(repo,[mapping],apply=True)=={"mapped":1,"already_mapped":0,"quarantined":0,"unresolved":0}
    assert backfill(repo,[mapping],apply=True)["already_mapped"]==1
    with repo.connect() as conn:
        row=conn.execute("SELECT * FROM catalog_article_current").fetchone()
        assert row["content_origin"]=="source" and row["canonical_revision_id"] is None
        assert row["processing_state"]=="queued"
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"]==1


@pytest.mark.parametrize("mutation",["wrong_vehicle","missing_proof","duplicate_mapping","wrong_ref"])
def test_invalid_mapping_is_quarantined_without_guessing(fresh_database,mutation):
    repo=fresh_database();mapping=seed(repo)
    if mutation=="wrong_vehicle":mapping["vehicle_id"]=str(seed_vehicle(repo))
    elif mutation=="missing_proof":mapping["proof"]={}
    elif mutation=="wrong_ref":mapping["source_article_ref"]="suffix/a"
    mappings=[mapping,mapping] if mutation=="duplicate_mapping" else [mapping]
    result=backfill(repo,mappings,apply=True)
    assert result["mapped"]==0 and result["quarantined"]>=1
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM canonical_articles").fetchone()["n"]==0
        assert conn.execute("SELECT count(*) AS n FROM source_review_items").fetchone()["n"]==1


def test_equal_title_and_refs_across_banks_never_merge(fresh_database):
    repo=fresh_database();first=seed(repo);second=seed(repo,"banktwo")
    assert backfill(repo,[first,second],apply=True)["mapped"]==2
    with repo.connect() as conn:assert conn.execute("SELECT count(DISTINCT canonical_article_id) AS n FROM canonical_article_aliases").fetchone()["n"]==2
