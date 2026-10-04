package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func catalogFixtureStore() *memoryCatalogStore {
	store := newMemoryCatalogStore()
	store.PutConfiguration(CatalogConfiguration{
		ID: "cfg-1", VehicleID: "vehicle-1", Year: 2024, Make: "Acme", Model: "Roadster",
		Region: "US", Trim: "Sport", Engine: "2.0L", Complete: true,
	})
	store.PutArticle(CatalogArticle{
		ID: "article-1", VehicleID: "vehicle-1", Title: "Replace filter", Kind: "procedure",
		ContentStatus: "content_complete", Complete: true,
		Steps: []CatalogStep{{Number: 2, Heading: "Install", Instructions: []string{"B"}}, {Number: 1, Heading: "Remove", Instructions: []string{"A"}}},
		Images: []CatalogImage{
			{ID: "image-1", URL: "/v1/catalog/images/local.png", Alt: "Filter location", StorageKey: "private/source-object/key"},
			{ID: "image-2", URL: "https://autoapitwo.vercel.app/diagram.png", Alt: "Filter wiring", StorageKey: "procedure-images/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
		},
		SourceOriginal: json.RawMessage(`{"provider":"opaque","steps":[{"n":2},{"n":1}]}`),
		Provenance:     []CatalogProvenance{{ID: "source-1", Version: "v1"}},
	})
	return store
}

func catalogServer(store CatalogStore) *Server {
	return NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{
		principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}},
	}, newMemoryRequestStore(), store)
}

func catalogRequest(server *Server, path string) *httptest.ResponseRecorder {
	request := httptest.NewRequest(http.MethodGet, path, nil)
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	return response
}

func TestCatalogYearsAreVersionedAndProviderNeutral(t *testing.T) {
	response := catalogRequest(catalogServer(catalogFixtureStore()), "/v1/catalog/years")
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d: %s", response.Code, http.StatusOK, response.Body.String())
	}
	var body CatalogYearsResponse
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body.Version != "v1" || len(body.Items) != 1 || body.Items[0].Year != 2024 {
		t.Fatalf("body = %#v", body)
	}
	if strings.Contains(response.Body.String(), "provider") || strings.Contains(response.Body.String(), "source_uri") {
		t.Fatalf("provider-shaped fields leaked: %s", response.Body.String())
	}
}

func TestCatalogCascadeReturnsMakesModelsAndConfigurations(t *testing.T) {
	server := catalogServer(catalogFixtureStore())
	for path, want := range map[string]string{
		"/v1/catalog/years/2024/makes":                                     "Acme",
		"/v1/catalog/years/2024/makes/acme/models":                         "Roadster",
		"/v1/catalog/years/2024/makes/acme/models/roadster/configurations": "cfg-1",
	} {
		response := catalogRequest(server, path)
		if response.Code != http.StatusOK {
			t.Fatalf("%s status = %d, want %d: %s", path, response.Code, http.StatusOK, response.Body.String())
		}
		if !strings.Contains(response.Body.String(), want) {
			t.Fatalf("%s body = %s, want %q", path, response.Body.String(), want)
		}
	}
}

func TestCatalogMakesDeduplicateProviderLabelVariants(t *testing.T) {
	store := newMemoryCatalogStore()
	store.PutConfiguration(CatalogConfiguration{ID: "gmc-1", Year: 1999, Make: "Gmc", Model: "Sierra", Region: "US"})
	store.PutConfiguration(CatalogConfiguration{ID: "gmc-2", Year: 1999, Make: "GMC", Model: "Sierra", Region: "US"})

	makes, err := store.Makes(nil, Principal{}, 1999, "")
	if err != nil {
		t.Fatal(err)
	}
	if len(makes) != 1 || makes[0].ID != "gmc" || makes[0].Name != "GMC" {
		t.Fatalf("makes = %#v, want one canonical GMC entry", makes)
	}
}

