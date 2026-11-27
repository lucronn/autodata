package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"slices"
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
			{ID: "image-2", URL: "https://banktwo.cars.tk/diagram.png", Alt: "Filter wiring", StorageKey: "procedure-images/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
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

func TestCatalogConfigurationChoicesIncludeAvailableVariantFacts(t *testing.T) {
	store := newMemoryCatalogStore()
	shared := CatalogConfiguration{
		Year: 2024, Make: "Acme", Model: "Roadster", Region: "US", Engine: "2.0", Trim: "Sport", Complete: true,
	}
	coupe := shared
	coupe.ID, coupe.BodyStyle, coupe.Drivetrain = "coupe-2wd", "Coupe", "2WD"
	sedan := shared
	sedan.ID, sedan.BodyStyle, sedan.Drivetrain = "sedan-awd", "Sedan", "AWD"
	legacy := shared
	legacy.ID = "legacy"
	for _, variant := range []CatalogConfiguration{coupe, sedan, legacy} {
		store.PutConfiguration(variant)
	}

	response := catalogRequest(catalogServer(store), "/v1/catalog/years/2024/makes/acme/models/roadster/configurations?region=US")
	var body struct {
		Items []map[string]any `json:"items"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &body); response.Code != http.StatusOK || err != nil || len(body.Items) != 3 {
		t.Fatalf("configuration choices: %d %s", response.Code, response.Body)
	}
	byID := map[string]map[string]any{}
	for _, item := range body.Items {
		id, ok := item["id"].(string)
		if !ok {
			t.Fatalf("configuration choice missing ID: %v", item)
		}
		byID[id] = item
	}
	for _, variant := range []CatalogConfiguration{coupe, sedan} {
		item := byID[variant.ID]
		if item["body_style"] != variant.BodyStyle || item["drivetrain"] != variant.Drivetrain {
			t.Fatalf("variant identity missing for %s: %v", variant.ID, item)
		}
	}
	legacyItem := byID[legacy.ID]
	if legacyItem == nil {
		t.Fatal("legacy configuration choice missing")
	}
	for _, field := range []string{"body_style", "drivetrain"} {
		if _, exists := legacyItem[field]; exists {
			t.Fatalf("absent %s was serialized: %v", field, legacyItem)
		}
	}
}

type incompleteScopeCatalogStore struct {
	*memoryCatalogStore
}

func (s incompleteScopeCatalogStore) CatalogScopeComplete(context.Context, Principal, string, int, string, string, string) (bool, error) {
	return false, nil
}

type catalogStatusErrorStore struct {
	*memoryCatalogStore
	statusErr error
}

func (s catalogStatusErrorStore) CatalogScopeComplete(context.Context, Principal, string, int, string, string, string) (bool, error) {
	return false, s.statusErr
}

func (s catalogStatusErrorStore) CatalogArticleProgress(context.Context, Principal, string) (*CatalogArticleProgress, error) {
	return nil, s.statusErr
}

func TestCatalogReturnsStoredRowsWhenDiscoveryStatusFails(t *testing.T) {
	store := catalogStatusErrorStore{catalogFixtureStore(), errors.New("status query failed")}
	server := catalogServer(store)
	for _, tc := range []struct {
		path string
		id   string
	}{
		{"/v1/catalog/years/2024/makes?region=US", "acme"},
		{"/v1/catalog/years/2024/makes/acme/models?region=US", "roadster"},
		{"/v1/catalog/years/2024/makes/acme/models/roadster/configurations?region=US", "cfg-1"},
		{"/v1/catalog/vehicles/vehicle-1/articles", "article-1"},
		{"/v1/catalog/vehicles/vehicle-1/articles?q=filter", "article-1"},
	} {
		t.Run(tc.path, func(t *testing.T) {
			w := catalogRequest(server, tc.path)
			var body struct {
				Complete bool
				Items    []struct{ ID string }
				Progress *CatalogArticleProgress
			}
			err := json.Unmarshal(w.Body.Bytes(), &body)
			if w.Code != 200 || err != nil || body.Complete || body.Progress != nil ||
				len(body.Items) != 1 || body.Items[0].ID != tc.id {
				t.Fatalf("stored rows unavailable: %d %s (%v)", w.Code, w.Body, err)
			}
		})
	}
	w := catalogRequest(server, "/v1/catalog/vehicles/vehicle-1/articles?q=absent")
	if w.Code != 503 {
		t.Fatalf("unknown completeness with no data returned %d: %s", w.Code, w.Body)
	}
	withdrawn := catalogServer(catalogStatusErrorStore{catalogFixtureStore(), ErrCatalogWithdrawn})
	w = catalogRequest(withdrawn, "/v1/catalog/vehicles/vehicle-1/articles")
	if w.Code != 410 || strings.Contains(w.Body.String(), "article-1") {
		t.Fatalf("withdrawn data returned %d: %s", w.Code, w.Body)
	}
}

func TestStoredConfigurationsReportActualDiscovery(t *testing.T) {
	for _, model := range []struct {
		name      string
		itemCount int
	}{
		{"roadster", 1},
		{"unknown", 0},
	} {
		t.Run(model.name, func(t *testing.T) {
			store := incompleteScopeCatalogStore{memoryCatalogStore: catalogFixtureStore()}
			capture := &blockingCatalogHydrationClient{
				started:  make(chan struct{}),
				release:  make(chan struct{}),
				finished: make(chan struct{}),
			}
			released := false
			defer func() {
				if !released {
					close(capture.release)
				}
			}()
			server := catalogServer(store)
			server.ingestionClient = capture
			path := "/v1/catalog/years/2024/makes/acme/models/" + model.name + "/configurations"
			assertState := func(suffix string, active bool) {
				t.Helper()
				response := catalogRequest(server, path+suffix)
				var body CatalogConfigurationsResponse
				err := json.Unmarshal(response.Body.Bytes(), &body)
				usable := model.itemCount > 0
				if response.Code != http.StatusOK || err != nil || body.Complete ||
					body.DiscoveryInstance != catalogDiscoveryInstance ||
					body.Discovering != (active && usable) || body.Hydrating != (active && !usable) ||
					len(body.Items) != model.itemCount || (usable && !body.Items[0].Complete) {
					t.Fatalf("configuration state %q with active=%t: status=%d body=%s err=%v",
						suffix, active, response.Code, response.Body, err)
				}
			}

			assertState("?stored_only=1", false)
			assertState("", true)
			select {
			case <-capture.started:
			case <-time.After(500 * time.Millisecond):
				t.Fatal("expected background discovery to start")
			}
			assertState("?stored_only=1", true)
			close(capture.release)
			released = true
			payload := map[string]any{
				"scope": "configurations", "year": 2024, "make": "acme", "model": model.name, "region": "US",
			}
			deadline := time.Now().Add(500 * time.Millisecond)
			for server.catalogHydrationRunning(payload) && time.Now().Before(deadline) {
				time.Sleep(time.Millisecond)
			}
			assertState("?stored_only=1", false)
		})
	}
}

type configurationCoverageTestStore struct {
	*memoryCatalogStore
	providerComplete bool
}

func (s *configurationCoverageTestStore) configurationCoverage(context.Context, int, string, string, string) (bool, bool, error) {
	return true, s.providerComplete, nil
}

func TestLegacyRawOnlyConfigurationsResumeDiscoveryAndSettle(t *testing.T) {
	store := &configurationCoverageTestStore{memoryCatalogStore: newMemoryCatalogStore()}
	raw := CatalogConfiguration{ID: "raw-option", VehicleID: "raw-option", Year: 2024, Make: "Acme", Model: "Legacy Roadster",
		Region: "US", Complete: true, ConfigurationUnresolved: true}
	store.PutConfiguration(raw)
	client := &blockingCatalogHydrationClient{started: make(chan struct{}), release: make(chan struct{}), finished: make(chan struct{})}
	released := false
	t.Cleanup(func() {
		if !released {
			close(client.release)
		}
	})
	server := catalogServer(store)
	server.ingestionClient = client
	path := "/v1/catalog/years/2024/makes/acme/models/legacy-roadster/configurations?region=US"
	assertState := func(suffix string, complete, hydrating, discovering bool, count int) {
		t.Helper()
		response := catalogRequest(server, path+suffix)
		var body CatalogConfigurationsResponse
		if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil || response.Code != http.StatusOK ||
			body.Complete != complete || body.Hydrating != hydrating || body.Discovering != discovering ||
			len(body.Items) != count || !slices.Contains(body.Items, raw) {
			t.Fatalf("state %q = %d %s (%v)", suffix, response.Code, response.Body, err)
		}
	}

	assertState("&stored_only=1", false, false, false, 1)
	assertState("", false, true, false, 1)
	select {
	case <-client.started:
	case <-time.After(time.Second):
		t.Fatal("legacy raw configuration suppressed discovery")
	}
	assertState("&stored_only=1", false, true, false, 1)
	assertState("", false, true, false, 1)

	store.PutConfiguration(CatalogConfiguration{ID: "verified-option", Year: 2024, Make: "Acme", Model: "Legacy Roadster",
		Region: "US", Engine: "2.0", Complete: true})
	assertState("&stored_only=1", false, false, true, 2)
	assertState("", false, false, true, 2)

	store.providerComplete = true
	close(client.release)
	released = true
	assertState("&stored_only=1", true, false, false, 2)
	// A later request must not schedule even after the first ensure exits.
	payload := map[string]any{"scope": "configurations", "year": 2024, "make": "acme", "model": "legacy roadster", "region": "US"}
	deadline := time.Now().Add(time.Second)
	for server.catalogHydrationRunning(payload) && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	assertState("", true, false, false, 2)

	store.providerComplete = false
	assertState("", true, false, false, 2)
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
	if body.Configuration != nil {
		t.Fatal("local detail returned paid configuration metadata")
	}
	if len(body.Article.Images) != 2 || body.Article.Images[0].Alt != "Filter location" {
		t.Fatalf("images = %#v, want the article illustrations", body.Article.Images)
	}
	if !strings.HasPrefix(body.Article.Images[1].URL, "/v1/catalog/images/") || strings.Contains(body.Article.Images[1].URL, "banktwo.cars.tk/diagram.png") {
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
		sourceURI:      "https://banktwo.cars.tk/api/v1/content/carids/1/articles/2",
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
	for _, forbidden := range []string{"<script", "autoapitwo.vercel.app", "banktwo.cars.tk", `?src=`, `href="/api/v1/content`} {
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
	if strings.Contains(htmlResponse.Body.String(), "autoapitwo.vercel.app") || strings.Contains(htmlResponse.Body.String(), "banktwo.cars.tk") || strings.Contains(htmlResponse.Body.String(), "?src=") {
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

func TestLegacyArticleListKeepsVariantRowsWithoutGenericHydration(t *testing.T) {
	configuration := CatalogConfiguration{
		ID: "cfg-cng", VehicleID: "vehicle-cng", Year: 2020, Make: "Chevy Truck", Model: "Express 4500",
		Region: "US", Engine: "6.0", EngineVariant: "CNG",
	}
	store := newMemoryCatalogStore()
	store.PutConfiguration(configuration)
	store.PutArticle(CatalogArticle{ID: "existing-article", VehicleID: configuration.VehicleID, Title: "Service information"})
	server := catalogServer(store)
	capture := &blockingCatalogHydrationClient{started: make(chan struct{}), release: make(chan struct{}), finished: make(chan struct{})}
	defer close(capture.release)
	server.ingestionClient = capture

	response := catalogRequest(server, "/v1/catalog/vehicles/vehicle-cng/articles")
	if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), "Service information") {
		t.Fatalf("legacy article list = %d %s", response.Code, response.Body.String())
	}
	if server.catalogHydrationRunning(map[string]any{
		"scope": "articles", "vehicle_id": configuration.VehicleID, "year": configuration.Year,
		"make": configuration.Make, "model": configuration.Model, "region": configuration.Region,
		"trim": configuration.Trim, "engine": configuration.Engine,
	}) {
		t.Fatal("qualified configuration initiated a generic legacy source read")
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
	capture := &blockingCatalogHydrationClient{started: make(chan struct{}), release: make(chan struct{}), finished: make(chan struct{})}
	server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{
		principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}},
	}, newMemoryRequestStore(), newMemoryCatalogStore())
	server.ingestionClient = capture

	defer func() {
		close(capture.release)
		select {
		case <-capture.finished:
		case <-time.After(time.Second):
			t.Error("years background hydration did not finish")
		}
	}()
	responses := make(chan *httptest.ResponseRecorder, 1)
	go func() { responses <- catalogRequest(server, "/v1/catalog/years") }()
	select {
	case response := <-responses:
		var body CatalogYearsResponse
		if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		if response.Code != http.StatusOK || body.Complete || !body.Hydrating || len(body.Items) != 0 {
			t.Fatalf("empty catalog response = %d %#v", response.Code, body)
		}
	case <-time.After(500 * time.Millisecond):
		t.Fatal("years read waited for source hydration")
	}
	select {
	case <-capture.started:
	case <-time.After(500 * time.Millisecond):
		t.Fatal("years read did not schedule source hydration")
	}
	var hydrationBody map[string]any
	if err := json.Unmarshal(capture.body, &hydrationBody); err != nil {
		t.Fatal(err)
	}
	if hydrationBody["scope"] != "years" || capture.idempotencyKey == "" || hydrationBody["idempotency_key"] != capture.idempotencyKey {
		t.Fatalf("years worker envelope = %#v, key %q", hydrationBody, capture.idempotencyKey)
	}
	response := catalogRequest(server, "/v1/catalog/years")
	if response.Code != http.StatusOK {
		t.Fatalf("second years read status = %d", response.Code)
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
	if body.Complete || body.Hydrating || len(body.Items) != 0 {
		t.Fatalf("body = %#v, want incomplete without inventing an active durable job", body)
	}
}

type blockingCatalogHydrationClient struct {
	started        chan struct{}
	release        chan struct{}
	finished       chan struct{}
	body           []byte
	idempotencyKey string
}

func (c *blockingCatalogHydrationClient) Do(_ *http.Request, path string, body []byte, key string) (int, []byte, error) {
	if path != "/v1/catalog/ensure" {
		return http.StatusBadRequest, nil, nil
	}
	c.body, c.idempotencyKey = body, key
	close(c.started)
	<-c.release
	close(c.finished)
	return http.StatusAccepted, []byte(`{"status":"scheduled"}`), nil
}

func TestStoredSelectorReadPreviewsWithoutStartingHydration(t *testing.T) {
	client := &blockingCatalogHydrationClient{started: make(chan struct{}), release: make(chan struct{}), finished: make(chan struct{})}
	defer close(client.release)
	server := catalogServer(newMemoryCatalogStore())
	server.ingestionClient = client
	for _, selector := range []struct {
		path    string
		payload map[string]any
	}{
		{"/v1/catalog/years?stored_only=1", map[string]any{"scope": "years"}},
		{"/v1/catalog/years/2024/makes?region=US&stored_only=1", map[string]any{"scope": "makes", "year": 2024, "region": "US"}},
		{"/v1/catalog/years/2024/makes/preview/models?region=US&stored_only=1", map[string]any{"scope": "models", "year": 2024, "region": "US", "make": "preview"}},
		{"/v1/catalog/years/2024/makes/preview/models/example/configurations?region=US&stored_only=1", map[string]any{"scope": "configurations", "year": 2024, "region": "US", "make": "preview", "model": "example"}},
	} {
		response := catalogRequest(server, selector.path)
		if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), `"items":[]`) {
			t.Fatalf("preview %s = %d %s", selector.path, response.Code, response.Body.String())
		}
		key, _, err := catalogHydrationRequest(selector.payload)
		if err != nil {
			t.Fatal(err)
		}
		if _, started := catalogHydrationInFlight.Load(key); started {
			t.Fatalf("preview %s initiated supplier hydration", selector.path)
		}
	}
}

