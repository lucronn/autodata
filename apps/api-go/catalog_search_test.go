package main

import (
	"fmt"
	"strings"
	"testing"
)

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
			{Type: "callout", Label: "Warning", Text: "Disconnect battery.", Images: []CatalogImage{{AssetID: "table-distinct", Alt: "VisibleAltMarker", Caption: "VisibleCaptionMarker"}}},
			{Type: "table", Label: "Torque values", Columns: []any{"Fastener"}, Rows: [][]any{{map[string]any{"text": "VisibleCellMarker", "label": "HiddenCellLabelMarker", "images": []any{map[string]any{"asset_id": "cell-duplicate", "alt": "VisibleCellAltMarker"}}}, float64(12)}}, Images: []CatalogImage{{AssetID: "table-distinct", Alt: "TableFigureMarker"}, {AssetID: "cell-duplicate", Alt: "HiddenDuplicateAltMarker"}}},
		}},
	}
	for _, query := range []string{"ground strap", "Warning", "VisibleAltMarker", "VisibleCaptionMarker", "VisibleCellMarker", "VisibleCellAltMarker", "TableFigureMarker", "12"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 1 {
			t.Fatalf("visible query %q did not match", query)
		}
	}
	for _, query := range []string{"HiddenBodyMarker", "HiddenStepLabelMarker", "HiddenParagraphImageMarker", "HiddenCellLabelMarker", "HiddenDuplicateAltMarker", "private-marker"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 0 {
			t.Fatalf("hidden query %q matched", query)
		}
	}
}

func TestPaidCatalogArticleSearchUsesReaderIdentityForStoredFigureCaption(t *testing.T) {
	const digest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	const key = "sources/0123456789abcdef/" + digest
	// HTML capture places the private asset_id and public image_id beside an
	// authored figcaption in the ordered table-cell document.
	document := []byte(fmt.Sprintf(`{"blocks":[{"type":"table","label":"Alignment service data","rows":[[{"blocks":[
		{"type":"image","asset_id":%q,"image_id":%q,"alt":"Gaugeface diagram","caption":"Alignment witness marks","status":"available"}
	]}]]}]}`, key, digest))
	images := []byte(fmt.Sprintf(`[{"asset_id":%q,"image_id":%q,"storage_key":%q,"status":"available"}]`, key, digest, key))
	for _, test := range []struct {
		name         string
		sourceImages []byte
		figure       bool
	}{
		{name: "retained figure", sourceImages: images, figure: true},
		{name: "unproven figure"},
		{name: "unavailable figure", sourceImages: []byte(fmt.Sprintf(`[{"image_id":%q,"storage_key":%q,"status":"unavailable"}]`, digest, key))},
	} {
		t.Run(test.name, func(t *testing.T) {
			projection := paidSearchProjection{document: document, images: images, sourceImages: test.sourceImages}
			for _, query := range []struct {
				text  string
				match bool
			}{
				{text: "Alignment service data", match: true},
				{text: "Alignment service data witness marks", match: test.figure},
				{text: "Gaugeface diagram", match: test.figure},
				{text: key, match: false},
			} {
				matched, err := projection.matchesContent(CatalogArticle{Title: "Pump removal"}, strings.Fields(strings.ToLower(query.text)))
				if err != nil || matched != query.match {
					t.Fatalf("query %q matched %v, want %v (error %v)", query.text, matched, query.match, err)
				}
			}
		})
	}
}

func TestPaidCatalogArticleSearchFindsProvenPathOnlyFigure(t *testing.T) {
	const key = "sources/0123456789abcdef/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	const otherKey = "sources/0123456789abcdef/1123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	document := []byte(fmt.Sprintf(`{"blocks":[{"type":"image","asset_id":%q,"alt":"Gaugeface diagram","caption":"Alignment witness marks","status":"available"}]}`, key))
	image := func(field, asset, objectKey, status string) []byte {
		return []byte(fmt.Sprintf(`[{%q:%q,"storage_key":%q,"status":%q}]`, field, asset, objectKey, status))
	}
	for _, test := range []struct {
		name   string
		field  string
		source []byte
		match  bool
	}{
		{name: "path-only asset_id", field: "asset_id", source: image("asset_id", key, key, "available"), match: true},
		{name: "legacy path-only id", field: "id", source: image("id", key, key, "available"), match: true},
		{name: "different source object", field: "id", source: image("id", key, otherKey, "available")},
		{name: "different source alias", field: "id", source: image("id", otherKey, key, "available")},
		{name: "unavailable source asset", field: "id", source: image("id", key, key, "unavailable")},
		{name: "no source membership", field: "id"},
	} {
		t.Run(test.name, func(t *testing.T) {
			projection := paidSearchProjection{document: document, images: image(test.field, key, key, "available"), sourceImages: test.source}
			for _, query := range [][]string{{"alignment", "witness", "marks"}, {"gaugeface", "diagram"}} {
				matched, err := projection.matchesContent(CatalogArticle{Title: "Pump removal"}, query)
				if err != nil || matched != test.match {
					t.Fatalf("query %q matched %v, want %v (error %v)", query, matched, test.match, err)
				}
			}
			if matched, err := projection.matchesContent(CatalogArticle{Title: "Pump removal"}, []string{key}); err != nil || matched {
				t.Fatalf("private object key became searchable (match %v, error %v)", matched, err)
			}
		})
	}
}

