package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"errors"
	firebaseadmin "firebase.google.com/go/v4"
	"google.golang.org/api/option"
	"io"
	"math/big"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"sync"
	"testing"
	"time"
)

// Shared test-only timing; decoding rejects duplicate/unknown keys and non-integers.
type workshopBrowserTiming struct {
	Values map[string]int
	SHA256 string
}

func loadWorkshopBrowserTiming(path string) (workshopBrowserTiming, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return workshopBrowserTiming{}, err
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	token, err := decoder.Token()
	if err != nil || token != json.Delim('{') {
		return workshopBrowserTiming{}, errors.New("timing object required")
	}
	allowed := map[string]bool{"version": true, "engines": true, "scenarios_per_engine": true, "case_execution_seconds": true, "case_cleanup_seconds": true, "provenance_seconds": true, "playwright_start_seconds": true, "engine_launch_seconds": true, "engine_close_seconds": true, "playwright_stop_seconds": true, "evidence_persistence_seconds": true, "worker_hard_seconds": true, "producer_hard_seconds": true, "worker_term_seconds": true, "worker_kill_seconds": true, "worker_reap_seconds": true, "readiness_seconds": true, "handoff_seconds": true, "fixture_stop_seconds": true, "safety_seconds": true, "dto_fixture_seconds": true, "api_fixture_seconds": true, "go_test_seconds": true, "fixture_startup_seconds": true, "fixture_teardown_seconds": true, "ci_exercise_seconds": true, "ci_job_minutes": true, "parent_initialization_seconds": true, "parent_progress_read_parse_seconds": true, "parent_final_read_parse_stage_seconds": true, "parent_commit_seconds": true, "io_helper_term_seconds": true, "io_helper_kill_seconds": true, "io_helper_reap_seconds": true, "max_io_helper_cleanup_episodes": true, "parent_scheduling_reserve_seconds": true, "worker_deadline_reserve_seconds": true}
	values := map[string]int{}
	seen := map[string]bool{}
	for decoder.More() {
		token, err = decoder.Token()
		if err != nil {
			return workshopBrowserTiming{}, err
		}
		key, ok := token.(string)
		if !ok || seen[key] || !allowed[key] {
			return workshopBrowserTiming{}, errors.New("duplicate/unknown timing key")
		}
		seen[key] = true
		var value any
		if err = decoder.Decode(&value); err != nil {
			return workshopBrowserTiming{}, err
		}
		if key == "version" {
			if value != "v1" {
				return workshopBrowserTiming{}, errors.New("timing version")
			}
			continue
		}
		number, ok := value.(json.Number)
		if !ok {
			return workshopBrowserTiming{}, errors.New("integer required")
		}
		integer, err := number.Int64()
		if err != nil || integer <= 0 || integer > 1000000 {
			return workshopBrowserTiming{}, errors.New("positive bounded integer required")
		}
		values[key] = int(integer)
	}
	if _, err = decoder.Token(); err != nil {
		return workshopBrowserTiming{}, err
	}
	var tail any
	if decoder.Decode(&tail) != io.EOF || len(seen) != len(allowed) {
		return workshopBrowserTiming{}, errors.New("incomplete timing")
	}
	t := values
	serial := t["provenance_seconds"] + t["playwright_start_seconds"] + 3*t["engine_launch_seconds"] + 120*(t["case_execution_seconds"]+t["case_cleanup_seconds"]) + 3*t["engine_close_seconds"] + t["playwright_stop_seconds"] + t["evidence_persistence_seconds"]
	cleanup := t["worker_term_seconds"] + t["worker_kill_seconds"] + t["worker_reap_seconds"] + 2*(t["io_helper_term_seconds"]+t["io_helper_kill_seconds"]+t["io_helper_reap_seconds"])
	parent := t["parent_initialization_seconds"] + t["worker_hard_seconds"] + cleanup + t["parent_final_read_parse_stage_seconds"] + t["parent_commit_seconds"] + t["parent_scheduling_reserve_seconds"]
	fixture := t["readiness_seconds"] + t["handoff_seconds"] + t["producer_hard_seconds"] + t["fixture_stop_seconds"] + t["safety_seconds"]
	goBound := t["fixture_startup_seconds"] + t["dto_fixture_seconds"] + t["fixture_teardown_seconds"]
	if t["engines"] != 3 || t["scenarios_per_engine"] != 40 || t["case_execution_seconds"] != 20 || t["case_cleanup_seconds"] != 3 || t["producer_hard_seconds"] != 4440 || t["api_fixture_seconds"] != 4400 || t["max_io_helper_cleanup_episodes"] != 2 || serial >= t["worker_hard_seconds"] || parent >= t["producer_hard_seconds"] || fixture >= t["dto_fixture_seconds"] || goBound >= t["go_test_seconds"] || t["go_test_seconds"]+t["fixture_stop_seconds"]+t["evidence_persistence_seconds"] >= t["ci_exercise_seconds"] || t["ci_exercise_seconds"] >= 60*t["ci_job_minutes"] || cleanup+t["parent_final_read_parse_stage_seconds"]+t["parent_commit_seconds"]+t["parent_scheduling_reserve_seconds"] > t["worker_deadline_reserve_seconds"] {
		return workshopBrowserTiming{}, errors.New("inconsistent timing schedule")
	}
	digest := sha256.Sum256(raw)
	return workshopBrowserTiming{Values: values, SHA256: hex.EncodeToString(digest[:])}, nil
}
func workshopBrowserFixtureLifetime(paid bool, timing workshopBrowserTiming) time.Duration {
	if paid {
		return 4400 * time.Second
	}
	return time.Duration(timing.Values["dto_fixture_seconds"]) * time.Second
}
func workshopBrowserFixtureEnded(stopped <-chan struct{}, deadline <-chan time.Time) bool {
	select {
	case <-stopped:
		return false
	case <-deadline:
		return true
	}
}

