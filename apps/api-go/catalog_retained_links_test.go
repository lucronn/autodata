package main

import (
	"context"
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"testing"
)

func TestCatalogRetainedLinksMatchUniqueBlockAndExactLabel(t *testing.T) {
	const label = "Connecteur d’alimentation"
	const retainedTarget = "11111111-1111-4111-8111-111111111111"
	const inlineTarget = "22222222-2222-4222-8222-222222222222"
	retainedHash := authoredLinkTestHash("retained target")
	inlineHash := authoredLinkTestHash("inline target")
	labelHash := authoredLinkTestHash(label)
	raw := []byte(fmt.Sprintf(`{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[
		{"type":"link","block_id":"inline","text":%[1]q,"target_ref_sha256":%[2]q},
		{"type":"ordered_list","items":[{"blocks":[{"type":"link","block_id":"nested","text":%[1]q}]}]},
		{"type":"link","block_id":"label-changed","text":" %[1]s"},
		{"type":"link","block_id":"duplicate","text":%[1]q},
		{"type":"paragraph","block_id":"duplicate","text":"Duplicate block ID"},
		{"type":"paragraph","block_id":"wrong-type","text":%[1]q},
		{"type":"link","block_id":"malformed-inline","text":%[1]q,"target_ref_sha256":17},
		{"type":"link","block_id":"unrelated","text":%[1]q}
	]}`, label, inlineHash))
	retained := make(map[string]retainedCatalogLink)
	for _, id := range []string{"inline", "nested", "label-changed", "duplicate", "wrong-type", "malformed-inline"} {
		retained[id] = retainedCatalogLink{labelSHA256: labelHash, targetSHA256: retainedHash}
	}
	var calls int
	projected := projectCatalogDocument(raw, catalogArticleLinkProjection{
		retained: retained,
		resolve: func(hashes []string) map[string]string {
			calls++
			if len(hashes) != 2 || hashes[0] == hashes[1] {
				t.Fatalf("expected one combined lookup for two unique bindings, got %v", hashes)
			}
			return map[string]string{inlineHash: inlineTarget, retainedHash: retainedTarget}
		},
	})
	if projected == nil || calls != 1 || projected.Blocks[0].TargetArticleID != inlineTarget {
		t.Fatal("the in-document link changed")
	}
	assertRetainedPublicLinks(t, projected, retainedTarget, 1, 2)
}

func assertRetainedPublicLinks(t *testing.T, doc *CatalogDocument, target string, count, total int) {
	t.Helper()
	raw, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	wire := string(raw)
	if strings.Count(wire, `"target_article_id":"`+target+`"`) != count ||
		strings.Count(wire, `"target_article_id"`) != total {
		t.Fatal("unexpected retained target projection")
	}
	for _, private := range []string{"label_sha256", "authored_id_sha256", "body_sha256", "target_ref_sha256", "fixture.invalid/private"} {
		if strings.Contains(wire, private) {
			t.Fatalf("private binding material reached the reader: %s", private)
		}
	}
}

