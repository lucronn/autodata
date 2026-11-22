package main

import (
	"context"
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

func TestCatalogArticleActiveReadRetryAfter(t *testing.T) {
	retryDelay := 9
	for _, test := range []struct {
		name, state string
		origin      string
		delay       *int
		status      int
		header      string
	}{
		{"cold queued", "queued", "", nil, 202, "1"},
		{"cold fetch", "fetching_source", "", nil, 202, "1"},
		{"stored source awaiting first publication", "rewriting", "source", nil, 200, "1"},
		{"published article during refresh", "rewriting", "canonical", nil, 200, "2"},
		{"explicit source delay", "rewriting", "source", &retryDelay, 200, "9"},
		{"explicit failed retry", "failed", "", &retryDelay, 202, "9"},
		{"review required", "needs_review", "source", nil, 200, ""},
	} {
		t.Run(test.name, func(t *testing.T) {
			store := newMemoryCatalogStore()
			article := CatalogArticle{
				ID: "a", VehicleID: "v", CanonicalArticleID: stringPointer("a"), Title: "Pump",
				Availability: "pending", Processing: &CatalogProcessing{
					JobID: "job", State: test.state, RetryAfterSeconds: test.delay, Retryable: test.state == "failed",
				},
			}
			if test.origin != "" {
				article.Availability = "available"
				article.ContentOrigin = stringPointer(test.origin)
				article.Document = &CatalogDocument{
					SchemaVersion: 1, NormalizationVersion: "ordered-article-v1",
					Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "Remove pump."}},
				}
			}
			store.PutArticle(article)
			response := catalogRequest(catalogServer(store), "/v1/catalog/vehicles/v/articles/a")
			if response.Code != test.status || response.Header().Get("Retry-After") != test.header {
				t.Fatalf("status=%d retry=%q, want status=%d retry=%q",
					response.Code, response.Header().Get("Retry-After"), test.status, test.header)
			}
		})
	}
}

func TestCatalogPrepareShortSourceCheckPreference(t *testing.T) {
	one, nine := 1, 9
	for _, tc := range []struct {
		name, method, state string
		prefer              bool
		delay               *int
		want                string
	}{
		{"queued prepare", http.MethodPost, "queued", true, nil, ""},
		{"fetching prepare", http.MethodPost, "fetching_source", true, nil, ""},
		{"older client", http.MethodPost, "queued", false, nil, "1"},
		{"short detail check", http.MethodGet, "queued", true, nil, ""},
		{"normal detail retrieval", http.MethodGet, "queued", false, nil, "1"},
		{"explicit short delay", http.MethodPost, "queued", true, &one, "1"},
		{"explicit failure delay", http.MethodPost, "failed", true, &nine, "9"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			article := lifecycleArticle(CatalogArticle{
				ID: "article", Availability: "pending", Processing: &CatalogProcessing{
					JobID: "job", State: tc.state, Retryable: tc.state == "failed", RetryAfterSeconds: tc.delay,
				},
			})
			request := httptest.NewRequest(tc.method, "/v1/catalog/vehicles/v/articles/article", nil)
			if tc.prefer {
				request.Header.Set("Prefer", shortSourceCheckPreference)
			}
			response := httptest.NewRecorder()
			catalogServer(newMemoryCatalogStore()).respondCatalogArticleView(response, request, Principal{}, CatalogArticleView{Article: article})
			if response.Code != http.StatusAccepted || response.Header().Get("Retry-After") != tc.want {
				t.Fatalf("accepted response had status %d and retry %q, want retry %q", response.Code, response.Header().Get("Retry-After"), tc.want)
			}
			var result CatalogArticleResponse
			if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil || result.Article.Processing == nil {
				t.Fatalf("unreadable processing response: %v", err)
			}
			applied := response.Header().Get("Preference-Applied") == shortSourceCheckPreference
			if applied != (tc.want == "") || (result.Article.Processing.RetryAfterSeconds == nil) != applied {
				t.Fatal("preference acknowledgment and retry delay disagree")
			}
		})
	}
}

