package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"
)

func TestPostgresPaidCatalogRetainedMediaPublication(t *testing.T) {
	f := paidSetup(t)
	order := f.grant(0, f.configuration, "US")
	mediaType := os.Getenv("AUTODATA_PAID_TEST_FIGURE_MEDIA_TYPE")
	switch mediaType {
	case "image/png", "image/jpeg", "image/gif", "image/webp":
	default:
		t.Fatal("fixture requires a supported raster content type")
	}
	wantDigest, err := hex.DecodeString(os.Getenv("AUTODATA_PAID_TEST_FIGURE_SHA256"))
	if err != nil || len(wantDigest) != sha256.Size {
		t.Fatal("fixture requires the provider figure SHA-256")
	}
	readFigure := func(path string) []byte {
		t.Helper()
		status, raw, headers := f.call(0, "GET", path, "")
		if status != 200 || headers.Get("Content-Type") != mediaType {
			t.Fatalf("retained figure returned status %d, media type %q; want status 200, media type %q",
				status, headers.Get("Content-Type"), mediaType)
		}
		return raw
	}
	previous := f.detail(0)
	if previous.SourceRevisionID == nil || previous.CanonicalRevisionID == nil ||
		previous.ReviewStatus == nil || *previous.ReviewStatus != "APPROVED" ||
		previous.Document == nil || len(previous.Document.Blocks) != 4 ||
		previous.Document.Blocks[3].Type != "image" || len(previous.Images) != 1 {
		t.Fatal("approved historical figure fixture missing")
	}
	sourcePath := f.path("/" + f.article + "/source?source_revision_id=" + *previous.SourceRevisionID)
	pinnedSource := func() CatalogSourceContentResponse {
		t.Helper()
		var source CatalogSourceContentResponse
		if err := json.Unmarshal(f.expect(0, "GET", sourcePath, "", 200), &source); err != nil ||
			source.Source.URL != sourcePath || len(source.Images) != 1 ||
			source.Images[0].URL == "" || source.Document == nil ||
			len(source.Document.Blocks) != 3 || source.Document.Blocks[2].Type != "image" {
			t.Fatal("pinned source did not retain the historical layout")
		}
		return source
	}
	oldImage := readFigure(previous.Images[0].URL)
	beforeSource := pinnedSource()
	oldHistoricalImage := readFigure(beforeSource.Images[0].URL)
	digest := sha256.Sum256(oldImage)
	if !bytes.Equal(digest[:], wantDigest) || !bytes.Equal(oldImage, oldHistoricalImage) {
		t.Fatal("localized figure bytes differ from the provider fixture before repair")
	}
	f.check("warm_owned_media_read", f.reader.calls.Load() == 2)

	f.controlPaid("publish-retained-media")
	reads := f.reader.calls.Load()
	f.image(0, previous.Images[0].URL, 404)
	f.image(0, beforeSource.Images[0].URL, 404)
	f.check("both_old_capabilities_denied_before_storage", f.reader.calls.Load() == reads)

	current := f.detail(0)
	if current.SourceRevisionID == nil || current.CanonicalRevisionID == nil ||
		current.ReviewStatus == nil || *current.ReviewStatus != "APPROVED" ||
		*current.SourceRevisionID == *previous.SourceRevisionID ||
		*current.CanonicalRevisionID == *previous.CanonicalRevisionID ||
		current.ViewRevision == nil || previous.ViewRevision == nil ||
		*current.ViewRevision == *previous.ViewRevision ||
		current.Document == nil || len(current.Document.Blocks) != 4 ||
		current.Document.Blocks[2].Type != "image" || len(current.Images) != 1 {
		t.Fatal("published repair did not move the approved figure to the expected position")
	}
	textBlocks := func(a CatalogArticle) []byte {
		t.Helper()
		var blocks []CatalogDocumentBlock
		for _, block := range a.Document.Blocks {
			if block.Type != "image" {
				// The new projection generates position-dependent IDs and source order.
				block.BlockID = ""
				block.SourceOrder = 0
				blocks = append(blocks, block)
			}
		}
		encoded, err := json.Marshal(blocks)
		if err != nil {
			t.Fatal(err)
		}
		return encoded
	}
	f.check("approved_prose_and_review_preserved", bytes.Equal(textBlocks(previous), textBlocks(current)))
	f.check("replacement_uses_same_retained_figure", bytes.Equal(readFigure(current.Images[0].URL), oldImage))

	historical := pinnedSource()
	beforeJSON, err := json.Marshal(beforeSource.Document)
	if err != nil {
		t.Fatal(err)
	}
	afterJSON, err := json.Marshal(historical.Document)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(beforeJSON, afterJSON) ||
		historical.Source.SnapshotID != beforeSource.Source.SnapshotID ||
		historical.Source.ContentSHA256 != beforeSource.Source.ContentSHA256 {
		t.Fatal("historical source bytes or metadata changed")
	}
	reference, err := openPaidCatalogImageReference(
		strings.TrimPrefix(historical.Images[0].URL, "/v1/catalog/images/"),
		f.applications[0].catalogImageKey, time.Now(),
	)
	f.check("historical_asset_pins_old_source_and_new_anchors", err == nil &&
		reference.Projection == "source" &&
		reference.SelectedSourceRevisionID == *previous.SourceRevisionID &&
		reference.AnchorSourceRevisionID == *current.SourceRevisionID &&
		reference.AnchorCanonicalRevisionID != nil &&
		*reference.AnchorCanonicalRevisionID == *current.CanonicalRevisionID)
	f.check("historical_new_capability_reads_same_figure", bytes.Equal(readFigure(historical.Images[0].URL), oldImage))
	reads = f.reader.calls.Load()
	f.expect(1, "GET", sourcePath, "", 403)
	f.image(1, current.Images[0].URL, 404)
	f.image(1, historical.Images[0].URL, 404)
	f.check("scope_denials_before_storage", f.reader.calls.Load() == reads)

	f.exec(`UPDATE entitlements SET status='revoked',revoked_at=now(),revoke_reason='fixture' WHERE commerce_order_id=$1::uuid`, order)
	f.image(0, current.Images[0].URL, 403)
	f.image(0, historical.Images[0].URL, 403)
	f.check("revoked_grant_denies_both_capabilities_before_storage", f.reader.calls.Load() == reads)
}
