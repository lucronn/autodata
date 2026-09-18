package main

import (
	"context"
	"sort"

	"github.com/jackc/pgx/v5/pgxpool"
)

// layeredVehicleIdentityStore keeps request-time normalization available to
// the API while reading durable selector values from PostgreSQL. The identity
// graph is single-organization in this phase; tenant isolation can be added
// when the identity tables receive an organization boundary.
type layeredVehicleIdentityStore struct {
	volatile *memoryVehicleIdentityStore
	durable  *postgresVehicleIdentityStore
}

func newLayeredVehicleIdentityStore(pool *pgxpool.Pool) *layeredVehicleIdentityStore {
	return &layeredVehicleIdentityStore{
		volatile: newMemoryVehicleIdentityStore(),
		durable:  &postgresVehicleIdentityStore{pool: pool},
	}
}

func (s *layeredVehicleIdentityStore) Resolve(
	principal Principal,
	input VehicleIdentityResolveInput,
	idempotencyKey string,
) (VehicleIdentityResolveRecord, bool, error) {
	return s.volatile.Resolve(principal, input, idempotencyKey)
}

func (s *layeredVehicleIdentityStore) Selectors(
	principal Principal,
) (VehicleIdentitySelectors, error) {
	volatile, err := s.volatile.Selectors(principal)
	if err != nil {
		return VehicleIdentitySelectors{}, err
	}
	durable, err := s.durable.Selectors(principal)
	if err != nil {
		return VehicleIdentitySelectors{}, err
	}
	return mergeVehicleIdentitySelectors(volatile, durable), nil
}

type postgresVehicleIdentityStore struct {
	pool *pgxpool.Pool
}

func stringPointerValue(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}

func (s *postgresVehicleIdentityStore) Selectors(_ Principal) (VehicleIdentitySelectors, error) {
	rows, err := s.pool.Query(context.Background(), `
		SELECT vib.vehicle_id::text, vib.make, vib.model, vib.model_year,
		       vib.region, COALESCE(vib.drivetrain, ''), COALESCE(vc.trim, ''),
		       vc.engine_displacement_l, vc.vehicle_configuration_id::text
		FROM vehicle_identity_bases vib
		LEFT JOIN vehicle_configurations vc
		  ON vc.vehicle_identity_base_id = vib.vehicle_identity_base_id
		WHERE vib.reviewer_state <> 'rejected'
		ORDER BY vib.make, vib.model, vib.model_year,
		         vib.drivetrain, vc.trim, vc.engine_displacement_l`)
	if err != nil {
		return VehicleIdentitySelectors{}, err
	}
	defer rows.Close()

	makes := map[string]bool{}
	models := map[string]bool{}
	years := map[int]bool{}
	drivetrains := map[string]bool{}
	trims := map[string]bool{}
	engines := map[float64]bool{}
	identityRows := []VehicleIdentityRow{}
	for rows.Next() {
		var vehicleID, makeName, model, region, drivetrain, trim string
		var year int
		var engine *float64
		var configurationID *string
		if err := rows.Scan(&vehicleID, &makeName, &model, &year, &region, &drivetrain, &trim, &engine, &configurationID); err != nil {
			return VehicleIdentitySelectors{}, err
		}
		identityRows = append(identityRows, VehicleIdentityRow{
			Year: year, Make: makeName, Model: model, Region: region,
			Drivetrain: drivetrain, Trim: trim, EngineDisplacementL: engine,
			vehicleID: vehicleID, vehicleConfigurationID: stringPointerValue(configurationID),
		})
		if makeName != "" {
			makes[makeName] = true
		}
		if model != "" {
			models[model] = true
		}
		if year != 0 {
			years[year] = true
		}
		if drivetrain != "" {
			drivetrains[drivetrain] = true
		}
		if trim != "" {
			trims[trim] = true
		}
		if engine != nil {
			engines[*engine] = true
		}
	}
	if err := rows.Err(); err != nil {
		return VehicleIdentitySelectors{}, err
	}
	yearRows, err := s.pool.Query(context.Background(), `
		SELECT year
		FROM vehicle_catalog_years
		WHERE provider = 'autoapitwo'
		ORDER BY year`)
	if err != nil {
		return VehicleIdentitySelectors{}, err
	}
	defer yearRows.Close()
	for yearRows.Next() {
		var year int
		if err := yearRows.Scan(&year); err != nil {
			return VehicleIdentitySelectors{}, err
		}
		if year >= 1886 && year <= 2100 {
			years[year] = true
		}
	}
	if err := yearRows.Err(); err != nil {
		return VehicleIdentitySelectors{}, err
	}
	syncRows, err := s.pool.Query(context.Background(), `
		SELECT status, row_count
		FROM vehicle_catalog_syncs
		WHERE provider = 'autoapitwo'
		  AND source_version = 'autoapitwo-fleet-v1'
		  AND traversal_version = 'fleet-vocabulary-v1'
		ORDER BY updated_at DESC
		LIMIT 1`)
	if err != nil {
		return VehicleIdentitySelectors{}, err
	}
	var catalogSync *CatalogSyncStatus
	if syncRows.Next() {
		var status string
		var rowCount int
		if err := syncRows.Scan(&status, &rowCount); err != nil {
			syncRows.Close()
			return VehicleIdentitySelectors{}, err
		}
		catalogSync = &CatalogSyncStatus{
			Provider:      "autoapitwo",
			SourceVersion: "autoapitwo-fleet-v1",
			Status:        status,
			RowCount:      rowCount,
		}
	}
	if err := syncRows.Err(); err != nil {
		syncRows.Close()
		return VehicleIdentitySelectors{}, err
	}
	syncRows.Close()
	records, _, err := normalizeVehicleIdentityRows(identityRows)
	if err != nil {
		return VehicleIdentitySelectors{}, err
	}
	return VehicleIdentitySelectors{
		Makes:                sortedStrings(makes),
		Models:               sortedStrings(models),
		Years:                sortedInts(years),
		Drivetrains:          sortedStrings(drivetrains),
		Trims:                sortedStrings(trims),
		EngineDisplacementsL: sortedFloats(engines),
		Vehicles:             records,
		CatalogSync:          catalogSync,
	}, nil
}