func TestCatalogShortPublicationCheckPreference(t *testing.T) {
	explicit := 1
	for _, tc := range []struct {
		name, origin, state, preference string
		delay                           *int
		wantRetry, wantApplied          string
	}{
		{"normalizing", "source", "normalizing", shortPublicationCheckPreference, nil, "", shortPublicationCheckPreference},
		{"rewriting", "source", "rewriting", shortSourceCheckPreference + ", " + shortPublicationCheckPreference, nil, "", shortPublicationCheckPreference},
		{"publishing", "source", "publishing", shortPublicationCheckPreference, nil, "", shortPublicationCheckPreference},
		{"older reader", "source", "rewriting", shortSourceCheckPreference, nil, "1", ""},
		{"explicit delay", "source", "rewriting", shortPublicationCheckPreference, &explicit, "1", ""},
		{"refresh", "canonical", "rewriting", shortPublicationCheckPreference, nil, "2", ""},
		{"waiting in queue", "source", "queued", shortPublicationCheckPreference, nil, "1", ""},
		{"review", "source", "needs_review", shortPublicationCheckPreference, nil, "", ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			article := lifecycleArticle(CatalogArticle{
				ID: "article", CanonicalArticleID: stringPointer("article"), Availability: "available",
				ContentOrigin: stringPointer(tc.origin),
				Document:      &CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "Remove pump."}}},
				Processing:    &CatalogProcessing{JobID: "job", State: tc.state, RetryAfterSeconds: tc.delay},
			})
			request := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/v/articles/article", nil)
			request.Header.Set("Prefer", tc.preference)
			response := httptest.NewRecorder()
			catalogServer(newMemoryCatalogStore()).respondCatalogArticleView(response, request, Principal{}, CatalogArticleView{Article: article})
			retry := response.Header().Get("Retry-After")
			applied := response.Header().Get("Preference-Applied")
			if response.Code != http.StatusOK || retry != tc.wantRetry || applied != tc.wantApplied {
				t.Fatalf("status=%d retry=%q applied=%q", response.Code, retry, applied)
			}
			var result CatalogArticleResponse
			if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil || result.Article.Processing == nil {
				t.Fatalf("unreadable processing response: %v", err)
			}
			if delay := result.Article.Processing.RetryAfterSeconds; (delay != nil) != (retry != "") {
				t.Fatalf("Retry-After and article processing disagree: %q / %v", retry, delay)
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
	doc := &CatalogDocument{SchemaVersion: 1, NormalizationVersion: "ordered-article-v1", Blocks: []CatalogDocumentBlock{{BlockID: "warning", Type: "warning", Label: "Warning", Text: "Disconnect <battery>."}, {BlockID: "table", Type: "table", Columns: []any{"Torque", "Diagram"}, Rows: [][]any{{"10 N·m", map[string]any{"text": "Pump", "asset_id": "missing"}}}}, {BlockID: "unknown", Type: "unknown", Text: "Retained unknown block"}}}
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

func TestCatalogOrderedSourceKeepsUnavailableChartCaptionInTable(t *testing.T) {
	var doc CatalogDocument
	if err := json.Unmarshal([]byte(`{"blocks":[{"type":"table","columns":[{"blocks":[
		{"type":"paragraph","text":"Check the pressure scale."},
		{"type":"image","asset_id":"chart","caption":"Pressure at <2,000> rpm & warm","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"},
		{"type":"paragraph","text":"Read the upper line."}
	]},{"asset_id":"inline","caption":"Inline figure caption","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"}],
		"rows":[["Supply",{"asset_id":"no-caption","alt":"Alt only","caption":"","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"}],
				["Draft",{"asset_id":"denied","caption":"Unproved caption","status":"unavailable"}]],
		"images":[{"asset_id":"chart","caption":"Pressure at <2,000> rpm & warm","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"},
			{"asset_id":"chart","caption":"Apply the outlet correction at altitude.","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"},
			{"asset_id":"inline","caption":"Inline figure caption","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"},
			{"asset_id":"no-caption","status":"unavailable","unavailable_reason":"SOURCE_NOT_FOUND"}]},
		{"type":"paragraph","text":"Continue after the table."}]}`), &doc); err != nil {
		t.Fatal(err)
	}
	content := renderCatalogOrderedSource(&doc, []CatalogImage{
		{AssetID: "chart", Status: "available", URL: "/v1/catalog/images/v2.chart"},
		{AssetID: "no-caption", Status: "available", URL: "/v1/catalog/images/v2.no-caption"},
		{AssetID: "denied", Status: "available", URL: "/v1/catalog/images/v2.denied"},
	})
	figure := "<figure><span>Image unavailable</span><figcaption>Pressure at &lt;2,000&gt; rpm &amp; warm</figcaption></figure>"
	before := strings.Index(content, "Check the pressure scale.")
	media := strings.Index(content, figure)
	after := strings.Index(content, "Read the upper line.")
	if before < 0 || media <= before || after <= media || strings.Count(content, figure) != 1 {
		t.Fatalf("unavailable image caption lost its ordered position: %s", content)
	}
	detachedFigure := "<figure><span>Image unavailable</span><figcaption>Apply the outlet correction at altitude.</figcaption></figure>"
	if !strings.Contains(content, "</table>"+detachedFigure+"</section>") {
		t.Fatalf("distinct unavailable caption lost its position after the table: %s", content)
	}
	if strings.Count(content, "Image unavailable") != 5 || strings.Count(content, "<figcaption>") != 3 ||
		!strings.Contains(content, "<figcaption>Inline figure caption</figcaption>") ||
		strings.Contains(content, "<img") || strings.Contains(content, "Alt only") || strings.Contains(content, "Unproved caption") {
		t.Fatalf("duplicate or unauthorized figure content: %s", content)
	}
}

func TestCatalogLifecycleConsumesR2StepsAndProjectsNestedImages(t *testing.T) {
	var step CatalogStep
	if err := json.Unmarshal([]byte(`{"number":3,"text":"Disconnect the battery.","evidence_ids":["evidence-1"]}`), &step); err != nil {
		t.Fatal(err)
	}
	if len(step.Instructions) != 1 || step.Instructions[0] != "Disconnect the battery." {
		t.Fatalf("R2 step prose lost: %#v", step)
	}
}
func TestCatalogLifecycleProjectsNestedImages(t *testing.T) {
	var article CatalogArticle
	key := "sources/" + strings.Repeat("a", 16) + "/" + strings.Repeat("a", 64)
	raw := `{"id":"a","vehicle_id":"v","document":{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[{"type":"table","rows":[[{"text":"Pump","images":[{"asset_id":"` + key + `","image_id":"` + strings.Repeat("a", 64) + `","storage_key":"` + key + `","url":"https://provider.invalid/private","status":"available"}]}]]}]}}`
	if err := json.Unmarshal([]byte(raw), &article); err != nil {
		t.Fatal(err)
	}
	article = lifecycleArticle(article)
	encoded, _ := json.Marshal(article)
	if strings.Contains(string(encoded), "storage_key") || strings.Contains(string(encoded), "sources/") || strings.Contains(string(encoded), "provider.invalid") {
		t.Fatalf("nested image leaked private locator: %s", encoded)
	}
	content := renderCatalogOrderedSource(article.Document, nil)
	if !strings.Contains(content, "Image unavailable") {
		t.Fatalf("nested image position lost: %s", content)
	}
}

func TestCatalogSourceOrderedStepNumbers(t *testing.T) {
	rendered := renderCatalogOrderedSource(&CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "step", Number: 3, Text: "Remove pump."}}}, nil)
	if !strings.Contains(rendered, `<ol start="3"><li>Remove pump.</li></ol>`) {
		t.Fatalf("stored step number lost: %s", rendered)
	}
}

