package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

const paidTestConfiguration = "33333333-3333-4333-8333-333333333333"
const paidTestVehicle = "44444444-4444-4444-8444-444444444444"

type paidScopeCatalog struct {
	CatalogStore
	configuration CatalogConfiguration
	err           error
	calls         int
}

func (c *paidScopeCatalog) ConfigurationByVehicle(context.Context, Principal, string) (CatalogConfiguration, error) {
	c.calls++
	return c.configuration, c.err
}

type paidGrantClient struct {
	calls                               int
	err                                 error
	account, org, configuration, region string
}

func (c *paidGrantClient) Do(context.Context, string, []byte, string) (int, []byte, error) {
	panic("unexpected generic commerce call")
}
func (c *paidGrantClient) CheckVehicleGrant(_ context.Context, a, o, configuration, region string) (VehicleGrant, error) {
	c.calls++
	c.account, c.org, c.configuration, c.region = a, o, configuration, region
	return VehicleGrant{ConfigurationID: configuration, Region: region}, c.err
}

func TestPaidCatalogExactScopeBeforeGrant(t *testing.T) {
	p := Principal{CustomerAccountID: "11111111-1111-4111-8111-111111111111", OrganizationID: "22222222-2222-4222-8222-222222222222"}
	for _, tc := range []struct {
		name, input, region string
		config              CatalogConfiguration
		want                error
		grants              int
	}{
		{"exact", paidTestConfiguration, "", CatalogConfiguration{ID: paidTestConfiguration, VehicleID: paidTestVehicle, Region: "CA"}, nil, 1},
		{"base", paidTestVehicle, "", CatalogConfiguration{ID: paidTestConfiguration, VehicleID: paidTestVehicle, Region: "CA"}, ErrCatalogNotFound, 0},
		{"region", paidTestConfiguration, "US", CatalogConfiguration{ID: paidTestConfiguration, Region: "CA"}, ErrCatalogNotFound, 0},
		{"invalid", "wrong", "", CatalogConfiguration{}, ErrCatalogNotFound, 0},
		{"missingregion", paidTestConfiguration, "", CatalogConfiguration{ID: paidTestConfiguration}, ErrCatalogNotFound, 0},
	} {
		t.Run(tc.name, func(t *testing.T) {
			c := &paidScopeCatalog{configuration: tc.config}
			g := &paidGrantClient{}
			s := &Server{catalog: c, commerceClient: g}
			got, err := s.resolvePaidCatalogScope(context.Background(), p, tc.input, tc.region)
			if !errors.Is(err, tc.want) || g.calls != tc.grants {
				t.Fatalf("scope=%+v err=%v grants=%d", got, err, g.calls)
			}
			if tc.grants > 0 && (g.account != p.CustomerAccountID || g.org != p.OrganizationID || g.configuration != paidTestConfiguration || g.region != "CA") {
				t.Fatal("untrusted or defaulted grant scope")
			}
		})
	}
}
func TestPaidCatalogGrantErrorsAreSafe(t *testing.T) {
	for _, tc := range []struct {
		err    error
		status int
		code   string
	}{{ErrVehicleGrantRequired, 403, "ENTITLEMENT_REQUIRED"}, {ErrVehicleGrantRevoked, 403, "ENTITLEMENT_REVOKED"}, {ErrVehicleGrantUnavailable, 503, "CATALOG_UNAVAILABLE"}, {ErrCatalogNotFound, 404, "CATALOG_NOT_FOUND"}, {ErrCatalogWithdrawn, 410, "CATALOG_WITHDRAWN"}, {errors.New("private provider detail"), 503, "CATALOG_UNAVAILABLE"}} {
		t.Run(tc.code, func(t *testing.T) {
			w := httptest.NewRecorder()
			s := &Server{}
			s.writePaidCatalogError(w, httptest.NewRequest("GET", "/v1/catalog/images/private-token", nil), tc.err)
			if w.Code != tc.status || w.Header().Get("Cache-Control") != "private, no-store" {
				t.Fatal(w.Code, w.Header())
			}
			if !strings.Contains(w.Body.String(), tc.code) || strings.Contains(w.Body.String(), "private provider") {
				t.Fatal(w.Body.String())
			}
		})
	}
}