func TestCatalogArticleSearchMatchesRenderedLegacyIntroductionAndSteps(t *testing.T) {
	article := CatalogArticle{
		Title: "Maintenance guide", Kind: "procedure", Body: "Check coolant level.",
		Steps: []CatalogStep{{Action: "Inspect reservoir", Heading: "HiddenHeadingMarker", Instructions: []string{"Top up approved fluid."}}},
	}
	for _, query := range []string{"coolant", "reservoir", "approved fluid", "maintenance procedure"} {
		if len(filterCatalogArticleSearch([]CatalogArticle{article}, query)) != 1 {
			t.Fatalf("legacy query %q did not match", query)
		}
	}
	for _, query := range []string{"HiddenHeadingMarker", "brake"} {
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

func TestPaidCatalogArticleSearchMatchesRetainedMissingAndPendingCaptions(t *testing.T) {
	projection := paidSearchProjection{
		document: []byte(`{"blocks":[
			{"type":"image","asset_id":"private-missing-figure","caption":"Missing standalone caption",
			 "alt":"Hidden missing alt","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"},
			{"type":"image","caption":"Pending standalone caption","alt":"Hidden pending alt",
			 "status":"available","unavailable_reason":"SOURCE_MEDIA_PENDING"},
			{"type":"image","asset_id":"unproven","caption":"Unproven media caption","alt":"Unproven media alt","status":"available"},
			{"type":"image","caption":"Wrong status caption","status":"available","unavailable_reason":"SOURCE_NOT_FOUND"},
			{"type":"image","caption":"Other failure caption","status":"unavailable","unavailable_reason":"UNKNOWN"},
			{"type":"ordered_list","items":[{"images":[
				{"caption":"Pending list caption","alt":"Hidden list alt","status":"unavailable","unavailable_reason":"SOURCE_MEDIA_PENDING"}
			]}]},
			{"type":"table","rows":[[{"caption":"Missing cell caption","alt":"Hidden cell alt","status":"unavailable",
			 "unavailable_reason":"SOURCE_NOT_FOUND"}]],"images":[
				{"asset_id":"table-missing","caption":"Missing table caption","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"}
			]}
		]}`),
		images: []byte(`[{"asset_id":"unproven","storage_key":"procedure-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]`),
	}
	for _, test := range []struct {
		query string
		want  bool
	}{
		{"missing standalone caption", true},
		{"pending standalone caption", true},
		{"pending list caption", true},
		{"missing cell caption", true},
		{"missing table caption", true},
		{"hidden missing alt", false},
		{"hidden pending alt", false},
		{"hidden list alt", false},
		{"hidden cell alt", false},
		{"unproven media", false},
		{"wrong status caption", false},
		{"other failure caption", false},
		{"private-missing-figure", false},
		{"table-missing", false},
		{"source_not_found", false},
		{"source_media_pending", false},
	} {
		matched, err := projection.matchesContent(CatalogArticle{Title: "Pump service"}, strings.Fields(test.query))
		if err != nil || matched != test.want {
			t.Errorf("query %q matched %v, want %v (error %v)", test.query, matched, test.want, err)
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

func TestCatalogArticleSearchLegacyStepImageAcceptsStoredLocalAsset(t *testing.T) {
	images := []CatalogImage{{
		ID: "stored", StorageKey: "procedure-images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		Alt: "StoredLegacyFigureMarker",
	}}
	article := CatalogArticle{Title: "Legacy guide", Steps: []CatalogStep{{Action: "Inspect harness", Images: &images}}}
	if len(filterCatalogArticleSearch([]CatalogArticle{article}, "StoredLegacyFigureMarker")) != 1 {
		t.Fatal("stored local image alt did not match before media URL signing")
	}
}

func TestCatalogArticleSearchMatchesRenderableLegacyStepImageIDs(t *testing.T) {
	article := CatalogArticle{
		Title: "Legacy wiring guide",
		Images: []CatalogImage{
			{ID: "ready", URL: "/v1/catalog/images/v2.ready", Alt: "VisibleConnectorMarker"},
			{ID: "missing-url", Alt: "HiddenConnectorMarker"},
		},
		Steps: []CatalogStep{{Action: "Inspect connector", ImageIDs: []string{"ready", "missing-url"}}},
	}
	if len(filterCatalogArticleSearch([]CatalogArticle{article}, "VisibleConnectorMarker")) != 1 {
		t.Fatal("rendered legacy step image_id alt did not match")
	}
	if len(filterCatalogArticleSearch([]CatalogArticle{article}, "HiddenConnectorMarker")) != 0 {
		t.Fatal("unrenderable legacy step image_id alt matched")
	}
}
