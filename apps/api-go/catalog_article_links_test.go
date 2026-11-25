package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"testing"
)

func TestCatalogAuthoredArticleLinkProjection(t *testing.T) {
	hash := strings.Repeat("a", 64)
	missing := strings.Repeat("b", 64)
	target := "11111111-1111-4111-8111-111111111111"
	forged := "22222222-2222-4222-8222-222222222222"
	raw := []byte(fmt.Sprintf(`{
	  "schema_version": 1, "normalization_version": "ordered-article-v1", "blocks": [
	    {"type":"link","text":"Pump cover","target_ref_sha256":%q,"target_article_id":%q,"href":"https://provider.invalid/private","evidence_ids":["proof"]},
	    {"type":"table","rows":[{"cells":[{"blocks":[
	      {"type":"link","text":"Nested reference","target_ref_sha256":%q},
	      {"type":"link","text":"Unresolved reference","target_ref_sha256":%q}
	    ]}]}]},
	    {"type":"link","text":"Unsafe stored target","target_article_id":[%q],"href":"/supplier/request"},
	    {"type":"link","text":"Ordinary reference","href":"#existing-section"},
	    {"type":"link","text":"Malformed hash","target_ref_sha256":%q},
	    {"type":"paragraph","text":"Nonlink","target_ref_sha256":%q}
	  ]}`, hash, forged, hash, missing, forged, strings.ToUpper(hash), strings.Repeat("c", 64)))
	var stored CatalogDocument
	if err := json.Unmarshal(raw, &stored); err != nil {
		t.Fatal(err)
	}
	calls := 0
	projected := projectStoredCatalogDocument(&stored, raw, catalogArticleLinkProjection{resolve: func(hashes []string) map[string]string {
		calls++
		if !reflect.DeepEqual(hashes, []string{hash, missing}) {
			t.Fatalf("lookup did not receive distinct valid authored refs: %v", hashes)
		}
		return map[string]string{hash: target, missing: "invalid"}
	}})
	if calls != 1 || projected == nil || len(projected.Blocks) != 6 {
		t.Fatalf("unexpected projection or lookup count: %d", calls)
	}
	wire, err := json.Marshal(projected)
	if err != nil {
		t.Fatal(err)
	}
	out := string(wire)
	if strings.Count(out, `"target_article_id":"`+target+`"`) != 2 {
		t.Fatalf("valid top-level or nested link missing: %s", out)
	}
	for _, private := range []string{"target_ref_sha256", hash, missing, forged, "provider.invalid", "/supplier/request", "invalid"} {
		if strings.Contains(out, private) {
			t.Fatalf("private value exposed: %s", private)
		}
	}
	first := projected.Blocks[0]
	if !reflect.DeepEqual(first.EvidenceIDs, []string{"proof"}) || first.Text != "Pump cover" ||
		projected.Blocks[3].Href != "#existing-section" {
		t.Fatal("ordinary text and evidence were changed")
	}
	legacy := publicCatalogDocument(&stored)
	if legacy.Blocks[0].TargetArticleID != "" {
		t.Fatal("unverified stored target survived default projection")
	}
	before := lifecycleArticle(CatalogArticle{Document: &stored})
	after := catalogArticleLifecycle(CatalogArticle{Document: projected})
	if before.ViewRevision == nil || after.ViewRevision == nil || *before.ViewRevision == *after.ViewRevision {
		t.Fatal("verified destination did not change presentation identity")
	}
}

func TestCatalogAuthoredArticleLinkLookupTargetsAreBounded(t *testing.T) {
	blocks := make([]map[string]string, 0, maxCatalogArticleLinkTargets+1)
	for i := 0; i <= maxCatalogArticleLinkTargets; i++ {
		blocks = append(blocks, map[string]string{"type": "link", "text": "Document reference",
			"target_ref_sha256": fmt.Sprintf("%064x", i)})
	}
	raw, err := json.Marshal(map[string]any{"blocks": blocks})
	if err != nil {
		t.Fatal(err)
	}
	projected := projectCatalogDocument(raw, catalogArticleLinkProjection{resolve: func([]string) map[string]string {
		t.Fatal("over-budget document must not issue a lookup")
		return nil
	}})
	if projected == nil || len(projected.Blocks) != len(blocks) {
		t.Fatal("over-budget link text became unavailable")
	}
	for _, block := range projected.Blocks {
		if block.TargetArticleID != "" || block.Text != "Document reference" {
			t.Fatal("over-budget document changed text or exposed a target")
		}
	}
}