type paidHTTPStore struct {
	*memoryCatalogStore
	protected int
	searches  int
	identity  PaidArticleIdentity
	view      *CatalogArticleView
	progress  *CatalogArticleProgress
}

func (c *paidHTTPStore) ConfigurationByVehicle(_ context.Context, _ Principal, id string) (CatalogConfiguration, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	for _, configuration := range c.configurations {
		if configuration.ID == id || configuration.VehicleID == id {
			return configuration, nil
		}
	}
	return CatalogConfiguration{}, ErrCatalogNotFound
}
func (c *paidHTTPStore) PaidArticleDescriptors(ctx context.Context, p Principal, id string) ([]CatalogArticle, error) {
	return c.Articles(ctx, p, id)
}
func (c *paidHTTPStore) PaidArticleSearchDescriptors(ctx context.Context, p Principal, id, query string) ([]CatalogArticle, error) {
	c.protected++
	c.searches++
	items, err := c.memoryCatalogStore.Articles(ctx, p, id)
	if err != nil {
		return nil, err
	}
	return filterCatalogArticleSearch(items, query), nil
}
func (c *paidHTTPStore) Articles(ctx context.Context, p Principal, id string) ([]CatalogArticle, error) {
	c.protected++
	return c.memoryCatalogStore.Articles(ctx, p, id)
}
func (c *paidHTTPStore) ArticleView(ctx context.Context, p Principal, v, id string) (CatalogArticleView, error) {
	c.protected++
	if c.view != nil {
		return *c.view, nil
	}
	return c.memoryCatalogStore.ArticleView(ctx, p, v, id)
}
func (c *paidHTTPStore) CatalogArticleProgress(context.Context, Principal, string) (*CatalogArticleProgress, error) {
	c.protected++
	return c.progress, nil
}
func (c *paidHTTPStore) PaidArticleIdentity(context.Context, string, string) (PaidArticleIdentity, error) {
	return c.identity, nil
}
func paidHTTPServer() (*Server, *paidHTTPStore, *paidGrantClient) {
	c := &paidHTTPStore{memoryCatalogStore: newMemoryCatalogStore()}
	c.PutConfiguration(CatalogConfiguration{ID: paidTestConfiguration, VehicleID: paidTestVehicle, Region: "CA", Year: 2024, Make: "Acme", Model: "Roadster", Complete: true})
	p := Principal{CustomerAccountID: "11111111-1111-4111-8111-111111111111", OrganizationID: "22222222-2222-4222-8222-222222222222", Roles: []string{"platform_admin"}}
	s := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{principal: p}, newMemoryRequestStore(), c)
	s.customerAuth = &customerAuthService{config: customerAuthConfig{Mode: "firebase"}}
	g := &paidGrantClient{err: ErrVehicleGrantRequired}
	s.commerceClient = g
	return s, c, g
}

func TestOpenDemoRequiresApprovedTestOrigin(t *testing.T) {
	for _, tc := range []struct {
		flag, environment, origin, want string
	}{
		{"1", "test", "http://localhost:3013", "localhost:3013"},
		{"1", "test", "http://127.0.0.1:3013", "127.0.0.1:3013"},
		{"1", "test", "https://demo.cars.tk", "demo.cars.tk"},
		{"", "test", "https://demo.cars.tk", ""},
		{"1", "staging", "https://demo.cars.tk", ""},
		{"1", "production", "https://demo.cars.tk", ""},
		{"", "test", "http://localhost:3013", ""},
		{"1", "staging", "http://localhost:3013", ""},
		{"1", "production", "http://localhost:3013", ""},
		{"1", "test", "https://autodata.cars.tk", ""},
		{"1", "test", "https://cars.tk", ""},
		{"1", "test", "http://demo.cars.tk", ""},
		{"1", "test", "https://demo.cars.tk:443", ""},
		{"1", "test", "https://demo.example", ""},
		{"1", "test", "http://localhost:3013/path", ""},
	} {
		if got := workshopOpenDemoHost(tc.flag, tc.environment, tc.origin); got != tc.want {
			t.Fatalf("open demo host for %q %q %q = %q, want %q", tc.flag, tc.environment, tc.origin, got, tc.want)
		}
	}
}

