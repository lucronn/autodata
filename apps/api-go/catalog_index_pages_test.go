package main

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"slices"
	"strings"
	"testing"
)

func fillPaidIndexPageFixture(store *paidHTTPStore, count int) []string {
	ids := make([]string, 0, count)
	for index := 1; index <= count; index++ {
		id := fmt.Sprintf("6aaaaaaa-0000-4000-8000-%012x", index)
		store.PutArticle(CatalogArticle{
			ID: id, CanonicalArticleID: stringPointer(id), VehicleID: paidTestConfiguration,
			Title: fmt.Sprintf("Brake procedure %03d", index), Kind: "procedure", Availability: "available",
			Body: "private body", Document: &CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "private document"}}},
			Steps: []CatalogStep{{Action: "private step"}}, Images: []CatalogImage{{URL: "private image"}},
		})
		ids = append(ids, id)
	}
	return ids
}

func callCatalogIndexPage(handler http.Handler, tail, preference, host string) *httptest.ResponseRecorder {
	request := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles?region=CA"+tail, nil)
	if preference != "" {
		request.Header.Add("Prefer", preference)
	}
	if host != "" {
		request.Host = host
	}
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	return response
}

func TestPaidCatalogIndexPagesUseCompleteDescriptorOrder(t *testing.T) {
	server, store, grants := paidHTTPServer()
	grants.err = nil
	store.progress = &CatalogArticleProgress{Complete: true, Status: "completed"}
	ids := fillPaidIndexPageFixture(store, 245)
	store.PutArticle(CatalogArticle{ID: "0-legacy", VehicleID: paidTestConfiguration, Title: "Excluded legacy alias"})
	foreignID := "6bbbbbbb-0000-4000-8000-000000000004"
	store.PutArticle(CatalogArticle{ID: foreignID, CanonicalArticleID: &foreignID, VehicleID: paidTestVehicle, Title: "Different scope"})
	handler := server.Handler()

	revision := ""
	for _, tc := range []struct {
		query       string
		offset, end int
	}{
		{"", 0, 100},
		{"&offset=0", 0, 100},
		{"&offset=100", 100, 200},
		{"&offset=200", 200, 245},
		{"&offset=300", 200, 245},
		{"&offset=9999999999999999999999999900", 200, 245},
		{"&anchor=" + ids[154], 100, 200},
		{"&anchor=" + ids[244], 200, 245},
		{"&anchor=" + foreignID, 0, 100},
	} {
		t.Run(tc.query, func(t *testing.T) {
			response := callCatalogIndexPage(handler, tc.query, "unrelated, "+catalogIndexPagesPreference, "")
			var body CatalogArticlesResponse
			if response.Code != http.StatusOK || json.Unmarshal(response.Body.Bytes(), &body) != nil || body.Page == nil {
				t.Fatalf("expected a paged success for %q, status=%d", tc.query, response.Code)
			}
			if response.Header().Get("Cache-Control") != "private, no-store" ||
				!slices.Contains(response.Header().Values("Preference-Applied"), catalogIndexPagesPreference) {
				t.Fatal("paged response lacks the expected private cache policy or preference")
			}
			if body.Page.Offset != tc.offset || body.Page.Total != len(ids) || len(body.Items) != tc.end-tc.offset {
				t.Fatalf("unexpected page coordinates %+v, rows=%d", body.Page, len(body.Items))
			}
			if revision == "" {
				digest, err := hex.DecodeString(body.Page.Revision)
				if err != nil || len(digest) != 32 || strings.ToLower(body.Page.Revision) != body.Page.Revision {
					t.Fatal("expected a lowercase SHA-256 index revision")
				}
				revision = body.Page.Revision
			} else if body.Page.Revision != revision {
				t.Fatal("different pages of the same ordered descriptors have different revisions")
			}
			for index, article := range body.Items {
				if article.ID != ids[tc.offset+index] || article.CanonicalArticleID == nil || *article.CanonicalArticleID != article.ID ||
					article.Body != "" || article.Document != nil || len(article.Steps) != 0 || len(article.Images) != 0 ||
					article.SourceReview != nil || article.OriginalSourceReview != nil {
					t.Fatal("page reordered, omitted, or returned content-bearing descriptors")
				}
			}
		})
	}

	fetchFirst := func() CatalogArticlesResponse {
		t.Helper()
		response := callCatalogIndexPage(handler, "", catalogIndexPagesPreference, "")
		var body CatalogArticlesResponse
		if response.Code != http.StatusOK || json.Unmarshal(response.Body.Bytes(), &body) != nil || body.Page == nil {
			t.Fatal("expected a first page")
		}
		return body
	}
	// Edits to non-index data cannot change the digest. A visible change on
	// another page, and a change to authorized membership, both must.
	store.mu.Lock()
	later := store.articles[ids[244]]
	later.Body = "different private body"
	store.articles[later.ID] = later
	store.mu.Unlock()
	if got := fetchFirst().Page.Revision; got != revision {
		t.Fatal("body-only mutation changed the index digest")
	}
	store.mu.Lock()
	later.Title = "New title in the final page"
	store.articles[later.ID] = later
	store.mu.Unlock()
	changed := fetchFirst().Page.Revision
	if changed == revision {
		t.Fatal("visible descriptor edit on another page did not change the revision")
	}
	store.mu.Lock()
	delete(store.articles, ids[244])
	store.mu.Unlock()
	if got := fetchFirst().Page; got.Revision == changed || got.Total != 244 {
		t.Fatal("index revision did not track a change to the authorized descriptors")
	}
}