func TestCatalogArticleDetailKeepsSourceOrderAndHidesOriginal(t *testing.T) {
	t.Setenv("AUTODATA_IMAGE_URL_KEY", testCatalogImageSecret)
	response := catalogRequest(catalogServer(catalogFixtureStore()), "/v1/catalog/vehicles/vehicle-1/articles/article-1")
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d: %s", response.Code, http.StatusOK, response.Body.String())
	}
	var body CatalogArticleResponse
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body.Version != "v1" || len(body.Article.Steps) != 2 || body.Article.Steps[0].Number != 1 || body.Article.Steps[1].Number != 2 {
		t.Fatalf("article = %#v", body.Article)
	}
	if len(body.Article.Images) != 2 || body.Article.Images[0].Alt != "Filter location" {
		t.Fatalf("images = %#v, want the article illustrations", body.Article.Images)
	}
	if !strings.HasPrefix(body.Article.Images[1].URL, "/v1/catalog/images/") || strings.Contains(body.Article.Images[1].URL, "autoapitwo.vercel.app/diagram.png") {
		t.Fatalf("provider image leaked or was not proxied: %#v", body.Article.Images[1])
	}
	if strings.Contains(response.Body.String(), "source_original") || strings.Contains(response.Body.String(), "provider") {
		t.Fatalf("internal source fields leaked: %s", response.Body.String())
	}
	if !body.Article.SourceReview.Available || body.Article.SourceReview.SnapshotID != "source-1" || body.Article.SourceReview.URL != "/v1/catalog/vehicles/vehicle-1/articles/article-1/source" {
		t.Fatalf("source review = %#v, want safe same-origin metadata", body.Article.SourceReview)
	}
}

func TestCatalogSourceRendersStoredHTMLWithoutProviderNavigation(t *testing.T) {
	t.Setenv("AUTODATA_IMAGE_URL_KEY", testCatalogImageSecret)
	store := newMemoryCatalogStore()
	store.PutConfiguration(CatalogConfiguration{ID: "cfg-1", VehicleID: "vehicle-1", Year: 2024, Make: "Acme", Model: "Roadster", Complete: true})
	store.PutArticle(CatalogArticle{
		ID: "article-1", VehicleID: "vehicle-1", Title: "Replace filter", ContentStatus: "content_complete", Complete: true,
		SourceOriginal: json.RawMessage(`{"_embedded":{"data":{"article":{"content":"<!doctype html><html><body><h2>REMOVAL</h2><p>Remove the cover.</p><table><tr><td><img src=\"/api/v1/content/carids/1/svgs/figure.svg\"></td></tr></table><script>alert(1)</script><a href=\"/api/v1/content/carids/1/components/2\">source link</a></body></html>"}}}}`),
		Provenance:     []CatalogProvenance{{ID: "source-1", Version: "autoapitwo-content-detail-v1"}},
		sourceURI:      "https://autoapitwo.vercel.app/api/v1/content/carids/1/articles/2",
	})
	server := catalogServer(store)
	request := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/vehicle-1/articles/article-1/source", nil)
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	request.Header.Set("Accept", "application/json")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d: %s", response.Code, http.StatusOK, response.Body.String())
	}
	var body CatalogSourceContentResponse
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body.Source.Format != "html" || !strings.Contains(body.Content, "REMOVAL") || strings.Contains(body.Content, "<img") {
		t.Fatalf("source response = %#v, want rendered text and omitted unlocalized image", body)
	}
	for _, forbidden := range []string{"<script", "autoapitwo.vercel.app", `?src=`, `href="/api/v1/content`} {
		if strings.Contains(body.Content, forbidden) {
			t.Fatalf("source content contains forbidden %q: %s", forbidden, body.Content)
		}
	}

	htmlRequest := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/vehicle-1/articles/article-1/source?evidence_id=e-1", nil)
	htmlRequest.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	htmlRequest.Header.Set("Accept", "text/html")
	htmlResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(htmlResponse, htmlRequest)
	if htmlResponse.Code != http.StatusOK || !strings.Contains(htmlResponse.Header().Get("Content-Security-Policy"), "default-src 'none'") || !strings.Contains(htmlResponse.Body.String(), "Evidence e-1") {
		t.Fatalf("browser source response = status %d headers %#v body %s", htmlResponse.Code, htmlResponse.Header(), htmlResponse.Body.String())
	}
	if strings.Contains(htmlResponse.Body.String(), "autoapitwo.vercel.app") || strings.Contains(htmlResponse.Body.String(), "?src=") {
		t.Fatalf("browser source response leaked a provider URL or legacy image route: %s", htmlResponse.Body.String())
	}

}