func TestOpenDemoReadsExactCatalogWithoutLoginOrGrant(t *testing.T) {
	s, c, grant := paidHTTPServer()
	s.auth = &fakeAuthenticator{err: ErrUnauthenticated}
	s.workshopOpenDemoHost = workshopOpenDemoHost("1", "test", "http://localhost:3013")
	id := "55555555-5555-4555-8555-555555555555"
	c.identity = PaidArticleIdentity{ConfigurationID: paidTestConfiguration, CanonicalArticleID: id, VehicleID: paidTestVehicle, ProviderSlug: "bankone", SourceVehicleRef: "opaque/vehicle", SourceArticleRef: "opaque/article"}
	c.PutArticle(CatalogArticle{ID: id, VehicleID: paidTestConfiguration, CanonicalArticleID: &id, Title: "Stored procedure", Availability: "available", Body: "private body"})
	unavailableID := "66666666-6666-4666-8666-666666666666"
	c.PutArticle(CatalogArticle{ID: unavailableID, VehicleID: paidTestConfiguration, CanonicalArticleID: &unavailableID, Title: "Index only", Availability: "unavailable", Body: "private body"})
	c.view = &CatalogArticleView{Article: CatalogArticle{ID: id, CanonicalArticleID: &id, Title: "Stored procedure", Availability: "available", Body: "private body", Images: []CatalogImage{{ID: "asset", URL: "https://provider.example/secret"}}}}
	c.progress = &CatalogArticleProgress{Status: "completed", Complete: true}
	root := "/v1/catalog/vehicles/" + paidTestConfiguration + "/articles"
	request := func(path, host string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(http.MethodGet, path, nil)
		r.Host = host
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, r)
		return w
	}
	mode := request("/workshop/demo-mode.json", "localhost:3013")
	if mode.Code != 200 || strings.TrimSpace(mode.Body.String()) != `{"enabled":true,"access":"open"}` {
		t.Fatalf("mode = %d %s", mode.Code, mode.Body.String())
	}
	for _, path := range []string{root + "?demo=1", root + "/" + id + "?demo=1"} {
		w := request(path, "localhost:3013")
		if w.Code != 200 || w.Header().Get("Cache-Control") != "private, no-store" {
			t.Fatalf("open demo %s = %d %s", path, w.Code, w.Body.String())
		}
		if path == root+"/"+id+"?demo=1" && (!strings.Contains(w.Body.String(), "private body") || strings.Contains(w.Body.String(), "provider.example")) {
			t.Fatal("article body missing or provider URL leaked")
		}
		if path == root+"/"+id+"?demo=1" && strings.Contains(w.Body.String(), `"configuration":`) {
			t.Fatal("open demo article returned paid configuration metadata")
		}
	}
	search := request(root+"?demo=1&q=private", "localhost:3013")
	if search.Code != 200 || !strings.Contains(search.Body.String(), id) || strings.Contains(search.Body.String(), unavailableID) || strings.Contains(search.Body.String(), "private body") {
		t.Fatalf("open demo search exposed unreadable content: %d %s", search.Code, search.Body.String())
	}
	if grant.calls != 0 {
		t.Fatal("open demo contacted purchase grant checker")
	}
	for _, path := range []string{root, root + "?demo=1&demo=1", root + "?demo=1&region=US", "/v1/catalog/vehicles/" + paidTestVehicle + "/articles?demo=1"} {
		w := request(path, "localhost:3013")
		if w.Code == 200 {
			t.Fatalf("unscoped request succeeded: %s", path)
		}
	}
	if w := request(root+"?demo=1", "public.example"); w.Code == 200 {
		t.Fatal("different Host received open demo content")
	}
	s.workshopOpenDemoHost = ""
	if w := request(root+"?demo=1", "localhost:3013"); w.Code == 200 {
		t.Fatal("disabled demo received open content")
	}
	s.workshopOpenDemoHost = workshopOpenDemoHost("1", "test", "https://demo.cars.tk")
	if w := request("/workshop/demo-mode.json", "demo.cars.tk"); w.Code != 200 || strings.TrimSpace(w.Body.String()) != `{"enabled":true,"access":"open"}` {
		t.Fatalf("external mode = %d %s", w.Code, w.Body.String())
	}
	for _, path := range []string{root + "?demo=1", root + "/" + id + "?demo=1", root + "?demo=1&q=private"} {
		if w := request(path, "demo.cars.tk"); w.Code != 200 {
			t.Fatalf("external demo %s = %d %s", path, w.Code, w.Body.String())
		}
	}
	if w := request(root+"?demo=1", "localhost:3013"); w.Code == 200 || grant.calls != 0 {
		t.Fatal("external demo accepted another Host or contacted the grant checker")
	}
}
func TestPaidCatalogPublicSelectorsAndDeniedBeforeWork(t *testing.T) {
	s, c, g := paidHTTPServer()
	for _, path := range []string{"/v1/catalog/years", "/v1/catalog/years/2024/makes", "/v1/catalog/years/2024/makes/acme/models", "/v1/catalog/years/2024/makes/acme/models/roadster/configurations"} {
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, httptest.NewRequest("GET", path, nil))
		if w.Code != 200 {
			t.Fatal(path, w.Code, w.Body.String())
		}
	}
	if g.calls != 0 || c.protected != 0 {
		t.Fatal("selectors reached protected work")
	}
	for _, suffix := range []string{"", "/55555555-5555-4555-8555-555555555555", "/55555555-5555-4555-8555-555555555555/source"} {
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles"+suffix, nil))
		if w.Code != 403 || w.Header().Get("Cache-Control") != "private, no-store" {
			t.Fatal(w.Code, w.Body.String())
		}
	}
	if c.protected != 0 {
		t.Fatal("unpaid request read content/progress")
	}
}
func TestPaidCatalogCustomerLegacyRoutesDenied(t *testing.T) {
	s, _, _ := paidHTTPServer()
	for _, route := range []string{"POST /dataset-requests", "GET /dataset-requests/x", "POST /vehicle-identities/resolve", "GET /vehicle-identities/selectors", "POST /knowledge-queries", "POST /job-plans", "GET /datasets/x", "GET /datasets/x/sections", "GET /datasets/x/revisions", "GET /datasets/x/evidence/x", "GET /datasets/x/search", "GET /datasets/x/knowledge", "POST /datasets/x/feedback"} {
		parts := strings.SplitN(route, " ", 2)
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, httptest.NewRequest(parts[0], parts[1], strings.NewReader("{}")))
		if w.Code != 403 || !strings.Contains(w.Body.String(), "CUSTOMER_ROUTE_UNAVAILABLE") {
			t.Fatal(route, w.Code, w.Body.String())
		}
	}
}

