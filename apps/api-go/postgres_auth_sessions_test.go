package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func TestPostgresCustomerStoreRequiresLiveSchema(t *testing.T) {
	store := &postgresCustomerSessions{}
	if err := store.CheckSchema(context.Background()); !errors.Is(err, ErrCustomerDependency) {
		t.Fatal("nil persistence accepted", err)
	}
}
func customerIntegrationPool(t *testing.T, variable string) *pgxpool.Pool {
	t.Helper()
	raw := os.Getenv(variable)
	u, err := url.Parse(raw)
	if os.Getenv("AUTODATA_REQUIRE_AUTH_INTEGRATION") != "1" {
		t.Skip("requires private auth fixture")
	}
	if os.Getenv("AUTODATA_LIFECYCLE_TEST") != "1" || err != nil || u.Host != "postgres:5432" || u.User == nil || u.User.Username() != "lifecycle_test" || !strings.HasPrefix(strings.TrimPrefix(u.Path, "/"), "lifecycle_test_") {
		t.Fatal("isolated auth fixture configuration required")
	}
	pool, err := pgxpool.New(context.Background(), raw)
	if err != nil {
		t.Fatal("fixture pool creation failed")
	}
	t.Cleanup(pool.Close)
	if err = pool.Ping(context.Background()); err != nil {
		t.Fatal("fixture database unavailable")
	}
	return pool
}
func TestPostgresAuthSessionsIntegration(t *testing.T) {
	pool := customerIntegrationPool(t, "AUTODATA_AUTH_TEST_DATABASE_URL")
	store := &postgresCustomerSessions{pool: pool}
	if err := store.CheckSchema(context.Background()); err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	now := time.Now().UTC().Truncate(time.Microsecond)
	identity := func(uid string) VerifiedCustomerIdentity {
		return VerifiedCustomerIdentity{ProjectID: "fixture-project", UID: uid, AuthTime: now.Unix(), IssuedAt: now.Unix(), Expires: now.Add(time.Hour).Unix()}
	}
	t.Run("ConcurrentCustomerProvisionAndRotation", func(t *testing.T) {
		other := customerIntegrationPool(t, "AUTODATA_AUTH_TEST_DATABASE_URL")
		stores := []*postgresCustomerSessions{store, {pool: other}}
		var wg sync.WaitGroup
		results := make(chan customerSession, 20)
		errs := make(chan error, 20)
		for i := 0; i < 20; i++ {
			wg.Add(1)
			go func(i int) {
				defer wg.Done()
				_, hash, err := newCustomerSessionToken()
				if err != nil {
					errs <- err
					return
				}
				s, err := stores[i%2].Rotate(ctx, identity("racing"), hash, nil, now, now.Add(customerSessionLifetime))
				if err != nil {
					errs <- err
					return
				}
				results <- s
			}(i)
		}
		wg.Wait()
		close(results)
		close(errs)
		for err := range errs {
			t.Fatal(err)
		}
		var account, org string
		count := 0
		for result := range results {
			count++
			if account == "" {
				account = result.AccountID
				org = result.OrganizationID
			}
			if account != result.AccountID || org != result.OrganizationID {
				t.Fatal("duplicate customer identity")
			}
		}
		if count != 20 {
			t.Fatal("missing racing results")
		}
		_, old, _ := newCustomerSessionToken()
		if _, err := store.Rotate(ctx, identity("rotation"), old, nil, now, now.Add(time.Hour)); err != nil {
			t.Fatal(err)
		}
		if _, err := store.Rotate(ctx, identity("rotation"), old, old, now, now.Add(time.Hour)); err == nil {
			t.Fatal("duplicate new session hash accepted")
		}
		if _, err := store.Lookup(ctx, old, now); err != nil {
			t.Fatal("failed rotation revoked old session")
		}
		_, next, _ := newCustomerSessionToken()
		if _, err := store.Rotate(ctx, identity("rotation"), next, old, now, now.Add(time.Hour)); err != nil {
			t.Fatal(err)
		}
		if _, err := store.Lookup(ctx, old, now); !errors.Is(err, ErrUnauthenticated) {
			t.Fatal("committed old session still valid")
		}
		foreign := identity("racing")
		foreign.ProjectID = "other-project"
		_, hash, _ := newCustomerSessionToken()
		s, err := store.Rotate(ctx, foreign, hash, nil, now, now.Add(time.Hour))
		if err != nil || s.AccountID == account || s.OrganizationID == org {
			t.Fatal("project identity isolation failed")
		}
	})
	t.Run("SharedSessionRevocation", func(t *testing.T) {
		token, hash, _ := newCustomerSessionToken()
		if _, err := store.Rotate(ctx, identity("revocation"), hash, nil, now, now.Add(time.Hour)); err != nil {
			t.Fatal(err)
		}
		other := &postgresCustomerSessions{pool: customerIntegrationPool(t, "AUTODATA_AUTH_TEST_DATABASE_URL")}
		makeService := func(persist customerSessionStore) *customerAuthService {
			return &customerAuthService{config: customerAuthConfig{Mode: "firebase", Origin: "https://cars.example"}, store: persist, verifier: &customerVerifierFixture{}, now: func() time.Time { return now }}
		}
		a := httptest.NewTLSServer(customerAuthHandler(makeService(store)))
		defer a.Close()
		b := httptest.NewTLSServer(customerAuthHandler(makeService(other)))
		defer b.Close()
		cookie := customerSessionCookie(token, now.Add(time.Hour), now)
		call := func(server *httptest.Server, method, path string) *http.Response {
			request, _ := http.NewRequest(method, server.URL+path, nil)
			request.AddCookie(cookie)
			if method == "POST" {
				request.Header.Set("Origin", "https://cars.example")
				request.Header.Set("X-CSRF-Token", customerCSRF(token))
			}
			response, err := server.Client().Do(request)
			if err != nil {
				t.Fatal(err)
			}
			io.Copy(io.Discard, response.Body)
			response.Body.Close()
			return response
		}
		if call(b, "GET", "/auth/session").StatusCode != 200 {
			t.Fatal("B rejected session minted by A store")
		}
		if call(a, "POST", "/auth/logout").StatusCode != 204 {
			t.Fatal("A logout failed")
		}
		if call(b, "GET", "/auth/session").StatusCode != 401 {
			t.Fatal("B accepted locally revoked session")
		}
		_, hash, _ = newCustomerSessionToken()
		session, err := store.Rotate(ctx, identity("blocked"), hash, nil, now, now.Add(time.Hour))
		if err != nil {
			t.Fatal(err)
		}
		if _, err = pool.Exec(ctx, "UPDATE customer_accounts SET status='blocked' WHERE customer_account_id=$1::uuid", session.AccountID); err != nil {
			t.Fatal(err)
		}
		if _, err = other.Lookup(ctx, hash, now); !errors.Is(err, ErrCustomerBlocked) {
			t.Fatal("account block ignored")
		}
	})
	t.Run("ExpiryAndPersistedSecrecy", func(t *testing.T) {
		token, hash, _ := newCustomerSessionToken()
		s, err := store.Rotate(ctx, identity("expiry"), hash, nil, now, now.Add(time.Hour))
		if err != nil {
			t.Fatal(err)
		}
		if _, err = store.Lookup(ctx, hash, now.Add(time.Hour)); !errors.Is(err, ErrUnauthenticated) {
			t.Fatal("expiry boundary accepted")
		}
		var raw []byte
		var length int
		if err = pool.QueryRow(ctx, "SELECT row_to_json(s)::text,octet_length(session_token_hash) FROM auth_sessions s WHERE session_token_hash=$1", hash).Scan(&raw, &length); err != nil {
			t.Fatal(err)
		}
		if length != 32 || bytes.Contains(raw, []byte(token)) {
			t.Fatal("persisted raw session")
		}
		actual := sha256.Sum256([]byte(token))
		if !bytes.Equal(actual[:], hash) {
			t.Fatal("wrong session hash")
		}
		_, other, _ := newCustomerSessionToken()
		again, err := store.Rotate(ctx, identity("expiry"), other, nil, now.Add(2*time.Hour), now.Add(3*time.Hour))
		if err != nil || again.AccountID != s.AccountID {
			t.Fatal("account failed restart/expiry continuity")
		}
	})
	t.Run("FirebaseExchangeAndUserRevocation", func(t *testing.T) { testFirebaseExchangeAndUserRevocation(t, store) })
	t.Run("FirebaseStartupRequiresMigratedPostgres", func(t *testing.T) {
		config := customerAuthConfig{Mode: "firebase", Origin: "https://cars.example", ProjectID: "fixture-project"}
		if _, err := newConfiguredCustomerAuth(ctx, config, store, &customerVerifierFixture{}); err != nil {
			t.Fatal("full039 startup failed", err)
		}
		if _, err := newConfiguredCustomerAuth(ctx, config, &customerSessionFixture{}, &customerVerifierFixture{}); !errors.Is(err, ErrCustomerDependency) {
			t.Fatal("memory startup accepted")
		}
		unavailable := customerIntegrationPool(t, "AUTODATA_AUTH_TEST_DATABASE_URL")
		unavailable.Close()
		if _, err := newConfiguredCustomerAuth(ctx, config, &postgresCustomerSessions{pool: unavailable}, &customerVerifierFixture{}); !errors.Is(err, ErrCustomerDependency) {
			t.Fatal("unavailable pool startup accepted")
		}

		if err := store.CheckSchema(ctx); err != nil {
			t.Fatal(err)
		}
		old := &postgresCustomerSessions{pool: customerIntegrationPool(t, "AUTODATA_AUTH_TEST_UNMIGRATED_DATABASE_URL")}
		if err := old.CheckSchema(ctx); !errors.Is(err, ErrCustomerDependency) {
			t.Fatal("038 schema accepted")
		}
		var count int
		if err := old.pool.QueryRow(ctx, "SELECT count(*) FROM schema_migrations").Scan(&count); err != nil || count != 38 {
			t.Fatal("startup mutated historical database")
		}
	})
}