func TestCatalogSourceAliasResolvesStoredSnapshot(t *testing.T) {
	store := newMemoryCatalogStore()
	store.PutArticle(CatalogArticle{
		ID: "catalog-row-1", VehicleID: "vehicle-1", sourceArticleID: "provider-article-1", ContentStatus: "list_only",
	})
	store.PutArticle(CatalogArticle{
		ID: "provider-article-1", VehicleID: "vehicle-1", sourceArticleID: "provider-article-1", ContentStatus: "content_complete",
		SourceOriginal: json.RawMessage(`{"title":"stored"}`), Provenance: []CatalogProvenance{{ID: "snapshot-1", Version: "v1"}},
	})
	content, err := store.ArticleSource(nil, Principal{}, "vehicle-1", "catalog-row-1")
	if err != nil || content.SnapshotID != "snapshot-1" || string(content.Original) != `{"title":"stored"}` {
		t.Fatalf("source = %#v err=%v, want alias to resolve the stored snapshot", content, err)
	}
}

func TestCatalogSourceJSONIsEscapedForBrowserRendering(t *testing.T) {
	store := newMemoryCatalogStore()
	store.PutArticle(CatalogArticle{
		ID: "article-json", VehicleID: "vehicle-1", ContentStatus: "content_complete",
		SourceOriginal: json.RawMessage(`{"message":"<script>alert(1)</script>"}`),
		Provenance:     []CatalogProvenance{{ID: "snapshot-json", Version: "v1"}},
	})
	server := catalogServer(store)
	request := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/vehicle-1/articles/article-json/source", nil)
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	request.Header.Set("Accept", "text/html")
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, request)
	if response.Code != http.StatusOK || strings.Contains(response.Body.String(), "<script>alert(1)") || !strings.Contains(response.Body.String(), `\u003cscript\u003e`) {
		t.Fatalf("escaped source = status %d body %s", response.Code, response.Body.String())
	}
}

func TestCatalogArticleAliasUsesCachedDetailWithoutHydratingAgain(t *testing.T) {
	store := newMemoryCatalogStore()
	store.PutConfiguration(CatalogConfiguration{
		ID: "cfg-1", VehicleID: "vehicle-1", Year: 2024, Make: "Acme", Model: "Roadster",
		Region: "US", Trim: "Sport", Engine: "2.0L", Complete: true,
	})
	store.PutArticle(CatalogArticle{
		ID: "catalog-row-1", VehicleID: "vehicle-1", Title: "Replace filter", Kind: "procedure",
		ContentStatus: "list_only", sourceArticleID: "autoapitwo:car:article",
	})
	store.PutArticle(CatalogArticle{
		ID: "autoapitwo:car:article", VehicleID: "vehicle-1", Title: "Replace filter", Kind: "procedure",
		ContentStatus: "content_complete", Complete: true, sourceArticleID: "autoapitwo:car:article",
		Document: &CatalogDocument{
			SchemaVersion: 1, NormalizationVersion: "ordered-article-v1",
			Blocks: []CatalogDocumentBlock{{BlockID: "block-1", SourceOrder: 1, Type: "heading", Text: "Removal"}},
		},
	})
	server := catalogServer(store)
	capture := &fakeIngestionClient{status: http.StatusAccepted}
	server.ingestionClient = capture

	response := catalogRequest(server, "/v1/catalog/vehicles/vehicle-1/articles/catalog-row-1")
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d: %s", response.Code, http.StatusOK, response.Body.String())
	}
	var body CatalogArticleResponse
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body.Article.ID != "autoapitwo:car:article" || len(body.Article.Document.Blocks) != 1 {
		t.Fatalf("article = %#v, want cached ordered detail", body.Article)
	}
	if capture.path != "" {
		t.Fatalf("hydration request = %q, want no source call", capture.path)
	}
}

