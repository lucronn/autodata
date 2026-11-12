package main

import (
	"fmt"
	"testing"
)

type paidSearchProjectionRow struct {
	document     []byte
	images       []byte
	sourceImages []byte
}

func (row paidSearchProjectionRow) Scan(dest ...any) error {
	if len(dest) != 14 {
		return fmt.Errorf("paid search projection scanned %d columns, want 14", len(dest))
	}
	*dest[0].(*string) = "00000000-0000-0000-0000-000000000111"
	*dest[1].(*string) = "Torque guide"
	*dest[9].(*[]byte) = row.document
	*dest[12].(*[]byte) = row.images
	*dest[13].(*[]byte) = row.sourceImages
	return nil
}

func TestPaidSearchProjectionResolvesVisibleTableImageWithoutReturningContent(t *testing.T) {
	const key = "procedure-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	row := paidSearchProjectionRow{
		document:     []byte(`{"schema_version":1,"blocks":[{"type":"table","label":"Torque values","rows":[["12 Nm"]],"images":[{"asset_id":"figure-1","alt":"Distinct mount view"}]}]}`),
		images:       []byte(`[{"id":"figure-1","storage_key":"` + key + `"}]`),
		sourceImages: []byte(`[{"id":"figure-1","storage_key":"` + key + `"}]`),
	}
	article, matched, err := scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", "Distinct mount view")
	if err != nil || !matched {
		t.Fatalf("visible table image was not matched by paid projection: matched=%t err=%v", matched, err)
	}
	if article.Document != nil || article.Body != "" || len(article.Steps) != 0 || len(article.Images) != 0 {
		t.Fatal("paid search returned content instead of a metadata-only descriptor")
	}
	if article.VehicleID != "00000000-0000-0000-0000-000000000222" || article.CanonicalArticleID == nil || *article.CanonicalArticleID != article.ID {
		t.Fatal("paid search descriptor lost canonical identity or configuration scope")
	}
	row.sourceImages = []byte(`[]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", "Distinct mount view"); err != nil || matched {
		t.Fatalf("image absent from selected source matched: matched=%t err=%v", matched, err)
	}
	row.sourceImages = []byte(`[{"id":"figure-1","storage_key":"` + key + `","status":"unavailable"}]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", "Distinct mount view"); err != nil || matched {
		t.Fatalf("unavailable selected source image matched: matched=%t err=%v", matched, err)
	}
	row.sourceImages = []byte(`[{"id":"figure-1","storage_key":"procedure-images/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", "Distinct mount view"); err != nil || matched {
		t.Fatalf("mismatched selected source asset matched: matched=%t err=%v", matched, err)
	}
	row.sourceImages = []byte(`[{"id":"figure-1","storage_key":"` + key + `"}]`)
	row.images = []byte(`[{"id":"figure-1","storage_key":"` + key + `","status":"unavailable"}]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", "Distinct mount view"); err != nil || matched {
		t.Fatalf("unavailable selected projection image matched: matched=%t err=%v", matched, err)
	}
	row.images = []byte(`[]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", "Distinct mount view"); err != nil || matched {
		t.Fatalf("unresolvable table image alt matched: matched=%t err=%v", matched, err)
	}
}
