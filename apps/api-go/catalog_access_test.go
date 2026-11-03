package main

import (
	"context"
	"encoding/json"
	"errors"
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
	identity  PaidArticleIdentity
	view      *CatalogArticleView
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
	return nil, nil
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
	}
	if ensure.path != "" {
		t.Fatal("observational GET scheduled work")
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
	for _, tc := range []struct {
		body, origin string
		want         int
	}{{"{}", "https://foreign.example", 403}, {"null", "https://cars.example", 400}, {"[]", "https://cars.example", 400}, {"{\"source_uri\":\"https://private.example\"}", "https://cars.example", 400}, {"{} {}", "https://cars.example", 400}, {strings.Repeat(" ", 2049), "https://cars.example", 413}, {"{}", "https://cars.example", 503}} {
		r := httptest.NewRequest("POST", "/v1/catalog/vehicles/"+paidTestConfiguration+"/articles/"+id+"/prepare", strings.NewReader(tc.body))
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
