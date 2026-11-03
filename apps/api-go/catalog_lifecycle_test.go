package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCatalogDetailLifecycle(t *testing.T) {
	for _, tc := range []struct {
		name, state string
		want        int
	}{{"accepted", "queued", 202}, {"review required", "needs_review", 409}} {
		t.Run(tc.name, func(t *testing.T) {
			store := newMemoryCatalogStore()
			var article CatalogArticle
			err := json.Unmarshal([]byte(`{"id":"article-1","vehicle_id":"vehicle-1","title":"Pump","canonical_article_id":"article-1","availability":"pending","complete":false,"content_status":"list_only","processing":{"job_id":"job-1","state":"`+tc.state+`","retryable":false,"retry_after_seconds":2}}`), &article)
			if err != nil {
				t.Fatal(err)
			}
			store.PutArticle(article)
			server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)
			response := httptest.NewRecorder()
			server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/vehicle-1/articles/article-1", nil))
			if response.Code != tc.want {
				t.Fatalf("status=%d want=%d body=%s", response.Code, tc.want, response.Body)
			}
			if response.Header().Get("Cache-Control") != "private, no-store" {
				t.Fatal("detail lifecycle must not cache")
			}
		})
	}
}

func TestCatalogLifecycleReadableSourceIgnoresWorkerOutage(t *testing.T) {
	for _, state := range []string{"rewriting", "failed", "needs_review"} {
		t.Run(state, func(t *testing.T) {
			store := newMemoryCatalogStore()
			a := CatalogArticle{ID: "a", VehicleID: "v", Title: "Pump", CanonicalArticleID: stringPointer("a"), SourceRevisionID: stringPointer("s"), ContentOrigin: stringPointer("source"), Availability: "available", ContentStatus: "content_partial", Body: "Remove pump.", Document: &CatalogDocument{SchemaVersion: 1, NormalizationVersion: "ordered-article-v1", Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "Remove pump."}}}, Processing: &CatalogProcessing{JobID: "job", State: state}}
			store.PutArticle(a)
			server := catalogServer(store)
			server.ingestionClient = &fakeIngestionClient{status: 503}
			response := catalogRequest(server, "/v1/catalog/vehicles/v/articles/a")
			if response.Code != 200 {
				t.Fatalf("readable source lost: %d %s", response.Code, response.Body)
			}
			var body CatalogArticleResponse
			json.Unmarshal(response.Body.Bytes(), &body)
			if body.Article.Complete || body.Article.CanonicalRevisionID != nil || !r3Origin(body.Article, "source") {
				t.Fatal("source falsely complete")
			}
		})
	}
}
func TestCatalogSchedulingAcknowledgmentCannotInventJob(t *testing.T) {
	store := newMemoryCatalogStore()
	store.PutArticle(CatalogArticle{ID: "a", VehicleID: "v", Title: "Pump", CanonicalArticleID: stringPointer("a"), Availability: "unavailable"})
	server := catalogServer(store)
	server.ingestionClient = &fakeIngestionClient{status: 202}
	response := catalogRequest(server, "/v1/catalog/vehicles/v/articles/a")
	if response.Code != 503 {
		t.Fatalf("unobservable acceptance must fail: %d %s", response.Code, response.Body)
	}
}
func TestCatalogLifecycleViewRevisionIgnoresProcessingAndURLs(t *testing.T) {
	a := CatalogArticle{ID: "a", VehicleID: "v", CanonicalArticleID: stringPointer("a"), SourceRevisionID: stringPointer("s"), ContentOrigin: stringPointer("source"), Document: &CatalogDocument{SchemaVersion: 1, NormalizationVersion: "ordered-article-v1", Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "Pump"}}}, Images: []CatalogImage{{ID: "asset", URL: "/v1/catalog/images/first"}}, Processing: &CatalogProcessing{JobID: "job", State: "rewriting", UpdatedAt: "first"}}
	before := lifecycleArticle(a)
	a.Images[0].URL = "/v1/catalog/images/second"
	a.Processing.State = "validating"
	a.Processing.UpdatedAt = "second"
	after := lifecycleArticle(a)
	if *before.ViewRevision != *after.ViewRevision {
		t.Fatal("processing or token rotation changed immutable view")
	}
	a.SourceRevisionID = stringPointer("new-source")
	if *lifecycleArticle(a).ViewRevision == *before.ViewRevision {
		t.Fatal("new source did not change view")
	}
}
func TestCatalogSourceOrderedTablesWarningsAndUnavailableMedia(t *testing.T) {
	doc := &CatalogDocument{SchemaVersion: 1, NormalizationVersion: "ordered-article-v1", Blocks: []CatalogDocumentBlock{{BlockID: "warning", Type: "warning", Label: "Warning", Text: "Disconnect <battery>."}, {BlockID: "table", Type: "table", Columns: []string{"Torque", "Diagram"}, Rows: [][]any{{"10 N·m", map[string]any{"text": "Pump", "asset_id": "missing"}}}}, {BlockID: "unknown", Type: "unknown", Text: "Retained unknown block"}}}
	rendered := renderCatalogOrderedSource(doc, nil)
	for _, text := range []string{"Warning", "Disconnect &lt;battery&gt;.", "<table>", "10 N·m", "Image unavailable", "Retained unknown block"} {
		if !strings.Contains(rendered, text) {
			t.Fatalf("lost ordered content %q: %s", text, rendered)
		}
	}
	sanitized, err := sanitizeCatalogSourceHTML(`<p data-secret="hidden" onclick="bad()">Text</p><video src="https://external.invalid/video"></video><img src="https://external.invalid/image"><table><tr><td>Value</td></tr></table>`, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(sanitized, "external.invalid") || strings.Contains(sanitized, "data-secret") || strings.Contains(sanitized, "onclick") {
		t.Fatal("active external surface leaked")
	}
	if !strings.Contains(sanitized, "Image unavailable") || !strings.Contains(sanitized, "<table>") {
		t.Fatal(sanitized)
	}
}
