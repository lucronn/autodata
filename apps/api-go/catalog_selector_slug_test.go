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

func openSelectorTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
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
	t.Cleanup(pool.Close)
	return pool
}

func TestPostgresPublicSelectorSlugsPreserveScope(t *testing.T) {
	ctx := context.Background()
	pool := openSelectorTestPool(t)
	// Temporary relations keep this read-path regression independent of durable fixture data.
	_, err := pool.Exec(ctx, `CREATE TEMP TABLE vehicle_identity_bases(vehicle_identity_base_id int, model_year int, make text, model text, region text, reviewer_state text, body_style text, drivetrain text);
 CREATE TEMP TABLE vehicle_configurations(vehicle_configuration_id text, vehicle_id text, vehicle_identity_base_id int, trim text, engine_displacement_l numeric, reviewer_state text, engine_variant text, engine_variant_market_verified boolean NOT NULL DEFAULT false);
 CREATE TEMP TABLE vehicle_catalog_hydration_scopes(scope text, model_year int, make text, model text, region text, completion_version int, selector_rows jsonb);
 CREATE TEMP TABLE vehicle_catalog_sync_scopes(vehicle_catalog_sync_id int, status text, scope_key text);
 CREATE TEMP TABLE vehicle_catalog_syncs(vehicle_catalog_sync_id int, provider text, status text);
 INSERT INTO vehicle_identity_bases(vehicle_identity_base_id,model_year,make,model,region,reviewer_state) VALUES (1,2020,'Ford','Figo (MEXICO)','US','approved'),(2,2019,'Ford','Figo (MEXICO)','US','approved'),(3,2020,'Ford','Figo (MEXICO)','CA','approved'),(4,2020,'Other','Figo (MEXICO)','US','approved'),(5,2020,'Mercedes Benz','A-Class','US','approved');
 INSERT INTO vehicle_configurations (vehicle_configuration_id,vehicle_id,vehicle_identity_base_id,trim,engine_displacement_l,reviewer_state) SELECT CASE vehicle_identity_base_id WHEN 1 THEN 'figo' WHEN 2 THEN 'year' WHEN 3 THEN 'region' WHEN 4 THEN 'make' ELSE 'punctuated' END, 'vehicle',vehicle_identity_base_id,'',NULL, 'approved' FROM vehicle_identity_bases;
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

func TestPostgresSparseSelectorKeepsEngineVariants(t *testing.T) {
	pool := openSelectorTestPool(t)
	ctx := context.Background()
	const (
		cng     = "11111111-1111-4111-8111-111111111111"
		lpg     = "22222222-2222-4222-8222-222222222222"
		legacy  = "33333333-3333-4333-8333-333333333333"
		vehicle = "44444444-4444-4444-8444-444444444444"
	)
	_, err := pool.Exec(ctx, `
        CREATE TEMP TABLE vehicle_identity_bases (vehicle_identity_base_id int, vehicle_id uuid, model_year int,
            make text, model text, region text, reviewer_state text, body_style text, drivetrain text);
        CREATE TEMP TABLE vehicle_configurations (vehicle_configuration_id uuid, vehicle_id uuid, vehicle_identity_base_id int,
            trim text, engine_displacement_l numeric, reviewer_state text, engine_variant text,
            engine_variant_market_verified boolean NOT NULL DEFAULT false);
        INSERT INTO vehicle_identity_bases VALUES (1, '`+vehicle+`', 2020, 'Chevy Truck', 'Express 4500', 'US', 'approved', NULL, NULL);
        INSERT INTO vehicle_configurations VALUES
            ('`+cng+`', '`+vehicle+`', 1, NULL, 6.0, 'pending', 'CNG', false),
            ('`+lpg+`', '`+vehicle+`', 1, NULL, 6.0, 'pending', 'LPG', true),
            ('`+legacy+`', '`+vehicle+`', 1, NULL, 6.0, 'approved', NULL, false)
    `)
	if err != nil {
		t.Fatal(err)
	}

	store := &postgresCatalogStore{pool: pool}
	rows, err := store.Configurations(ctx, Principal{}, 2020, "chevy-truck", "express-4500", "US")
	if err != nil || len(rows) != 3 {
		t.Fatalf("configurations = %#v, %v", rows, err)
	}
	for index, want := range []struct {
		id               string
		variant          string
		marketUnverified bool
	}{
		{cng, "CNG", true},
		{lpg, "LPG", false},
		{legacy, "", false},
	} {
		row := rows[index]
		if row.ID != want.id || row.Engine != "6.0" || row.EngineVariant != want.variant ||
			row.EngineVariantMarketUnverified != want.marketUnverified {
			t.Fatalf("configuration %d = %#v", index, row)
		}
		exact, err := store.ConfigurationByVehicle(ctx, Principal{}, want.id)
		if err != nil || exact != row {
			t.Fatalf("exact configuration = %#v, %v", exact, err)
		}
	}
	base, err := store.ConfigurationByVehicle(ctx, Principal{}, vehicle)
	if err != nil || base.ID != legacy {
		t.Fatalf("legacy vehicle lookup = %#v, %v", base, err)
	}
	old := &postgresVehicleIdentityStore{pool: pool}
	selectors, err := old.Selectors(Principal{})
	if err != nil || len(selectors.Vehicles) != 1 {
		t.Fatalf("legacy selectors = %#v, %v", selectors, err)
	}
	configurations := selectors.Vehicles[0].Configurations
	if len(configurations) != 1 || configurations[0].VehicleConfigurationID != legacy {
		t.Fatalf("legacy configurations = %#v", configurations)
	}
}