func TestPaidCatalogColdReadsDoNotScheduleAndDescriptorsHaveNoBodies(t *testing.T) {
	s, c, g := paidHTTPServer()
	g.err = nil
	id := "55555555-5555-4555-8555-555555555555"
	c.identity = PaidArticleIdentity{ConfigurationID: paidTestConfiguration, CanonicalArticleID: id, VehicleID: paidTestVehicle, ProviderSlug: "bankone", SourceVehicleRef: "opaque/vehicle", SourceArticleRef: "opaque/article"}
	c.view = &CatalogArticleView{Article: CatalogArticle{ID: id, CanonicalArticleID: &id, Availability: "unavailable"}, CanSchedule: true}
	c.PutArticle(CatalogArticle{ID: id, VehicleID: paidTestConfiguration, CanonicalArticleID: &id, Body: "private body", Images: []CatalogImage{{ID: "private-image"}}})
	c.PutArticle(CatalogArticle{ID: "legacy", VehicleID: paidTestConfiguration, Body: "legacy private"})
	ensure := &fakeIngestionClient{}
	s.ingestionClient = ensure
	for _, suffix := range []string{"", "/" + id} {
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles"+suffix, nil))
		want := 200
		if suffix != "" {
			want = 503
		}
		if w.Code != want {
			t.Fatal(w.Code, w.Body.String())
		}
		if suffix == "" && (strings.Contains(w.Body.String(), "private") || strings.Contains(w.Body.String(), "legacy")) {
			t.Fatal(w.Body.String())
		}
		if suffix == "" {
			var list CatalogArticlesResponse
			if err := json.Unmarshal(w.Body.Bytes(), &list); err != nil || list.Configuration == nil ||
				list.Configuration.ID != paidTestConfiguration || list.Configuration.Region != "CA" ||
				list.Configuration.Year != 2024 || list.Configuration.Model != "Roadster" {
				t.Fatalf("exact article index configuration missing: %s", w.Body)
			}
		}
	}
	if ensure.path != "" {
		t.Fatal("observational GET scheduled work")
	}
}
func TestPaidCatalogContentSearchUsesGrantAndReturnsOnlyMatchingDescriptors(t *testing.T) {
	s, c, g := paidHTTPServer()
	g.err = nil
	matchID := "55555555-5555-4555-8555-555555555555"
	otherID := "66666666-6666-4666-8666-666666666666"
	c.PutArticle(CatalogArticle{ID: matchID, VehicleID: paidTestConfiguration, CanonicalArticleID: &matchID,
		Title: "Service notes", Body: "Hidden compatibility body.", Document: &CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "Inspect the ground strap."}}}})
	c.PutArticle(CatalogArticle{ID: otherID, VehicleID: paidTestConfiguration, CanonicalArticleID: &otherID,
		Title: "Service notes", Body: "Check the coolant level."})

	w := httptest.NewRecorder()
	s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles?q=ground", nil))
	if w.Code != http.StatusOK {
		t.Fatal(w.Code, w.Body.String())
	}
	var result CatalogArticlesResponse
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if g.calls != 1 || c.searches != 1 || len(result.Items) != 1 || result.Items[0].ID != matchID {
		t.Fatalf("grant calls=%d searches=%d items=%+v", g.calls, c.searches, result.Items)
	}
	if result.Items[0].Body != "" || result.Items[0].Document != nil || len(result.Items[0].Steps) != 0 || len(result.Items[0].Images) != 0 || strings.Contains(w.Body.String(), "ground strap") {
		t.Fatal("paid content leaked in search descriptors", w.Body.String())
	}
	w = httptest.NewRecorder()
	s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles?q=service", nil))
	if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), matchID) || !strings.Contains(w.Body.String(), otherID) {
		t.Fatal("title search did not preserve paid descriptor matches", w.Code, w.Body.String())
	}

	g.err = ErrVehicleGrantRevoked
	c.protected, c.searches = 0, 0
	w = httptest.NewRecorder()
	s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles?q=ground", nil))
	if w.Code != http.StatusForbidden || c.protected != 0 || c.searches != 0 {
		t.Fatalf("revoked search read protected content: status=%d protected=%d searches=%d", w.Code, c.protected, c.searches)
	}
}

