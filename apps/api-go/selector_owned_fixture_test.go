package main

import (
	"context"
	"encoding/json"
	"net"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Opt-in cross-language fixture: actual Go handler -> Python HTTP -> owned
// authored connector -> PostgreSQL, followed by the real catalog store read.
func newOwnedSelectorFixture(t *testing.T) (*Server, *pgxpool.Pool, context.Context) {
	t.Helper()
	if os.Getenv("AUTODATA_SELECTOR_GO_TEST") != "1" {
		t.Skip("explicit isolated selector fixture required")
	}
	dsn := os.Getenv("AUTODATA_SELECTOR_GO_DSN")
	u, err := url.Parse(dsn)
	if err != nil || u.Scheme != "postgres" || !regexp.MustCompile(`^/selector436_test_[a-f0-9]{32}$`).MatchString(u.Path) || u.User == nil || u.User.Username() != "selector436" || !strings.HasPrefix(u.Hostname(), "172.") || net.ParseIP(u.Hostname()) == nil || !net.ParseIP(u.Hostname()).IsPrivate() {
		t.Fatal("isolated selector database required")
	}
	password, ok := u.User.Password()
	if !ok || password != "selector436_fixture_only" {
		t.Fatal("fixture-only credential required")
	}
	worker, err := url.Parse(os.Getenv("AUTODATA_SELECTOR_WORKER_URL"))
	if err != nil || worker.Scheme != "http" || worker.Hostname() != "127.0.0.1" {
		t.Fatal("local authored worker required")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	t.Cleanup(cancel)
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	store := newPostgresCatalogStore(pool)
	server := catalogServer(store)
	server.ingestionClient, err = NewHTTPIngestionClient(worker.String(), "selector436-fixture-token", 23*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	return server, pool, ctx
}

func TestSelectorOwnedColdYearsFixture(t *testing.T) {
	server, pool, ctx := newOwnedSelectorFixture(t)
	readYears := func(path string) CatalogYearsResponse {
		t.Helper()
		response := catalogRequest(server, path)
		if response.Code != http.StatusOK {
			t.Fatalf("status=%d body=%s", response.Code, response.Body.String())
		}
		var body CatalogYearsResponse
		if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		return body
	}
	initial := readYears("/v1/catalog/years")
	if len(initial.Items) != 0 || initial.Complete || !initial.Hydrating {
		t.Fatalf("initial empty catalog should be hydrating, got %#v", initial)
	}
	key, _, err := catalogHydrationRequest(map[string]any{"scope": "years"})
	if err != nil {
		t.Fatal(err)
	}
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()
	for {
		if _, running := catalogHydrationInFlight.Load(key); !running {
			break
		}
		select {
		case <-ctx.Done():
			t.Fatal("year hydration did not finish within the fixture deadline")
		case <-ticker.C:
		}
	}
	if os.Getenv("AUTODATA_SELECTOR_EXPECT_EMPTY") == "1" {
		body := readYears("/v1/catalog/years?stored_only=1")
		if len(body.Items) != 0 {
			t.Fatalf("partial years escaped into durable reader: %#v", body.Items)
		}
	} else {
		for i := 0; i < 2; i++ {
			body := readYears("/v1/catalog/years")
			if !body.Complete || body.Hydrating || len(body.Items) != 2 || body.Items[0].Year != 2023 || body.Items[1].Year != 2024 {
				t.Fatalf("unordered/unusable years: %#v", body)
			}
		}
	}
	var count int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM vehicle_catalog_hydration_scopes").Scan(&count); err != nil || count != 0 {
		t.Fatalf("false years marker count=%d err=%v", count, err)
	}
}

func TestSelectorOwnedProgressFixture(t *testing.T) {
	server, _, ctx := newOwnedSelectorFixture(t)
	scope := os.Getenv("AUTODATA_SELECTOR_PROGRESS_SCOPE")
	payload := map[string]any{"scope": scope, "year": 2024, "region": "US"}
	path := "/v1/catalog/years/2024/makes"
	switch scope {
	case "makes":
	case "models":
		path += "/authored/models"
		payload["make"] = "authored"
	default:
		t.Fatal("explicit makes or models fixture required")
	}
	path += "?region=US"
	type selectorResponse struct {
		Items []struct{ Name string }
		CatalogHydrationResponse
	}
	read := func(path string) selectorResponse {
		t.Helper()
		response := catalogRequest(server, path)
		var body selectorResponse
		if err := json.Unmarshal(response.Body.Bytes(), &body); response.Code != http.StatusOK || err != nil {
			t.Fatalf("selector status=%d body=%s err=%v", response.Code, response.Body.String(), err)
		}
		return body
	}
	start := time.Now()
	initial := read(path)
	if len(initial.Items) != 0 || initial.Complete || !initial.Hydrating {
		t.Fatalf("initial selector state = %#v", initial)
	}
	key, _, err := catalogHydrationRequest(payload)
	if err != nil {
		t.Fatal(err)
	}
	ticker := time.NewTicker(40 * time.Millisecond)
	defer ticker.Stop()
	var partialAt time.Duration
	for {
		body := read(path + "&stored_only=1")
		if partialAt == 0 && !body.Complete && body.Hydrating && len(body.Items) == 1 && body.Items[0].Name == "First" {
			partialAt = time.Since(start)
		}
		if _, running := catalogHydrationInFlight.Load(key); !running {
			break
		}
		select {
		case <-ctx.Done():
			t.Fatal("selector hydration did not finish within the fixture deadline")
		case <-ticker.C:
		}
	}
	if partialAt == 0 || partialAt >= 5*time.Second {
		t.Fatalf("first supplier choices must be visible before the second dispatch, got %s", partialAt)
	}
	final := read(path + "&stored_only=1")
	if os.Getenv("AUTODATA_SELECTOR_EXPECT_PARTIAL") == "1" {
		if final.Complete || !final.Hydrating || len(final.Items) != 1 || final.Items[0].Name != "First" {
			t.Fatalf("first supplier rows after second supplier rate limit = %#v", final)
		}
	} else if !final.Complete || final.Hydrating || len(final.Items) != 2 ||
		final.Items[0].Name != "First" || final.Items[1].Name != "Second" {
		t.Fatalf("completed selector rows = %#v", final)
	}
	t.Logf("%s first selectable rows in %s, worker finished in %s", scope, partialAt, time.Since(start))
}
