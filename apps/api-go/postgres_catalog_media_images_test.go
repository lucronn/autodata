package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"reflect"
	"strings"
	"testing"
	"time"
)

func TestPostgresPaidCatalogSourceImagesReadScope(t *testing.T) {
	f := paidSetup(t)
	order := f.grant(0, f.configuration, "US")
	f.publish()
	previous := f.detail(0)
	if previous.SourceRevisionID == nil || len(previous.Images) == 0 {
		t.Fatal("published figure fixture missing")
	}
	oldRevision := *previous.SourceRevisionID
	f.controlPaid("refresh-source")
	f.control.wait("snapshot", func(s map[string]any) bool {
		return r3Int(r3Map(s, "counts"), "published_revisions") == 2
	})
	current := f.detail(0)
	if current.SourceRevisionID == nil || *current.SourceRevisionID == oldRevision || len(current.Images) == 0 {
		t.Fatal("refreshed source figure fixture missing")
	}
	f.image(0, previous.Images[0].URL, http.StatusNotFound)
	store := newPostgresCatalogStore(f.pool)
	ctx := context.Background()
	for _, revision := range []string{oldRevision, *current.SourceRevisionID} {
		full, err := store.ArticleSourceRevision(ctx, Principal{}, f.configuration, f.article, revision)
		if err != nil {
			t.Fatal(err)
		}
		images, err := store.paidCatalogSourceImages(ctx, f.configuration, f.article, revision)
		if err != nil || len(images) == 0 || !reflect.DeepEqual(full.Images, images) {
			t.Fatal("narrow lookup changed the selected source images", err)
		}
		var fullBytes, imageBytes int
		err = f.pool.QueryRow(ctx, `SELECT
			octet_length(source_document::text) + octet_length(source_body) + octet_length(source_steps::text) + octet_length(source_images::text),
			octet_length(source_images::text)
			FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid`, revision).Scan(&fullBytes, &imageBytes)
		if err != nil || imageBytes <= 0 || fullBytes <= imageBytes {
			t.Fatalf("expected an image-only projection, full=%d images=%d err=%v", fullBytes, imageBytes, err)
		}
		t.Logf("stored source payload fields %d bytes, image-only %d bytes", fullBytes, imageBytes)
	}
	if _, err := store.paidCatalogSourceImages(ctx, f.configuration, f.other, oldRevision); !errors.Is(err, ErrCatalogNotFound) {
		t.Fatal("source image revision was accepted for a different article", err)
	}
	if _, err := store.paidCatalogSourceImages(ctx, f.adjacent, f.article, oldRevision); !errors.Is(err, ErrCatalogNotFound) {
		t.Fatal("source image revision was accepted for a different configuration", err)
	}
	path := f.path("/" + f.article + "/source?source_revision_id=" + oldRevision)
	var historical CatalogSourceContentResponse
	if err := json.Unmarshal(f.expect(0, http.MethodGet, path, "", http.StatusOK), &historical); err != nil ||
		len(historical.Images) == 0 || historical.Images[0].URL == "" {
		t.Fatal("historical source capability fixture missing", err)
	}
	media := historical.Images[0].URL
	f.image(0, media, http.StatusOK)
	reads := f.reader.calls.Load()
	ref, err := openPaidCatalogImageReference(strings.TrimPrefix(media, "/v1/catalog/images/"), f.applications[0].catalogImageKey, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	ref.ObjectKey = "procedure-images/" + strings.Repeat("b", 64)
	f.image(0, f.token(ref, time.Now()), http.StatusNotFound)

	// A blocked historical body suppresses its figure, even while the current
	// article and that figure's own asset snapshot remain approved.
	var quarantine string
	if err := f.pool.QueryRow(ctx, `INSERT INTO source_review_items(item_key,item_kind,reason_code,source_snapshot_ids)
		SELECT gen_random_uuid()::text,'quarantine','FIXTURE',jsonb_build_array(body_source_snapshot_id::text)
		FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid
		RETURNING source_review_item_id::text`, oldRevision).Scan(&quarantine); err != nil {
		t.Fatal(err)
	}
	f.image(0, media, http.StatusNotFound)
	f.exec(`UPDATE source_review_items SET status='approved' WHERE source_review_item_id=$1::uuid`, quarantine)
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=(
		SELECT body_source_snapshot_id FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid)`, *current.SourceRevisionID)
	f.image(0, media, http.StatusGone)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=(
		SELECT body_source_snapshot_id FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid)`, *current.SourceRevisionID)
	f.exec(`UPDATE entitlements SET status='revoked',revoked_at=now(),revoke_reason='fixture' WHERE commerce_order_id=$1::uuid`, order)
	f.image(0, media, http.StatusForbidden)
	if actual := f.reader.calls.Load(); actual != reads {
		t.Fatalf("paid denials reached storage, reads before=%d after=%d", reads, actual)
	}
}