func TestPaidArticleDisplaysSourceBodyWhileFullCaptureRuns(t *testing.T) {
	const id = "55555555-5555-4555-8555-555555555555"
	const sourceText = "Disconnect the battery ground cable."
	s, store, grant := paidHTTPServer()
	grant.err = nil
	store.identity = PaidArticleIdentity{
		ConfigurationID: paidTestConfiguration, CanonicalArticleID: id, VehicleID: paidTestVehicle,
		ProviderSlug: "banktwo", SourceVehicleRef: "fixture-vehicle", SourceArticleRef: "fixture-article",
	}
	store.view = &CatalogArticleView{
		Article: CatalogArticle{
			ID: id, CanonicalArticleID: stringPointer(id), Title: "Battery", Availability: "pending",
			Processing: &CatalogProcessing{JobID: "fixture-job", State: "fetching_source"},
		},
		sourceBodyPreview: &CatalogDocument{SchemaVersion: 1, Blocks: []CatalogDocumentBlock{
			{Type: "callout", Label: "Warning", Text: sourceText, Href: "https://fixture.invalid/private-resource"},
		}},
	}
	path := "/v1/catalog/vehicles/" + paidTestConfiguration + "/articles/" + id
	read := func(path string, demo bool) *httptest.ResponseRecorder {
		w := httptest.NewRecorder()
		r := httptest.NewRequest(http.MethodGet, path, nil)
		if demo {
			r.Host = "localhost:3013"
		}
		s.Handler().ServeHTTP(w, r)
		return w
	}
	w := read(path, false)
	var result CatalogArticleResponse
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	body := result.Article
	if w.Code != http.StatusOK || w.Header().Get("Cache-Control") != "private, no-store" ||
		!body.SourceBodyPreview || body.ContentStatus != "content_partial" ||
		body.ContentOrigin == nil || *body.ContentOrigin != "source" ||
		body.SourceReview != nil || body.SourceRevisionID != nil || body.ViewRevision == nil ||
		body.Processing == nil || body.Processing.State != "fetching_source" ||
		body.Document == nil || len(body.Document.Blocks) != 1 ||
		body.Document.Blocks[0].Text != sourceText || body.Document.Blocks[0].Href != "" {
		t.Fatalf("incorrect source body response: %d %s", w.Code, w.Body)
	}
	s.workshopOpenDemoHost = workshopOpenDemoHost("1", "test", "http://localhost:3013")
	if w = read(path+"?demo=1", true); w.Code != http.StatusAccepted || strings.Contains(w.Body.String(), sourceText) {
		t.Fatalf("preview leaked into demo: %d %s", w.Code, w.Body)
	}
	grant.err = ErrVehicleGrantRevoked
	if w = read(path, false); w.Code != http.StatusForbidden || strings.Contains(w.Body.String(), sourceText) {
		t.Fatalf("preview leaked after revocation: %d %s", w.Code, w.Body)
	}
}