func TestPostgresPaidCatalogAuthoredArticleLinks(t *testing.T) {
	f := paidSetup(t)
	if f.provider != "bankone" {
		t.Skip("Bankone authored links fixture")
	}
	order := f.grant(0, f.configuration, "US")
	f.grant(1, f.adjacent, "US")

	// Leading spaces and UTF-8 are stored as part of the provider reference.
	exactRef := " fixture:référence "
	otherConfigRef := "fixture:adjacent-only"
	otherProviderRef := "fixture:other-provider"
	otherSourceVehicleRef := "fixture:other-source-vehicle"
	target := f.seedAuthoredLinkArticle(f.configuration, "bankone", "", exactRef)
	adjacent := f.seedAuthoredLinkArticle(f.adjacent, "bankone", "", otherConfigRef)
	_ = f.seedAuthoredLinkArticle(f.adjacent, "bankone", "", exactRef)
	_ = f.seedAuthoredLinkArticle(f.configuration, "banktwo", "", otherProviderRef)
	_ = f.seedAuthoredLinkArticle(f.configuration, "bankone", "another-fixture-source-vehicle", otherSourceVehicleRef)

	f.seedAuthoredLinkSource(target, `{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[{"type":"paragraph","text":"Exact linked target."}]}`)
	f.seedAuthoredLinkSource(f.article, fmt.Sprintf(`{
	  "schema_version":1,"normalization_version":"ordered-article-v1","blocks":[
	    {"type":"link","text":"Exact target","target_ref_sha256":%q,"target_article_id":%q,"href":"https://provider.invalid/secret"},
	    {"type":"unordered_list","items":[{"blocks":[{"type":"link","text":"Nested target","target_ref_sha256":%q}]}]},
	    {"type":"link","text":"Neighboring configuration","target_ref_sha256":%q},
	    {"type":"link","text":"Other provider","target_ref_sha256":%q},
	    {"type":"link","text":"Other source vehicle","target_ref_sha256":%q},
	    {"type":"link","text":"Unverified destination","target_article_id":%q}
	  ]}`, authoredLinkTestHash(exactRef), adjacent, authoredLinkTestHash(exactRef), authoredLinkTestHash(otherConfigRef), authoredLinkTestHash(otherProviderRef), authoredLinkTestHash(otherSourceVehicleRef), adjacent))

	originPath := f.path("/" + f.article)
	targetPath := f.path("/" + target)
	assertLinkProjection := func(raw []byte, expected int) {
		t.Helper()
		wire := string(raw)
		for _, forbidden := range []string{"target_ref_sha256", "provider.invalid", authoredLinkTestHash(exactRef), adjacent} {
			if strings.Contains(wire, forbidden) {
				t.Fatalf("protected origin exposed an unverified reference: %s", forbidden)
			}
		}
		if strings.Count(wire, `"target_article_id":"`+target+`"`) != expected ||
			strings.Count(wire, `"target_article_id"`) != expected {
			t.Fatal("wrong number of exact-scope authored destinations")
		}
	}
	readOrigin := func(expected int) CatalogArticle {
		t.Helper()
		raw := f.expect(0, "GET", originPath, "", 200)
		assertLinkProjection(raw, expected)
		var response CatalogArticleResponse
		if err := json.Unmarshal(raw, &response); err != nil || response.Article.ViewRevision == nil {
			t.Fatal("invalid authored-link response", err)
		}
		return response.Article
	}

	before := readOrigin(2)
	if before.SourceRevisionID == nil {
		t.Fatal("the source revision was not visible")
	}
	originalPath := originPath + "/source?source_revision_id=" + *before.SourceRevisionID
	assertLinkProjection(f.expect(0, "GET", originalPath, "", 200), 2)
	if !strings.Contains(string(f.expect(0, "GET", targetPath, "", 200)), "Exact linked target.") {
		t.Fatal("protected direct detail failed to read the linked target")
	}
	for _, deniedPath := range []string{originPath, originalPath, targetPath} {
		f.expect(-1, "GET", deniedPath, "", 401)
		f.expect(1, "GET", deniedPath, "", 403)
	}
	f.expect(0, "GET", f.path("/"+adjacent), "", 404)
	f.expect(0, "GET", f.path("/"+target+"?region=CA"), "", 404)
	f.exec(`UPDATE canonical_articles SET membership_status='retired' WHERE canonical_article_id=$1::uuid`, target)
	after := readOrigin(0)
	if *before.ViewRevision == *after.ViewRevision {
		t.Fatal("removed destination must invalidate the rendered view")
	}
	f.expect(0, "GET", targetPath, "", 404)
	f.exec(`UPDATE canonical_articles SET membership_status='active',takedown_status='takedown' WHERE canonical_article_id=$1::uuid`, target)
	readOrigin(0)
	assertLinkProjection(f.expect(0, "GET", originalPath, "", 200), 0)
	f.expect(0, "GET", targetPath, "", 410)

	f.exec(`UPDATE entitlements SET status='revoked',revoked_at=now(),revoke_reason='fixture'
	        WHERE commerce_order_id=$1::uuid`, order)
	f.expect(0, "GET", originPath, "", 403)
	f.expect(0, "POST", targetPath+"/prepare", "{}", 403)
}

