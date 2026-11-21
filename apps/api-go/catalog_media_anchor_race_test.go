package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type paidMediaRaceStore struct {
	*paidMediaCatalog
	beforeArticleView  func()
	beforeImageView    func()
	configurationReads int
}

func (c *paidMediaRaceStore) ConfigurationByVehicle(ctx context.Context, principal Principal, configuration string) (CatalogConfiguration, error) {
	c.configurationReads++
	return c.paidMediaCatalog.ConfigurationByVehicle(ctx, principal, configuration)
}

func (c *paidMediaRaceStore) ArticleView(ctx context.Context, principal Principal, configuration, article string) (CatalogArticleView, error) {
	if c.beforeArticleView != nil {
		c.beforeArticleView()
		c.beforeArticleView = nil
	}
	return c.paidMediaCatalog.ArticleView(ctx, principal, configuration, article)
}

func (c *paidMediaRaceStore) paidCatalogImageView(ctx context.Context, configuration, article, revision string, _ bool) (CatalogArticleView, []CatalogImage, error) {
	if c.beforeImageView != nil {
		c.beforeImageView()
		c.beforeImageView = nil
	}
	source, err := c.paidMediaCatalog.ArticleSourceRevision(ctx, Principal{}, configuration, article, revision)
	return c.view, source.Images, err
}

type paidMediaRaceIngestion struct {
	ensure func()
}

func (c paidMediaRaceIngestion) Do(request *http.Request, path string, body []byte, key string) (int, []byte, error) {
	if path != "/v1/catalog/ensure" || len(body) == 0 || key == "" {
		return 0, nil, errors.New("unexpected fixture ingestion request")
	}
	if err := request.Context().Err(); err != nil {
		return 0, nil, err
	}
	c.ensure()
	return http.StatusAccepted, []byte("{\"job_id\":\"fixture-job\"}"), nil
}

func paidMediaRaceRequest(t *testing.T, s *Server, p Principal, ref paidCatalogImageReference, method string) *http.Request {
	t.Helper()
	now := time.Now()
	token, _, err := newCustomerSessionToken()
	if err != nil {
		t.Fatal(err)
	}
	auth := &customerAuthService{config: customerAuthConfig{Mode: "firebase", Origin: "https://cars.example"},
		store: &customerSessionFixture{session: customerSession{AccountID: p.CustomerAccountID, OrganizationID: p.OrganizationID,
			ProjectID: "fixture-project", UID: "fixture-user", AuthTime: now.Unix(), ExpiresAt: now.Add(time.Hour)}},
		verifier: &customerVerifierFixture{}}
	s.customerAuth, s.auth = auth, auth
	path := "/v1/catalog/vehicles/" + ref.ConfigurationID + "/articles/" + ref.CanonicalArticleID
	body := ""
	if method == http.MethodPost {
		path += "/prepare"
		body = "{}"
	}
	request := httptest.NewRequest(method, path, strings.NewReader(body))
	request.AddCookie(customerSessionCookie(token, now.Add(time.Hour), now))
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Origin", "https://cars.example")
	request.Header.Set("X-CSRF-Token", customerCSRF(token))
	request.Header.Set("Prefer", shortSourceCheckPreference)
	return request
}