func TestPaidCatalogContentSearchRejectsUnboundedQueriesBeforeCatalogRead(t *testing.T) {
	s, c, g := paidHTTPServer()
	g.err = nil
	for _, suffix := range []string{
		"?q=one&q=two",
		"?q=" + strings.Repeat("a", 121),
		"?q=one+two+three+four+five+six+seven+eight+nine",
	} {
		c.protected, c.searches = 0, 0
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles"+suffix, nil))
		if w.Code != http.StatusUnprocessableEntity || c.protected != 0 || c.searches != 0 {
			t.Fatalf("query %q: status=%d protected=%d searches=%d", suffix, w.Code, c.protected, c.searches)
		}
	}
}
func TestPaidCatalogIndexReadinessHydration(t *testing.T) {
	for _, tc := range []struct {
		name                string
		progress            *CatalogArticleProgress
		complete, hydrating bool
	}{
		{"pending", &CatalogArticleProgress{Status: "pending"}, false, true},
		{"running", &CatalogArticleProgress{Status: "running"}, false, true},
		{"retryable failed", &CatalogArticleProgress{Status: "failed", Retryable: true}, false, true},
		{"terminal failed", &CatalogArticleProgress{Status: "failed"}, false, false},
		{"completed", &CatalogArticleProgress{Status: "completed", Complete: true}, true, false},
		{"nil", nil, false, false},
		{"complete overrides running", &CatalogArticleProgress{Status: "running", Complete: true}, true, false},
	} {
		for _, nonempty := range []bool{false, true} {
			t.Run(fmt.Sprintf("%s/nonempty=%t", tc.name, nonempty), func(t *testing.T) {
				s, c, g := paidHTTPServer()
				g.err = nil
				c.progress = tc.progress
				id := "55555555-5555-4555-8555-555555555555"
				if nonempty {
					c.PutArticle(CatalogArticle{ID: id, VehicleID: paidTestConfiguration, CanonicalArticleID: &id, Title: "Available descriptor", Body: "private body", Document: &CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "private document"}}}, Images: []CatalogImage{{ID: "private-image"}}, SourceReview: &CatalogSourceReview{URL: "private-source"}})
				}
				ensure := &fakeIngestionClient{}
				s.ingestionClient = ensure
				w := httptest.NewRecorder()
				s.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles", nil))
				if w.Code != http.StatusOK || w.Header().Get("Cache-Control") != "private, no-store" {
					t.Fatal(w.Code, w.Header(), w.Body.String())
				}
				var response CatalogArticlesResponse
				if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil {
					t.Fatal(err)
				}
				if response.Complete != tc.complete || response.Hydrating != tc.hydrating {
					t.Fatalf("complete=%t hydrating=%t, want complete=%t hydrating=%t: %s", response.Complete, response.Hydrating, tc.complete, tc.hydrating, w.Body.String())
				}
				wantCount := 0
				if nonempty {
					wantCount = 1
				}
				if len(response.Items) != wantCount {
					t.Fatal("partial descriptors lost", w.Body.String())
				}
				var wire map[string]json.RawMessage
				if err := json.Unmarshal(w.Body.Bytes(), &wire); err != nil {
					t.Fatal(err)
				}
				if _, exists := wire["complete"]; !exists {
					t.Fatal("missing explicit complete flag")
				}
				for _, item := range response.Items {
					if item.ID != id || item.Body != "" || item.Document != nil || len(item.Steps) != 0 || len(item.Images) != 0 || item.SourceReview != nil {
						t.Fatal("protected content in descriptor", w.Body.String())
					}
				}
				if strings.Contains(w.Body.String(), "private") || strings.Contains(w.Body.String(), "source_snapshot") || strings.Contains(w.Body.String(), "source_uri") {
					t.Fatal("protected source metadata", w.Body.String())
				}
				if ensure.path != "" {
					t.Fatal("paid collection GET scheduled ingestion")
				}
			})
		}
	}
}