// Explicit test-only process entry point. It always serves the production
// embedded assets, over TLS; DTO interception belongs to the browser harness.
func TestWorkshopBrowserFixtureHTTP(t *testing.T) {
	if os.Getenv("AUTODATA_WORKSHOP_BROWSER_FIXTURE") != "1" {
		return
	}
	output := os.Getenv("AUTODATA_WORKSHOP_BROWSER_READY")
	if output == "" {
		t.Fatal("owned fixture ready-file path is required")
	}
	var paid *paidFixture
	if os.Getenv("AUTODATA_REQUIRE_WORKSHOP_BROWSER_INTEGRATION") == "1" {
		if os.Getenv("AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION") != "1" {
			t.Fatal("real paid fixture flag required")
		}
		paid = paidSetup(t)
	}
	firebase := newWorkshopFirebaseSDKFixture(t)
	server, customer := newWorkshopBrowserApplication(t, paid, firebase, "https://fixture.invalid")
	stopped := make(chan struct{})
	restart := make(chan struct{}, 1)
	generation := 1
	var once sync.Once
	var tlsServer *httptest.Server
	mux := http.NewServeMux()
	mux.HandleFunc("GET /__fixture/token", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		uid := "fixture-user"
		if r.URL.Query().Get("account") == "other" {
			uid = "fixture-other"
		}
		token := firebase.token(t, func(claims map[string]any) {
			claims["sub"] = uid
			if r.URL.Query().Get("stale") == "1" {
				claims["auth_time"] = firebase.now.Unix() - 301
			}
		})
		writeJSON(w, 200, map[string]any{"idToken": token, "refreshToken": "synthetic-refresh-never-persist", "expiresIn": "3600", "localId": uid, "email": "fixture@example.invalid", "providerId": "google.com"})
	})
	mux.HandleFunc("POST /__fixture/stop", func(w http.ResponseWriter, r *http.Request) { once.Do(func() { close(stopped) }); w.WriteHeader(204) })
	mux.HandleFunc("GET /__fixture/runtime", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"application_generation": generation})
	})
	mux.HandleFunc("POST /__fixture/restart", func(w http.ResponseWriter, r *http.Request) {
		if paid == nil {
			http.Error(w, "actual fixture required", 400)
			return
		}
		w.WriteHeader(204)
		if flush, ok := w.(http.Flusher); ok {
			flush.Flush()
		}
		select {
		case restart <- struct{}{}:
		default:
		}
	})
	mux.HandleFunc("GET /__fixture/policy/{kind}", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		io.WriteString(w, "Synthetic browser fixture policy. No merchant or live payment.")
	})
	if paid != nil {
		mountWorkshopPaidControls(t, mux, paid, firebase, func() *httptest.Server { return tlsServer })
		mux.HandleFunc("GET /workshop/purchase-config.json", func(w http.ResponseWriter, r *http.Request) {
			origin := "https://" + r.Host
			writeJSON(w, 200, map[string]any{"enabled": true, "terms_version": "workshop-v1", "terms_url": origin + "/__fixture/policy/terms", "privacy_url": origin + "/__fixture/policy/privacy", "refund_url": origin + "/__fixture/policy/refund", "contact_url": origin + "/__fixture/policy/contact", "tax_notice": "Synthetic fixture tax included."})
		})
	}
	application := server.Handler()
	mux.Handle("/", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { application.ServeHTTP(w, r) }))
	tlsServer = httptest.NewTLSServer(mux)
	defer func() { tlsServer.Close() }()
	if customer != nil {
		customer.config.Origin = tlsServer.URL
	}
	digest := sha256.Sum256(tlsServer.Certificate().Raw)
	sdk, err := dashboardFiles.ReadFile("workshop/firebase-web.mjs")
	if err != nil {
		t.Fatal(err)
	}
	sdkHash := sha256.Sum256(sdk)
	metadata := map[string]any{"version": "v1", "kind": "dto-fixture", "origin": tlsServer.URL, "certificate_sha256": hex.EncodeToString(digest[:]), "sdk_sha256": hex.EncodeToString(sdkHash[:])}
	if paid != nil {
		metadata["kind"] = "api-fixture"
		metadata["scope"] = map[string]string{"configuration": paid.configuration, "adjacent": paid.adjacent, "other_region": paid.regionConfiguration, "vehicle": paid.vehicle, "article": paid.article, "unscoped": paid.unscoped, "provider": paid.provider}
	}
	timing := workshopBrowserTiming{}
	if paid == nil {
		timing, err = loadWorkshopBrowserTiming("../../scripts/dev/fixtures/workshop_customer/timing.json")
		if err != nil {
			t.Fatal(err)
		}
		metadata["lifetime_seconds"] = int(workshopBrowserFixtureLifetime(false, timing) / time.Second)
		metadata["timing_contract_sha256"] = timing.SHA256
	}
	// Start before readiness publication so handoff consumes the selected lifetime.
	deadline := time.NewTimer(workshopBrowserFixtureLifetime(paid != nil, timing))
	defer deadline.Stop()
	body, _ := json.Marshal(metadata)
	if err = os.WriteFile(output, body, 0600); err != nil {
		t.Fatal(err)
	}
	for {
		select {
		case <-stopped:
			return
		case <-deadline.C:
			t.Fatal("browser fixture hard deadline exceeded")
		case <-restart:
			origin := tlsServer.URL
			// Close waits for every prior handler before replacing application state.
			tlsServer.Close()
			server, customer = newWorkshopBrowserApplication(t, paid, firebase, origin)
			application = server.Handler()
			generation++
			var err error
			tlsServer, err = restartWorkshopTLSFixture(tlsServer, mux)
			if err != nil {
				t.Fatal(err)
			}
		}
	}
}

