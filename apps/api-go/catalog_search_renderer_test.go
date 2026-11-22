package main

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// The same independently authored examples are rendered by the actual Workshop
// harness. Neither suite derives its expected terms from the other implementation.
func TestCatalogSearchCurrentRendererParity(t *testing.T) {
	raw, err := os.ReadFile("testdata/workshop-search-renderer.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Name       string         `json:"name"`
		Article    CatalogArticle `json:"article"`
		Visible    []string       `json:"visible_queries"`
		Accessible []string       `json:"accessible_queries"`
		Hidden     []string       `json:"hidden_queries"`
		Once       []string       `json:"once"`
	}
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	for _, item := range cases {
		t.Run(item.Name, func(t *testing.T) {
			for _, query := range append(item.Visible, item.Accessible...) {
				if len(filterCatalogArticleSearch([]CatalogArticle{item.Article}, query)) != 1 {
					t.Errorf("visible term %q did not match", query)
				}
			}
			for _, query := range item.Hidden {
				if len(filterCatalogArticleSearch([]CatalogArticle{item.Article}, query)) != 0 {
					t.Errorf("hidden term %q matched", query)
				}
			}
			text := catalogArticleSearchText(item.Article, false)
			for _, phrase := range item.Once {
				if n := strings.Count(text, phrase); n != 1 {
					t.Errorf("displayed phrase %q appeared %d times, want once", phrase, n)
				}
			}
		})
	}
}

func TestCatalogSearchPaidOpaqueImageURLRemainsExcluded(t *testing.T) {
	article := CatalogArticle{Images: []CatalogImage{{ID: "figure", URL: "/v1/catalog/images/" + strings.Repeat("AbCd0123_-", 15), Alt: "OpaquePaidMarker"}}, Steps: []CatalogStep{{Action: "Inspect", ImageIDs: []string{"figure"}}}}
	if len(filterCatalogArticleSearch([]CatalogArticle{article}, "OpaquePaidMarker")) != 0 {
		t.Fatal("local-only opaque URL became searchable through the paid projection")
	}
}
