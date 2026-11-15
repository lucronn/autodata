package main

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

func TestCatalogPublicSelectorSlugsPreserveScope(t *testing.T) {
	store := newMemoryCatalogStore()
	for _, row := range []CatalogConfiguration{
		{ID: "figo", Year: 2020, Make: "Ford", Model: "Figo (MEXICO)", Region: "US", Complete: true},
		{ID: "year", Year: 2019, Make: "Ford", Model: "Figo (MEXICO)", Region: "US"},
		{ID: "region", Year: 2020, Make: "Ford", Model: "Figo (MEXICO)", Region: "CA"},
		{ID: "make", Year: 2020, Make: "Other", Model: "Figo (MEXICO)", Region: "US"},
		{ID: "punctuated", Year: 2020, Make: "Mercedes Benz", Model: "A-Class", Region: "US"},
	} {
		store.PutConfiguration(row)
	}
	assertPublicSelectorSlugs(t, store)
}

func assertPublicSelectorSlugs(t *testing.T, store CatalogStore) {
	t.Helper()
	ctx := context.Background()
	for _, tc := range []struct{ makeName, model, id string }{
		{"ford", "figo-mexico", "figo"},
		{"FORD", "Figo (MEXICO)", "figo"},
		{"mercedes-benz", "a-class", "punctuated"},
	} {
		rows, err := store.Configurations(ctx, Principal{}, 2020, tc.makeName, tc.model, "US")
		if err != nil || len(rows) != 1 || rows[0].ID != tc.id {
			t.Fatalf("%s/%s configurations = %#v, %v", tc.makeName, tc.model, rows, err)
		}
		complete, err := store.CatalogScopeComplete(ctx, Principal{}, "configurations", 2020, tc.makeName, tc.model, "US")
		if err != nil || !complete {
			t.Fatalf("%s/%s complete = %v, %v", tc.makeName, tc.model, complete, err)
		}
	}
	models, err := store.Models(ctx, Principal{}, 2020, "mercedes-benz", "US")
	if err != nil || len(models) != 1 || models[0].ID != "a-class" {
		t.Fatalf("models = %#v, %v", models, err)
	}
	for _, tc := range []struct {
		year                    int
		makeName, model, region string
	}{
		{2021, "ford", "figo-mexico", "US"}, {2020, "ford", "figo-mexico", "MX"}, {2020, "saab", "figo-mexico", "US"},
	} {
		rows, err := store.Configurations(ctx, Principal{}, tc.year, tc.makeName, tc.model, tc.region)
		if err != nil || len(rows) != 0 {
			t.Fatalf("off-scope configurations = %#v, %v", rows, err)
		}
		complete, err := store.CatalogScopeComplete(ctx, Principal{}, "configurations", tc.year, tc.makeName, tc.model, tc.region)
		if err != nil || complete {
			t.Fatalf("off-scope complete = %v, %v", complete, err)
		}
	}
}

func TestPostgresPublicSelectorSlugsPreserveScope(t *testing.T) {
	dsn := os.Getenv("AUTODATA_SELECTOR_TEST_DSN")
	if dsn == "" {
		t.Skip("isolated selector PostgreSQL fixture required")
	}
	if os.Getenv("AUTODATA_LIFECYCLE_TEST") != "1" || !strings.HasPrefix(dsn, "postgres://lifecycle_test:lifecycle_test_only@postgres:5432/lifecycle_test_") {
		t.Fatal("isolated database required")
	}
	ctx := context.Background()
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		t.Fatal(err)
	}
	cfg.MaxConns = 1
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	// Temporary relations keep this read-path regression independent of durable fixture data.
	_, err = pool.Exec(ctx, `CREATE TEMP TABLE vehicle_identity_bases(vehicle_identity_base_id int, model_year int, make text, model text, region text, reviewer_state text);
 CREATE TEMP TABLE vehicle_configurations(vehicle_configuration_id text, vehicle_id text, vehicle_identity_base_id int, trim text, engine_displacement_l numeric, reviewer_state text);
 CREATE TEMP TABLE vehicle_catalog_hydration_scopes(scope text, model_year int, make text, model text, region text, completion_version int, selector_rows jsonb);
 CREATE TEMP TABLE vehicle_catalog_sync_scopes(vehicle_catalog_sync_id int, status text, scope_key text);
 CREATE TEMP TABLE vehicle_catalog_syncs(vehicle_catalog_sync_id int, provider text, status text);
 INSERT INTO vehicle_identity_bases VALUES (1,2020,'Ford','Figo (MEXICO)','US','approved'),(2,2019,'Ford','Figo (MEXICO)','US','approved'),(3,2020,'Ford','Figo (MEXICO)','CA','approved'),(4,2020,'Other','Figo (MEXICO)','US','approved'),(5,2020,'Mercedes Benz','A-Class','US','approved');
 INSERT INTO vehicle_configurations SELECT CASE vehicle_identity_base_id WHEN 1 THEN 'figo' WHEN 2 THEN 'year' WHEN 3 THEN 'region' WHEN 4 THEN 'make' ELSE 'punctuated' END, 'vehicle',vehicle_identity_base_id,'',NULL, 'approved' FROM vehicle_identity_bases;
 INSERT INTO vehicle_catalog_hydration_scopes SELECT 'configurations',model_year,make,model,region,1,'[]'::jsonb FROM vehicle_identity_bases;`)
	if err != nil {
		t.Fatal(err)
	}
	store := &postgresCatalogStore{pool: pool}
	assertPublicSelectorSlugs(t, store)
	_, err = pool.Exec(ctx, `INSERT INTO vehicle_catalog_hydration_scopes VALUES
	 ('models',2020,'Mercedes Benz','','US',1,'[{"model":"B-Class"}]'),
	 ('models',2020,'Mercedes Benz','','CA',1,'[{"model":"Canada only"}]'),
	 ('models',2019,'Mercedes Benz','','US',1,'[{"model":"Other year"}]'),
	 ('models',2020,'Other','','US',1,'[{"model":"Other make"}]')`)
	if err != nil {
		t.Fatal(err)
	}
	models, err := store.Models(ctx, Principal{}, 2020, "mercedes-benz", "US")
	if err != nil || len(models) != 2 || models[0].ID != "a-class" || models[1].ID != "b-class" {
		t.Fatalf("sparse public model selector = %#v, %v", models, err)
	}
	complete, err := store.CatalogScopeComplete(ctx, Principal{}, "models", 2020, "mercedes-benz", "", "US")
	if err != nil || !complete {
		t.Fatalf("sparse public model completeness = %v, %v", complete, err)
	}

}