// The single-user identity helper is extended here only for browser account isolation.
func newWorkshopFirebaseSDKFixture(t *testing.T) *firebaseSDKFixture {
	t.Helper()
	for key, value := range map[string]string{"FIREBASE_AUTH_EMULATOR_HOST": "", "GOOGLE_API_GO_EXPERIMENTAL_DISABLE_NEW_AUTH_LIB": "true", "GOOGLE_API_USE_CLIENT_CERTIFICATE": "false", "GOOGLE_API_USE_MTLS_ENDPOINT": "never", "EXPERIMENTAL_GOOGLE_API_USE_S2A": "false"} {
		t.Setenv(key, value)
	}
	f := &firebaseSDKFixture{now: time.Now().UTC().Truncate(time.Second)}
	var err error
	f.key, err = rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	cert := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "fixture-token-key"}, NotBefore: f.now.Add(-time.Hour), NotAfter: f.now.Add(time.Hour), KeyUsage: x509.KeyUsageDigitalSignature}
	der, err := x509.CreateCertificate(rand.Reader, cert, cert, &f.key.PublicKey, f.key)
	if err != nil {
		t.Fatal(err)
	}
	certPEM := string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}))
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" && r.URL.Path == "/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com" {
			f.certCalls.Add(1)
			w.Header().Set("Cache-Control", "max-age=3600")
			json.NewEncoder(w).Encode(map[string]string{"fixture-key": certPEM})
			return
		}
		if r.Method == "POST" && r.URL.Path == "/v1/projects/fixture-project/accounts:lookup" {
			f.userCalls.Add(1)
			f.mu.Lock()
			defer f.mu.Unlock()
			if f.delay > 0 {
				select {
				case <-r.Context().Done():
					return
				case <-time.After(f.delay):
				}
			}
			if f.status != 0 {
				w.WriteHeader(f.status)
				json.NewEncoder(w).Encode(map[string]any{"error": map[string]any{"message": "PERMISSION_DENIED"}})
				return
			}
			if f.deleted {
				json.NewEncoder(w).Encode(map[string]any{"users": []any{}})
				return
			}
			var lookup struct {
				LocalID []string `json:"localId"`
			}
			if json.NewDecoder(r.Body).Decode(&lookup) != nil || len(lookup.LocalID) != 1 || (lookup.LocalID[0] != "fixture-user" && lookup.LocalID[0] != "fixture-other") {
				http.Error(w, "unexpected fixture identity", 400)
				return
			}
			json.NewEncoder(w).Encode(map[string]any{"users": []any{map[string]any{"localId": lookup.LocalID[0], "disabled": f.disabled, "validSince": strconv.FormatInt(f.validSince, 10)}}})
			return
		}
		f.unexpected.Add(1)
		http.Error(w, "unexpected fixture request", 500)
	}))
	t.Cleanup(server.Close)
	dial := &tls.Dialer{NetDialer: &net.Dialer{}, Config: server.Client().Transport.(*http.Transport).TLSClientConfig.Clone()}
	transport := func(allowed string) *http.Transport {
		return &http.Transport{Proxy: nil, DialTLSContext: func(ctx context.Context, network, address string) (net.Conn, error) {
			if address != allowed {
				f.unexpected.Add(1)
				return nil, errors.New("unexpected SDK destination")
			}
			return dial.DialContext(ctx, network, server.Listener.Addr().String())
		}}
	}
	previous := http.DefaultTransport
	certTransport := transport("www.googleapis.com:443")
	http.DefaultTransport = certTransport
	t.Cleanup(func() { http.DefaultTransport = previous; certTransport.CloseIdleConnections() })
	userTransport := transport("identitytoolkit.googleapis.com:443")
	t.Cleanup(userTransport.CloseIdleConnections)
	app, err := firebaseadmin.NewApp(context.Background(), &firebaseadmin.Config{ProjectID: "fixture-project"}, option.WithoutAuthentication(), option.WithHTTPClient(&http.Client{Transport: userTransport, Timeout: 2 * time.Second}))
	if err != nil {
		t.Fatal(err)
	}
	client, err := app.Auth(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	f.verifier = &firebaseCustomerVerifier{client: client, projectID: "fixture-project", now: func() time.Time { return f.now }}
	t.Cleanup(func() {
		if f.unexpected.Load() != 0 {
			t.Errorf("unexpected SDK dials/requests: %d", f.unexpected.Load())
		}
	})
	return f
}