func mergeVehicleIdentitySelectors(left, right VehicleIdentitySelectors) VehicleIdentitySelectors {
	makes := selectorStringSet(left.Makes, right.Makes)
	models := selectorStringSet(left.Models, right.Models)
	drivetrains := selectorStringSet(left.Drivetrains, right.Drivetrains)
	trims := selectorStringSet(left.Trims, right.Trims)
	years := map[int]bool{}
	for _, year := range append(append([]int{}, left.Years...), right.Years...) {
		years[year] = true
	}
	engines := map[float64]bool{}
	for _, engine := range append(append([]float64{}, left.EngineDisplacementsL...), right.EngineDisplacementsL...) {
		engines[engine] = true
	}
	vehicles := map[string]VehicleIdentityRecord{}
	for _, record := range append(append([]VehicleIdentityRecord{}, left.Vehicles...), right.Vehicles...) {
		existing, ok := vehicles[record.VehicleIDKey]
		if !ok {
			vehicles[record.VehicleIDKey] = record
			continue
		}
		configurations := map[string]VehicleConfigurationRecord{}
		for _, configuration := range append(existing.Configurations, record.Configurations...) {
			configurations[configuration.ConfigurationKey] = configuration
		}
		existing.Configurations = existing.Configurations[:0]
		for _, configuration := range configurations {
			existing.Configurations = append(existing.Configurations, configuration)
		}
		sort.Slice(existing.Configurations, func(i, j int) bool {
			return existing.Configurations[i].ConfigurationKey < existing.Configurations[j].ConfigurationKey
		})
		if existing.Status != "needs_review" && record.Status == "needs_review" {
			existing.Status = "needs_review"
		}
		vehicles[record.VehicleIDKey] = existing
	}
	vehicleKeys := make([]string, 0, len(vehicles))
	for key := range vehicles {
		vehicleKeys = append(vehicleKeys, key)
	}
	sort.Strings(vehicleKeys)
	mergedVehicles := make([]VehicleIdentityRecord, 0, len(vehicleKeys))
	for _, key := range vehicleKeys {
		mergedVehicles = append(mergedVehicles, vehicles[key])
	}
	catalogSync := right.CatalogSync
	if catalogSync == nil {
		catalogSync = left.CatalogSync
	}
	return VehicleIdentitySelectors{
		Makes:                sortedStrings(makes),
		Models:               sortedStrings(models),
		Years:                sortedInts(years),
		Drivetrains:          sortedStrings(drivetrains),
		Trims:                sortedStrings(trims),
		EngineDisplacementsL: sortedFloats(engines),
		Vehicles:             mergedVehicles,
		CatalogSync:          catalogSync,
	}
}

func selectorStringSet(values ...[]string) map[string]bool {
	result := map[string]bool{}
	for _, group := range values {
		for _, value := range group {
			if value != "" {
				result[value] = true
			}
		}
	}
	return result
}