func TestCatalogIndexPagesValidateOnlyOptedInBoundaries(t *testing.T) {
	server, store, grants := paidHTTPServer()
	grants.err = nil
	store.progress = &CatalogArticleProgress{Complete: true, Status: "completed"}
	ids := fillPaidIndexPageFixture(store, 130)
	handler := server.Handler()
	for _, query := range []string{
		"&offset=", "&offset=1", "&offset=-100", "&offset=%2B100", "&offset=0100", "&offset=100.0",
		"&offset=1e2", "&offset=100%20", "&offset=100&offset=100",
		"&anchor=", "&anchor=legacy", "&anchor=" + strings.ToUpper(ids[0]), "&anchor=" + ids[0] + "&anchor=" + ids[0],
		"&offset=100&anchor=" + ids[0], "&offset=0&q=", "&offset=0&title=Brake", "&anchor=" + ids[0] + "&q=Brake",
	} {
		t.Run(query, func(t *testing.T) {
			before := store.protected
			response := callCatalogIndexPage(handler, query, catalogIndexPagesPreference, "")
			if response.Code != http.StatusUnprocessableEntity || store.protected != before ||
				!strings.Contains(response.Body.String(), "INVALID_REQUEST") || strings.Contains(response.Body.String(), `"page"`) {
				t.Fatalf("invalid opted-in boundary reached the index, status=%d", response.Code)
			}
		})
	}
	for _, preference := range []string{"", "workshop-index-pages-extra", "workshop-index-pages=true"} {
		response := callCatalogIndexPage(handler, "&offset=legacy&anchor=ignored", preference, "")
		var body CatalogArticlesResponse
		if response.Code != http.StatusOK || json.Unmarshal(response.Body.Bytes(), &body) != nil || body.Page != nil || len(body.Items) != len(ids) {
			t.Fatal("legacy request changed its handling of unknown parameters")
		}
	}
	// Access checks run on every page, including a malformed or foreign cursor.
	grants.err = ErrVehicleGrantRevoked
	before := store.protected
	response := callCatalogIndexPage(handler, "&offset=bad", catalogIndexPagesPreference, "")
	if response.Code != http.StatusForbidden || store.protected != before ||
		response.Header().Get("Cache-Control") != "private, no-store" || response.Header().Get("Preference-Applied") != "" {
		t.Fatal("a revoked owner reached pagination before the current grant check")
	}
	server.auth.(*fakeAuthenticator).err = ErrUnauthenticated
	response = callCatalogIndexPage(handler, "&anchor="+ids[124], catalogIndexPagesPreference, "")
	if response.Code != http.StatusUnauthorized || store.protected != before || response.Header().Get("Preference-Applied") != "" {
		t.Fatal("unauthenticated anchor reached pagination")
	}
}

func TestCatalogIndexPagesPreserveOtherIndexShapes(t *testing.T) {
	for _, tc := range []struct {
		name, query  string
		progress     *CatalogArticleProgress
		count, want  int
		demo, legacy bool
		paged        bool
	}{
		{name: "terminal failed", progress: &CatalogArticleProgress{Status: "failed"}, count: 130, want: 30, paged: true, query: "&offset=100"},
		{name: "retrying", progress: &CatalogArticleProgress{Status: "failed", Retryable: true}, count: 130, want: 130, query: "&offset=100"},
		{name: "running", progress: &CatalogArticleProgress{Status: "running"}, count: 130, want: 130},
		{name: "pending", progress: &CatalogArticleProgress{Status: "pending"}, count: 130, want: 130},
		{name: "missing", count: 130, want: 130},
		{name: "exactly 100", progress: &CatalogArticleProgress{Complete: true}, count: 100, want: 100},
		{name: "demo", demo: true, progress: &CatalogArticleProgress{Complete: true}, count: 130, want: 130, query: "&demo=1&offset=100"},
		{name: "legacy", legacy: true, progress: &CatalogArticleProgress{Complete: true}, count: 130, want: 130, query: "&offset=100"},
		{name: "query", progress: &CatalogArticleProgress{Complete: true}, count: 130, want: 130, query: "&q=Brake"},
		{name: "empty query", progress: &CatalogArticleProgress{Complete: true}, count: 130, want: 130, query: "&q="},
		{name: "title", progress: &CatalogArticleProgress{Complete: true}, count: 130, want: 1, query: "&title=" + url.QueryEscape("Brake procedure 006")},
	} {
		t.Run(tc.name, func(t *testing.T) {
			server, store, grants := paidHTTPServer()
			store.progress, grants.err = tc.progress, nil
			fillPaidIndexPageFixture(store, tc.count)
			host := ""
			if tc.demo {
				host = "localhost:3013"
				server.workshopOpenDemoHost = host
			}
			if tc.legacy {
				server.customerAuth = nil
				server.auth.(*fakeAuthenticator).principal.Roles = []string{"dataset_viewer"}
			}
			response := callCatalogIndexPage(server.Handler(), tc.query, catalogIndexPagesPreference, host)
			var body CatalogArticlesResponse
			if response.Code != http.StatusOK || json.Unmarshal(response.Body.Bytes(), &body) != nil ||
				(body.Page != nil) != tc.paged || len(body.Items) != tc.want ||
				slices.Contains(response.Header().Values("Preference-Applied"), catalogIndexPagesPreference) != tc.paged {
				t.Fatalf("wrong index shape: status=%d, items=%d, page=%+v", response.Code, len(body.Items), body.Page)
			}
			if tc.paged && (body.Hydrating || body.Complete || body.Page.Total != tc.count || body.Page.Offset != 100) {
				t.Fatal("paging changed settled failed progress or its page bounds")
			}
		})
	}
}