func TestPaidCatalogPrepareBodyOriginAndNoAcknowledgement(t *testing.T) {
	s, c, g := paidHTTPServer()
	g.err = nil
	id := "55555555-5555-4555-8555-555555555555"
	c.identity = PaidArticleIdentity{ConfigurationID: paidTestConfiguration, CanonicalArticleID: id, VehicleID: paidTestVehicle, ProviderSlug: "bankone", SourceVehicleRef: "opaque/vehicle", SourceArticleRef: "opaque/article"}
	c.view = &CatalogArticleView{Article: CatalogArticle{ID: id, CanonicalArticleID: &id, Availability: "unavailable"}, CanSchedule: true}
	now := time.Now()
	token, _, _ := newCustomerSessionToken()
	service := &customerAuthService{config: customerAuthConfig{Mode: "firebase", Origin: "https://cars.example"}, store: &customerSessionFixture{session: customerSession{AccountID: "11111111-1111-4111-8111-111111111111", OrganizationID: "22222222-2222-4222-8222-222222222222", ProjectID: "fixture-project", UID: "user", AuthTime: now.Unix(), ExpiresAt: now.Add(time.Hour)}}, verifier: &customerVerifierFixture{}}
	s.customerAuth, s.auth = service, service
	path := "/v1/catalog/vehicles/" + paidTestConfiguration + "/articles/" + id
	for _, tc := range []struct {
		body, origin string
		want         int
	}{{"{}", "https://foreign.example", 403}, {"null", "https://cars.example", 400}, {"[]", "https://cars.example", 400}, {"{\"source_uri\":\"https://private.example\"}", "https://cars.example", 400}, {"{} {}", "https://cars.example", 400}, {strings.Repeat(" ", 2049), "https://cars.example", 413}, {"{}", "https://cars.example", 503}} {
		r := httptest.NewRequest("POST", path+"/prepare", strings.NewReader(tc.body))
		r.AddCookie(customerSessionCookie(token, now.Add(time.Hour), now))
		r.Header.Set("Origin", tc.origin)
		r.Header.Set("X-CSRF-Token", customerCSRF(token))
		r.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, r)
		if w.Code != tc.want {
			t.Fatal(tc.body, w.Code, w.Body.String())
		}
	}
	ensure := &fakeIngestionClient{status: http.StatusAccepted}
	s.ingestionClient = ensure
	want := CatalogConfiguration{ID: paidTestConfiguration, VehicleID: paidTestVehicle, Region: "CA", Year: 2024, Make: "Acme", Model: "Roadster", Complete: true}
	for _, tc := range []struct {
		method, availability string
		want                 int
	}{
		{http.MethodPost, "available", http.StatusOK},
		{http.MethodPost, "pending", http.StatusAccepted},
		{http.MethodGet, "available", http.StatusOK},
		{http.MethodGet, "pending", http.StatusAccepted},
	} {
		// A GET with a schedulable view must still be strictly observational.
		c.view.CanSchedule = tc.method == http.MethodGet
		c.view.Article.Availability = tc.availability
		c.view.Article.Processing = &CatalogProcessing{JobID: "fixture", State: "queued"}
		target := path
		if tc.method == http.MethodPost {
			target += "/prepare"
		}
		r := httptest.NewRequest(tc.method, target+"?region=CA", strings.NewReader("{}"))
		r.AddCookie(customerSessionCookie(token, now.Add(time.Hour), now))
		r.Header.Set("Origin", "https://cars.example")
		r.Header.Set("X-CSRF-Token", customerCSRF(token))
		r.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, r)
		var response CatalogArticleResponse
		if w.Code != tc.want || json.Unmarshal(w.Body.Bytes(), &response) != nil {
			t.Fatalf("%s %s status=%d body=%s", tc.method, tc.availability, w.Code, w.Body.String())
		}
		if response.Configuration == nil || *response.Configuration != want {
			t.Fatalf("%s returned configuration %#v, want %#v", tc.method, response.Configuration, want)
		}
	}
	for _, tc := range []struct {
		path  string
		owner bool
		grant error
		want  int
	}{
		{path, false, nil, http.StatusUnauthorized},
		{path + "?region=US", true, nil, http.StatusNotFound},
		{path, true, ErrVehicleGrantRevoked, http.StatusForbidden},
		{strings.Replace(path, paidTestConfiguration, paidTestVehicle, 1), true, nil, http.StatusNotFound},
	} {
		g.err = tc.grant
		r := httptest.NewRequest(http.MethodGet, tc.path, nil)
		if tc.owner {
			r.AddCookie(customerSessionCookie(token, now.Add(time.Hour), now))
		}
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, r)
		if w.Code != tc.want || strings.Contains(w.Body.String(), `"configuration":`) || strings.Contains(w.Body.String(), "Roadster") {
			t.Fatalf("denied detail status=%d want=%d body=%s", w.Code, tc.want, w.Body.String())
		}
	}
	if ensure.path != "" {
		t.Fatal("observational detail GET scheduled work")
	}
}
func TestPaidCatalogProductionDependenciesFailClosed(t *testing.T) {
	s, _, _ := paidHTTPServer()
	if s.validatePaidCatalogDependencies() == nil {
		t.Fatal("memory catalog accepted as production dependency")
	}
	w := httptest.NewRecorder()
	s.Handler().ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/readyz", nil))
	if w.Code != 503 {
		t.Fatal("incomplete paid runtime ready")
	}
	s.customerAuth = nil
	if s.validatePaidCatalogDependencies() != nil {
		t.Fatal("explicit local injection lost compatibility")
	}
}

