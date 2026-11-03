"""Conservative rewrite contract and durable recovery regressions."""
from copy import deepcopy
import json
import pytest
from autodata_ingestion import procedure_rewrite as rewrite


def document():
    return {"schema_version": 1, "normalization_version": "ordered-article-v1", "blocks": [
        {"block_id":"p", "source_order":1,"type":"paragraph","text":"Remove the pump.","evidence_ids":["e"]},
        {"block_id":"w", "source_order":2,"type":"callout","text":"Warning: Do not loosen tool T-42.","evidence_ids":["e"]},
        {"block_id":"t", "source_order":3,"type":"table","rows":[[{"text":"10 Nm","blocks":[]}]],"evidence_ids":["e"]},
        {"block_id":"i", "source_order":4,"type":"image","status":"unavailable","unavailable_reason":"missing","evidence_ids":["e"]},
        {"block_id":"l", "source_order":5,"type":"ordered_list","items":[{"text":"Install the cover."}],"evidence_ids":["e"]},
    ]}


class Model:
    def complete_json(self, prompt):
        self.prompt = prompt
        slots = json.loads(prompt)["slots"]
        return {"replacements":[{**s,"text":s["text"].replace("Remove", "Take off").replace("Install", "Fit")} for s in slots]}


def test_ordered_phrase_rewrite_preserves_table_warning_image_and_evidence():
    original=document(); model=Model()
    result=rewrite.rewrite_ordered_document(original,client=model,context={})
    assert result.error_code is None
    assert result.document["blocks"][0]["text"]=="Take off the pump."
    assert result.document["blocks"][1:4]==original["blocks"][1:4]
    assert result.document["blocks"][4]["items"][0]["text"]=="Fit the cover."
    assert rewrite.validate_article_rewrite(original,result.document,profile_version="technical-prose-v1").passed
    assert original==document()


@pytest.mark.parametrize("mutation",["torque","warning","evidence","image","order","missing","unknown","tool","negation","applicability"])
def test_protected_mutation_rejected(mutation):
    original=document(); candidate=deepcopy(original); candidate["blocks"][0]["text"]="Take off the pump."
    if mutation=="torque": candidate["blocks"][2]["rows"][0][0]["text"]="100 Nm"
    elif mutation=="warning": candidate["blocks"][1]["text"]="Do loosen tool T-42."
    elif mutation=="evidence": candidate["blocks"][0]["evidence_ids"]=[]
    elif mutation=="image": candidate["blocks"][3]["unavailable_reason"]="other"
    elif mutation=="order": candidate["blocks"].reverse()
    elif mutation=="missing": candidate["blocks"].pop()
    elif mutation=="unknown": original["blocks"][2]["type"]="unknown"; candidate["blocks"][2]["type"]="unknown"
    else: candidate["blocks"][0]["text"] += {"tool":" Using wrench.","negation":" Do not proceed.","applicability":" Diesel only."}[mutation]
    assert not rewrite.validate_article_rewrite(original,candidate,profile_version="technical-prose-v1").passed


@pytest.mark.parametrize("mode",["missing","duplicate","extra","unchanged","blank"])
def test_slot_contract_fails_closed(mode):
    class BadModel(Model):
        def complete_json(self,prompt):
            response=super().complete_json(prompt); rows=response["replacements"]
            if mode=="missing": rows.pop()
            elif mode=="duplicate": rows.append(rows[0])
            elif mode=="extra": rows[0]["path"]="/blocks/1/text"
            elif mode=="blank": rows[0]["text"]=""
            else:
                return {"replacements":json.loads(prompt)["slots"]}
            return response
    result=rewrite.rewrite_ordered_document(document(),client=BadModel(),context={})
    assert result.error_code and result.document==document()


def test_prompt_limit_never_calls_model():
    source=document(); source["metadata"]="x"*(201*1024)
    class Never:
        def complete_json(self,prompt): pytest.fail("oversized prompt sent")
    assert rewrite.rewrite_ordered_document(source,client=Never(),context={}).error_code=="REWRITE_INPUT_LIMIT"


def test_protected_projection_literal():
    source={"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[document()["blocks"][0]]}
    assert rewrite.protected_projection(source)=={"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[{"block_id":"p","source_order":1,"type":"paragraph","text":{"editable":"/blocks/0/text"},"evidence_ids":["e"]}]}

from lifecycle_support import fresh_database
from test_source_article_capture import capture_fixture


def prepare_transform(repo, fixture):
    from test_article_source_persistence import prepare
    from autodata_ingestion.article_lifecycle_store import store_captured_source, load_source_revision
    from dataclasses import replace
    context,lease,captured=prepare(repo,fixture)
    source=store_captured_source(repo,lease,captured)
    lease=replace(lease,source_revision_id=source,phase="normalizing")
    stored=load_source_revision(repo,source)
    return lease,stored


def test_durable_result_reused_after_lease_reclaim_without_model(fresh_database,capture_fixture):
    from autodata_ingestion import article_lifecycle_store as store
    from autodata_ingestion.source_job_persistence import claim_source_job, LeaseLost
    from uuid import uuid4
    repo=fresh_database();lease,source=prepare_transform(repo,capture_fixture)
    store.save_normalized_input(repo,lease,source.as_article())
    attempt=store.prepare_rewrite_attempt(repo,lease,source.source_document,context=source.vehicle,model="fixture")
    store.mark_rewrite_dispatched(repo,lease,attempt)
    result=rewrite.rewrite_ordered_document(source.source_document,client=Model(),context=source.vehicle)
    revision=store.store_rewrite_result(repo,lease,result)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s",(lease.job_id,))
    new=claim_source_job(repo,worker_id=uuid4())
    assert store.load_candidate(repo,new)["canonical_article_revision_id"]==revision
    with pytest.raises(LeaseLost): store.store_validation(repo,lease,rewrite.validate_article_rewrite(source.source_document,result.document,profile_version=lease.rewrite_profile_version))
    validation=rewrite.validate_article_rewrite(source.source_document,result.document,profile_version=new.rewrite_profile_version)
    store.store_validation(repo,new,validation)
    row=store.load_candidate(repo,new)
    assert row["status"]=="validated" and row["validation_report"]["passed"]
    with repo.connect() as conn:
        attempt=conn.execute("SELECT * FROM canonical_article_rewrite_attempts").fetchone()
        assert attempt["status"]=="succeeded" and attempt["response"]==result.raw_response
        assert attempt["canonical_article_revision_id"]==revision
