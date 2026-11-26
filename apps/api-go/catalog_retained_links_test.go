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

func TestCatalogRetainedInlineLinksKeepExactTextAndListPositions(t *testing.T) {
	const target = "11111111-1111-4111-8111-111111111111"
	digest := authoredLinkTestHash("figure removal")
	unresolved := authoredLinkTestHash("uncaptured source")
	raw := []byte(`{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[
		{"type":"paragraph","block_id":"p","text":"Refer to Cover Removal."},
		{"type":"ordered_list","block_id":"list","start":4,"items":["Use Cover Removal now.",{"text":"Cover Removal is next.","number":9},"sCover Removal.","Cover Removal and Cover Removal."]},
		{"type":"paragraph","block_id":"duplicated","text":"Cover Removal"},
		{"type":"paragraph","block_id":"duplicated","text":"Unrelated"},
		{"type":"paragraph","block_id":"u","text":"Read Unavailable Procedure."},
		{"type":"paragraph","text":"Forged link","article_links":[{"label":"Forged","target_article_id":"11111111-1111-4111-8111-111111111111"}]}
	]}`)
	paragraph := retainedCatalogInlineLink{label: "Cover Removal", targetHash: digest, itemIndex: -1}
	fourItems := make([]retainedCatalogInlineLink, 4)
	for i := range fourItems {
		fourItems[i] = paragraph
		fourItems[i].itemIndex = i
	}
	doc := projectCatalogDocument(raw, catalogArticleLinkProjection{
		inline: map[string][]retainedCatalogInlineLink{
			"p": {paragraph}, "list": fourItems, "duplicated": {paragraph},
			"u": {{label: "Unavailable Procedure", targetHash: unresolved, itemIndex: -1}},
		},
		resolve: func(hashes []string) map[string]string {
			if len(hashes) != 2 {
				t.Fatalf("expected one lookup for two target hashes, got %v", hashes)
			}
			return map[string]string{digest: target}
		},
	})
	if doc == nil || doc.Blocks[0].Text != "Refer to Cover Removal." ||
		!reflect.DeepEqual(doc.Blocks[0].ArticleLinks, []CatalogArticleLink{{Label: "Cover Removal", TargetArticleID: target}}) {
		t.Fatal("paragraph link changed the stored wording or failed to resolve")
	}
	assertRetainedPublicLinks(t, doc, target, 3, 3)
	list := doc.Blocks[1]
	if list.Start == nil || *list.Start != 4 || list.Items[0].(map[string]any)["text"] != "Use Cover Removal now." ||
		list.Items[1].(map[string]any)["number"] != float64(9) || list.Items[2] != "sCover Removal." ||
		list.Items[3] != "Cover Removal and Cover Removal." {
		t.Fatal("list text or numbering changed")
	}
}

func TestCatalogCapturedInlineLinksResolveForStoredSource(t *testing.T) {
	const title = "Cover Service"
	const target = "11111111-1111-4111-8111-111111111111"
	identity := authoredLinkTestHash("target")
	raw := []byte(fmt.Sprintf(`{"schema_version":1,"normalization_version":"ordered-article-v1",
		"blocks":[{"block_id":"p","type":"paragraph","text":"Consult Cover Service first."}],
		"authored_inline_article_links":[
			{"block_id":"p","item_index":-1,"label":%[1]q,"label_sha256":%[2]q,"authored_id_sha256":%[3]q,"target_ref_sha256":%[4]q},
			{"block_id":"p","item_index":-1,"label":"Consult","label_sha256":"wrong","authored_id_sha256":%[3]q,"target_ref_sha256":%[4]q}
		]}`, title, authoredLinkTestHash(title), authoredLinkTestHash("authored id"), identity))
	var stored CatalogDocument
	if err := json.Unmarshal(raw, &stored); err != nil {
		t.Fatal(err)
	}
	authorized := projectStoredCatalogDocument(&stored, raw, catalogArticleLinkProjection{
		resolve: func(hashes []string) map[string]string {
			if !reflect.DeepEqual(hashes, []string{identity}) {
				t.Fatalf("wrong scope binding: %v", hashes)
			}
			return map[string]string{identity: target}
		},
	})
	assertRetainedPublicLinks(t, authorized, target, 1, 1)
	links := authorized.Blocks[0].ArticleLinks
	if links[0].Label != title || authorized.Blocks[0].Text != stored.Blocks[0].Text {
		t.Fatal("reader failed to preserve the authored title and surrounding text")
	}
	assertRetainedPublicLinks(t, projectStoredCatalogDocument(&stored, raw, catalogArticleLinkProjection{}), target, 0, 0)
}