func TestCatalogLifecyclePersistedEmptyImagesSurviveHTTP(t *testing.T) {
	var persisted CatalogArticle
	if err := json.Unmarshal([]byte(`{"id":"a","vehicle_id":"v","canonical_article_id":"a","source_revision_id":"s","content_origin":"source","availability":"available","document":{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[{"type":"ordered_list","items":["Remove the pump."]}]},"body":"Remove the pump.","steps":[{"number":1,"text":"Remove the pump.","evidence_ids":["e"]}],"images":[]}`), &persisted); err != nil {
		t.Fatal(err)
	}
	store := newMemoryCatalogStore()
	store.PutArticle(persisted)
	response := catalogRequest(catalogServer(store), "/v1/catalog/vehicles/v/articles/a")
	if response.Code != 200 {
		t.Fatal(response.Code, response.Body.String())
	}
	var decoded CatalogArticleResponse
	if err := json.Unmarshal(response.Body.Bytes(), &decoded); err != nil {
		t.Fatal(err)
	}
	if decoded.Article.Images == nil {
		t.Fatalf("persisted empty image array lost over HTTP: %s", response.Body)
	}
	want, _ := json.Marshal(r3Projection(lifecycleArticle(persisted)))
	got, _ := json.Marshal(r3Projection(decoded.Article))
	if string(want) != string(got) {
		t.Fatalf("PG/public projection differs: want=%s got=%s", want, got)
	}
}

