package main

import (
	"fmt"
	"testing"
)

type paidSearchProjectionRow struct {
	document     []byte
	body         string
	steps        []byte
	images       []byte
	sourceImages []byte
	original     []byte
}

func (row paidSearchProjectionRow) Scan(dest ...any) error {
	if len(dest) != 16 {
		return fmt.Errorf("paid search projection scanned %d columns, want 16", len(dest))
	}
	*dest[0].(*string) = "00000000-0000-0000-0000-000000000111"
	*dest[1].(*string) = "Torque guide"
	*dest[9].(*[]byte) = row.document
	*dest[10].(*string) = row.body
	*dest[11].(*[]byte) = row.steps
	*dest[12].(*[]byte) = row.images
	*dest[13].(*[]byte) = row.sourceImages
	*dest[15].(*[]byte) = row.original
	return nil
}

func TestPaidSearchCurrentOriginalMatchesWithoutReturningItsContent(t *testing.T) {
	row := paidSearchProjectionRow{
		document: []byte(`{"schema_version":1,"blocks":[{"type":"paragraph","text":"Take off the cover"}]}`),
		original: []byte(`{"schema_version":1,"blocks":[{"type":"paragraph","text":"Remove the cover"}]}`),
	}
	const configurationID = "00000000-0000-0000-0000-000000000222"
	for _, test := range []struct {
		words []string
		want  bool
	}{
		{[]string{"remove", "cover"}, true},
		{[]string{"take", "cover"}, true},
		{[]string{"take", "remove"}, false},
	} {
		article, matched, err := scanPaidArticleSearchRow(row, configurationID, test.words)
		if err != nil || matched != test.want || article.Document != nil || article.Body != "" || len(article.Images) != 0 {
			t.Fatalf("query %v matched=%t err=%v", test.words, matched, err)
		}
	}
	row.original = []byte(`{`)
	if _, matched, err := scanPaidArticleSearchRow(row, configurationID, []string{"remove"}); err != nil || matched {
		t.Fatalf("unreadable Original matched=%t err=%v", matched, err)
	}
}

func TestPaidSearchProjectionResolvesVisibleTableImageWithoutReturningContent(t *testing.T) {
	const key = "procedure-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	row := paidSearchProjectionRow{
		document:     []byte(`{"schema_version":1,"blocks":[{"type":"table","label":"Torque values","rows":[["12 Nm"]],"images":[{"asset_id":"figure-1","alt":"Distinct mount view"}]}]}`),
		images:       []byte(`[{"id":"figure-1","storage_key":"` + key + `"}]`),
		sourceImages: []byte(`[{"id":"figure-1","storage_key":"` + key + `"}]`),
	}
	words := []string{"distinct", "mount", "view"}
	article, matched, err := scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", words)
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
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", words); err != nil || matched {
		t.Fatalf("image absent from selected source matched: matched=%t err=%v", matched, err)
	}
	row.sourceImages = []byte(`[{"id":"figure-1","storage_key":"` + key + `","status":"unavailable"}]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", words); err != nil || matched {
		t.Fatalf("unavailable selected source image matched: matched=%t err=%v", matched, err)
	}
	row.sourceImages = []byte(`[{"id":"figure-1","storage_key":"procedure-images/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", words); err != nil || matched {
		t.Fatalf("mismatched selected source asset matched: matched=%t err=%v", matched, err)
	}
	row.sourceImages = []byte(`[{"id":"figure-1","storage_key":"` + key + `"}]`)
	row.images = []byte(`[{"id":"figure-1","storage_key":"` + key + `","status":"unavailable"}]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", words); err != nil || matched {
		t.Fatalf("unavailable selected projection image matched: matched=%t err=%v", matched, err)
	}
	row.images = []byte(`[]`)
	if _, matched, err = scanPaidArticleSearchRow(row, "00000000-0000-0000-0000-000000000222", words); err != nil || matched {
		t.Fatalf("unresolvable table image alt matched: matched=%t err=%v", matched, err)
	}
}

func TestPaidSearchOrderedDocumentKeepsStepFigureAndExcludesCompatibilityProse(t *testing.T) {
	const key = "procedure-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	const configurationID = "00000000-0000-0000-0000-000000000222"
	row := paidSearchProjectionRow{
		document:     []byte(`{"schema_version":1,"blocks":[{"type":"image","image_id":"step-figure","alt":"Retention clip"},{"type":"step","text":"Inspect the harness"}]}`),
		body:         "Check the relief spring.",
		steps:        []byte(`[{"action":"Inspect the legacy bushing","images":[{"image_id":"step-figure","storage_key":"` + key + `","alt":"Reference diagram"}]}]`),
		sourceImages: []byte(`[{"image_id":"step-figure","storage_key":"` + key + `"}]`),
	}
	for _, test := range []struct {
		words   []string
		matched bool
	}{
		{[]string{"torque", "guide"}, true},
		{[]string{"torque", "retention", "clip"}, true},
		{[]string{"torque", "harness"}, true},
		{[]string{"relief", "spring"}, false},
		{[]string{"legacy", "bushing"}, false},
	} {
		if article, matched, err := scanPaidArticleSearchRow(row, configurationID, test.words); err != nil || matched != test.matched || article.Document != nil || article.Body != "" {
			t.Fatalf("ordered query %v matched=%t err=%v", test.words, matched, err)
		}
	}
	row.document = []byte(`{"schema_version":1,"blocks":[]}`)
	for _, words := range [][]string{{"relief", "spring"}, {"legacy", "bushing"}, {"reference", "diagram"}} {
		if _, matched, err := scanPaidArticleSearchRow(row, configurationID, words); err != nil || !matched {
			t.Fatalf("legacy query %v matched=%t err=%v", words, matched, err)
		}
	}
}