func authoredLinkTestHash(value string) string {
	return fmt.Sprintf("%x", sha256.Sum256([]byte(value)))
}

func (f *paidFixture) seedAuthoredLinkArticle(configuration, provider, sourceVehicle, sourceArticle string) string {
	f.t.Helper()
	id := f.uuid()
	id = id[:14] + "4" + id[15:19] + "8" + id[20:]
	f.exec(`INSERT INTO canonical_articles
			(canonical_article_id, provider_slug, vehicle_id, vehicle_configuration_id, scope_key,
			 source_vehicle_ref, source_article_ref, identity_key, descriptor, descriptor_source_snapshot_id, title)
			SELECT $1::uuid, $2, a.vehicle_id, $3::uuid, 'configuration:'||$3,
			       COALESCE(NULLIF($4,''),a.source_vehicle_ref), $5, $6, a.descriptor, a.descriptor_source_snapshot_id, 'Linked fixture procedure'
			FROM canonical_articles a WHERE a.canonical_article_id=$7::uuid`,
		id, provider, configuration, sourceVehicle, sourceArticle, authoredLinkTestHash(id), f.article)
	return id
}

func (f *paidFixture) seedAuthoredLinkSource(article, document string) (string, string) {
	f.t.Helper()
	id := f.uuid()
	job := f.uuid()
	f.exec(`INSERT INTO canonical_article_source_revisions
			(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,
			 source_document,source_images,source_body,source_steps,projection_version,projection_status,evidence_manifest,captured_at)
			SELECT $1::uuid,a.canonical_article_id,$2,a.descriptor_source_snapshot_id,
			       '[{"role":"body","media_type":"application/json"}]',
			       $3::jsonb,'[]','Retained fixture procedure.','[]','source-projection-v2',
			       'readable','[{"evidence_id":"fixture"}]',now()
			FROM canonical_articles a WHERE a.canonical_article_id=$4::uuid`, id, authoredLinkTestHash(id), document, article)
	f.exec(`INSERT INTO source_fetch_jobs
			(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,
			 source_version,connector_name,idempotency_key,status,job_kind,canonical_article_id,
			 source_revision_id,request_generation,normalization_version,rewrite_profile_version)
			SELECT $1::uuid,a.provider_slug,a.vehicle_id,a.source_vehicle_ref,a.source_article_ref,
			       'fixture','fixture',$1::uuid::text,'completed','article',a.canonical_article_id,
			       $2::uuid,a.request_generation+1,a.target_normalization_version,a.target_rewrite_profile_version
			FROM canonical_articles a WHERE a.canonical_article_id=$3::uuid`, job, id, article)
	f.exec(`UPDATE canonical_articles SET current_source_revision_id=$1::uuid,current_job_id=$2::uuid,
			request_generation=request_generation+1 WHERE canonical_article_id=$3::uuid`, id, job, article)
	return id, job
}
