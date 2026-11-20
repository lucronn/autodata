package main

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestPostgresPaidCatalogRetainedMediaPublication(t *testing.T) {
	f := paidSetup(t)
	f.grant(0, f.configuration, "US")
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
	oldImage := f.expect(0, "GET", previous.Images[0].URL, "", 200)
	beforeSource := pinnedSource()
	oldHistoricalImage := f.expect(0, "GET", beforeSource.Images[0].URL, "", 200)
	if !bytes.Equal(oldImage, oldHistoricalImage) ||
		!bytes.HasPrefix(oldImage, []byte("\x89PNG\r\n\x1a\n")) {
		t.Fatal("localized PNG bytes differ before repair")
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
	f.check("replacement_uses_same_retained_png", bytes.Equal(
		f.expect(0, "GET", current.Images[0].URL, "", 200), oldImage,
	))

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
	f.check("historical_new_capability_reads_same_png", bytes.Equal(
		f.expect(0, "GET", historical.Images[0].URL, "", 200), oldImage,
	))
	reads = f.reader.calls.Load()
	f.expect(1, "GET", sourcePath, "", 403)
	f.image(1, current.Images[0].URL, 404)
	f.image(1, historical.Images[0].URL, 404)
	f.check("scope_denials_before_storage", f.reader.calls.Load() == reads)
}