func TestCatalogArticleSourceOriginalIsImmutableAcrossUpsert(t *testing.T) {
	store := newMemoryCatalogStore()
	original := json.RawMessage(`{"title":"original"}`)
	store.PutArticle(CatalogArticle{ID: "a", VehicleID: "v", Title: "first", SourceOriginal: original})
	original[2] = 'X'
	store.PutArticle(CatalogArticle{ID: "a", VehicleID: "v", Title: "second", SourceOriginal: json.RawMessage(`{"title":"replacement"}`)})
	store.mu.RLock()
	article := store.articles["a"]
	store.mu.RUnlock()
	if string(article.SourceOriginal) != `{"title":"original"}` || article.Title != "first" {
		t.Fatalf("stored article = %#v, want immutable first publication", article)
	}
}

func TestCatalogRoutesReuseAuthorizationConvention(t *testing.T) {
	server := NewServerWithCatalogStore(staticReadiness{}, HeaderAuthenticator{}, newMemoryRequestStore(), catalogFixtureStore())
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/v1/catalog/years", nil))
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnauthorized)
	}
}

func TestIncompleteCatalogReadHydratesOnceAndCompleteReadSkipsWorker(t *testing.T) {
	capture := &fakeIngestionClient{status: http.StatusAccepted, responseBody: []byte(`{"status":"hydrated"}`)}
	server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{
		principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}},
	}, newMemoryRequestStore(), newMemoryCatalogStore())
	server.ingestionClient = capture

	response := catalogRequest(server, "/v1/catalog/years")
	if response.Code != http.StatusOK {
		t.Fatalf("incomplete read status = %d, want %d", response.Code, http.StatusOK)
	}
	if capture.path != "/v1/catalog/ensure" || capture.idempotencyKey == "" || !strings.Contains(string(capture.body), `"scope":"years"`) {
		t.Fatalf("hydration request = path %q body %q key %q", capture.path, capture.body, capture.idempotencyKey)
	}
	var hydrationBody map[string]any
	if err := json.Unmarshal(capture.body, &hydrationBody); err != nil {
		t.Fatal(err)
	}
	if hydrationBody["idempotency_key"] != capture.idempotencyKey {
		t.Fatalf("worker envelope idempotency key = %#v, want %q", hydrationBody["idempotency_key"], capture.idempotencyKey)
	}

	complete := catalogFixtureStore()
	completeServer := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{
		principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}},
	}, newMemoryRequestStore(), complete)
	completeCapture := &fakeIngestionClient{status: http.StatusAccepted}
	completeServer.ingestionClient = completeCapture
	response = catalogRequest(completeServer, "/v1/catalog/years")
	if response.Code != http.StatusOK {
		t.Fatalf("complete read status = %d, want %d", response.Code, http.StatusOK)
	}
	if completeCapture.path != "" {
		t.Fatalf("complete cache made provider hydration call: %q", completeCapture.path)
	}
}

func TestArticleIndexReturnsHydratingStateInsteadOfBlockingOnSource(t *testing.T) {
	store := newMemoryCatalogStore()
	store.PutConfiguration(CatalogConfiguration{
		ID: "cfg-1", VehicleID: "vehicle-1", Year: 2024, Make: "Acme", Model: "Roadster", Region: "US", Complete: true,
	})
	server := catalogServer(store)
	server.ingestionClient = &fakeIngestionClient{status: http.StatusAccepted}

	response := catalogRequest(server, "/v1/catalog/vehicles/vehicle-1/articles")
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d: %s", response.Code, http.StatusOK, response.Body.String())
	}
	var body CatalogArticlesResponse
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body.Complete || !body.Hydrating || len(body.Items) != 0 {
		t.Fatalf("body = %#v, want an empty hydrating response", body)
	}
}

