package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type paidFixtureVerifier struct {
	calls atomic.Int64
	mu    sync.Mutex
	err   error
}

func (v *paidFixtureVerifier) VerifyLogin(context.Context, string) (VerifiedCustomerIdentity, error) {
	return VerifiedCustomerIdentity{}, errors.New("fixture does not exchange credentials")
}
func (v *paidFixtureVerifier) CheckUser(context.Context, string, string, int64) error {
	v.calls.Add(1)
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.err
}

type paidFixtureReader struct {
	delegate catalogImageObjectReader
	calls    atomic.Int64
}

func (r *paidFixtureReader) ReadImage(ctx context.Context, key string) ([]byte, string, error) {
	r.calls.Add(1)
	return r.delegate.ReadImage(ctx, key)
}

type paidFixtureOwner struct {
	token   string
	session customerSession
}
type paidHTTPObservation struct {
	Method         string            `json:"method"`
	Path           string            `json:"path"`
	OwnerIndex     int               `json:"owner_index"`
	Status         int               `json:"status"`
	Headers        map[string]string `json:"headers"`
	Body           any               `json:"body,omitempty"`
	BodySHA256     string            `json:"body_sha256"`
	BodySize       int               `json:"body_size"`
	BodyTruncated  bool              `json:"body_truncated"`
	ReaderBefore   int64             `json:"reader_before"`
	ReaderAfter    int64             `json:"reader_after"`
	IdentityBefore int64             `json:"identity_before"`
	IdentityAfter  int64             `json:"identity_after"`
}

type paidFixture struct {
	observationMu                                                                             sync.Mutex
	observations                                                                              []paidHTTPObservation
	heldModelReceipt                                                                          map[string]any
	t                                                                                         *testing.T
	pool                                                                                      *pgxpool.Pool
	control                                                                                   *r3Fixture
	servers                                                                                   []*httptest.Server
	applications                                                                              []*Server
	owners                                                                                    []paidFixtureOwner
	verifier                                                                                  *paidFixtureVerifier
	reader                                                                                    *paidFixtureReader
	configuration, adjacent, regionConfiguration, vehicle, article, other, unscoped, provider string
	assertions                                                                                map[string]bool
	phases                                                                                    map[string]any
	views                                                                                     []CatalogArticle
}