func TestIncompleteSelectorReadReportsBackgroundHydration(t *testing.T) {
	for _, selector := range []struct {
		scope   string
		suffix  string
		payload map[string]any
	}{
		{"makes", "/makes", map[string]any{"scope": "makes", "year": 1993, "region": "US"}},
		{"models", "/makes/acme/models", map[string]any{"scope": "models", "year": 1993, "make": "acme", "region": "US"}},
	} {
		t.Run(selector.scope, func(t *testing.T) {
			client := &blockingCatalogHydrationClient{
				started: make(chan struct{}), release: make(chan struct{}), finished: make(chan struct{}),
			}
			released := false
			t.Cleanup(func() {
				if !released {
					close(client.release)
				}
			})
			server := catalogServer(newMemoryCatalogStore())
			server.ingestionClient = client
			path := "/v1/catalog/years/1993" + selector.suffix
			assertState := func(response *httptest.ResponseRecorder, hydrating bool) {
				t.Helper()
				var body struct {
					CatalogHydrationResponse
					Items []json.RawMessage
				}
				err := json.Unmarshal(response.Body.Bytes(), &body)
				if response.Code != http.StatusOK || err != nil || body.Complete || body.Hydrating != hydrating ||
					body.DiscoveryInstance != catalogDiscoveryInstance || body.Items == nil || len(body.Items) != 0 {
					t.Fatalf("selector response with hydrating=%t: %d %s (%v)", hydrating, response.Code, response.Body, err)
				}
			}
			stored := path + "?stored_only=1"
			assertState(catalogRequest(server, stored), false)
			responseCh := make(chan *httptest.ResponseRecorder, 1)
			go func() { responseCh <- catalogRequest(server, path) }()
			select {
			case response := <-responseCh:
				assertState(response, true)
			case <-time.After(time.Second):
				t.Fatal("selector read waited for source hydration")
			}
			select {
			case <-client.started:
			case <-time.After(time.Second):
				t.Fatal("selector read did not schedule source hydration")
			}
			assertState(catalogRequest(server, stored), true)
			close(client.release)
			released = true
			deadline := time.Now().Add(time.Second)
			for server.catalogHydrationRunning(selector.payload) && time.Now().Before(deadline) {
				time.Sleep(time.Millisecond)
			}
			assertState(catalogRequest(server, stored), false)
		})
	}
}