// These routes are compiled only into the guarded test process, never production.
func mountWorkshopPaidControls(t *testing.T, mux *http.ServeMux, paid *paidFixture, identity *firebaseSDKFixture, public func() *httptest.Server) {
	mux.HandleFunc("GET /__fixture/metadata", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"kind": "api-fixture", "scope": map[string]string{"configuration": paid.configuration, "adjacent": paid.adjacent, "other_region": paid.regionConfiguration, "vehicle": paid.vehicle, "article": paid.article, "unscoped": paid.unscoped, "provider": paid.provider}})
	})
	mux.HandleFunc("GET /__fixture/measurement", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		result := map[string]any{}
		for _, table := range []string{"auth_sessions", "workshop_orders", "workshop_checkout_requests", "entitlements", "dataset_requests", "dataset_projections", "payment_events"} {
			var count int
			if err := paid.pool.QueryRow(ctx, "SELECT count(*) FROM "+table).Scan(&count); err != nil {
				http.Error(w, "fixture measurement failed", 500)
				return
			}
			result[table] = count
		}
		rows, err := paid.pool.Query(ctx, "SELECT order_id::text,status,customer_account_id::text,configuration_id::text,region FROM workshop_orders ORDER BY created_at")
		if err != nil {
			http.Error(w, "fixture orders failed", 500)
			return
		}
		defer rows.Close()
		orders := []map[string]string{}
		for rows.Next() {
			var id, state, owner, configuration, region string
			if rows.Scan(&id, &state, &owner, &configuration, &region) != nil {
				http.Error(w, "fixture row failed", 500)
				return
			}
			orders = append(orders, map[string]string{"order_id": id, "state": state, "owner": owner, "configuration_id": configuration, "region": region})
		}
		var hashed int
		if err := paid.pool.QueryRow(ctx, "SELECT count(*) FROM auth_sessions WHERE octet_length(session_token_hash)=32").Scan(&hashed); err != nil {
			http.Error(w, "fixture session measurement failed", 500)
			return
		}
		result["hashed_sessions"] = hashed
		result["orders"] = orders
		result["sdk_cert_calls"] = identity.certCalls.Load()
		result["sdk_user_calls"] = identity.userCalls.Load()
		result["sdk_unexpected"] = identity.unexpected.Load()
		result["image_reads"] = paid.reader.calls.Load()
		writeJSON(w, 200, result)
	})
	mux.HandleFunc("GET /__fixture/snapshot", func(w http.ResponseWriter, r *http.Request) {
		req, _ := http.NewRequestWithContext(r.Context(), "GET", paid.control.control+"/r3-fixture/snapshot", nil)
		req.Header.Set("X-R3-Fixture-Token", paid.control.token)
		response, err := (&http.Client{Timeout: 3 * time.Second}).Do(req)
		if err != nil {
			http.Error(w, "fixture snapshot unavailable", 500)
			return
		}
		defer response.Body.Close()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(response.StatusCode)
		io.Copy(w, io.LimitReader(response.Body, 8<<20))
	})
	mux.HandleFunc("POST /__fixture/disable", func(w http.ResponseWriter, r *http.Request) {
		identity.mu.Lock()
		identity.disabled = true
		identity.mu.Unlock()
		w.WriteHeader(204)
	})
	mux.HandleFunc("POST /__fixture/control/{action}", func(w http.ResponseWriter, r *http.Request) {
		paths := map[string]string{"start-workers": "/r3-fixture/start-workers", "release-model": "/r3-fixture/release-model", "lose-response": "/browser-fixture/lose-response"}
		path, ok := paths[r.PathValue("action")]
		if !ok {
			http.Error(w, "unknown fixture action", 400)
			return
		}
		req, _ := http.NewRequestWithContext(r.Context(), "POST", paid.control.control+path, nil)
		req.Header.Set("X-R3-Fixture-Token", paid.control.token)
		response, err := (&http.Client{Timeout: 5 * time.Second}).Do(req)
		if err != nil {
			http.Error(w, "fixture control unavailable", 500)
			return
		}
		defer response.Body.Close()
		w.WriteHeader(response.StatusCode)
		io.Copy(w, io.LimitReader(response.Body, 1<<20))
	})
	mux.HandleFunc("POST /__fixture/payment/{action}", func(w http.ResponseWriter, r *http.Request) {
		action := r.PathValue("action")
		order := r.URL.Query().Get("order_id")
		if (action != "settle" && action != "refund") || !commerceUUID(order) {
			http.Error(w, "invalid fixture event", 400)
			return
		}
		req, _ := http.NewRequestWithContext(r.Context(), "GET", paid.control.control+"/browser-fixture/event?order_id="+order+"&action="+action, nil)
		req.Header.Set("X-R3-Fixture-Token", paid.control.token)
		response, err := (&http.Client{Timeout: 5 * time.Second}).Do(req)
		if err != nil {
			http.Error(w, "fixture event unavailable", 500)
			return
		}
		defer response.Body.Close()
		var event struct {
			Signature string `json:"signature"`
			Body      string `json:"body"`
		}
		if response.StatusCode != 200 || json.NewDecoder(response.Body).Decode(&event) != nil {
			http.Error(w, "fixture event invalid", 500)
			return
		}
		// Actual public webhook, official private verifier and reconciler; no grant insertion.
		api := public()
		webhook, _ := http.NewRequestWithContext(r.Context(), "POST", api.URL+"/v1/payments/stripe/webhook", bytes.NewBufferString(event.Body))
		webhook.Header.Set("Stripe-Signature", event.Signature)
		webhook.Header.Set("Content-Type", "application/json")
		client := *api.Client()
		client.Timeout = 5 * time.Second
		delivered, err := client.Do(webhook)
		if err != nil {
			http.Error(w, "actual webhook delivery failed", 500)
			return
		}
		defer delivered.Body.Close()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(delivered.StatusCode)
		io.Copy(w, io.LimitReader(delivered.Body, 1<<20))
	})
}