func TestPaidHTTPObservationPreservesEvidenceAndRedactsCapabilitiesConcurrently(t *testing.T) {
	f := &paidFixture{reader: &paidFixtureReader{}, verifier: &paidFixtureVerifier{}}
	const token = "v2.synthetic-private-capability"
	raw := []byte(`{"images":[{"url":"/v1/catalog/images/` + token + `"}],"unexpected_private_field":"must-remain-visible"}`)
	headers := http.Header{"Content-Type": []string{"application/json"}, "Cache-Control": []string{"private, no-store"}, "Set-Cookie": []string{"secret-cookie"}}
	var wg sync.WaitGroup
	for range 32 {
		wg.Add(1)
		go func() { defer wg.Done(); f.observe(0, "GET", "/v1/catalog/images/"+token, 200, headers, raw, 0, 0) }()
	}
	wg.Wait()
	if len(f.observations) != 32 {
		t.Fatal("lost concurrent HTTP receipts")
	}
	encoded, err := json.Marshal(f.observations)
	if err != nil || strings.Contains(string(encoded), token) || strings.Contains(string(encoded), "secret-cookie") || !strings.Contains(string(encoded), "must-remain-visible") || !strings.Contains(string(encoded), "[sha256:") {
		t.Fatal("HTTP evidence lost fields or leaked a capability")
	}
	for _, observation := range f.observations {
		if observation.BodySize != len(raw) || len(observation.BodySHA256) != 64 || observation.Headers["Cache-Control"] != "private, no-store" || observation.BodyTruncated {
			t.Fatal("HTTP receipt integrity lost")
		}
	}
}
