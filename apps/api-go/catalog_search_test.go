package main

import "testing"

func TestCatalogArticleSearchUsesRenderedDocumentNotHiddenCompatibilityFields(t *testing.T) {
	article := CatalogArticle{
		ID: "private-marker", Title: "Service notes", Body: "HiddenBodyMarker",
		Images: []CatalogImage{
			{ID: "table-distinct", URL: "/v1/catalog/images/v2.table-distinct"},
			{ID: "cell-duplicate", URL: "/v1/catalog/images/v2.cell-duplicate"},
		},
		Document: &CatalogDocument{Blocks: []CatalogDocumentBlock{
			{Type: "step", Text: "Inspect ground strap.", Label: "HiddenStepLabelMarker"},
			{Type: "paragraph", Text: "Use approved fastener.", Images: []CatalogImage{{Alt: "HiddenParagraphImageMarker"}}},
			{Type: "callout", Label: "Warning", Text: "Disconnect battery.", Images: []CatalogImage{{AssetID: "table-distinct", Alt: "VisibleAltMarker", Caption: "HiddenCaptionMarker"}}},
			{Type: "table", Label: "Torque values", Columns: []string{"Fastener"}, Rows: [][]any{{map[string]any{"text": "VisibleCellMarker", "label": "HiddenCellLabelMarker", "images": []any{map[string]any{"asset_id": "cell-duplicate", "alt": "VisibleCellAltMarker"}}}, float64(12)}}, Images: []CatalogImage{{AssetID: "table-distinct", Alt: "TableFigureMarker"}, {AssetID: "cell-duplicate", Alt: "HiddenDuplicateAltMarker"}}},
		}},
	}
	for _, query := range []string{"ground strap", "Warning", "VisibleAltMarker", "VisibleCellMarker", "VisibleCellAltMarker", "TableFigureMarker", "12"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 1 {
			t.Fatalf("visible query %q did not match", query)
		}
	}
	for _, query := range []string{"HiddenBodyMarker", "HiddenStepLabelMarker", "HiddenParagraphImageMarker", "HiddenCaptionMarker", "HiddenCellLabelMarker", "HiddenDuplicateAltMarker", "private-marker"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 0 {
			t.Fatalf("hidden query %q matched", query)
		}
	}
}

func TestCatalogArticleSearchMatchesRenderedLegacyStepsBeforeHiddenBody(t *testing.T) {
	article := CatalogArticle{
		Title: "Maintenance guide", Kind: "procedure", Body: "Check coolant level.",
		Steps: []CatalogStep{{Action: "Inspect reservoir", Heading: "HiddenHeadingMarker", Instructions: []string{"Top up approved fluid."}}},
	}
	for _, query := range []string{"reservoir", "approved fluid", "maintenance procedure"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 1 {
			t.Fatalf("legacy query %q did not match", query)
		}
	}
	for _, query := range []string{"coolant", "HiddenHeadingMarker", "brake"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 0 {
			t.Fatalf("hidden or unrelated query %q matched", query)
		}
	}
	article.Steps = []CatalogStep{{Text: "No visible instructions"}}
	if len(filterCatalogArticleSearch([]CatalogArticle{article}, "coolant")) != 1 {
		t.Fatal("body fallback did not match when steps are unusable")
	}
}

func TestCatalogArticleSearchOmitsUnrenderableImageAltText(t *testing.T) {
	article := CatalogArticle{
		Title: "Illustration guide",
		Images: []CatalogImage{
			{ID: "rendered", URL: "/v1/catalog/images/v2.rendered", Status: "available"},
			{ID: "missing-url", Status: "available"},
			{ID: "unavailable", URL: "/v1/catalog/images/v2.unavailable", Status: "unavailable"},
			{ID: "external", URL: "https://provider.example/image.png", Status: "available"},
		},
		Document: &CatalogDocument{Blocks: []CatalogDocumentBlock{
			{Type: "image", AssetID: "rendered", Alt: "RenderedFigureMarker"},
			{Type: "image", AssetID: "missing-url", Alt: "MissingURLFigureMarker"},
			{Type: "image", AssetID: "unavailable", Alt: "UnavailableFigureMarker"},
			{Type: "image", AssetID: "missing-asset", Alt: "MissingAssetFigureMarker"},
			{Type: "callout", Text: "Inspect the connector.", Images: []CatalogImage{{AssetID: "missing-url", Alt: "MissingCalloutMarker"}, {AssetID: "rendered", Alt: "RenderedCalloutMarker"}}},
			{Type: "step", Text: "Verify continuity.", Images: []CatalogImage{{AssetID: "unavailable", Alt: "UnavailableStepMarker"}}},
			{Type: "table", Label: "Measurements", Rows: [][]any{{map[string]any{"text": "Voltage", "images": []any{map[string]any{"asset_id": "external", "alt": "ExternalCellMarker"}, map[string]any{"asset_id": "rendered", "alt": "RenderedCellMarker"}}}}}, Images: []CatalogImage{{AssetID: "missing-url", Alt: "MissingTableMarker"}, {AssetID: "rendered", Alt: "RenderedTableMarker"}}},
		}},
	}
	for _, query := range []string{"RenderedFigureMarker", "RenderedCalloutMarker", "RenderedCellMarker"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 1 {
			t.Errorf("rendered image text %q did not match", query)
		}
	}
	for _, query := range []string{"MissingURLFigureMarker", "UnavailableFigureMarker", "MissingAssetFigureMarker", "MissingCalloutMarker", "UnavailableStepMarker", "ExternalCellMarker", "MissingTableMarker", "RenderedTableMarker"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 0 {
			t.Errorf("unrendered image text %q matched", query)
		}
	}
}

func TestCatalogArticleSearchLegacyStepImageRequiresRenderableURL(t *testing.T) {
	images := []CatalogImage{
		{ID: "ready", URL: "/v1/catalog/images/v2.ready", Alt: "ReadyLegacyFigureMarker"},
		{ID: "missing", Alt: "MissingLegacyFigureMarker"},
	}
	article := CatalogArticle{
		Title: "Legacy guide",
		Steps: []CatalogStep{{Action: "Inspect harness", Images: &images}},
	}
	if len(filterCatalogArticleSearch([]CatalogArticle{article}, "ReadyLegacyFigureMarker")) != 1 {
		t.Fatal("rendered legacy step image alt did not match")
	}
	if len(filterCatalogArticleSearch([]CatalogArticle{article}, "MissingLegacyFigureMarker")) != 0 {
		t.Fatal("unrendered legacy step image alt matched")
	}
}