func TestPaidCatalogArticleRetainsFiguresWhenSourceArrivesDuringRequest(t *testing.T) {
	for _, tc := range []struct {
		name, method   string
		previousSource *string
	}{
		{"first source during prepare", http.MethodPost, nil},
		{"first source during read", http.MethodGet, nil},
		{"replacement source during read", http.MethodGet, stringPointer("99999999-9999-4999-8999-999999999999")},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, c, g, reader, p, ref := paidMediaFixture()
			store := &paidMediaRaceStore{paidMediaCatalog: c}
			s.catalog = store
			initialIdentity, ready := c.identity, c.view
			ready.Article.CanonicalRevisionID = nil
			ready.Article.ContentOrigin = stringPointer("source")
			ready.Article.Document = c.source.Document
			c.identity.CurrentSourceRevisionID = tc.previousSource
			c.view = CatalogArticleView{CanSchedule: true, Article: CatalogArticle{
				ID: ref.CanonicalArticleID, CanonicalArticleID: stringPointer(ref.CanonicalArticleID), Availability: "unavailable",
			}}
			capture := func() {
				c.identity = initialIdentity
				c.view = ready
			}
			wantGrants, wantViews := int32(2), int32(1)
			if tc.method == http.MethodPost {
				s.ingestionClient = paidMediaRaceIngestion{ensure: capture}
				wantGrants, wantViews = 3, 2
			} else {
				store.beforeArticleView = capture
			}
			request := paidMediaRaceRequest(t, s, p, ref, tc.method)
			response := httptest.NewRecorder()
			s.Handler().ServeHTTP(response, request)
			if response.Code != http.StatusOK || response.Header().Get("Preference-Applied") != "" {
				t.Fatalf("status=%d, want 200", response.Code)
			}
			var result CatalogArticleResponse
			if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
				t.Fatal(err)
			}
			if len(result.Article.Images) != 1 || !strings.HasPrefix(result.Article.Images[0].URL, "/v1/catalog/images/v2.") ||
				len(result.Article.Steps) != 1 || result.Article.Steps[0].Images == nil || len(*result.Article.Steps[0].Images) != 1 ||
				!strings.HasPrefix((*result.Article.Steps[0].Images)[0].URL, "/v1/catalog/images/v2.") {
				t.Fatal("first readable source lacks scoped top-level or step figures")
			}
			if g.calls.Load() != wantGrants || c.viewCalls.Load() != wantViews || c.identityCalls.Load() != 2 || store.configurationReads != 2 || c.sourceCalls.Load() != 1 {
				t.Fatal("cold source recovery did not perform a single recheck")
			}
			figure := result.Article.Images[0].URL
			capability, err := openPaidCatalogImageReference(strings.TrimPrefix(figure, "/v1/catalog/images/"), s.catalogImageKey, time.Now())
			if err != nil || capability.AnchorSourceRevisionID != ref.SelectedSourceRevisionID ||
				capability.SelectedSourceRevisionID != ref.SelectedSourceRevisionID || capability.AnchorCanonicalRevisionID != nil ||
				capability.CustomerAccountID != p.CustomerAccountID || capability.ConfigurationID != ref.ConfigurationID ||
				capability.Region != ref.Region || capability.ProviderSlug != ref.ProviderSlug {
				t.Fatal("figure did not bind the first retained source", err)
			}
			imageRequest := httptest.NewRequest(http.MethodGet, figure, nil)
			imageRequest.Header.Set("Cookie", request.Header.Get("Cookie"))
			imageResponse := httptest.NewRecorder()
			s.Handler().ServeHTTP(imageResponse, imageRequest)
			if imageResponse.Code != http.StatusOK || reader.calls.Load() != 1 {
				t.Fatalf("enrolled reader could not fetch the rebound figure, status %d", imageResponse.Code)
			}
			g.err = ErrVehicleGrantRevoked
			imageResponse = httptest.NewRecorder()
			s.Handler().ServeHTTP(imageResponse, imageRequest)
			if imageResponse.Code != http.StatusForbidden || reader.calls.Load() != 1 {
				t.Fatal("revocation did not deny the rebound figure before storage")
			}
		})
	}
}

