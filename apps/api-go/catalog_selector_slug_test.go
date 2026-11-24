package main

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	figoSelectorID   = "11111111-1111-4111-8111-111111111111"
	aClassSelectorID = "22222222-2222-4222-8222-222222222222"
)

func TestCatalogPublicSelectorSlugsPreserveScope(t *testing.T) {
	store := newMemoryCatalogStore()
	for _, row := range []CatalogConfiguration{
		{ID: figoSelectorID, Year: 2020, Make: "Ford", Model: "Figo (MEXICO)", Region: "US", Complete: true},
		{ID: "year", Year: 2019, Make: "Ford", Model: "Figo (MEXICO)", Region: "US"},
		{ID: "region", Year: 2020, Make: "Ford", Model: "Figo (MEXICO)", Region: "CA"},
		{ID: "make", Year: 2020, Make: "Other", Model: "Figo (MEXICO)", Region: "US"},
		{ID: aClassSelectorID, Year: 2020, Make: "Mercedes Benz", Model: "A-Class", Region: "US"},
	} {
		store.PutConfiguration(row)
	}
	assertPublicSelectorSlugs(t, store)
}

func assertPublicSelectorSlugs(t *testing.T, store CatalogStore) {
	t.Helper()
	ctx := context.Background()
	for _, tc := range []struct{ makeName, model, id string }{
		{"ford", "figo-mexico", figoSelectorID},
		{"FORD", "Figo (MEXICO)", figoSelectorID},
		{"mercedes-benz", "a-class", aClassSelectorID},
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
 CREATE TEMP TABLE vehicle_configurations(vehicle_configuration_id uuid, vehicle_id uuid, vehicle_identity_base_id int, trim text, engine_displacement_l numeric, reviewer_state text, engine_variant text, engine_variant_market_verified boolean NOT NULL DEFAULT false);
 CREATE TEMP TABLE vehicle_catalog_hydration_scopes(scope text, model_year int, make text, model text, region text, completion_version int, selector_rows jsonb);
 CREATE TEMP TABLE vehicle_catalog_sync_scopes(vehicle_catalog_sync_id int, status text, scope_key text);
 CREATE TEMP TABLE vehicle_catalog_syncs(vehicle_catalog_sync_id int, provider text, status text);
 INSERT INTO vehicle_identity_bases(vehicle_identity_base_id,model_year,make,model,region,reviewer_state) VALUES (1,2020,'Ford','Figo (MEXICO)','US','approved'),(2,2019,'Ford','Figo (MEXICO)','US','approved'),(3,2020,'Ford','Figo (MEXICO)','CA','approved'),(4,2020,'Other','Figo (MEXICO)','US','approved'),(5,2020,'Mercedes Benz','A-Class','US','approved');
 INSERT INTO vehicle_configurations (vehicle_configuration_id,vehicle_id,vehicle_identity_base_id,trim,engine_displacement_l,reviewer_state)
 SELECT CASE vehicle_identity_base_id WHEN 1 THEN '`+figoSelectorID+`'::uuid WHEN 5 THEN '`+aClassSelectorID+`'::uuid ELSE gen_random_uuid() END,
   '33333333-3333-4333-8333-333333333333',vehicle_identity_base_id,'',NULL,'approved' FROM vehicle_identity_bases;
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

func TestPostgresUnresolvedConfigurationRequiresExactEvidence(t *testing.T) {
	pool := openSelectorTestPool(t)
	ctx := context.Background()
	_, err := pool.Exec(ctx, `
		CREATE TEMP TABLE vehicle_identity_bases (vehicle_identity_base_id int, vehicle_id uuid,
		  model_year int, make text, model text, region text, reviewer_state text, body_style text, drivetrain text);
		CREATE TEMP TABLE vehicle_configurations (vehicle_configuration_id uuid, vehicle_id uuid,
		  vehicle_identity_base_id int, trim text, engine_displacement_l numeric, reviewer_state text,
		  engine_variant text, engine_variant_market_verified boolean);
		CREATE TEMP TABLE vehicle_provider_mappings (vehicle_id uuid, vehicle_configuration_id uuid,
		  provider text, entity_type text, mapping_status text, provider_id text);
		CREATE TEMP TABLE catalog_article_provider_scopes (scope_key text, provider_slug text, source_vehicle_ref text);
		CREATE TEMP TABLE canonical_articles (scope_key text, provider_slug text, membership_status text, takedown_status text,
		  source_vehicle_ref text, source_article_ref text);
		INSERT INTO vehicle_identity_bases VALUES
		  (1, '44444444-4444-4444-8444-444444444444', 2024, 'Buick Truck', 'Envision AWD', 'US', 'approved', NULL, NULL);
		INSERT INTO vehicle_configurations
		  SELECT ('00000000-0000-4000-8000-' || lpad(n::text, 12, '0'))::uuid, vehicle_id, 1,
		    CASE WHEN n=1 THEN chr(9) || ' ' END, CASE WHEN n=2 THEN 2.0 END, 'pending', NULL, false
		  FROM generate_series(1, 7) n CROSS JOIN vehicle_identity_bases;
		-- A vehicle-wide mapping and an empty or ambiguous exact mapping do not verify a scope.
		INSERT INTO vehicle_provider_mappings
		  SELECT vehicle_id, NULL, 'bankone', 'car', 'verified', 'vehicle-wide' FROM vehicle_identity_bases;
		INSERT INTO vehicle_provider_mappings
		  SELECT vehicle_id, vehicle_configuration_id, 'bankone', 'car', 'verified', ref
		  FROM vehicle_configurations
		  JOIN (VALUES ('3','mapped'),('3','mapped'),('6','one'),('6','two'),('7',' ')) refs(suffix, ref)
		    ON right(vehicle_configuration_id::text, 1) = refs.suffix;
		INSERT INTO catalog_article_provider_scopes VALUES
		  ('configuration:00000000-0000-4000-8000-000000000004','bankone','bound');
		INSERT INTO canonical_articles (scope_key, provider_slug, membership_status, takedown_status) VALUES
		  ('configuration:00000000-0000-4000-8000-000000000005','banktwo','active','active'),
		  ('configuration:00000000-0000-4000-8000-000000000007','banktwo','retired','active');
	`)
	if err != nil {
		t.Fatal(err)
	}
	store := &postgresCatalogStore{pool: pool}
	rows, err := store.Configurations(ctx, Principal{}, 2024, "buick-truck", "envision-awd", "US")
	wantUnresolved := []bool{true, false, false, false, false, true, true}
	if err != nil || len(rows) != len(wantUnresolved) {
		t.Fatalf("configurations = %#v, %v", rows, err)
	}
	for i, want := range wantUnresolved {
		if rows[i].ConfigurationUnresolved != want {
			t.Fatalf("configuration %d unresolved = %v, want %v", i+1, rows[i].ConfigurationUnresolved, want)
		}
		exact, err := store.ConfigurationByVehicle(ctx, Principal{}, rows[i].ID)
		if err != nil || exact != rows[i] {
			t.Fatalf("exact configuration %d = %#v, %v", i+1, exact, err)
		}
	}
}