func TestCatalogLifecyclePendingAndLegacyImagesAreArrays(t *testing.T) {
	for _, pending := range []bool{true, false} {
		article := CatalogArticle{ID: "a", VehicleID: "v", Body: "Legacy source"}
		wantStatus := 200
		if pending {
			article.Body = ""
			article.CanonicalArticleID = stringPointer("a")
			article.Processing = &CatalogProcessing{JobID: "j", State: "queued"}
			wantStatus = 202
		}
		store := newMemoryCatalogStore()
		store.PutArticle(article)
		response := catalogRequest(catalogServer(store), "/v1/catalog/vehicles/v/articles/a")
		var envelope map[string]any
		if err := json.Unmarshal(response.Body.Bytes(), &envelope); err != nil {
			t.Fatal(err)
		}
		if response.Code != wantStatus {
			t.Fatal(response.Code, response.Body.String())
		}
		wireArticle := envelope["article"].(map[string]any)
		images, ok := wireArticle["images"].([]any)
		if !ok || len(images) != 0 {
			t.Fatalf("pending=%v images must be []: %s", pending, response.Body)
		}
	}
}

type descriptorOnlyCatalogStore struct {
	CatalogStore
	detailReads int
}

func (s *descriptorOnlyCatalogStore) ArticleView(context.Context, Principal, string, string) (CatalogArticleView, error) {
	s.detailReads++
	return CatalogArticleView{}, ErrCatalogNotFound
}
func (s *descriptorOnlyCatalogStore) Article(context.Context, Principal, string, string) (CatalogArticle, error) {
	s.detailReads++
	return CatalogArticle{}, ErrCatalogNotFound
}
func (s *descriptorOnlyCatalogStore) ArticleSource(context.Context, Principal, string, string) (CatalogSourceContent, error) {
	s.detailReads++
	return CatalogSourceContent{}, ErrCatalogNotFound
}
func (s *descriptorOnlyCatalogStore) ArticleSourceRevision(context.Context, Principal, string, string, string) (CatalogSourceContent, error) {
	s.detailReads++
	return CatalogSourceContent{}, ErrCatalogNotFound
}
func (s *descriptorOnlyCatalogStore) CatalogArticleProgress(context.Context, Principal, string) (*CatalogArticleProgress, error) {
	return &CatalogArticleProgress{Status: "complete", Complete: true}, nil
}
func TestCatalogDescriptorListImagesAreArraysWithoutDetailWork(t *testing.T) {
	memory := newMemoryCatalogStore()
	memory.PutArticle(CatalogArticle{ID: "canonical", VehicleID: "v", CanonicalArticleID: stringPointer("canonical"), Title: "Managed descriptor"})
	memory.PutArticle(CatalogArticle{ID: "legacy", VehicleID: "v", Title: "Legacy descriptor"})
	store := &descriptorOnlyCatalogStore{CatalogStore: memory}
	client := &fakeIngestionClient{status: 503}
	server := catalogServer(store)
	server.ingestionClient = client
	response := catalogRequest(server, "/v1/catalog/vehicles/v/articles")
	if response.Code != 200 {
		t.Fatal(response.Code, response.Body.String())
	}
	var envelope struct {
		Items []map[string]any `json:"items"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &envelope); err != nil {
		t.Fatal(err)
	}
	if len(envelope.Items) != 2 {
		t.Fatal(response.Body.String())
	}
	for _, item := range envelope.Items {
		images, ok := item["images"].([]any)
		if !ok || len(images) != 0 {
			t.Fatalf("descriptor %v images must be []: %s", item["id"], response.Body)
		}
		for _, field := range []string{"body", "document", "steps"} {
			if _, ok := item[field]; ok {
				t.Fatalf("descriptor loaded %s: %s", field, response.Body)
			}
		}
	}
	if store.detailReads != 0 || client.path != "" {
		t.Fatalf("list performed source/model detail work: reads=%d ingestion=%s", store.detailReads, client.path)
	}
}

func TestCatalogCanonicalR2StepPreservesActualCompatibilityShape(t *testing.T) {
	for _, raw := range []string{
		`{"action":"Take off the pump.","instructions":[],"images":[],"evidence_ids":["e1","e2"]}`,
		`{"action":"Take off the pump.","instructions":[],"evidence_ids":["e1"]}`,
		`{"number":0,"action":"Take off the pump.","instructions":[],"evidence_ids":["e1"]}`,
		`{"number":-2,"action":"Take off the pump.","instructions":[],"evidence_ids":["e1"]}`,
		`{"action":"Take off the pump.","text":"Additional source context.","instructions":[],"images":[],"evidence_ids":["e1"]}`,
		`{"number":7,"action":"Take off the pump.","instructions":["Keep the seal.","Inspect the bracket."],"images":[],"evidence_ids":["e2","e1"]}`,
	} {
		var step CatalogStep
		if err := json.Unmarshal([]byte(raw), &step); err != nil {
			t.Fatal(err)
		}
		encoded, err := json.Marshal(step)
		if err != nil {
			t.Fatal(err)
		}
		var actual, expected map[string]any
		json.Unmarshal(encoded, &actual)
		json.Unmarshal([]byte(raw), &expected)
		if len(actual) != len(expected) {
			t.Fatalf("canonical step fields lost or fabricated: expected=%s actual=%s", raw, encoded)
		}
		for key, want := range expected {
			got, _ := json.Marshal(actual[key])
			required, _ := json.Marshal(want)
			if string(got) != string(required) {
				t.Fatalf("canonical %s changed: expected=%s actual=%s", key, raw, encoded)
			}
		}
	}
}

func TestCatalogCanonicalStepImagesUseSafeLocalReferences(t *testing.T) {
	key := "sources/" + strings.Repeat("a", 16) + "/" + strings.Repeat("a", 64)
	raw := `{"action":"Inspect pump.","instructions":["Keep the seal."],"images":[{"image_id":"` + strings.Repeat("a", 64) + `","storage_key":"` + key + `","url":"https://provider.invalid/private","alt":"Seal","media_type":"image/png","status":"available"}],"evidence_ids":["e"]}`
	var step CatalogStep
	if err := json.Unmarshal([]byte(raw), &step); err != nil {
		t.Fatal(err)
	}
	article := CatalogArticle{Steps: []CatalogStep{step}}
	rewriteCatalogImageURLs(&article, deriveCatalogImageReferenceKey("r3-step-fixture-only-media-key-1234567890"))
	encoded, _ := json.Marshal(article.Steps)
	if strings.Contains(string(encoded), "storage_key") || strings.Contains(string(encoded), "sources/") || strings.Contains(string(encoded), "provider.invalid") {
		t.Fatalf("step image leaked private source: %s", encoded)
	}
	var projected []map[string]any
	json.Unmarshal(encoded, &projected)
	images, ok := projected[0]["images"].([]any)
	if !ok || len(images) != 1 {
		t.Fatalf("step image position lost: %s", encoded)
	}
	image := images[0].(map[string]any)
	url, _ := image["url"].(string)
	if image["image_id"] != strings.Repeat("a", 64) || image["alt"] != "Seal" || !strings.HasPrefix(url, "/v1/catalog/images/") {
		t.Fatalf("step image reference changed: %s", encoded)
	}
}

func TestCatalogCanonicalStepImageURLsDoNotChangeViewRevision(t *testing.T) {
	images := []CatalogImage{{ImageID: "figure-1", URL: "first-local-url", StorageKey: "first-private-key", Alt: "Seal"}}
	article := CatalogArticle{CanonicalArticleID: stringPointer("a"), SourceRevisionID: stringPointer("s"), CanonicalRevisionID: stringPointer("c"), ContentOrigin: stringPointer("canonical"), Document: &CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "Inspect pump."}}}, Steps: []CatalogStep{{Action: "Inspect pump.", Instructions: []string{}, Images: &images}}}
	first := lifecycleArticle(article)
	images[0].URL = "second-local-url"
	images[0].StorageKey = "second-private-key"
	second := lifecycleArticle(article)
	if first.ViewRevision == nil || second.ViewRevision == nil || *first.ViewRevision != *second.ViewRevision {
		t.Fatal("step image transport reference changed view identity")
	}
	images[0].Alt = "Bracket"
	changed := lifecycleArticle(article)
	if *changed.ViewRevision == *first.ViewRevision {
		t.Fatal("step image content did not change view identity")
	}
}

func TestCatalogOrderedListsKeepNumberingInPaidDocumentAndHTML(t *testing.T) {
	raw := []byte(`{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[
		{"type":"ordered_list","start":0,"items":["Remove",{"text":"Inspect","number":-3,
			"blocks":[{"type":"ordered_list","start":-2147483648,"items":[{"text":"Nested","number":2147483647}]}]},
			"Fit",{"text":"Zero","number":0},{"text":"Fraction","number":1.5},
			{"text":"Out of range","number":2147483648},{"text":"String ordinal","number":"9"}]},
		{"type":"ordered_list","items":["Legacy sequence"]},
		{"type":"unordered_list","start":6,"items":[{"text":"Bullet","number":8}]},
		{"type":"ordered_list","start":2147483648,"items":["Invalid start"]}
	]}`)
	var stored CatalogDocument
	if err := json.Unmarshal(raw, &stored); err != nil {
		t.Fatal(err)
	}
	public := publicCatalogDocument(&stored)
	if public == nil {
		t.Fatal("public document is missing")
	}
	dto, err := json.Marshal(public)
	if err != nil {
		t.Fatal(err)
	}
	for _, field := range []string{`"start":0`, `"number":0`, `"number":-3`, `"start":-2147483648`, `"number":2147483647`} {
		if !strings.Contains(string(dto), field) {
			t.Errorf("public document missing %s: %s", field, dto)
		}
	}
	html := renderCatalogOrderedSource(public, nil)
	for _, part := range []string{
		`<ol start="0"><li>Remove</li><li value="-3">Inspect`,
		`<ol start="-2147483648"><li value="2147483647">Nested</li></ol>`,
		`<li>Fit</li><li value="0">Zero</li><li>Fraction</li><li>Out of range</li><li>String ordinal</li>`,
		`<ol><li>Legacy sequence</li></ol>`, `<ul><li>Bullet</li></ul>`, `<ol><li>Invalid start</li></ol>`,
	} {
		if !strings.Contains(html, part) {
			t.Errorf("source HTML missing %s: %s", part, html)
		}
	}
}

func TestCatalogOrderedSourceKeepsStructuredListsAndTableCells(t *testing.T) {
	raw := []byte(`{
		"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[
			{"type":"unordered_list","items":["Legacy item",{"text":"Inspect before proceeding",
				"images":[{"asset_id":"list-diagram","alt":"Inspect","caption":"List detail"}],
				"blocks":[{"type":"ordered_list","items":["Nested operation"]}]}]},
			{"type":"table","caption":"Table title","columns":[{"text":"Diagram"}],
				"rows":[{"cells":[{"text":"Cell detail","blocks":[{"type":"image","asset_id":"cell-diagram","alt":"View","caption":"Cell view"},
					{"type":"paragraph","text":"Nested cell instruction"}]}]}],
				"images":[{"asset_id":"cell-diagram","caption":"Summary description"}]},
			{"type":"link","text":"Related manual","href":"https://provider.invalid/private.pdf"}
		]}`)
	var doc CatalogDocument
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("could not decode a valid structured article: %v", err)
	}
	doc = *publicCatalogDocument(&doc)
	encoded, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(encoded), "provider.invalid") || !strings.Contains(string(encoded), "Nested cell instruction") {
		t.Fatalf("public document must retain nested content and omit private URLs: %s", encoded)
	}
	html := renderCatalogOrderedSource(&doc, []CatalogImage{
		{ID: "list-diagram", URL: "/v1/catalog/images/v2.list"},
		{ID: "cell-diagram", URL: "/v1/catalog/images/v2.cell"},
	})
	for _, part := range []string{
		"<ul><li>Legacy item</li>", "<ol><li>Nested operation</li></ol>",
		"<figcaption>List detail</figcaption>", "<caption>Table title</caption>",
		"<th scope=\"col\">Diagram</th>", "<figcaption>Cell view</figcaption>",
		"<p>Nested cell instruction</p>", "Related manual",
	} {
		if !strings.Contains(html, part) {
			t.Errorf("stored source is missing %q: %s", part, html)
		}
	}
	if strings.Count(html, "/v1/catalog/images/v2.cell") != 1 || strings.Contains(html, "Summary description") ||
		strings.Contains(html, "provider.invalid") || strings.Contains(html, "href=") {
		t.Fatalf("cell media must remain in place and provider link stay inert: %s", html)
	}
}