func TestPaidCatalogArticleRechecksChangedMediaScope(t *testing.T) {
	for _, tc := range []struct {
		name        string
		status      int
		grantCalls  int32
		sourceCalls int32
		change      func(*paidMediaRaceStore, *paidMediaGrant, context.CancelFunc)
	}{
		{"revoked grant", 403, 2, 1, func(_ *paidMediaRaceStore, grant *paidMediaGrant, _ context.CancelFunc) {
			grant.err = ErrVehicleGrantRevoked
		}},
		{"changed region", 404, 1, 0, func(store *paidMediaRaceStore, _ *paidMediaGrant, _ context.CancelFunc) {
			store.configuration.Region = "CA"
		}},
		{"changed vehicle", 404, 1, 0, func(store *paidMediaRaceStore, _ *paidMediaGrant, _ context.CancelFunc) {
			store.identity.VehicleID = "99999999-9999-4999-8999-999999999999"
			store.configuration.VehicleID = store.identity.VehicleID
		}},
		{"changed provider", 404, 1, 0, func(store *paidMediaRaceStore, _ *paidMediaGrant, _ context.CancelFunc) {
			store.identity.ProviderSlug = "banktwo"
		}},
		{"changed provider reference", 404, 1, 0, func(store *paidMediaRaceStore, _ *paidMediaGrant, _ context.CancelFunc) {
			store.identity.SourceArticleRef = "changed-provider-article"
		}},
		{"withdrawn projection", 410, 1, 1, func(store *paidMediaRaceStore, _ *paidMediaGrant, _ context.CancelFunc) {
			store.beforeImageView = func() { store.sourceErr = ErrCatalogWithdrawn }
		}},
		{"changed source projection", 404, 1, 1, func(store *paidMediaRaceStore, _ *paidMediaGrant, _ context.CancelFunc) {
			store.beforeImageView = func() { store.view.Article.SourceRevisionID = stringPointer("99999999-9999-4999-8999-999999999999") }
		}},
		{"changed canonical projection", 404, 1, 1, func(store *paidMediaRaceStore, _ *paidMediaGrant, _ context.CancelFunc) {
			store.beforeImageView = func() { store.view.Article.CanonicalRevisionID = stringPointer("99999999-9999-4999-8999-999999999999") }
		}},
		{"canceled request", 503, 1, 0, func(_ *paidMediaRaceStore, _ *paidMediaGrant, cancel context.CancelFunc) { cancel() }},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, c, grant, reader, principal, ref := paidMediaFixture()
			store := &paidMediaRaceStore{paidMediaCatalog: c}
			s.catalog = store
			initial := c.identity
			c.identity.CurrentSourceRevisionID = nil
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			store.beforeArticleView = func() {
				c.identity = initial
				tc.change(store, grant, cancel)
			}
			request := paidMediaRaceRequest(t, s, principal, ref, http.MethodGet).WithContext(ctx)
			response := httptest.NewRecorder()
			s.Handler().ServeHTTP(response, request)
			if response.Code != tc.status {
				t.Fatalf("status=%d, want %d", response.Code, tc.status)
			}
			if grant.calls.Load() != tc.grantCalls || c.sourceCalls.Load() != tc.sourceCalls ||
				reader.calls.Load() != 0 || strings.Contains(response.Body.String(), "/v1/catalog/images/") {
				t.Fatal("changed media scope reached an unauthorized or repeated check")
			}
		})
	}
}

func TestPaidCatalogArticleKeepsStableMediaReadCost(t *testing.T) {
	s, c, grant, _, principal, ref := paidMediaFixture()
	store := &paidMediaRaceStore{paidMediaCatalog: c}
	s.catalog = store
	response := httptest.NewRecorder()
	s.Handler().ServeHTTP(response, paidMediaRaceRequest(t, s, principal, ref, http.MethodGet))
	if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), "/v1/catalog/images/v2.") {
		t.Fatal("stable article failed to mint figures")
	}
	if grant.calls.Load() != 1 || c.sourceCalls.Load() != 1 || c.identityCalls.Load() != 1 || c.viewCalls.Load() != 1 || store.configurationReads != 1 {
		t.Fatal("stable article performed extra reads")
	}
}

