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
	mode := os.Getenv("AUTODATA_SELECTOR_YEARS_MODE")
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
	assertYears := func(body CatalogYearsResponse, complete bool, expected ...int) {
		t.Helper()
		if body.Complete != complete || body.Hydrating == complete || len(body.Items) != len(expected) {
			t.Fatalf("year coverage = %#v, want complete=%t years=%v", body, complete, expected)
		}
		for i, year := range expected {
			if body.Items[i].Year != year {
				t.Fatalf("unordered or missing years: %#v, want %v", body.Items, expected)
			}
		}
	}
	initial := readYears("/v1/catalog/years")
	switch mode {
	case "legacy":
		assertYears(initial, true, 2021)
		return
	case "legacy-inventory":
		assertYears(initial, true, 2022)
		return
	case "partial-inventory":
		assertYears(initial, false, 2022, 2023)
	case "resume", "replace-with-empty":
		assertYears(initial, false, 2023, 2024)
	default:
		assertYears(initial, false)
	}
	key, _, err := catalogHydrationRequest(map[string]any{"scope": "years"})
	if err != nil {
		t.Fatal(err)
	}
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()
	seenPartial := false
	for {
		if _, running := catalogHydrationInFlight.Load(key); !running {
			break
		}
		if mode == "partial" && !seenPartial {
			body := readYears("/v1/catalog/years?stored_only=1")
			if len(body.Items) > 0 {
				assertYears(body, false, 2023, 2024)
				seenPartial = true
			}
		}
		select {
		case <-ctx.Done():
			t.Fatal("year hydration did not finish within the fixture deadline")
		case <-ticker.C:
		}
	}
	switch mode {
	case "partial":
		if !seenPartial {
			t.Fatal("verified years did not become selectable before the worker finished")
		}
		assertYears(readYears("/v1/catalog/years?stored_only=1"), false, 2023, 2024)
	case "complete-empty":
		assertYears(readYears("/v1/catalog/years"), true)
		if _, running := catalogHydrationInFlight.Load(key); running {
			t.Fatal("complete empty scope scheduled hydration again")
		}
	case "replace-with-empty":
		assertYears(readYears("/v1/catalog/years?stored_only=1"), false)
	case "resume", "resume-cleared":
		assertYears(readYears("/v1/catalog/years"), true, 2023, 2024, 2025)
	case "partial-inventory":
		assertYears(readYears("/v1/catalog/years"), true, 2022, 2023, 2024)
	default:
		for i := 0; i < 2; i++ {
			assertYears(readYears("/v1/catalog/years"), true, 2023, 2024)
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