func TestPostgresPaidCatalogRetainedArticleLinks(t *testing.T) {
	f := paidSetup(t)
	if f.provider != "bankone" {
		t.Skip("Bankone retained links fixture")
	}
	order := f.grant(0, f.configuration, "US")
	f.grant(1, f.adjacent, "US")
	const ref = "fixture:retained-exact"
	const adjacentRef = "fixture:retained-adjacent"
	const label = "Connecteur d’alimentation"
	target := f.seedAuthoredLinkArticle(f.configuration, "bankone", "", ref)
	adjacent := f.seedAuthoredLinkArticle(f.adjacent, "bankone", "", adjacentRef)
	f.seedAuthoredLinkSource(target, `{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[{"type":"paragraph","text":"Retained target procedure."}]}`)
	blockID := f.article + ":block:0020:item:0003:block:0001:item:0001:block:0001"
	adjacentBlockID := f.article + ":block:0020:item:0003:block:0001:item:0002:block:0001"
	bodyMismatchBlockID := f.article + ":block:0020:item:0003:block:0001:item:0003:block:0001"
	nested := fmt.Sprintf(`{"type":"ordered_list","items":[{"blocks":[
		{"type":"unordered_list","items":[
			{"blocks":[{"type":"link","block_id":%q,"text":%q,"evidence_ids":["retained"],"href":"https://fixture.invalid/private"}]},
			{"blocks":[{"type":"link","block_id":%q,"text":"Other procedure"}]},
			{"blocks":[{"type":"link","block_id":%q,"text":"Mismatched body"}]}
		]}
	]}]},{"type":"paragraph","text":"Unchanged source instructions."}`, blockID, label, adjacentBlockID, bodyMismatchBlockID)
	const docStart = `{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[`
	sourceDocument := docStart + nested + `]}`
	canonicalDocument := docStart + `{"type":"paragraph","text":"Published introduction."},` + nested + `]}`
	sourceRevision, job := f.seedAuthoredLinkSource(f.article, sourceDocument)
	canonicalRevision, historical := f.uuid(), f.uuid()
	seedRetainedFixturePublication(f, sourceRevision, job, canonicalRevision, historical, canonicalDocument)
	ctx := context.Background()
	var bodyHash string
	if err := f.pool.QueryRow(ctx, `SELECT snapshot.content_sha256::text FROM source_snapshots snapshot
		JOIN canonical_article_source_revisions source ON source.body_source_snapshot_id=snapshot.source_snapshot_id
		WHERE source.source_revision_id=$1::uuid`, sourceRevision).Scan(&bodyHash); err != nil {
		t.Fatal(err)
	}
	storedDocuments := func() []string {
		t.Helper()
		var source, canonical, normalized string
		if err := f.pool.QueryRow(ctx, `SELECT source.source_document::text,published.canonical_document::text,published.normalized_source_document::text
			FROM canonical_article_source_revisions source JOIN canonical_article_revisions published USING(source_revision_id,canonical_article_id)
			WHERE published.canonical_article_revision_id=$1::uuid`, canonicalRevision).Scan(&source, &canonical, &normalized); err != nil {
			t.Fatal(err)
		}
		return []string{source, canonical, normalized}
	}
	storedBefore := storedDocuments()
	mainPath := f.path("/" + f.article)
	originalPath := mainPath + "/source?source_revision_id=" + sourceRevision
	historicalPath := mainPath + "/source?source_revision_id=" + historical
	readMain := func(expected int) CatalogArticle {
		t.Helper()
		var response CatalogArticleResponse
		if err := json.Unmarshal(f.expect(0, "GET", mainPath, "", 200), &response); err != nil {
			t.Fatal(err)
		}
		if response.Article.Document == nil || response.Article.ViewRevision == nil {
			t.Fatal("published article fixture was unavailable")
		}
		assertRetainedPublicLinks(t, response.Article.Document, target, expected, expected)
		return response.Article
	}
	readOriginal := func(path string, expected int) CatalogSourceContentResponse {
		t.Helper()
		var response CatalogSourceContentResponse
		if err := json.Unmarshal(f.expect(0, "GET", path, "", 200), &response); err != nil {
			t.Fatal(err)
		}
		if response.Document == nil || response.ViewRevision == nil {
			t.Fatal("retained original fixture was unavailable")
		}
		assertRetainedPublicLinks(t, response.Document, target, expected, expected)
		return response
	}
	mainBefore, originalBefore := readMain(0), readOriginal(originalPath, 0)
	if !mainBefore.Complete || mainBefore.Document.Blocks[0].Text != "Published introduction." ||
		originalBefore.Document.Blocks[0].Type != "ordered_list" {
		t.Fatal("archived source and published document structure did not differ as expected")
	}
	insert := func(id, text, targetRef, digest string) {
		f.exec(`INSERT INTO canonical_article_link_bindings (canonical_article_id,source_revision_id,canonical_article_revision_id,
			block_id,label_sha256,authored_id_sha256,target_ref_sha256,body_sha256)
			VALUES ($1::uuid,$2::uuid,$3::uuid,$4,$5,$6,$7,$8)`, f.article, sourceRevision, canonicalRevision,
			id, authoredLinkTestHash(text), authoredLinkTestHash(id), authoredLinkTestHash(targetRef), digest)
	}
	insert(blockID, label, ref, bodyHash)
	insert(adjacentBlockID, "Other procedure", adjacentRef, bodyHash)
	insert("absent-block", label, ref, bodyHash)
	insert(bodyMismatchBlockID, "Mismatched body", ref, authoredLinkTestHash("wrong captured body"))
	store := newPostgresCatalogStore(f.pool)
	links := store.retainedArticleLinkBindings(ctx, f.article, &sourceRevision, &canonicalRevision, bodyHash, []byte(sourceDocument))
	if _, found := links[bodyMismatchBlockID]; found || len(links) != 3 {
		t.Fatal("sidecar lookup admitted the wrong body or missed the current revision pair")
	}
	mainWith, originalWith := readMain(1), readOriginal(originalPath, 1)
	if *mainWith.ViewRevision == *mainBefore.ViewRevision || *originalWith.ViewRevision == *originalBefore.ViewRevision {
		t.Fatal("link projection must change each reader view revision")
	}
	if !reflect.DeepEqual(mainBefore.Document, publicCatalogDocument(mainWith.Document)) ||
		!reflect.DeepEqual(originalBefore.Document, publicCatalogDocument(originalWith.Document)) {
		t.Fatal("link projection changed the stored prose, evidence or block order")
	}
	var prepared CatalogArticleResponse
	if err := json.Unmarshal(f.expect(0, "POST", mainPath+"/prepare", "{}", 200), &prepared); err != nil {
		t.Fatal(err)
	}
	assertRetainedPublicLinks(t, prepared.Article.Document, target, 1, 1)
	readOriginal(historicalPath, 0)
	for _, path := range []string{mainPath, originalPath, f.path("/" + target)} {
		f.expect(-1, "GET", path, "", 401)
		f.expect(1, "GET", path, "", 403)
	}
	f.expect(0, "GET", f.path("/"+adjacent), "", 404)
	f.expect(0, "GET", f.path("/"+target+"?region=CA"), "", 404)
	f.exec(`UPDATE canonical_articles SET takedown_status='takedown' WHERE canonical_article_id=$1::uuid`, target)
	readMain(0)
	readOriginal(originalPath, 0)
	f.expect(0, "GET", f.path("/"+target), "", 410)
	f.exec(`UPDATE canonical_articles SET takedown_status='active' WHERE canonical_article_id=$1::uuid`, target)
	f.exec(`UPDATE canonical_articles SET current_canonical_revision_id=NULL WHERE canonical_article_id=$1::uuid`, f.article)
	if readMain(0).Complete {
		t.Fatal("the source-only view was unexpectedly published")
	}
	readOriginal(originalPath, 0)
	if !reflect.DeepEqual(storedBefore, storedDocuments()) {
		t.Fatal("link projection changed the archived source or published document")
	}
	f.exec(`UPDATE entitlements SET status='revoked',revoked_at=now(),revoke_reason='fixture'
	        WHERE commerce_order_id=$1::uuid`, order)
	f.expect(0, "GET", mainPath, "", 403)
	f.expect(0, "GET", originalPath, "", 403)
}