func TestWorkshopBrowserOfficialIdentityAccounts(t *testing.T) {
	identity := newWorkshopFirebaseSDKFixture(t)
	for _, uid := range []string{"fixture-user", "fixture-other"} {
		token := identity.token(t, func(claims map[string]any) { claims["sub"] = uid })
		verified, err := identity.verifier.VerifyLogin(context.Background(), token)
		if err != nil || verified.UID != uid {
			t.Fatalf("official browser identity fixture failed for %s: %v", uid, err)
		}
	}
	if identity.certCalls.Load() == 0 || identity.userCalls.Load() < 4 || identity.unexpected.Load() != 0 {
		t.Fatal("official signature and current-user fixture calls missing")
	}
}

func TestWorkshopBrowserRestartPreservesOriginAndReplacesHandler(t *testing.T) {
	first := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "first application") }))
	defer first.Close()
	origin := first.URL
	response, err := first.Client().Get(origin)
	if err != nil {
		t.Fatal(err)
	}
	body, _ := io.ReadAll(response.Body)
	response.Body.Close()
	if string(body) != "first application" {
		t.Fatal("initial application missing")
	}
	second, err := restartWorkshopTLSFixture(first, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "fresh application") }))
	if err != nil {
		t.Fatal(err)
	}
	defer second.Close()
	if second.URL != origin {
		t.Fatal("restart changed cookie origin")
	}
	response, err = second.Client().Get(origin)
	if err != nil {
		t.Fatal(err)
	}
	body, _ = io.ReadAll(response.Body)
	response.Body.Close()
	if string(body) != "fresh application" {
		t.Fatal("restart retained old handler")
	}
}