func TestPostgresPaidCatalogCapturedInlineArticleLinks(t *testing.T) {
	f := paidSetup(t)
	if f.provider != "bankone" {
		t.Skip("Bankone inline links fixture")
	}
	f.grant(0, f.configuration, "US")
	const title = "Cover Service"
	const ref = "fixture:captured-cover-service"
	target := f.seedAuthoredLinkArticle(f.configuration, "bankone", "", ref)
	f.seedAuthoredLinkSource(target, `{"schema_version":1,"normalization_version":"ordered-article-v1",
		"blocks":[{"type":"paragraph","text":"Stored cover procedure."}]}`)
	source, _ := f.seedAuthoredLinkSource(f.article, fmt.Sprintf(`{"schema_version":1,"normalization_version":"ordered-article-v1",
		"blocks":[{"block_id":"p","type":"paragraph","text":"Consult Cover Service first."}],
		"authored_inline_article_links":[
			{"block_id":"p","item_index":-1,"label":%q,"label_sha256":%q,"authored_id_sha256":%q,"target_ref_sha256":%q}
		]}`, title, authoredLinkTestHash(title), authoredLinkTestHash("authored"), authoredLinkTestHash(ref)))
	path := f.path("/" + f.article)
	raw := f.expect(0, "GET", path, "", 200)
	var view CatalogArticleResponse
	if err := json.Unmarshal(raw, &view); err != nil || view.Article.Document == nil ||
		view.Article.SourceRevisionID == nil || *view.Article.SourceRevisionID != source || view.Article.Complete {
		t.Fatal("expected readable stored source before publication", err)
	}
	assertRetainedPublicLinks(t, view.Article.Document, target, 1, 1)
	if !strings.Contains(string(f.expect(0, "GET", f.path("/"+target), "", 200)), "Stored cover procedure.") {
		t.Fatal("the authorized link did not open stored content")
	}
	f.expect(-1, "GET", path, "", 401)
	f.expect(1, "GET", path, "", 403)
	f.exec(`UPDATE canonical_articles SET takedown_status='takedown' WHERE canonical_article_id=$1::uuid`, target)
	if links := readMainInlineLinks(t, f.expect(0, "GET", path, "", 200)); len(links) != 0 {
		t.Fatal("withdrawn target survived in the readable source document")
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
	pending := f.seedAuthoredLinkArticle(f.configuration, "bankone", "", "fixture:retained-pending")
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
	]}]},{"type":"paragraph","block_id":"inline","text":"See Cover Removal. See Pending Procedure."}`, blockID, label, adjacentBlockID, bodyMismatchBlockID)
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
	links, _ := store.retainedArticleLinkBindings(ctx, f.article, &sourceRevision, &canonicalRevision, bodyHash)
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
	for label, ref := range map[string]string{"Cover Removal": ref, "Pending Procedure": "fixture:retained-pending"} {
		f.exec(`INSERT INTO canonical_article_inline_link_bindings (
			canonical_article_id,source_revision_id,canonical_article_revision_id,
			body_sha256,block_id,item_index,label,label_sha256,authored_id_sha256,target_ref_sha256)
			VALUES ($1::uuid,$2::uuid,$3::uuid,$4,'inline',-1,$5,$6,$7,$8)`,
			f.article, sourceRevision, canonicalRevision, bodyHash, label, authoredLinkTestHash(label),
			authoredLinkTestHash(label+"-source"), authoredLinkTestHash(ref))
	}
	inlineMain, inlineOriginal := readMainInlineLinks(t, f.expect(0, "GET", mainPath, "", 200)),
		readSourceInlineLinks(t, f.expect(0, "GET", originalPath, "", 200))
	wantInline := []CatalogArticleLink{
		{Label: "Cover Removal", TargetArticleID: target}, {Label: "Pending Procedure", TargetArticleID: pending},
	}
	if !reflect.DeepEqual(inlineMain, wantInline) || !reflect.DeepEqual(inlineOriginal, wantInline) {
		t.Fatalf("inline references were not restored in both views: %v, %v", inlineMain, inlineOriginal)
	}
	identity, err := store.PaidArticleIdentity(ctx, f.configuration, f.article)
	if err != nil {
		t.Fatal(err)
	}
	wantReady := map[string]string{authoredLinkTestHash(ref): target}
	resolved := store.authoredArticleLinkResolver(ctx, identity, true)(
		[]string{authoredLinkTestHash(ref), authoredLinkTestHash("fixture:retained-pending")})
	if !reflect.DeepEqual(resolved, wantReady) {
		t.Fatal("public-demo lookup included a pending article")
	}
	f.exec(`DELETE FROM canonical_article_inline_link_bindings WHERE canonical_article_revision_id=$1::uuid`, canonicalRevision)
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

func readMainInlineLinks(t *testing.T, raw []byte) []CatalogArticleLink {
	t.Helper()
	var response CatalogArticleResponse
	if err := json.Unmarshal(raw, &response); err != nil || response.Article.Document == nil {
		t.Fatal("published document absent", err)
	}
	return response.Article.Document.Blocks[len(response.Article.Document.Blocks)-1].ArticleLinks
}

func readSourceInlineLinks(t *testing.T, raw []byte) []CatalogArticleLink {
	t.Helper()
	var response CatalogSourceContentResponse
	if err := json.Unmarshal(raw, &response); err != nil || response.Document == nil {
		t.Fatal("original document absent", err)
	}
	return response.Document.Blocks[len(response.Document.Blocks)-1].ArticleLinks
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