func TestPaidCatalogArticleFinishPublishedBodyPreference(t *testing.T) {
	for _, tc := range []struct {
		name, method, region, origin, state string
		prefer, applied, retry              string
		status                              int
		demo, emptyDocument, explicitRetry  bool
	}{
		{name: "terminal publication", origin: "canonical", state: "completed", prefer: finishPublishedBodyPreference, applied: finishPublishedBodyPreference, status: 200},
		{name: "published without a job", origin: "canonical", prefer: "other, " + finishPublishedBodyPreference, applied: finishPublishedBodyPreference, status: 200},
		{name: "published without preference", origin: "canonical", status: 200},
		{name: "published without readable blocks", origin: "canonical", emptyDocument: true, prefer: finishPublishedBodyPreference, status: 200},
		{name: "published with active refresh", origin: "canonical", state: "rewriting", prefer: finishPublishedBodyPreference, retry: "2", status: 200},
		{name: "explicit retry hint", origin: "canonical", state: "completed", explicitRetry: true, prefer: finishPublishedBodyPreference, retry: "5", status: 200},
		{name: "stored source", origin: "source", state: "rewriting", prefer: finishPublishedBodyPreference, retry: "1", status: 200},
		{name: "stored source short check", origin: "source", state: "rewriting", prefer: finishPublishedBodyPreference + ", " + shortPublicationCheckPreference, applied: shortPublicationCheckPreference, status: 200},
		{name: "pending", state: "fetching_source", prefer: finishPublishedBodyPreference, retry: "1", status: 202},
		{name: "pending short check", state: "fetching_source", prefer: finishPublishedBodyPreference + ", " + shortSourceCheckPreference, applied: shortSourceCheckPreference, status: 202},
		{name: "wrong region", origin: "canonical", region: "CA", prefer: finishPublishedBodyPreference, status: 404},
		{name: "prepare", method: http.MethodPost, origin: "canonical", prefer: finishPublishedBodyPreference, status: 200},
		{name: "OpenDemo", origin: "canonical", demo: true, prefer: finishPublishedBodyPreference, status: 200},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, catalog, grant, _, principal, ref := paidMediaFixture()
			article := catalog.view.Article
			if tc.origin == "" {
				article.Availability = "unavailable"
			} else {
				article.ContentOrigin = stringPointer(tc.origin)
				if !tc.emptyDocument {
					article.Document = &CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "Remove pump."}}}
				}
			}
			if tc.origin != "canonical" {
				article.CanonicalRevisionID = nil
			}
			if tc.state != "" {
				article.Processing = &CatalogProcessing{JobID: "fixture-job", State: tc.state}
				if tc.explicitRetry {
					retry := 5
					article.Processing.RetryAfterSeconds = &retry
				}
			}
			catalog.view.Article = lifecycleArticle(article)
			method := tc.method
			if method == "" {
				method = http.MethodGet
			}
			request := paidMediaRaceRequest(t, s, principal, ref, method)
			request.Header.Del("Prefer")
			if tc.prefer != "" {
				request.Header.Set("Prefer", tc.prefer)
			}
			if tc.region != "" {
				request.URL.RawQuery = "region=" + tc.region
			}
			if tc.demo {
				s.workshopOpenDemoHost = request.Host
				request.URL.RawQuery = "demo=1"
			}
			response := httptest.NewRecorder()
			s.Handler().ServeHTTP(response, request)
			if response.Code != tc.status || response.Header().Get("Preference-Applied") != tc.applied || response.Header().Get("Retry-After") != tc.retry {
				t.Fatalf("unexpected status %d, preference %q, retry %q", response.Code, response.Header().Get("Preference-Applied"), response.Header().Get("Retry-After"))
			}
			if tc.applied == finishPublishedBodyPreference && (grant.calls.Load() != 1 || catalog.sourceCalls.Load() != 1 ||
				!strings.Contains(response.Body.String(), "Remove pump.") || !strings.Contains(response.Body.String(), "/v1/catalog/images/v2.")) {
				t.Fatal("published success bypassed scope/media or omitted readable content")
			}
		})
	}
}
