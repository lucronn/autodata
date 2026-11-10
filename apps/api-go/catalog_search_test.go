package main

import "testing"

func TestCatalogArticleSearchUsesRenderedDocumentNotHiddenCompatibilityFields(t *testing.T) {
	article := CatalogArticle{
		ID: "private-marker", Title: "Service notes", Body: "HiddenBodyMarker",
		Document: &CatalogDocument{Blocks: []CatalogDocumentBlock{
			{Type: "step", Text: "Inspect ground strap.", Label: "HiddenStepLabelMarker"},
			{Type: "paragraph", Text: "Use approved fastener.", Images: []CatalogImage{{Alt: "HiddenParagraphImageMarker"}}},
			{Type: "callout", Label: "Warning", Text: "Disconnect battery.", Images: []CatalogImage{{Alt: "VisibleAltMarker", Caption: "HiddenCaptionMarker"}}},
			{Type: "table", Label: "Torque values", Columns: []string{"Fastener"}, Rows: [][]any{{map[string]any{"text": "VisibleCellMarker", "label": "HiddenCellLabelMarker"}, float64(12)}}},
		}},
	}
	for _, query := range []string{"ground strap", "Warning", "VisibleAltMarker", "VisibleCellMarker", "12"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 1 {
			t.Fatalf("visible query %q did not match", query)
		}
	}
	for _, query := range []string{"HiddenBodyMarker", "HiddenStepLabelMarker", "HiddenParagraphImageMarker", "HiddenCaptionMarker", "HiddenCellLabelMarker", "private-marker"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 0 {
			t.Fatalf("hidden query %q matched", query)
		}
	}
}

func TestCatalogArticleSearchFallsBackToLegacyBodyAndSteps(t *testing.T) {
	article := CatalogArticle{
		Title: "Maintenance guide", Kind: "procedure", Body: "Check coolant level.",
		Steps: []CatalogStep{{Action: "Inspect reservoir", Instructions: []string{"Top up approved fluid."}}},
	}
	for _, query := range []string{"coolant", "reservoir", "approved fluid", "maintenance procedure"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 1 {
			t.Fatalf("legacy query %q did not match", query)
		}
	}
	if len(filterCatalogArticleSearch([]CatalogArticle{article}, "brake")) != 0 {
		t.Fatal("unrelated article matched")
	}
}