func newWorkshopBrowserApplication(t *testing.T, paid *paidFixture, firebase *firebaseSDKFixture, origin string) (*Server, *customerAuthService) {
	t.Helper()
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	var customer *customerAuthService
	if paid != nil {
		var err error
		customer, err = newConfiguredCustomerAuth(context.Background(), customerAuthConfig{Environment: "test", Mode: "firebase", Origin: origin, ProjectID: "fixture-project", APIKey: "fixture-key", AuthDomain: "fixture-project.firebaseapp.com", AppID: "1:123456:web:abcdef"}, &postgresCustomerSessions{pool: paid.pool}, firebase.verifier)
		if err != nil {
			t.Fatal(err)
		}
		server = NewServerWithCatalogStore(staticReadiness{}, customer, newMemoryRequestStore(), newPostgresCatalogStore(paid.pool))
		server.customerAuth = customer
		server.commerceClient = paid.applications[0].commerceClient
		server.ingestionClient = paid.applications[0].ingestionClient
		server.catalogImageKey = paid.applications[0].catalogImageKey
		server.catalogImageReader = paid.reader
		if err = server.validatePaidCatalogDependencies(); err != nil {
			t.Fatal(err)
		}
	}
	return server, customer
}

// Rebind the exact HTTPS origin after terminating the prior HTTP server. The
// caller constructs fresh production application/store/auth instances over PG.
func restartWorkshopTLSFixture(previous *httptest.Server, handler http.Handler) (*httptest.Server, error) {
	address := previous.Listener.Addr().String()
	previous.Close()
	listener, err := net.Listen("tcp", address)
	if err != nil {
		return nil, err
	}
	next := httptest.NewUnstartedServer(handler)
	next.Listener.Close()
	next.Listener = listener
	next.TLS = previous.TLS.Clone()
	next.StartTLS()
	return next, nil
}
