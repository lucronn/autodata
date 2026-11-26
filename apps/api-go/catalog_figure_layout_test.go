package main

import (
	"strings"
	"testing"
)

func TestCatalogFigureLabelsAreProjectedAndEscaped(t *testing.T) {
	const definition = `{"width":500,"height":250,"labels":[{"left":250,"top":10,"font_size":16,"lines":["A","<marker>"]}]}`
	document := func(layout string) *CatalogDocument {
		return projectCatalogDocument([]byte(`{"schema_version":1,"blocks":[{"type":"image","asset_id":"test-image","figure_layout":`+layout+`}]}`),
			catalogArticleLinkProjection{})
	}
	valid := document(definition)
	block := valid.Blocks[0]
	if block.FigureLayout == nil || block.FigureLayout.Labels[0].Lines[1] != "<marker>" {
		t.Fatalf("layout not retained: %+v", block.FigureLayout)
	}
	html := renderCatalogOrderedSource(valid, []CatalogImage{
		{AssetID: block.AssetID, URL: "/v1/catalog/images/test-image"},
	})
	for _, text := range []string{`style="position:relative;container-type:inline-size`, `left:50.000000%;top:4.000000%;`,
		"A\n&lt;marker&gt;", `src="/v1/catalog/images/test-image"`} {
		if !strings.Contains(html, text) {
			t.Errorf("missing source figure markup %q in %s", text, html)
		}
	}
	for _, invalid := range []string{
		strings.Replace(definition, "\"left\":250", "\"left\":501", 1),
		strings.Replace(definition, "\"top\":10", "\"top\":\"20%;display:none\"", 1),
		strings.Replace(definition, "\"left\":250", "\"left\":250,\"url\":\"https://provider.invalid\"", 1),
	} {
		projected := document(invalid)
		if projected == nil || projected.Blocks[0].FigureLayout != nil {
			t.Errorf("unreadable source or invalid geometry was included: %s", invalid)
		}
	}
}