func TestCatalogSourceImageFailsClosedWithoutImageKey(t *testing.T) {
	for _, raw := range []string{"/figures/one.png", "data:image/png;base64,AA=="} {
		if path, ok := catalogSourceAssetURL("https://banktwo.cars.tk/article/1", raw, nil); ok || path != "" {
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
		sourceURI:      "https://banktwo.cars.tk/api/v1/content/carids/1/articles/2",
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

// A complete scope marker, not row count, proves an authoritative empty result.
type fixedCompletionCatalogStore struct {
	*memoryCatalogStore
	complete bool
}

func (s fixedCompletionCatalogStore) CatalogScopeComplete(context.Context, Principal, string, int, string, string, string) (bool, error) {
	return s.complete, nil
}

func TestCatalogConfigurationsCompletedEmptyIsTerminal(t *testing.T) {
	for _, tc := range []struct {
		name          string
		complete      bool
		incompleteRow bool
		wantComplete  bool
		wantHydrating bool
	}{
		{"completed empty", true, false, true, false},
		{"incomplete empty", false, false, false, true},
		{"marker cannot complete an incomplete row", true, true, false, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			memory := newMemoryCatalogStore()
			if tc.incompleteRow {
				memory.PutConfiguration(CatalogConfiguration{ID: "cfg-incomplete", Year: 2024, Make: "Acme", Model: "Roadster", Region: "US", Complete: false})
			}
			store := fixedCompletionCatalogStore{memoryCatalogStore: memory, complete: tc.complete}
			capture := &blockingCatalogHydrationClient{started: make(chan struct{}), release: make(chan struct{}), finished: make(chan struct{})}
			close(capture.release)
			server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)
			server.ingestionClient = capture
			response := catalogRequest(server, "/v1/catalog/years/2024/makes/acme/models/roadster/configurations")
			if response.Code != http.StatusOK {
				t.Fatalf("status %d: %s", response.Code, response.Body.String())
			}
			var body CatalogConfigurationsResponse
			if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body.Complete != tc.wantComplete || body.Hydrating != tc.wantHydrating {
				t.Fatalf("complete=%v hydrating=%v, want %v/%v", body.Complete, body.Hydrating, tc.wantComplete, tc.wantHydrating)
			}
			if tc.wantHydrating {
				select {
				case <-capture.finished:
				case <-time.After(time.Second):
					t.Fatal("hydration not scheduled")
				}
			} else {
				select {
				case <-capture.started:
					t.Fatal("completed empty scope rehydrated")
				case <-time.After(20 * time.Millisecond):
				}
			}
		})
	}
}