func paidSetup(t *testing.T) *paidFixture {
	t.Helper()
	if os.Getenv("AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION") != "1" {
		t.Skip("requires isolated paid catalog runtime")
	}
	if os.Getenv("AUTODATA_LIFECYCLE_TEST") != "1" || os.Getenv("AUTODATA_CATALOG_INTEGRATION_REQUIRED") != "1" {
		t.Fatal("required lifecycle/catalog flags missing")
	}
	dsn := os.Getenv("AUTODATA_CATALOG_TEST_DSN")
	u, err := url.Parse(dsn)
	if err != nil || u.Scheme != "postgres" || u.Host != "postgres:5432" || u.User == nil || u.User.Username() != "lifecycle_test" || u.Query().Get("sslmode") != "disable" || len(u.Query()) != 1 || !regexp.MustCompile(`^/lifecycle_test_[a-f0-9]{32}$`).MatchString(u.Path) {
		t.Fatal("isolated fixture DSN required")
	}
	password, ok := u.User.Password()
	if !ok || password != "lifecycle_test_only" {
		t.Fatal("fixture credential mismatch")
	}
	f := &paidFixture{t: t, configuration: os.Getenv("AUTODATA_PAID_TEST_CONFIGURATION_ID"), adjacent: os.Getenv("AUTODATA_PAID_TEST_ADJACENT_CONFIGURATION_ID"), regionConfiguration: os.Getenv("AUTODATA_PAID_TEST_REGION_CONFIGURATION_ID"), vehicle: os.Getenv("AUTODATA_CATALOG_TEST_VEHICLE_ID"), article: os.Getenv("AUTODATA_CATALOG_TEST_ARTICLE_ID"), other: os.Getenv("AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID"), unscoped: os.Getenv("AUTODATA_PAID_TEST_UNSCOPED_ARTICLE_ID"), provider: os.Getenv("AUTODATA_CATALOG_TEST_PROVIDER"), assertions: map[string]bool{}, phases: map[string]any{}}
	for _, id := range []string{f.configuration, f.adjacent, f.regionConfiguration, f.vehicle, f.article, f.other, f.unscoped} {
		if !commerceUUID(id) {
			t.Fatal("fixture canonical UUID required")
		}
	}
	if f.provider != "bankone" && f.provider != "banktwo" {
		t.Fatal("fixture provider invalid")
	}
	if !regexp.MustCompile(`^[a-f0-9]{40}$`).MatchString(os.Getenv("AUTODATA_CATALOG_TEST_CANDIDATE_SHA")) {
		t.Fatal("candidate SHA required")
	}
	ensureURL, controlURL := os.Getenv("AUTODATA_CATALOG_TEST_ENSURE_URL"), os.Getenv("AUTODATA_CATALOG_TEST_CONTROL_URL")
	for _, raw := range []string{ensureURL, controlURL} {
		target, e := url.Parse(raw)
		if e != nil || target.Scheme != "http" || target.Hostname() != "127.0.0.1" || target.Port() == "" || target.User != nil || target.Path != "" || target.RawQuery != "" || target.Fragment != "" {
			t.Fatal("only loopback fixture HTTP permitted")
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	f.pool, err = pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(f.pool.Close)
	if err = f.pool.Ping(ctx); err != nil {
		t.Fatal(err)
	}
	store := &postgresCustomerSessions{pool: f.pool}
	if err = store.CheckSchema(ctx); err != nil {
		t.Fatal(err)
	}
	f.verifier = &paidFixtureVerifier{}
	f.reader = &paidFixtureReader{delegate: configuredCatalogImageReader()}
	if f.reader.delegate == nil {
		t.Fatal("real fixture S3 reader required")
	}
	now := time.Now().UTC()
	for _, uid := range []string{"paid-owner-a", "paid-owner-b"} {
		token, hash, e := newCustomerSessionToken()
		if e != nil {
			t.Fatal(e)
		}
		session, e := store.Rotate(ctx, VerifiedCustomerIdentity{ProjectID: "fixture-project", UID: uid, AuthTime: now.Unix(), IssuedAt: now.Unix(), Expires: now.Add(time.Hour).Unix()}, hash, nil, now, now.Add(time.Hour))
		if e != nil {
			t.Fatal(e)
		}
		f.owners = append(f.owners, paidFixtureOwner{token: token, session: session})
	}
	commerce, e := NewHTTPCommerceClient(ensureURL, "fixture-r3-internal")
	if e != nil {
		t.Fatal(e)
	}
	ingestion, e := NewHTTPIngestionClient(ensureURL, "fixture-r3-internal", 2*time.Second)
	if e != nil {
		t.Fatal(e)
	}
	for range 2 {
		auth := &customerAuthService{config: customerAuthConfig{Environment: "test", Mode: "firebase", Origin: "https://cars.example"}, store: store, verifier: f.verifier}
		server := NewServerWithCatalogStore(staticReadiness{}, auth, newMemoryRequestStore(), newPostgresCatalogStore(f.pool))
		server.customerAuth = auth
		server.commerceClient = commerce
		server.ingestionClient = ingestion
		server.catalogImageKey = deriveCatalogImageReferenceKey(strings.Repeat("paid-fixture-key-", 3))
		server.catalogImageReader = f.reader
		if server.validatePaidCatalogDependencies() != nil {
			t.Fatal("actual paid fixture dependency wiring invalid")
		}
		api := httptest.NewTLSServer(server.Handler())
		f.servers = append(f.servers, api)
		f.applications = append(f.applications, server)
		t.Cleanup(api.Close)
	}
	f.control = &r3Fixture{t: t, pool: f.pool, control: controlURL, token: os.Getenv("AUTODATA_CATALOG_TEST_CONTROL_TOKEN")}
	if f.control.token == "" {
		t.Fatal("control token required")
	}
	t.Cleanup(func() {
		if t.Failed() {
			request, _ := http.NewRequest("GET", f.control.control+"/r3-fixture/snapshot", nil)
			request.Header.Set("X-R3-Fixture-Token", f.control.token)
			client := http.Client{Timeout: 2 * time.Second}
			if response, err := client.Do(request); err == nil {
				var snapshot map[string]any
				if response.StatusCode == 200 && json.NewDecoder(io.LimitReader(response.Body, 8<<20)).Decode(&snapshot) == nil {
					snapshot["reader_calls"] = f.reader.calls.Load()
					snapshot["identity_checks"] = f.verifier.calls.Load()
					f.phases["failure"] = snapshot
				}
				response.Body.Close()
			}
		}
		raw, _ := json.MarshalIndent(map[string]any{"phase_snapshots": f.phases, "assertion_results": f.assertions, "observed_views": f.views, "identity_checks": f.verifier.calls.Load(), "reader_calls": f.reader.calls.Load(), "http_observations": f.observations, "held_model_receipt": f.heldModelReceipt}, "", "  ")
		if err := os.WriteFile(filepath.Join(os.Getenv("AUTODATA_CATALOG_TEST_CASE_DIR"), "go-measurement.json"), raw, 0644); err != nil {
			t.Error(err)
		}
	})
	return f
}
func (f *paidFixture) exec(sql string, args ...any) {
	f.t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if _, err := f.pool.Exec(ctx, sql, args...); err != nil {
		f.t.Fatal(err)
	}
}
func (f *paidFixture) uuid() string {
	id, err := newRequestID()
	if err != nil {
		f.t.Fatal(err)
	}
	return id
}
func (f *paidFixture) grant(owner int, configuration, region string) string {
	f.t.Helper()
	o := f.owners[owner].session
	order, request, entitlement := f.uuid(), f.uuid(), f.uuid()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	tx, err := f.pool.Begin(ctx)
	if err != nil {
		f.t.Fatal(err)
	}
	defer tx.Rollback(ctx)
	statements := []struct {
		q    string
		args []any
	}{
		{`INSERT INTO workshop_orders(order_id,customer_account_id,organization_id,configuration_id,region,dataset_product_id,terms_version,amount_minor,currency,stripe_account_id,livemode,expected_price_id,provider_idempotency_key,status,first_create_attempt_at,paid_at) SELECT $1::uuid,$2::uuid,$3::uuid,$4::uuid,$5,dataset_product_id,'workshop-v1',2000,'USD','acct_fixture',false,'price_fixture',$6,'paid',now(),now() FROM dataset_products WHERE product_key='workshop-configuration-v1' AND product_version=1`, []any{order, o.AccountID, o.OrganizationID, configuration, region, "fixture:" + order}},
		{`INSERT INTO dataset_requests(dataset_request_id,dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id) SELECT $1::uuid,dataset_product_id,$2,$3,'purchased','fast',$4::uuid,$5,'workshop-v1',$6::uuid FROM dataset_products WHERE product_key='workshop-configuration-v1' AND product_version=1`, []any{request, configuration, region, order, "fixture:" + request, o.OrganizationID}},
		{`INSERT INTO entitlements(entitlement_id,organization_id,dataset_request_id,provider_event_id,status,granted_at,customer_account_id,configuration_id,region,commerce_order_id) VALUES($1::uuid,$2::uuid,$3::uuid,$4,'active',now(),$5::uuid,$6::uuid,$7,$8::uuid)`, []any{entitlement, o.OrganizationID, request, "fixture:" + entitlement, o.AccountID, configuration, region, order}},
		{`INSERT INTO dataset_projections(dataset_projection_id,dataset_product_id,dataset_request_id,entitlement_id) SELECT gen_random_uuid(),dataset_product_id,$1::uuid,$2::uuid FROM dataset_requests WHERE dataset_request_id=$1::uuid`, []any{request, entitlement}},
		{`UPDATE workshop_orders SET entitlement_id=$1::uuid,dataset_request_id=$2::uuid WHERE order_id=$3::uuid`, []any{entitlement, request, order}},
	}
	for _, s := range statements {
		if _, err = tx.Exec(ctx, s.q, s.args...); err != nil {
			f.t.Fatal(err)
		}
	}
	if err = tx.Commit(ctx); err != nil {
		f.t.Fatal(err)
	}
	return order
}
func (f *paidFixture) path(suffix string) string {
	return "/v1/catalog/vehicles/" + f.configuration + "/articles" + suffix
}

func (f *paidFixture) contentSearch(owner int, query string) CatalogArticlesResponse {
	f.t.Helper()
	var response CatalogArticlesResponse
	if err := json.Unmarshal(f.expect(owner, "GET", f.path("?q="+url.QueryEscape(query)), "", 200), &response); err != nil {
		f.t.Fatal("content search JSON invalid:", err)
	}
	for _, item := range response.Items {
		if item.Body != "" || item.Document != nil || len(item.Steps) != 0 || len(item.Images) != 0 || item.SourceReview != nil || item.CanonicalArticleID == nil || *item.CanonicalArticleID != item.ID {
			f.t.Fatal("content search returned a content-bearing or unmanaged descriptor")
		}
	}
	return response
}

// Superseded-term checks exercise the current Postgres projection directly so
// the guarded HTTP observation inventory remains an exact, independent oracle.
func (f *paidFixture) supersededTermAbsent(query string) bool {
	f.t.Helper()
	store, ok := f.applications[0].catalog.(*postgresCatalogStore)
	if !ok {
		f.t.Fatal("paid fixture catalog store missing")
	}
	items, err := store.PaidArticleSearchDescriptors(context.Background(), Principal{}, f.configuration, query)
	if err != nil {
		f.t.Fatal(err)
	}
	for _, item := range items {
		if item.ID == f.article {
			return false
		}
	}
	return true
}

func paidSearchHas(response CatalogArticlesResponse, id, origin string) bool {
	for _, item := range response.Items {
		if item.ID == id && item.ContentOrigin != nil && *item.ContentOrigin == origin {
			return true
		}
	}
	return false
}

// Redact only capability strings. Unexpected keys/private source strings remain
// visible in the permitted JSON/HTML projection for independent leak detection.
var paidObservationMediaURL = regexp.MustCompile(`/v1/catalog/images/[A-Za-z0-9_.-]+`)

func paidObservationRedact(value string) string {
	return paidObservationMediaURL.ReplaceAllStringFunc(value, func(url string) string {
		sum := sha256.Sum256([]byte(strings.TrimPrefix(url, "/v1/catalog/images/")))
		return "/v1/catalog/images/[sha256:" + hex.EncodeToString(sum[:]) + "]"
	})
}
func (f *paidFixture) observe(owner int, method, path string, status int, headers http.Header, raw []byte, readerBefore, identityBefore int64) {
	sum := sha256.Sum256(raw)
	observation := paidHTTPObservation{Method: method, Path: paidObservationRedact(path), OwnerIndex: owner, Status: status, Headers: map[string]string{}, BodySHA256: hex.EncodeToString(sum[:]), BodySize: len(raw), ReaderBefore: readerBefore, ReaderAfter: f.reader.calls.Load(), IdentityBefore: identityBefore, IdentityAfter: f.verifier.calls.Load()}
	for _, key := range []string{"Content-Type", "Cache-Control", "Cross-Origin-Resource-Policy", "X-Content-Type-Options", "Content-Security-Policy", "Referrer-Policy", "Retry-After"} {
		if value := headers.Get(key); value != "" {
			observation.Headers[key] = value
		}
	}
	contentType := headers.Get("Content-Type")
	if strings.HasPrefix(contentType, "application/json") || strings.HasPrefix(contentType, "text/html") {
		projection := raw
		if len(projection) > 256<<10 {
			projection = projection[:256<<10]
			observation.BodyTruncated = true
		}
		redacted := paidObservationRedact(string(projection))
		if strings.HasPrefix(contentType, "application/json") && !observation.BodyTruncated {
			var body any
			if json.Unmarshal([]byte(redacted), &body) == nil {
				observation.Body = body
			} else {
				observation.Body = redacted
			}
		} else {
			observation.Body = redacted
		}
	}
	f.observationMu.Lock()
	defer f.observationMu.Unlock()
	f.observations = append(f.observations, observation)
}
func (f *paidFixture) call(owner int, method, path, body string) (int, []byte, http.Header) {
	f.t.Helper()
	index := 0
	if owner >= 0 {
		index = owner % len(f.servers)
	}
	api := f.servers[index]
	r, err := http.NewRequest(method, api.URL+path, strings.NewReader(body))
	if err != nil {
		f.t.Fatal(err)
	}
	r.Header.Set("Accept", "application/json")
	if owner >= 0 {
		o := f.owners[owner]
		r.AddCookie(customerSessionCookie(o.token, o.session.ExpiresAt, time.Now()))
		if method == "POST" {
			r.Header.Set("Origin", "https://cars.example")
			r.Header.Set("X-CSRF-Token", customerCSRF(o.token))
			r.Header.Set("Content-Type", "application/json")
		}
	}
	client := *api.Client()
	client.Timeout = 10 * time.Second
	client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	readerBefore, identityBefore := f.reader.calls.Load(), f.verifier.calls.Load()
	response, err := client.Do(r)
	if err != nil {
		f.t.Fatal("actual paid HTTP request failed", err)
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(response.Body, 13<<20))
	if err != nil {
		f.t.Fatal(err)
	}
	if strings.HasPrefix(path, "/v1/catalog/vehicles/") || strings.HasPrefix(path, "/v1/catalog/images") {
		if response.Header.Get("Cache-Control") != "private, no-store" {
			f.t.Fatal("protected response lacks private no-store")
		}
	}
	f.observe(owner, method, path, response.StatusCode, response.Header, raw, readerBefore, identityBefore)
	return response.StatusCode, raw, response.Header
}
func (f *paidFixture) expect(owner int, method, path, body string, want int) []byte {
	f.t.Helper()
	status, raw, _ := f.call(owner, method, path, body)
	if status != want {
		f.t.Fatalf("paid route %s status%d want%d", method, status, want)
	}
	return raw
}
func (f *paidFixture) detail(owner int) CatalogArticle {
	f.t.Helper()
	raw := f.expect(owner, "GET", f.path("/"+f.article), "", 200)
	var envelope CatalogArticleResponse
	if json.Unmarshal(raw, &envelope) != nil {
		f.t.Fatal("article JSON invalid")
	}
	copy := envelope.Article
	clonePaidCatalogArticleImages(&copy)
	f.views = append(f.views, copy)
	return envelope.Article
}
func (f *paidFixture) snapshot(name string) map[string]any {
	snapshot := f.control.controlCall("GET", "snapshot")
	snapshot["reader_calls"] = f.reader.calls.Load()
	snapshot["identity_checks"] = f.verifier.calls.Load()
	f.phases[name] = snapshot
	return snapshot
}
func (f *paidFixture) check(name string, ok bool) {
	f.t.Helper()
	if !ok {
		f.t.Fatal("paid invariant failed:", name)
	}
	f.assertions[name] = true
}
func (f *paidFixture) controlPaid(path string) {
	f.t.Helper()
	r, _ := http.NewRequest("POST", f.control.control+"/paid-fixture/"+path, nil)
	r.Header.Set("X-R3-Fixture-Token", f.control.token)
	client := http.Client{Timeout: 3 * time.Second}
	response, err := client.Do(r)
	if err != nil {
		f.t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		f.t.Fatal("paid control failed")
	}
}
func (f *paidFixture) publish() {
	f.t.Helper()
	f.control.controlCall("POST", "release-model")
	f.expect(0, "POST", f.path("/"+f.article+"/prepare"), "{}", 202)
	f.control.controlCall("POST", "start-workers")
	f.control.wait("snapshot", func(s map[string]any) bool { return r3Int(r3Map(s, "counts"), "published_revisions") == 1 })
}
func paidWorkUnchanged(a, b map[string]any) bool {
	for _, key := range []string{"entered", "completed"} {
		if r3Int(r3Map(a, "selector_ensure"), key) != r3Int(r3Map(b, "selector_ensure"), key) {
			return false
		}
	}
	return r3Int(r3Map(b, "selector_ensure"), "active") == 0 && r3ZeroDelta(a, b) && r3Int(r3Map(a, "counts"), "article_jobs") == r3Int(r3Map(b, "counts"), "article_jobs") && r3Int(r3Map(a, "counts"), "canonical_revisions") == r3Int(r3Map(b, "counts"), "canonical_revisions") && a["reader_calls"] == b["reader_calls"]
}

func paidSelectorsMetadataOnly(before, after map[string]any) bool {
	// Only selector discovery may advance; article ensure and every body/model/
	// object-reader counter remain unchanged even when selectors read through.
	for _, key := range []string{"counts", "ensure", "source_calls", "asset_calls"} {
		a, _ := json.Marshal(before[key])
		b, _ := json.Marshal(after[key])
		if !bytes.Equal(a, b) {
			return false
		}
	}
	if before["reader_calls"] != after["reader_calls"] || before["model_calls"] != after["model_calls"] || r3Int(r3Map(before, "proxy"), "request_received") != r3Int(r3Map(after, "proxy"), "request_received") {
		return false
	}
	requests, ok := after["selector_ensure_requests"].([]any)
	if !ok || len(requests) != 3 {
		return false
	}
	seen := map[string]bool{}
	for _, item := range requests {
		receipt, ok := item.(map[string]any)
		if !ok || receipt["completed"] != true || r3Int(receipt, "status") != 200 {
			return false
		}
		scope, _ := receipt["scope"].(string)
		if (scope != "makes" && scope != "models" && scope != "configurations") || seen[scope] {
			return false
		}
		seen[scope] = true
		payload := r3Map(receipt, "payload")
		if payload["scope"] != scope {
			return false
		}
		for key := range payload {
			switch key {
			case "scope", "year", "make", "model", "region", "idempotency_key":
			default:
				return false
			}
		}
	}
	for _, provider := range []string{"bankone", "banktwo"} {
		traces, ok := r3Map(after, "provider_traces")[provider].([]any)
		if !ok {
			return false
		}
		for _, trace := range traces {
			path, ok := trace.(string)
			if !ok {
				return false
			}
			parsed, err := url.Parse(path)
			if err != nil || parsed.IsAbs() {
				return false
			}
			switch parsed.Path {
			case "/v1/catalog/years", "/v1/catalog/makes", "/v1/catalog/models", "/v1/catalog/configurations":
			default:
				return false
			}
		}
	}
	return true
}

func TestPostgresPaidCatalogGrantBeforeWork(t *testing.T) {
	f := paidSetup(t)
	before := f.snapshot("before")
	for _, path := range []string{"/v1/catalog/years", "/v1/catalog/years/2024/makes", "/v1/catalog/years/2024/makes/example/models", "/v1/catalog/years/2024/makes/example/models/car/configurations"} {
		f.expect(-1, "GET", path, "", 200)
	}
	f.control.wait("snapshot", func(s map[string]any) bool {
		selector := r3Map(s, "selector_ensure")
		return r3Int(selector, "entered") == 3 && r3Int(selector, "completed") == 3 && r3Int(selector, "active") == 0
	})
	selectors := f.snapshot("selectors")
	f.check("public_selectors_metadata_only", paidSelectorsMetadataOnly(before, selectors))
	for _, suffix := range []string{"", "/" + f.article, "/" + f.article + "/source"} {
		f.expect(0, "GET", f.path(suffix), "", 403)
	}
	f.expect(0, "GET", f.path("?q=repair"), "", 403)
	f.expect(0, "POST", f.path("/"+f.article+"/prepare"), "{}", 403)
	f.image(0, "/v1/catalog/images/invalid-v2-token", 404)
	f.check("unpaid_denied_before_work", paidWorkUnchanged(selectors, f.snapshot("unpaid")))
	f.exec(`UPDATE auth_sessions SET created_at=now()-interval '2 hours',expires_at=now()-interval '1 hour',firebase_auth_time=floor(extract(epoch FROM now()-interval '2 hours'))::bigint WHERE customer_account_id=$1::uuid`, f.owners[1].session.AccountID)
	for _, suffix := range []string{"", "/" + f.article, "/" + f.article + "/source"} {
		f.expect(1, "GET", f.path(suffix), "", 401)
	}
	f.expect(1, "POST", f.path("/"+f.article+"/prepare"), "{}", 401)
	f.image(1, "/v1/catalog/images/invalid-v2-token", 401)
	f.check("expired_session_denied_before_work", paidWorkUnchanged(selectors, f.snapshot("expired")))
	f.grant(0, f.configuration, "US")
	f.expect(0, "GET", f.path(""), "", 200)
	f.expect(0, "GET", f.path("/"+f.article), "", 503)
	f.check("paid_gets_observational", paidWorkUnchanged(selectors, f.snapshot("paid_cold")))
	f.controlPaid("grant-unavailable")
	f.expect(0, "GET", f.path("/"+f.article), "", 503)
	f.controlPaid("grant-available")
	f.verifier.mu.Lock()
	f.verifier.err = ErrCustomerDependency
	f.verifier.mu.Unlock()
	f.expect(0, "GET", f.path("/"+f.article), "", 503)
	f.verifier.mu.Lock()
	f.verifier.err = nil
	f.verifier.mu.Unlock()
	f.check("unavailable_grant_denied_before_work", paidWorkUnchanged(selectors, f.snapshot("unavailable")))
}
func TestPostgresPaidCatalogExactScopeAndOwnerIsolation(t *testing.T) {
	f := paidSetup(t)
	order := f.grant(0, f.configuration, "US")
	f.grant(1, f.adjacent, "US")
	var descriptors CatalogArticlesResponse
	if json.Unmarshal(f.expect(0, "GET", f.path(""), "", 200), &descriptors) != nil {
		t.Fatal("exact-scope descriptor JSON invalid")
	}
	if descriptors.Configuration == nil || descriptors.Configuration.ID != f.configuration || descriptors.Configuration.Region != "US" ||
		!descriptors.Complete || descriptors.Hydrating || descriptors.Progress == nil || descriptors.Progress.Status != "completed" || descriptors.Progress.Processed != 2 {
		t.Fatal("paid index lost exact vehicle context or provider completion")
	}
	firstArticle := f.article
	if f.provider == "banktwo" {
		firstArticle = f.other
	}
	if len(descriptors.Items) != 2 || descriptors.Items[0].ID != firstArticle {
		t.Fatal("paid index must keep Bank One first")
	}
	ids := map[string]bool{}
	for _, article := range descriptors.Items {
		ids[article.ID] = true
		if article.CanonicalArticleID == nil || *article.CanonicalArticleID != article.ID {
			t.Fatal("paid index exposed unmanaged identity")
		}
	}
	f.expect(1, "GET", f.path(""), "", 403)
	f.expect(1, "GET", f.path("?q=repair"), "", 403)
	f.check("exact_scope_grants", len(ids) == 2 && ids[f.article] && ids[f.other])
	for _, id := range []string{f.vehicle, f.adjacent, f.regionConfiguration} {
		want := 403
		if id == f.vehicle {
			want = 404
		}
		f.expect(0, "GET", "/v1/catalog/vehicles/"+id+"/articles", "", want)
	}
	f.expect(0, "GET", f.path("?region=CA"), "", 404)
	f.expect(0, "GET", f.path("?region=CA&q=repair"), "", 404)
	var adjacentArticle string
	if err := f.pool.QueryRow(context.Background(), `SELECT canonical_article_id::text FROM canonical_articles WHERE vehicle_configuration_id::text=$1 AND provider_slug=$2`, f.adjacent, f.provider).Scan(&adjacentArticle); err != nil {
		t.Fatal(err)
	}
	f.expect(0, "GET", f.path("/"+adjacentArticle), "", 404)
	f.check("owner_region_configuration_isolation", true)
	f.expect(0, "GET", f.path("/"+f.unscoped), "", 404)
	f.expect(0, "GET", f.path("/legacy"), "", 404)
	f.check("canonical_only", true)
	f.exec(`UPDATE entitlements SET status='revoked',revoked_at=now(),revoke_reason='fixture' WHERE commerce_order_id=$1::uuid`, order)
	f.expect(0, "GET", f.path(""), "", 403)
	f.expect(0, "GET", f.path("?q=repair"), "", 403)
	f.exec(`UPDATE entitlements SET customer_account_id=NULL,configuration_id=NULL,region=NULL,commerce_order_id=NULL,status='active',revoked_at=NULL WHERE commerce_order_id=$1::uuid`, order)
	f.expect(0, "GET", f.path(""), "", 403)
	f.check("revoked_and_legacy_denied", true)
	f.snapshot("isolated")
}
func TestPostgresPaidCatalogExactTitleSearch(t *testing.T) {
	f := paidSetup(t)
	title := "Removing and installing the high pressure fuel pump and checking the control wiring above the primary filter housing"
	path := f.path("?title=" + url.QueryEscape(" "+strings.ToUpper(title)+" "))
	f.exec(`UPDATE canonical_articles SET title=$1 WHERE canonical_article_id=$2::uuid`, " "+title+" ", f.article)
	f.exec(`UPDATE canonical_articles SET title=$1 WHERE canonical_article_id=$2::uuid`, title+" cover", f.other)
	f.expect(-1, "GET", path, "", 401)
	f.expect(1, "GET", path, "", 403)
	order := f.grant(0, f.configuration, "US")
	f.grant(1, f.adjacent, "US")
	f.expect(1, "GET", path, "", 403)
	f.expect(0, "GET", path+"&region=CA", "", 404)
	f.expect(0, "GET", f.path("?q="+url.QueryEscape(title)), "", 422)
	f.expect(0, "GET", path+"&q=pump", "", 422)
	results := func() []CatalogArticle {
		var list CatalogArticlesResponse
		if err := json.Unmarshal(f.expect(0, "GET", path, "", 200), &list); err != nil {
			t.Fatal("invalid exact title response", err)
		}
		for _, item := range list.Items {
			if item.CanonicalArticleID == nil || *item.CanonicalArticleID != item.ID ||
				item.Document != nil || item.Body != "" || len(item.Steps) != 0 || len(item.Images) != 0 || item.SourceReview != nil {
				t.Fatal("exact title response contained unmanaged identity or article content")
			}
		}
		return list.Items
	}
	if items := results(); len(items) != 1 || items[0].ID != f.article {
		t.Fatal("displayed long title did not match the exact entitled article")
	}
	f.exec(`UPDATE canonical_articles SET title=$1 WHERE canonical_article_id=$2::uuid`, title, f.other)
	first := f.article
	if f.provider == "banktwo" {
		first = f.other
	}
	if items := results(); len(items) != 2 || items[0].ID != first {
		t.Fatal("identical titles did not retain catalog order")
	}
	f.exec(`UPDATE canonical_articles SET title=$1 WHERE canonical_article_id=$2::uuid`, title+" cover", f.other)
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=(
		SELECT descriptor_source_snapshot_id FROM canonical_articles WHERE canonical_article_id=$1::uuid)`, f.article)
	if items := results(); len(items) != 0 {
		t.Fatal("exact title search exposed a withdrawn descriptor")
	}
	f.exec(`UPDATE entitlements SET status='revoked',revoked_at=now(),revoke_reason='fixture' WHERE commerce_order_id=$1::uuid`, order)
	f.expect(0, "GET", path, "", 403)
}

func TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse(t *testing.T) {
	f := paidSetup(t)
	f.grant(0, f.configuration, "US")
	f.grant(1, f.configuration, "US")
	cold := f.snapshot("cold")
	f.expect(0, "GET", f.path("/"+f.article), "", 503)
	f.check("explicit_prepare_only", paidWorkUnchanged(cold, f.snapshot("before_prepare")))
	var wg sync.WaitGroup
	statuses := make(chan int, 8)
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func(owner int) {
			defer wg.Done()
			status, _, _ := f.call(owner, "POST", f.path("/"+f.article+"/prepare"), "{}")
			statuses <- status
		}(i % 2)
	}
	wg.Wait()
	close(statuses)
	responses := 0
	for status := range statuses {
		responses++
		if status != 202 {
			t.Fatal("concurrent prepare did not observe durable accepted work", status)
		}
	}
	if responses != 8 {
		t.Fatal("missing concurrent prepare response", responses)
	}
	scheduled := f.snapshot("scheduled")
	f.check("shared_article_job", r3Int(r3Map(scheduled, "counts"), "article_jobs") == 1)
	f.control.controlCall("POST", "start-workers")
	held := f.control.wait("model-held", func(m map[string]any) bool {
		return r3Int(m, "downstream_waiting") == 1 && m["response_captured"] == true
	})
	f.heldModelReceipt = held
	f.check("actual_model_response_held", held["response_captured"] == true)
	source := f.detail(0)
	f.check("source_readable_during_hold", r3Origin(source, "source") && source.Processing != nil)
	// The fixture source says "Remove the pump."; the held model rewrites it to
	// "Take off the pump." Neither phrase appears in the "Pump" descriptor.
	sourceSearch := f.contentSearch(0, "Remove the pump")
	f.check("source_content_search_current_projection", paidSearchHas(sourceSearch, f.article, "source"))
	f.snapshot("source_held")
	f.control.controlCall("POST", "release-model")
	f.control.wait("snapshot", func(m map[string]any) bool { return r3Int(r3Map(m, "counts"), "published_revisions") == 1 })
	first := f.detail(0)
	canonicalSearch := f.contentSearch(0, "Take off the pump")
	f.check("canonical_content_search_current_projection", paidSearchHas(canonicalSearch, f.article, "canonical"))
	if !f.supersededTermAbsent("Remove the pump") {
		t.Fatal("source phrase matched without the paid search context")
	}
	// Keep the guarded HTTP receipt unchanged while testing the source fallback
	// against the same real PostgreSQL rows and the authorization context.
	searcher := f.applications[0].catalog.(paidArticleSearchStore)
	for _, test := range []struct {
		scopeID  string
		openDemo bool
		want     bool
	}{
		{f.configuration, false, true},
		{f.configuration, true, false},
		{f.adjacent, false, false},
	} {
		scope := paidCatalogContext{configuration: CatalogConfiguration{ID: test.scopeID}, openDemo: test.openDemo}
		ctx := context.WithValue(context.Background(), paidCatalogContextKey{}, scope)
		matches, err := searcher.PaidArticleSearchDescriptors(ctx, Principal{}, f.configuration, "Remove the pump")
		if err != nil {
			t.Fatal(err)
		}
		found := paidSearchHas(CatalogArticlesResponse{Items: matches}, f.article, "canonical")
		if found != test.want {
			t.Fatalf("Original matched=%t, want=%t for exact scope=%t openDemo=%t",
				found, test.want, test.scopeID == f.configuration, test.openDemo)
		}
		for _, item := range matches {
			if item.Body != "" || item.Document != nil || len(item.Steps) != 0 || len(item.Images) != 0 {
				t.Fatal("an Original search returned article content")
			}
		}
	}
	before := f.snapshot("published")
	second := f.detail(1)
	f.expect(1, "POST", f.path("/"+f.article+"/prepare"), "{}", 200)
	after := f.snapshot("reopened")
	f.check("canonical_reused_two_owners", first.CanonicalRevisionID != nil && samePaidCatalogID(first.CanonicalRevisionID, second.CanonicalRevisionID) && paidWorkUnchanged(before, after))
	var raw []byte
	if err := f.pool.QueryRow(context.Background(), `SELECT canonical_steps FROM canonical_article_revisions WHERE canonical_article_revision_id=$1::uuid`, *first.CanonicalRevisionID).Scan(&raw); err != nil {
		t.Fatal(err)
	}
	var expected []CatalogStep
	if json.Unmarshal(raw, &expected) != nil {
		t.Fatal("raw steps invalid")
	}
	copy := first
	clonePaidCatalogArticleImages(&copy)
	expectedArticle := CatalogArticle{Steps: expected}
	clonePaidCatalogArticleImages(&expectedArticle)
	actual, _ := json.Marshal(copy.Steps)
	want, _ := json.Marshal(expectedArticle.Steps)
	f.check("canonical_steps_preserved", bytes.Equal(actual, want) && len(first.Steps) > 0 && first.Steps[0].Action != "" && first.Steps[0].Number == 0)
	f.check("payment_grants_persist", r3Int(after, "payment_calls") == 0 && len(r3Map(after, "paid_rows")["entitlements"].([]any)) == 2)
}

func TestPostgresPaidCatalogSourceBodyPreviewRights(t *testing.T) {
	const snapshot = "c271a09e-5679-4445-93e0-0bddc85ad5bd"
	const text = "Hold the latch open while disconnecting the negative cable."
	const query = "disconnecting the negative cable"
	f := paidSetup(t)
	f.grant(0, f.configuration, "US")
	detail := f.path("/" + f.article)
	assertSearch := func(want bool) {
		t.Helper()
		found := false
		for _, match := range f.contentSearch(0, query).Items {
			if match.ID == f.article {
				found = true
				if match.SourceRevisionID != nil {
					t.Fatal("preview search unexpectedly required a stored source revision")
				}
			}
		}
		if found != want {
			t.Fatalf("source preview searchable = %t, want %t", found, want)
		}
	}
	var title string
	if err := f.pool.QueryRow(context.Background(), `SELECT title FROM canonical_articles
		WHERE canonical_article_id=$1::uuid AND current_source_revision_id IS NULL`, f.article).Scan(&title); err != nil {
		t.Fatal(err)
	}
	found := false
	for _, match := range f.contentSearch(0, title).Items {
		if match.ID == f.article && match.SourceRevisionID == nil {
			found = true
		}
	}
	if !found {
		t.Fatal("the title search dropped an article before its body was captured")
	}
	assertSearch(false)
	f.expect(0, "POST", detail+"/prepare", "{}", 202)
	f.exec(`INSERT INTO source_snapshots(source_snapshot_id,adapter_name,source_uri,source_version,content_sha256,object_key,
		license_metadata,retrieved_at)
		VALUES($1::uuid,'banktwo','https://fixture.invalid/preview','fixture',repeat('8',64),'sources/preview','{}',now())`, snapshot)
	f.exec(`UPDATE source_fetch_jobs j SET checkpoint=j.checkpoint||jsonb_build_object('source_body_preview',
		jsonb_build_object('snapshot_id',$2::text,'descriptor_snapshot_id',a.descriptor_source_snapshot_id::text,
		'document',jsonb_build_object('schema_version',1,'blocks',jsonb_build_array(jsonb_build_object('type','paragraph','text',$3::text)))))
		FROM canonical_articles a WHERE a.canonical_article_id=$1::uuid AND a.current_job_id=j.source_fetch_job_id`, f.article, snapshot, text)
	assertVisible := func() {
		t.Helper()
		got := f.detail(0)
		if !got.SourceBodyPreview || got.SourceRevisionID != nil || got.SourceReview != nil ||
			got.Document == nil || len(got.Document.Blocks) != 1 || got.Document.Blocks[0].Text != text {
			t.Fatal("owner did not receive the original source body")
		}
		assertSearch(true)
	}
	assertHidden := func(owner, status int) {
		t.Helper()
		if bytes.Contains(f.expect(owner, "GET", detail, "", status), []byte(text)) {
			t.Fatalf("preview body was visible to owner index %d with status %d", owner, status)
		}
		if owner == 0 {
			assertSearch(false)
		} else {
			f.expect(owner, "GET", f.path("?q="+url.QueryEscape(query)), "", status)
		}
	}
	assertVisible()
	// Demo searches use the same store but must never match a preview-only term.
	demoContext := context.WithValue(context.Background(), paidCatalogContextKey{}, paidCatalogContext{
		configuration: CatalogConfiguration{ID: f.configuration}, openDemo: true,
	})
	demoItems, err := f.applications[0].catalog.(paidArticleSearchStore).PaidArticleSearchDescriptors(
		demoContext, Principal{}, f.configuration, query,
	)
	if err != nil {
		t.Fatal(err)
	}
	for _, item := range demoItems {
		if item.ID == f.article {
			t.Fatal("demo search matched a customer-only source preview")
		}
	}
	assertHidden(-1, http.StatusUnauthorized)
	assertHidden(1, http.StatusForbidden)
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=$1::uuid`, snapshot)
	assertHidden(0, http.StatusAccepted)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=$1::uuid`, snapshot)
	f.exec(`INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids)
		VALUES(gen_random_uuid(),'source-body-preview-quarantine','quarantine','FIXTURE',jsonb_build_array($1::text))`, snapshot)
	assertHidden(0, http.StatusAccepted)
	f.exec(`UPDATE source_review_items SET status='approved' WHERE item_key='source-body-preview-quarantine'`)
	assertVisible()
	f.exec(`INSERT INTO source_artifacts(source_snapshot_id,artifact_kind,media_type,content_sha256,object_key,extraction_status)
		SELECT source_snapshot_id,'document','application/pdf',content_sha256,object_key,'candidate_ready'
		FROM source_snapshots WHERE source_snapshot_id=$1::uuid`, snapshot)
	assertVisible()
	f.exec(`UPDATE source_artifacts SET extraction_status='quarantined' WHERE source_snapshot_id=$1::uuid`, snapshot)
	assertHidden(0, http.StatusAccepted)
	f.exec(`UPDATE source_artifacts SET extraction_status='candidate_ready' WHERE source_snapshot_id=$1::uuid`, snapshot)
	assertVisible()
	f.exec(`UPDATE canonical_articles SET request_generation=request_generation+1 WHERE canonical_article_id=$1::uuid`, f.article)
	assertHidden(0, http.StatusAccepted)
}

func TestPostgresPaidCatalogLinkedPDFPreviewRights(t *testing.T) {
	const wrapperText = "Set aside the retaining collar."
	const pdfText = "Inspect the zinc sensor connector."
	const pdfQuery = "zinc sensor connector"
	f := paidSetup(t)
	f.grant(0, f.configuration, "US")
	detail := f.path("/" + f.article)
	f.expect(0, "POST", detail+"/prepare", "{}", http.StatusAccepted)

	body := f.uuid()
	var snapshots []string
	for i, character := range []string{"b", "c", "d", "e", "f", "7"} {
		id, digest, key := body, strings.Repeat(character, 64), "sources/"+character
		if i != 0 {
			id = f.uuid()
			snapshots = append(snapshots, id)
		}
		f.exec(`INSERT INTO source_snapshots(source_snapshot_id,adapter_name,source_uri,source_version,content_sha256,object_key,
			license_metadata,retrieved_at)
			VALUES($1::uuid,$2,'https://fixture.invalid/preview','fixture',$3,$4,'{}',now())`, id, f.provider, digest, key)
		if i != 0 {
			f.exec(`INSERT INTO source_artifacts(source_snapshot_id,artifact_kind,media_type,content_sha256,object_key,extraction_status)
				VALUES($1::uuid,'document','application/pdf',$2,$3,'candidate_ready')`, id, digest, key)
		}
	}
	makeDocument := func(paragraphs ...string) CatalogDocument {
		document := CatalogDocument{SchemaVersion: 1}
		for _, paragraph := range paragraphs {
			document.Blocks = append(document.Blocks, CatalogDocumentBlock{Type: "paragraph", Text: paragraph})
		}
		return document
	}
	wrapper, linked := makeDocument(wrapperText), makeDocument(wrapperText, pdfText)
	ids := snapshots[:2]
	storePreview := func(document, linkedDocument, attachments any) {
		t.Helper()
		preview, err := json.Marshal(map[string]any{
			"snapshot_id": body,
			"document":    document,
			"linked_preview": map[string]any{
				"document": linkedDocument, "snapshot_ids": attachments,
			},
		})
		if err != nil {
			t.Fatal(err)
		}
		f.exec(`UPDATE source_fetch_jobs j SET checkpoint=checkpoint||jsonb_build_object('source_body_preview',
			$2::jsonb||jsonb_build_object('descriptor_snapshot_id',a.descriptor_source_snapshot_id::text))
			FROM canonical_articles a WHERE a.canonical_article_id=$1::uuid AND a.current_job_id=j.source_fetch_job_id`,
			f.article, string(preview))
	}
	assertSearch := func(query string, want bool) {
		t.Helper()
		found := false
		for _, item := range f.contentSearch(0, query).Items {
			found = found || item.ID == f.article
		}
		if found != want {
			t.Fatalf("query %q searchable = %t, want %t", query, found, want)
		}
	}
	assertDetail := func(want ...string) {
		t.Helper()
		got := f.detail(0)
		if !got.SourceBodyPreview || got.SourceRevisionID != nil || got.SourceReview != nil || got.Document == nil {
			t.Fatal("expected an early source document without published source identifiers")
		}
		var paragraphs []string
		for _, block := range got.Document.Blocks {
			paragraphs = append(paragraphs, block.Text)
		}
		if !reflect.DeepEqual(paragraphs, want) {
			t.Fatalf("preview paragraphs = %v, want %v", paragraphs, want)
		}
	}
	assertWrapper := func() {
		t.Helper()
		assertDetail(wrapperText)
		assertSearch("retaining collar", true)
		assertSearch(pdfQuery, false)
	}

	storePreview(wrapper, linked, ids)
	assertDetail(wrapperText, pdfText)
	assertSearch(pdfQuery, true)

	// Withdraw the descriptor after the paid middleware's exact identity check,
	// but before the detail handler reads the saved body.
	server := f.applications[0]
	var descriptor string
	if err := f.pool.QueryRow(context.Background(), `SELECT descriptor_source_snapshot_id::text
		FROM canonical_articles WHERE canonical_article_id=$1::uuid`, f.article).Scan(&descriptor); err != nil {
		t.Fatal(err)
	}
	guarded := server.catalogProtected(func(w http.ResponseWriter, r *http.Request, p Principal) {
		f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=$1::uuid`, descriptor)
		server.getCatalogArticle(w, r, p)
	}, true)
	request := httptest.NewRequest("GET", "https://cars.example"+detail, nil)
	request.SetPathValue("vehicle_id", f.configuration)
	request.SetPathValue("article_id", f.article)
	owner := f.owners[0]
	request.AddCookie(customerSessionCookie(owner.token, owner.session.ExpiresAt, time.Now()))
	response := httptest.NewRecorder()
	guarded.ServeHTTP(response, request)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=$1::uuid`, descriptor)
	if response.Code != http.StatusAccepted || bytes.Contains(response.Body.Bytes(), []byte(wrapperText)) ||
		bytes.Contains(response.Body.Bytes(), []byte(pdfText)) {
		t.Fatalf("a descriptor withdrawn at the detail boundary must suppress source previews, status=%d", response.Code)
	}
	assertDetail(wrapperText, pdfText)

	for _, observer := range []struct{ owner, status int }{{-1, 401}, {1, 403}} {
		for _, path := range []string{detail, f.path("?q=" + url.QueryEscape(pdfQuery))} {
			if bytes.Contains(f.expect(observer.owner, "GET", path, "", observer.status), []byte(pdfText)) {
				t.Fatal("linked preview content was visible without a grant")
			}
		}
	}
	demoContext := context.WithValue(context.Background(), paidCatalogContextKey{}, paidCatalogContext{
		configuration: CatalogConfiguration{ID: f.configuration}, openDemo: true,
	})
	demoItems, err := f.applications[0].catalog.(paidArticleSearchStore).PaidArticleSearchDescriptors(
		demoContext, Principal{}, f.configuration, pdfQuery,
	)
	if err != nil {
		t.Fatal(err)
	}
	for _, item := range demoItems {
		if item.ID == f.article {
			t.Fatal("demo search matched customer-only PDF text")
		}
	}

	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=$1::uuid`, ids[1])
	assertWrapper()
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=$1::uuid`, ids[1])
	f.exec(`INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids)
		VALUES(gen_random_uuid(),'linked-pdf-preview-quarantine','quarantine','FIXTURE',jsonb_build_array($1::text))`, ids[1])
	assertWrapper()
	f.exec(`UPDATE source_review_items SET status='approved' WHERE item_key='linked-pdf-preview-quarantine'`)
	for _, change := range []struct{ fields, restore string }{
		{"extraction_status='quarantined'", "extraction_status='candidate_ready'"},
		{"media_type='application/json'", "media_type='application/pdf'"},
		{"content_sha256=repeat('0',64)", "content_sha256=repeat('d',64)"},
		{"object_key='sources/wrong'", "object_key='sources/d'"},
	} {
		f.exec(`UPDATE source_artifacts SET `+change.fields+` WHERE source_snapshot_id=$1::uuid`, ids[1])
		assertWrapper()
		f.exec(`UPDATE source_artifacts SET `+change.restore+` WHERE source_snapshot_id=$1::uuid`, ids[1])
	}
	for _, attachments := range []any{
		nil, ids[0], map[string]string{"id": ids[0]}, []string{}, []string{ids[0], ids[0]},
		[]any{ids[0], nil}, []string{ids[0], "not-a-uuid"}, []string{ids[0], f.uuid()}, snapshots,
	} {
		storePreview(wrapper, linked, attachments)
		assertWrapper()
	}
	for _, badDocument := range []any{
		nil, "not a document",
		json.RawMessage(`{"schema_version":1,"blocks":[{"type":false}]}`),
		json.RawMessage(`{"schema_version":1,"blocks":[null]}`),
	} {
		storePreview(wrapper, badDocument, ids)
		assertWrapper()
	}
	storePreview(nil, makeDocument(pdfText), ids)
	assertDetail(pdfText)
	assertSearch(pdfQuery, true)
	f.exec(`DELETE FROM source_artifacts WHERE source_snapshot_id=$1::uuid`, ids[1])
	f.expect(0, "GET", detail, "", http.StatusAccepted)
	assertSearch(pdfQuery, false)
	storePreview(wrapper, linked, ids)
	assertWrapper()
}

func (f *paidFixture) image(owner int, path string, want int) http.Header {
	f.t.Helper()
	status, raw, headers := f.call(owner, "GET", path, "")
	if status != want {
		f.t.Fatalf("media status%d want%d", status, want)
	}
	if status == 200 && !validCatalogImageMedia(raw, strings.Split(headers.Get("Content-Type"), ";")[0]) {
		f.t.Fatal("real S3 image bytes invalid")
	}
	return headers
}
func (f *paidFixture) token(ref paidCatalogImageReference, at time.Time) string {
	f.t.Helper()
	token, err := sealPaidCatalogImageReference(ref, f.applications[0].catalogImageKey, at)
	if err != nil {
		f.t.Fatal("fixture contextual token could not be sealed")
	}
	return "/v1/catalog/images/" + token
}
func TestPostgresPaidCatalogContextualMediaAndRevocation(t *testing.T) {
	f := paidSetup(t)
	order := f.grant(0, f.configuration, "US")
	f.grant(1, f.configuration, "US")
	f.publish()
	a := f.detail(0)
	if len(a.Images) == 0 || a.Images[0].URL == "" || len(a.Steps) == 0 || a.Steps[0].Images == nil || len(*a.Steps[0].Images) == 0 {
		t.Fatal("actual nested/top-level source asset projections required")
	}
	before := f.reader.calls.Load()
	headers := f.image(0, a.Images[0].URL, 200)
	f.image(0, (*a.Steps[0].Images)[0].URL, 200)
	f.check("actual_s3_reader", f.reader.calls.Load() == before+2)
	f.check("media_security_headers", headers.Get("Cross-Origin-Resource-Policy") == "same-origin" && headers.Get("X-Content-Type-Options") == "nosniff" && strings.Contains(headers.Get("Content-Security-Policy"), "sandbox") && headers.Get("Referrer-Policy") == "no-referrer")
	before = f.reader.calls.Load()
	ref, err := openPaidCatalogImageReference(strings.TrimPrefix(a.Images[0].URL, "/v1/catalog/images/"), f.applications[0].catalogImageKey, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	f.image(1, a.Images[0].URL, 404)
	f.image(0, "/v1/catalog/images/v2.forged", 404)
	legacy, _ := sealCatalogImageReference(ref.ObjectKey, f.applications[0].catalogImageKey)
	f.image(0, "/v1/catalog/images/"+legacy, 404)
	for _, mutate := range []func(*paidCatalogImageReference){func(r *paidCatalogImageReference) { r.SourceVehicleRefSHA256 = strings.Repeat("a", 64) }, func(r *paidCatalogImageReference) { r.SourceArticleRefSHA256 = strings.Repeat("b", 64) }, func(r *paidCatalogImageReference) {
		r.ProviderSlug = "banktwo"
		if f.provider == "banktwo" {
			r.ProviderSlug = "bankone"
		}
	}, func(r *paidCatalogImageReference) { r.AssetID = "unmapped-asset" }, func(r *paidCatalogImageReference) { r.ObjectKey = "procedure-images/" + strings.Repeat("f", 64) }, func(r *paidCatalogImageReference) { r.CanonicalArticleID = f.other }} {
		changed := ref
		mutate(&changed)
		f.image(0, f.token(changed, time.Now()), 404)
	}
	old := time.Now().Add(-301 * time.Second)
	expired := ref
	expired.IssuedAt = old.Unix()
	expired.ExpiresAt = old.Unix() + 300
	f.image(0, f.token(expired, old), 404)
	f.check("invalid_media_zero_reader", f.reader.calls.Load() == before)
	f.exec(`UPDATE entitlements SET status='revoked',revoked_at=now(),revoke_reason='fixture' WHERE commerce_order_id=$1::uuid`, order)
	f.image(0, a.Images[0].URL, 403)
	f.exec(`UPDATE entitlements SET status='active',revoked_at=NULL,revoke_reason=NULL WHERE commerce_order_id=$1::uuid`, order)
	f.exec(`UPDATE customer_accounts SET status='blocked' WHERE customer_account_id=$1::uuid`, f.owners[0].session.AccountID)
	f.image(0, a.Images[0].URL, 403)
	f.exec(`UPDATE customer_accounts SET status='active' WHERE customer_account_id=$1::uuid`, f.owners[0].session.AccountID)
	f.exec(`UPDATE auth_sessions SET revoked_at=now() WHERE customer_account_id=$1::uuid`, f.owners[0].session.AccountID)
	f.image(0, a.Images[0].URL, 401)
	// A fresh same-account session may retain a valid account-bound reference.
	token, hash, _ := newCustomerSessionToken()
	now := time.Now()
	session, e := (&postgresCustomerSessions{pool: f.pool}).Rotate(context.Background(), VerifiedCustomerIdentity{ProjectID: "fixture-project", UID: f.owners[0].session.UID, AuthTime: now.Unix(), IssuedAt: now.Unix(), Expires: now.Add(time.Hour).Unix()}, hash, nil, now, now.Add(time.Hour))
	if e != nil {
		t.Fatal(e)
	}
	f.owners[0] = paidFixtureOwner{token: token, session: session}
	f.image(0, a.Images[0].URL, 200)
	f.check("current_grant_identity_rechecked", f.verifier.calls.Load() > 0 && f.reader.calls.Load() == before+1)
	before = f.reader.calls.Load()
	f.exec(`UPDATE canonical_articles SET current_canonical_revision_id=NULL WHERE canonical_article_id=$1::uuid`, f.article)
	f.image(0, a.Images[0].URL, 404)
	f.exec(`UPDATE canonical_articles SET current_canonical_revision_id=$1::uuid WHERE canonical_article_id=$2::uuid`, *a.CanonicalRevisionID, f.article)
	f.controlPaid("refresh-source")
	f.control.wait("snapshot", func(s map[string]any) bool { return r3Int(r3Map(s, "counts"), "published_revisions") == 2 })
	f.image(0, a.Images[0].URL, 404)
	f.check("stale_context_zero_reader", f.reader.calls.Load() == before)
	fresh := f.detail(0)
	f.image(0, fresh.Images[0].URL, 200)
	f.snapshot("media_final")
}
func TestPostgresPaidCatalogHistoricalSourceAndRights(t *testing.T) {
	f := paidSetup(t)
	f.grant(0, f.configuration, "US")
	f.publish()
	a := f.detail(0)
	oldSource := *a.SourceRevisionID
	sourcePath := f.path("/" + f.article + "/source?source_revision_id=" + oldSource)
	raw := f.expect(0, "GET", sourcePath, "", 200)
	var source CatalogSourceContentResponse
	if json.Unmarshal(raw, &source) != nil || len(source.Images) == 0 || source.Images[0].URL == "" || !strings.Contains(source.Content, "<img") {
		t.Fatal("ordered source JSON lacks permitted embedded media")
	}
	f.image(0, source.Images[0].URL, 200)
	request, _ := http.NewRequest("GET", f.servers[0].URL+sourcePath, nil)
	request.Header.Set("Accept", "text/html")
	request.AddCookie(customerSessionCookie(f.owners[0].token, f.owners[0].session.ExpiresAt, time.Now()))
	readerBefore, identityBefore := f.reader.calls.Load(), f.verifier.calls.Load()
	response, err := f.servers[0].Client().Do(request)
	if err != nil {
		t.Fatal(err)
	}
	html, _ := io.ReadAll(response.Body)
	response.Body.Close()
	f.observe(0, "GET", sourcePath, response.StatusCode, response.Header, html, readerBefore, identityBefore)
	f.check("source_html_json_media", response.StatusCode == 200 && bytes.Contains(html, []byte("<img")))
	f.controlPaid("refresh-source")
	f.control.wait("snapshot", func(s map[string]any) bool { return r3Int(r3Map(s, "counts"), "published_revisions") == 2 })
	fresh := f.detail(0)
	store := newPostgresCatalogStore(f.pool)
	for _, revision := range []string{"", *fresh.SourceRevisionID, oldSource} {
		full, fullErr := store.ArticleSourceRevision(context.Background(), Principal{}, f.configuration, f.article, revision)
		identity, anchor, narrow, narrowErr := store.paidCatalogSourceView(context.Background(), f.configuration, f.article, revision, false)
		if fullErr != nil || narrowErr != nil || !reflect.DeepEqual(full, narrow) || !samePaidCatalogID(identity.CurrentSourceRevisionID, fresh.SourceRevisionID) || !samePaidCatalogID(anchor.Article.CanonicalRevisionID, fresh.CanonicalRevisionID) {
			t.Fatal("scoped read changed source, version, display hash, or current anchor", fullErr, narrowErr)
		}
	}
	if _, _, _, err := store.paidCatalogSourceView(context.Background(), f.adjacent, f.article, oldSource, false); !errors.Is(err, ErrCatalogNotFound) {
		t.Fatal("scoped source lookup accepted an adjacent configuration", err)
	}
	// refresh-source independently seeds "Remove the refreshed pump.". The
	// older canonical phrase must not match the newly selected source view.
	searchBefore := f.contentSearch(0, "refreshed pump")
	f.check("content_search_before_rights_change", fresh.ContentOrigin != nil && paidSearchHas(searchBefore, f.article, *fresh.ContentOrigin))
	if !f.supersededTermAbsent("Take off the pump") {
		t.Fatal("superseded canonical phrase still matched after source refresh")
	}
	raw = f.expect(0, "GET", sourcePath, "", 200)
	if json.Unmarshal(raw, &source) != nil {
		t.Fatal("historical JSON invalid")
	}
	ref, err := openPaidCatalogImageReference(strings.TrimPrefix(source.Images[0].URL, "/v1/catalog/images/"), f.applications[0].catalogImageKey, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	f.check("historical_source_selected", ref.SelectedSourceRevisionID == oldSource && ref.AnchorSourceRevisionID == *fresh.SourceRevisionID)
	f.image(0, source.Images[0].URL, 200)
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=(SELECT body_source_snapshot_id FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid)`, oldSource)
	f.expect(0, "GET", sourcePath, "", 404)
	f.expect(0, "GET", f.path("/"+f.article+"/source"), "", 200)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=(SELECT body_source_snapshot_id FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid)`, oldSource)
	before := f.reader.calls.Load()
	rightsBefore := f.snapshot("rights_before")
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=(SELECT body_source_snapshot_id FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid)`, *fresh.SourceRevisionID)
	f.expect(0, "GET", f.path("/"+f.article), "", 410)
	f.expect(0, "GET", sourcePath, "", 410)
	f.image(0, fresh.Images[0].URL, 410)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=(SELECT body_source_snapshot_id FROM canonical_article_source_revisions WHERE source_revision_id=$1::uuid)`, *fresh.SourceRevisionID)
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE content_sha256::text IN (SELECT asset->>'sha256' FROM canonical_article_source_revisions, jsonb_array_elements(resource_manifest) asset WHERE source_revision_id=$1::uuid AND asset->>'role'='asset')`, *fresh.SourceRevisionID)
	f.expect(0, "GET", f.path("/"+f.article), "", 410)
	f.expect(0, "GET", sourcePath, "", 410)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE content_sha256::text IN (SELECT asset->>'sha256' FROM canonical_article_source_revisions, jsonb_array_elements(resource_manifest) asset WHERE source_revision_id=$1::uuid AND asset->>'role'='asset')`, *fresh.SourceRevisionID)
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=(SELECT descriptor_source_snapshot_id FROM canonical_articles WHERE canonical_article_id=$1::uuid)`, f.article)
	var index CatalogArticlesResponse
	if json.Unmarshal(f.expect(0, "GET", f.path(""), "", 200), &index) != nil {
		t.Fatal("descriptor index JSON invalid")
	}
	for _, descriptor := range index.Items {
		if descriptor.ID == f.article {
			t.Fatal("withdrawn descriptor exposed by paid index")
		}
	}
	for _, descriptor := range f.contentSearch(0, "refreshed pump").Items {
		if descriptor.ID == f.article {
			t.Fatal("withdrawn descriptor exposed by paid content search")
		}
	}
	f.expect(0, "GET", f.path("/"+f.article), "", 410)
	f.expect(0, "GET", sourcePath, "", 410)
	f.image(0, fresh.Images[0].URL, 410)
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=(SELECT descriptor_source_snapshot_id FROM canonical_articles WHERE canonical_article_id=$1::uuid)`, f.article)
	rows, err := f.pool.Query(context.Background(), `SELECT snapshot.source_snapshot_id::text FROM canonical_articles a JOIN canonical_article_source_revisions revision ON revision.source_revision_id=a.current_source_revision_id JOIN source_snapshots snapshot ON snapshot.source_snapshot_id IN (a.descriptor_source_snapshot_id,revision.body_source_snapshot_id) OR EXISTS(SELECT 1 FROM jsonb_array_elements(revision.resource_manifest) asset WHERE asset->>'sha256'=snapshot.content_sha256::text) WHERE a.canonical_article_id::text=$1 ORDER BY snapshot.source_snapshot_id`, f.article)
	if err != nil {
		t.Fatal(err)
	}
	var snapshots []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			t.Fatal(err)
		}
		snapshots = append(snapshots, id)
	}
	rows.Close()
	if rows.Err() != nil || len(snapshots) < 3 {
		t.Fatal("descriptor/body/resource rights fixture incomplete", rows.Err(), len(snapshots))
	}
	for _, snapshot := range snapshots {
		var review string
		if err := f.pool.QueryRow(context.Background(), `INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids) VALUES(gen_random_uuid(),gen_random_uuid()::text,'quarantine','FIXTURE',jsonb_build_array($1::text)) RETURNING source_review_item_id::text`, snapshot).Scan(&review); err != nil {
			t.Fatal(err)
		}
		f.expect(0, "GET", f.path("/"+f.article), "", 404)
		f.expect(0, "GET", sourcePath, "", 404)
		f.image(0, fresh.Images[0].URL, 404)
		var index CatalogArticlesResponse
		if err := json.Unmarshal(f.expect(0, "GET", f.path(""), "", 200), &index); err != nil {
			t.Fatal(err)
		}
		for _, result := range [][]CatalogArticle{index.Items, f.contentSearch(0, "refreshed pump").Items} {
			for _, descriptor := range result {
				if descriptor.ID == f.article {
					t.Fatal("quarantined article exposed by paid index or search")
				}
			}
		}
		f.exec(`UPDATE source_review_items SET status='approved' WHERE source_review_item_id::text=$1`, review)
	}
	f.exec(`UPDATE canonical_articles SET membership_status='retired' WHERE canonical_article_id=$1::uuid`, f.article)
	f.expect(0, "GET", f.path("/"+f.article), "", 404)
	f.exec(`UPDATE canonical_articles SET membership_status='active' WHERE canonical_article_id=$1::uuid`, f.article)
	f.exec(`UPDATE vehicle_configurations SET reviewer_state='rejected' WHERE vehicle_configuration_id=$1::uuid`, f.configuration)
	f.expect(0, "GET", f.path("/"+f.article), "", 404)
	f.exec(`UPDATE vehicle_configurations SET reviewer_state='approved' WHERE vehicle_configuration_id=$1::uuid`, f.configuration)
	f.expect(0, "GET", f.path("/"+f.other+"/source?source_revision_id="+oldSource), "", 404)
	f.check("rights_denied_before_reader", f.reader.calls.Load() == before && paidWorkUnchanged(rightsBefore, f.snapshot("rights_denied")))
	sanitized, err := sanitizeCatalogSourceHTML(`<img src="https://provider.invalid/private"><script>secret()</script>`, "https://provider.invalid/private", f.applications[0].catalogImageKey)
	f.check("source_sanitizer_no_private_leak", err == nil && !strings.Contains(sanitized, "https://provider.invalid") && !strings.Contains(sanitized, "script") && !bytes.Contains(raw, []byte("storage_key")) && !bytes.Contains(raw, []byte("source_article_ref")))
	f.snapshot("rights_final")
	assertStagedMediaRefreshFence(t, f, fresh)
}

func assertStagedMediaRefreshFence(t *testing.T, f *paidFixture, current CatalogArticle) {
	t.Helper()
	if current.SourceRevisionID == nil || current.CanonicalRevisionID == nil {
		t.Fatal("published anchor fixture missing")
	}
	currentSource := *current.SourceRevisionID
	staged, historical, job, canonical := f.uuid(), f.uuid(), f.uuid(), f.uuid()
	var svgSnapshot, svgDigest, resolution string
	if f.provider == "bankone" {
		svgSnapshot, resolution = f.uuid(), f.uuid()
		for _, id := range []string{svgSnapshot, resolution} {
			digest := sha256.Sum256([]byte(id))
			checksum := hex.EncodeToString(digest[:])
			f.exec(`INSERT INTO source_snapshots (source_snapshot_id,adapter_name,source_uri,source_version,content_sha256,object_key,license_metadata,retrieved_at)
				VALUES ($1::uuid,'fixture','fixture:positioned-source','fixture-positioned',$2::text,'sources/'||left($2::text,16)||'/'||$2::text,'{}',now())`, id, checksum)
			if id == svgSnapshot {
				svgDigest = checksum
			}
		}
	}
	for _, revision := range []string{staged, historical} {
		fingerprint := sha256.Sum256([]byte(revision))
		original := "[]"
		if revision == staged && svgDigest != "" {
			original = `[{"role":"asset_original","media_type":"image/svg+xml","sha256":"` + svgDigest + `"}]`
		}
		f.exec(`INSERT INTO canonical_article_source_revisions
			(source_revision_id,canonical_article_id,source_fingerprint,body_source_snapshot_id,resource_manifest,
			 source_document,source_images,source_body,source_steps,projection_version,projection_status,evidence_manifest,captured_at)
			SELECT $1::uuid,canonical_article_id,$2,body_source_snapshot_id,resource_manifest || $4::jsonb,
			 source_document,source_images,source_body,source_steps,projection_version,projection_status,evidence_manifest,now()
			FROM canonical_article_source_revisions WHERE source_revision_id=$3::uuid`,
			revision, hex.EncodeToString(fingerprint[:]), currentSource, original)
	}
	transformation := sha256.Sum256([]byte(job))
	f.exec(`INSERT INTO source_fetch_jobs
		(source_fetch_job_id,provider_slug,canonical_vehicle_id,source_vehicle_ref,source_article_ref,
		 source_version,connector_name,idempotency_key,status,checkpoint,job_kind,canonical_article_id,
		 source_revision_id,request_generation,phase,transformation_key,normalization_version,rewrite_profile_version,
		 lease_owner,lease_token,lease_expires_at,heartbeat_at)
		SELECT $1::uuid,j.provider_slug,j.canonical_vehicle_id,j.source_vehicle_ref,j.source_article_ref,
		 j.source_version,j.connector_name,$1::text,'processing','{"staged_media_refresh":true}','article',j.canonical_article_id,
		 $2::uuid,(SELECT max(prior.request_generation)+1 FROM source_fetch_jobs prior
			WHERE prior.job_kind='article' AND prior.canonical_article_id=j.canonical_article_id),
		 'rewriting',$3,j.normalization_version,j.rewrite_profile_version,
		 $1::uuid,1,now()+interval '2 minutes',now()
		FROM source_fetch_jobs j JOIN canonical_articles a ON a.current_job_id=j.source_fetch_job_id
		WHERE a.canonical_article_id=$4::uuid`, job, staged, hex.EncodeToString(transformation[:]), f.article)

	sourcePath := func(revision string) string {
		return f.path("/" + f.article + "/source?source_revision_id=" + revision)
	}
	var original CatalogSourceContentResponse
	if err := json.Unmarshal(f.expect(0, http.MethodGet, sourcePath(currentSource), "", http.StatusOK), &original); err != nil || len(original.Images) == 0 {
		t.Fatal("current source capability fixture missing", err)
	}
	ref, err := openPaidCatalogImageReference(strings.TrimPrefix(original.Images[0].URL, "/v1/catalog/images/"), f.applications[0].catalogImageKey, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	ref.SelectedSourceRevisionID = staged
	media := f.token(ref, time.Now())
	store := newPostgresCatalogStore(f.pool)
	checkDenied := func() {
		t.Helper()
		raw := f.expect(0, http.MethodGet, sourcePath(staged), "", http.StatusNotFound)
		if bytes.Contains(raw, []byte("/v1/catalog/images/")) {
			t.Fatal("denied source issued a media capability")
		}
		if _, err := store.ArticleSourceRevision(context.Background(), Principal{}, f.configuration, f.article, staged); !errors.Is(err, ErrCatalogNotFound) {
			t.Fatal("general source lookup returned the staged revision", err)
		}
		reads := f.reader.calls.Load()
		f.image(0, media, http.StatusNotFound)
		if f.reader.calls.Load() != reads {
			t.Fatal("staged media denial reached storage")
		}
	}
	checkDenied()
	f.expect(0, http.MethodGet, sourcePath(historical), "", http.StatusOK)
	f.image(0, original.Images[0].URL, http.StatusOK)
	if f.provider == "bankone" {
		assertBoundStagedOriginal(t, f, current, staged, job, svgSnapshot, svgDigest, resolution, original.Images[0].URL)
		checkDenied()
	}

	f.exec(`INSERT INTO canonical_article_revisions
		(canonical_article_revision_id,canonical_article_id,source_revision_id,transformation_key,normalization_version,
		 rewrite_profile_version,status,normalized_source_document,normalized_source_hash,canonical_document,
		 canonical_body,canonical_steps,canonical_images,validation_report,validation_hash,rewrite_result_hash,model_metadata)
		SELECT $1::uuid,previous.canonical_article_id,j.source_revision_id,j.transformation_key,j.normalization_version,
		 j.rewrite_profile_version,'validated',previous.normalized_source_document,previous.normalized_source_hash,previous.canonical_document,
		 previous.canonical_body,previous.canonical_steps,previous.canonical_images,previous.validation_report,previous.validation_hash,
		 previous.rewrite_result_hash,previous.model_metadata
		FROM canonical_article_revisions previous JOIN source_fetch_jobs j USING(canonical_article_id)
		WHERE previous.canonical_article_revision_id=$2::uuid AND j.source_fetch_job_id=$3::uuid`,
		canonical, *current.CanonicalRevisionID, job)
	checkDenied()
	f.exec(`UPDATE source_fetch_jobs
		SET status='dead_letter',lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL
		WHERE source_fetch_job_id=$1::uuid`, job)
	checkDenied()
	f.exec(`UPDATE canonical_article_revisions SET status='published',published_at=now() WHERE canonical_article_revision_id=$1::uuid`, canonical)
	f.expect(0, http.MethodGet, sourcePath(staged), "", http.StatusOK)
	f.image(0, media, http.StatusOK)
	if stillCurrent := f.detail(0); !samePaidCatalogID(stillCurrent.SourceRevisionID, current.SourceRevisionID) ||
		!samePaidCatalogID(stillCurrent.CanonicalRevisionID, current.CanonicalRevisionID) {
		t.Fatal("publishing a historical source changed the selected reader anchor")
	}
}

func assertBoundStagedOriginal(t *testing.T, f *paidFixture, current CatalogArticle, staged, job, svgSnapshot, svgDigest, resolution, oldImage string) {
	t.Helper()
	currentSource, currentCanonical := *current.SourceRevisionID, *current.CanonicalRevisionID
	detailPath := f.path("/" + f.article)
	sourcePath := detailPath + "/source?source_revision_id=" + staged
	f.exec(`INSERT INTO canonical_article_source_observations
		(source_observation_id,canonical_article_id,source_revision_id,source_fetch_job_id,request_generation,
		 body_provider_revision,resource_provenance,captured_context,resolution_source_snapshot_id,descriptor_source_snapshot_id,captured_at)
		SELECT gen_random_uuid(),j.canonical_article_id,j.source_revision_id,j.source_fetch_job_id,j.request_generation,
		 'fixture-positioned',old.resource_provenance || jsonb_build_array(jsonb_build_object(
		 'role','asset_original','media_type','image/svg+xml','sha256',$4::text,'source_snapshot_id',$5::text)),
		 old.captured_context,$6::uuid,a.descriptor_source_snapshot_id,now()
		FROM source_fetch_jobs j JOIN canonical_articles a USING (canonical_article_id)
		JOIN LATERAL (SELECT resource_provenance,captured_context FROM canonical_article_source_observations
		 WHERE canonical_article_id=$1::uuid AND source_revision_id=$3::uuid ORDER BY captured_at,source_observation_id LIMIT 1) old ON true
		WHERE a.canonical_article_id=$1::uuid AND j.source_fetch_job_id=$2::uuid`,
		f.article, job, currentSource, svgDigest, svgSnapshot, resolution)
	f.exec(`UPDATE source_fetch_jobs SET checkpoint=jsonb_build_object('staged_media_refresh',jsonb_build_object(
		'version',1,'source_revision_id',$2::uuid,'prior_source_revision_id',$3::uuid,'prior_canonical_revision_id',$4::uuid))
		WHERE source_fetch_job_id=$1::uuid`, job, staged, currentSource, currentCanonical)
	var previousJob string
	if err := f.pool.QueryRow(context.Background(), `SELECT current_job_id::text FROM canonical_articles WHERE canonical_article_id=$1::uuid`, f.article).Scan(&previousJob); err != nil {
		t.Fatal(err)
	}
	f.exec(`UPDATE canonical_articles a SET current_job_id=j.source_fetch_job_id,request_generation=j.request_generation
		FROM source_fetch_jobs j WHERE j.source_fetch_job_id=$1::uuid AND a.canonical_article_id=j.canonical_article_id`, job)
	checkDetail := func(wantOriginal bool) CatalogArticle {
		t.Helper()
		got := f.detail(0)
		if !samePaidCatalogID(got.SourceRevisionID, current.SourceRevisionID) || !samePaidCatalogID(got.CanonicalRevisionID, current.CanonicalRevisionID) ||
			!samePaidCatalogID(got.ViewRevision, current.ViewRevision) || got.SourceReview == nil || got.SourceReview.URL != current.SourceReview.URL ||
			(got.OriginalSourceReview != nil) != wantOriginal {
			t.Fatal("staged capture changed the current rewrite or source citation, or returned the wrong Original metadata")
		}
		return got
	}
	for _, phase := range []string{"normalizing", "rewriting", "validating", "publishing"} {
		f.exec(`UPDATE source_fetch_jobs SET phase=$2 WHERE source_fetch_job_id=$1::uuid`, job, phase)
		checkDetail(true)
	}
	f.exec(`UPDATE source_fetch_jobs SET status='dead_letter',error_code='REWRITE_TECHNICAL_MUTATION',
		lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL WHERE source_fetch_job_id=$1::uuid`, job)
	metadata := checkDetail(true).OriginalSourceReview
	if !metadata.Available || metadata.URL != sourcePath || metadata.Version != "fixture-positioned" ||
		metadata.ContentSHA256 != current.SourceReview.ContentSHA256 || metadata.SnapshotID != current.SourceReview.SnapshotID {
		t.Fatal("staged Original metadata did not bind to the exact same-body source")
	}
	f.exec(`UPDATE source_fetch_jobs SET error_code='REWRITE_RESPONSE_INVALID' WHERE source_fetch_job_id=$1::uuid`, job)
	checkDetail(true)
	var selected CatalogSourceContentResponse
	if err := json.Unmarshal(f.expect(0, "GET", sourcePath, "", 200), &selected); err != nil || selected.Source != *metadata ||
		selected.Document == nil || len(selected.Document.Blocks) == 0 || len(selected.Images) == 0 || selected.Images[0].URL == "" {
		t.Fatal("staged Original did not return its exact protected document and media", err)
	}
	media := selected.Images[0].URL
	ref, err := openPaidCatalogImageReference(strings.TrimPrefix(media, "/v1/catalog/images/"), f.applications[0].catalogImageKey, time.Now())
	if err != nil || ref.Projection != "source" || ref.SelectedSourceRevisionID != staged || ref.AnchorSourceRevisionID != currentSource ||
		!samePaidCatalogID(ref.AnchorCanonicalRevisionID, current.CanonicalRevisionID) {
		t.Fatal("staged media was not bound to the approved pair", err)
	}
	f.image(0, media, 200)
	f.image(0, oldImage, 200)
	f.expect(-1, "GET", sourcePath, "", 401)
	f.expect(1, "GET", sourcePath, "", 403)
	f.expect(0, "GET", sourcePath+"&region=CA", "", 404)
	f.image(1, media, 404)
	store := newPostgresCatalogStore(f.pool)
	if _, err := store.ArticleSourceRevision(context.Background(), Principal{}, f.configuration, f.article, staged); !errors.Is(err, ErrCatalogNotFound) {
		t.Fatal("staged Original escaped the general source fence", err)
	}
	app := f.applications[0]
	app.workshopOpenDemoHost = "demo.cars.tk"
	demo := httptest.NewRequest("GET", "https://demo.cars.tk"+sourcePath+"&demo=1", nil)
	demoResult := httptest.NewRecorder()
	app.Handler().ServeHTTP(demoResult, demo)
	app.workshopOpenDemoHost = ""
	if demoResult.Code != 404 {
		t.Fatal("open demo admitted an unpublished Original")
	}
	htmlRequest := httptest.NewRequest("GET", "https://cars.example"+sourcePath, nil)
	htmlRequest.Header.Set("Accept", "text/html")
	htmlRequest.AddCookie(customerSessionCookie(f.owners[0].token, f.owners[0].session.ExpiresAt, time.Now()))
	html := httptest.NewRecorder()
	app.Handler().ServeHTTP(html, htmlRequest)
	if html.Code != 200 || !strings.Contains(html.Body.String(), "<img") {
		t.Fatal("standalone Original HTML omitted its authorized figure")
	}
	checkDenied := func() {
		t.Helper()
		before := f.reader.calls.Load()
		checkDetail(false)
		f.expect(0, "GET", sourcePath, "", 404)
		f.image(0, media, 404)
		if f.reader.calls.Load() != before {
			t.Fatal("blocked Original reached the image store")
		}
		f.image(0, oldImage, 200)
	}
	f.exec(`UPDATE source_snapshots SET takedown_status='takedown' WHERE source_snapshot_id=$1::uuid`, resolution)
	checkDenied()
	f.exec(`UPDATE source_snapshots SET takedown_status='active' WHERE source_snapshot_id=$1::uuid`, resolution)
	f.exec(`INSERT INTO source_artifacts (source_snapshot_id,artifact_kind,media_type,content_sha256,object_key,extraction_status)
		SELECT source_snapshot_id,'diagram','image/svg+xml',content_sha256,object_key,'quarantined' FROM source_snapshots WHERE source_snapshot_id=$1::uuid`, svgSnapshot)
	checkDenied()
	f.exec(`UPDATE source_artifacts SET extraction_status='complete' WHERE source_snapshot_id=$1::uuid`, svgSnapshot)
	checkDetail(true)
	f.exec(`UPDATE canonical_articles SET request_generation=request_generation+1 WHERE canonical_article_id=$1::uuid`, f.article)
	checkDenied()
	f.exec(`UPDATE canonical_articles SET current_job_id=$2::uuid WHERE canonical_article_id=$1::uuid`, f.article, previousJob)
	checkDenied()
	t.Log("verified staged Original kept the approved rewrite through recovery and candidate withdrawal")
}

func TestPostgresPaidCatalogCustomerLegacyRoutesDenied(t *testing.T) {
	f := paidSetup(t)
	order := f.grant(0, f.configuration, "US")
	legacyRequest := f.uuid()
	f.exec(`INSERT INTO dataset_requests(dataset_request_id,dataset_product_id,vehicle_key,region,status,lane,correlation_id,idempotency_key,processing_version,organization_id) SELECT $1::uuid,dataset_product_id,vehicle_key,region,status,lane,gen_random_uuid(),$1,'fixture-legacy',organization_id FROM dataset_requests WHERE dataset_request_id=(SELECT dataset_request_id FROM workshop_orders WHERE order_id=$2::uuid)`, legacyRequest, order)
	f.exec(`INSERT INTO entitlements(organization_id,dataset_request_id,provider_event_id,status,granted_at) VALUES($1::uuid,$2::uuid,$3,'active',now())`, f.owners[0].session.OrganizationID, legacyRequest, "legacy:"+legacyRequest)
	before := f.snapshot("before")
	routes := []string{"POST /dataset-requests", "GET /dataset-requests/x", "POST /vehicle-identities/resolve", "GET /vehicle-identities/selectors", "POST /knowledge-queries", "POST /job-plans", "GET /datasets/x", "GET /datasets/x/sections", "GET /datasets/x/revisions", "GET /datasets/x/evidence/x", "GET /datasets/x/search", "GET /datasets/x/knowledge", "POST /datasets/x/feedback"}
	for _, route := range routes {
		parts := strings.SplitN(route, " ", 2)
		f.expect(0, parts[0], parts[1], "{}", 403)
	}
	f.check("thirteen_routes_denied_before_work", paidWorkUnchanged(before, f.snapshot("denied")))
	for _, route := range routes {
		parts := strings.SplitN(route, " ", 2)
		f.expect(-1, parts[0], parts[1], "{}", 401)
	}
	f.check("unauthenticated_401", true)
	local := catalogServer(catalogFixtureStore())
	w := httptest.NewRecorder()
	local.Handler().ServeHTTP(w, httptest.NewRequest("GET", "/v1/catalog/vehicles/vehicle-1/articles/article-1", nil))
	f.observe(-1, "GET", "/v1/catalog/vehicles/vehicle-1/articles/article-1", w.Code, w.Header(), w.Body.Bytes(), f.reader.calls.Load(), f.verifier.calls.Load())
	f.check("explicit_local_compatibility", w.Code == 200 && !local.paidCatalogEnabled())
	f.snapshot("final")
}