func seedRetainedFixturePublication(f *paidFixture, source, job, canonical, historical, document string) {
	f.t.Helper()
	f.exec(`UPDATE source_fetch_jobs SET transformation_key=$2,phase='completed' WHERE source_fetch_job_id=$1::uuid`, job, authoredLinkTestHash(job))
	f.exec(`INSERT INTO canonical_article_revisions
		(canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,normalization_version,rewrite_profile_version,
		 status,normalized_source_document,normalized_source_hash,canonical_document,canonical_body,canonical_steps,canonical_images,
		 validation_report,validation_hash,rewrite_result_hash,model_metadata,published_at)
		SELECT $1::uuid,j.canonical_article_id,s.source_revision_id,j.transformation_key,j.normalization_version,j.rewrite_profile_version,
		 'published',s.source_document,$3,$4::jsonb,'Published instructions.','[]','[]',
		 '{"passed":true,"changed_slots":["intro"],"evidence_ids":["retained"]}',$3,$3,
		 '{"model":"fixture","profile_version":"technical-prose-v1"}',now()
		FROM canonical_article_source_revisions s JOIN source_fetch_jobs j USING(source_revision_id,canonical_article_id)
		WHERE s.source_revision_id=$2::uuid AND j.source_fetch_job_id=$5::uuid`, canonical, source, authoredLinkTestHash(document), document, job)
	f.exec(`UPDATE canonical_articles SET current_canonical_revision_id=$1::uuid WHERE canonical_article_id=$2::uuid`, canonical, f.article)
	f.exec(`INSERT INTO canonical_article_source_revisions
		(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,
		 source_document,source_images,source_body,source_steps,projection_version,projection_status,evidence_manifest,captured_at)
		SELECT $1::uuid,canonical_article_id,$2,body_source_snapshot_id,resource_manifest,source_document,source_images,
		 source_body,source_steps,projection_version,projection_status,evidence_manifest,captured_at-interval '1 day'
		FROM canonical_article_source_revisions WHERE source_revision_id=$3::uuid`, historical, authoredLinkTestHash(historical), source)
}
