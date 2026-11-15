package main

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

type completeEmptySelectorStore struct{ *memoryCatalogStore }

func (s completeEmptySelectorStore) CatalogScopeComplete(context.Context, Principal, string, int, string, string, string) (bool, error) {
	return true, nil
}

func TestCompleteEmptySelectorsDoNotHydrateAgain(t *testing.T) {
	server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), completeEmptySelectorStore{newMemoryCatalogStore()})
	// A complete empty enumeration must not schedule any ingestion request.
	server.ingestionClient = &failingSelectorHydrationClient{t: t}
	for _, path := range []string{"/v1/catalog/years/2014/makes", "/v1/catalog/years/2014/makes/ford/models"} {
		response := catalogRequest(server, path)
		if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), `"complete":true`) || !strings.Contains(response.Body.String(), `"hydrating":false`) {
			t.Fatalf("%s: %s", path, response.Body.String())
		}
	}
}

type failingSelectorHydrationClient struct{ t *testing.T }

func (c *failingSelectorHydrationClient) Do(*http.Request, string, []byte, string) (int, []byte, error) {
	c.t.Error("complete empty scope scheduled hydration")
	return 500, nil, nil
}

func TestPostgresSparseSelectorVisibilityAndLegacyRecovery(t *testing.T) {
	dsn := os.Getenv("AUTODATA_SELECTOR_TEST_DSN")
	if dsn == "" {
		t.Skip("isolated selector PostgreSQL fixture required")
	}
	if os.Getenv("AUTODATA_LIFECYCLE_TEST") != "1" || !strings.HasPrefix(dsn, "postgres://lifecycle_test:lifecycle_test_only@postgres:5432/lifecycle_test_") {
		t.Fatal("isolated database required")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	exec := func(query string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, query, args...); err != nil {
			t.Fatal(err)
		}
	}
	exec(`INSERT INTO vehicle_catalog_hydration_scopes(scope_key,scope,model_year,make,region) VALUES ('legacy','makes',2014,'','US')`)
	store := &postgresCatalogStore{pool: pool}
	complete, err := store.CatalogScopeComplete(ctx, Principal{}, "makes", 2014, "", "", "US")
	if err != nil || complete {
		t.Fatalf("legacy sparse marker trusted: %v %v", complete, err)
	}
	exec(`UPDATE vehicle_catalog_hydration_scopes SET selector_rows='[{"year":2014,"make":"Ford","region":"US"},{"year":2014,"make":"Saab","region":"US"}]',completion_version=1 WHERE scope_key='legacy'`)
	exec(`INSERT INTO vehicle_catalog_hydration_scopes(scope_key,scope,model_year,make,region,selector_rows,completion_version) VALUES
 ('models','models',2020,'Ford','US','[{"year":2020,"make":"Ford","model":"Focus","region":"US"},{"year":2020,"make":"Ford","model":"Bronco","region":"US"}]',1),
 ('other-region','models',2020,'Ford','CA','[{"year":2020,"make":"Ford","model":"Canada only","region":"CA"}]',1),
 ('other-make','models',2020,'Saab','US','[{"year":2020,"make":"Saab","model":"900","region":"US"}]',1)`)
	server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), store)
	server.ingestionClient = &failingSelectorHydrationClient{t: t}
	response := catalogRequest(server, "/v1/catalog/years/2014/makes?region=US")
	var makes CatalogMakesResponse
	if err := json.Unmarshal(response.Body.Bytes(), &makes); err != nil {
		t.Fatal(err)
	}
	if !makes.Complete || makes.Hydrating || len(makes.Items) != 2 {
		t.Fatalf("sparse makes unavailable: %s", response.Body.String())
	}
	response = catalogRequest(server, "/v1/catalog/years/2020/makes/ford/models?region=US")
	var models CatalogModelsResponse
	if err := json.Unmarshal(response.Body.Bytes(), &models); err != nil {
		t.Fatal(err)
	}
	if !models.Complete || models.Hydrating || len(models.Items) != 2 || strings.Contains(response.Body.String(), "Canada only") || strings.Contains(response.Body.String(), "900") {
		t.Fatalf("sparse models scope leak: %s", response.Body.String())
	}
	wrongYear, err := store.Models(ctx, Principal{}, 2019, "Ford", "US")
	if err != nil || len(wrongYear) != 0 {
		t.Fatalf("year isolation: %v %v", wrongYear, err)
	}
	allRegions, err := store.Models(ctx, Principal{}, 2020, "Ford", "")
	if err != nil || len(allRegions) != 3 {
		t.Fatalf("unfiltered regions: %v %v", allRegions, err)
	}
	exec(`UPDATE vehicle_catalog_hydration_scopes SET completion_version=0 WHERE scope_key='models'`)
	complete, err = store.CatalogScopeComplete(ctx, Principal{}, "models", 2020, "Ford", "", "US")
	if err != nil || complete {
		t.Fatalf("partial scope trusted: %v %v", complete, err)
	}
	partial, err := store.Models(ctx, Principal{}, 2020, "Ford", "US")
	if err != nil || len(partial) != 2 {
		t.Fatalf("partial rows lost: %v %v", partial, err)
	}
}
