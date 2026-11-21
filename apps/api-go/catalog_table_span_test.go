package main

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestPublicCatalogTableSpansSurviveOrderedSourceRendering(t *testing.T) {
	var input CatalogDocument
	raw := `{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[{
		"type":"table","block_id":"torques","columns":[{"text":"Connection","colspan":2},"Torque"],
		"rows":[[{"text":"Pump housing","rowspan":2,"images":[{"image_id":"diagram","alt":"Housing diagram","storage_key":"private/source"}]},"Upper bolt","25 Nm"],
			["Lower bolt","12 Nm"],
			[{"text":"Drain bolt","rowspan":1.5,"colspan":1001},{"text":"10 Nm","rowspan":"2\" onclick=\"unsafe","colspan":true}]],
		"images":[{"image_id":"diagram"}]
	}]}`
	if err := json.Unmarshal([]byte(raw), &input); err != nil {
		t.Fatal(err)
	}
	document := publicCatalogDocument(&input)
	if document == nil {
		t.Fatal("public table missing")
	}
	public, err := json.Marshal(document)
	if err != nil {
		t.Fatal(err)
	}
	for _, bad := range []string{"storage_key", "private/source", "onclick", "1001", "1.5"} {
		if strings.Contains(string(public), bad) {
			t.Fatalf("unsafe span or locator %q in projection", bad)
		}
	}
	if strings.Count(string(public), `"rowspan":2`) != 1 || strings.Count(string(public), `"colspan":2`) != 1 {
		t.Fatal("authored spans were not retained in the public table")
	}
	html := renderCatalogOrderedSource(document, []CatalogImage{{ImageID: "diagram", URL: "/v1/catalog/images/v2.fixture", Status: "available"}})
	if !strings.Contains(html, `<th scope="col" colspan="2">Connection</th><th scope="col">Torque</th>`) ||
		!strings.Contains(html, `<td rowspan="2">Pump housing<figure>`) ||
		!strings.Contains(html, `<tr><td>Lower bolt</td><td>12 Nm</td></tr>`) ||
		strings.Count(html, `<img `) != 1 {
		t.Fatalf("ordered table lost spans or duplicated its figure: %s", html)
	}
}