type blockingCatalogHydrationClient struct {
	started  chan struct{}
	release  chan struct{}
	finished chan struct{}
}

func (c *blockingCatalogHydrationClient) Do(_ *http.Request, path string, _ []byte, _ string) (int, []byte, error) {
	if path != "/v1/catalog/ensure" {
		return http.StatusBadRequest, nil, nil
	}
	close(c.started)
	<-c.release
	close(c.finished)
	return http.StatusAccepted, []byte(`{"status":"scheduled"}`), nil
}

func TestIncompleteSelectorReadReturnsWhileHydrationRunsInBackground(t *testing.T) {
	client := &blockingCatalogHydrationClient{
		started:  make(chan struct{}),
		release:  make(chan struct{}),
		finished: make(chan struct{}),
	}
	server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{
		principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}},
	}, newMemoryRequestStore(), newMemoryCatalogStore())
	server.ingestionClient = client

	responseCh := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		responseCh <- catalogRequest(server, "/v1/catalog/years/1993/makes")
	}()

	var response *httptest.ResponseRecorder
	select {
	case response = <-responseCh:
	case <-time.After(500 * time.Millisecond):
		t.Fatal("selector read waited for source hydration")
	}
	if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), `"items":[]`) {
		t.Fatalf("response = %d %s", response.Code, response.Body.String())
	}
	var body CatalogMakesResponse
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body.Complete || !body.Hydrating {
		t.Fatalf("hydration state = complete:%t hydrating:%t, want incomplete and hydrating", body.Complete, body.Hydrating)
	}
	select {
	case <-client.started:
	case <-time.After(500 * time.Millisecond):
		t.Fatal("selector read did not schedule source hydration")
	}
	close(client.release)
	select {
	case <-client.finished:
	case <-time.After(500 * time.Millisecond):
		t.Fatal("background hydration did not finish")
	}
}

func TestCatalogSourceImageFailsClosedWithoutImageKey(t *testing.T) {
	for _, raw := range []string{"/figures/one.png", "data:image/png;base64,AA=="} {
		if path, ok := catalogSourceAssetURL("https://autoapitwo.vercel.app/article/1", raw, nil); ok || path != "" {
			t.Fatalf("source image %q should fail closed without image key, got %q, %v", raw, path, ok)
		}
	}
}

func TestCatalogSourceOmitsInlineDataImagesFromJSONAndHTML(t *testing.T) {
	store := newMemoryCatalogStore()
	store.PutConfiguration(CatalogConfiguration{ID: "cfg-1", VehicleID: "vehicle-1", Year: 2024, Make: "Acme", Model: "Roadster", Complete: true})
	store.PutArticle(CatalogArticle{
		ID: "article-1", VehicleID: "vehicle-1", Title: "Replace filter", ContentStatus: "content_complete", Complete: true,
		SourceOriginal: json.RawMessage(`{"_embedded":{"data":{"article":{"content":"<html><body><h2>Removal</h2><img src=\"data:image/png;base64,AA==\"></body></html>"}}}}`),
		Provenance:     []CatalogProvenance{{ID: "source-1", Version: "autoapitwo-content-detail-v1"}},
		sourceURI:      "https://autoapitwo.vercel.app/api/v1/content/carids/1/articles/2",
	})
	server := catalogServer(store)
	t.Setenv("AUTODATA_IMAGE_URL_KEY", "")
	for _, accept := range []string{"application/json", "text/html"} {
		request := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/vehicle-1/articles/article-1/source", nil)
		request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
		request.Header.Set("Accept", accept)
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, request)
		if response.Code != http.StatusOK {
			t.Fatalf("source response for Accept %q = %d: %s", accept, response.Code, response.Body.String())
		}
		if strings.Contains(response.Body.String(), "data:image/") || strings.Contains(response.Body.String(), "<img") {
			t.Fatalf("source response for Accept %q kept inline image without image key: %s", accept, response.Body.String())
		}
	}
}
