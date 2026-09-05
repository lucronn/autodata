package main

import (
	"context"

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

func (s *postgresVehicleIdentityStore) Selectors(_ Principal) (VehicleIdentitySelectors, error) {
	rows, err := s.pool.Query(context.Background(), `
		SELECT vib.make, vib.model, vib.model_year,
		       COALESCE(vib.drivetrain, ''), COALESCE(vc.trim, ''),
		       vc.engine_displacement_l
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
	for rows.Next() {
		var makeName, model, drivetrain, trim string
		var year int
		var engine *float64
		if err := rows.Scan(&makeName, &model, &year, &drivetrain, &trim, &engine); err != nil {
			return VehicleIdentitySelectors{}, err
		}
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
	return VehicleIdentitySelectors{
		Makes:                sortedStrings(makes),
		Models:               sortedStrings(models),
		Years:                sortedInts(years),
		Drivetrains:          sortedStrings(drivetrains),
		Trims:                sortedStrings(trims),
		EngineDisplacementsL: sortedFloats(engines),
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
	return VehicleIdentitySelectors{
		Makes:                sortedStrings(makes),
		Models:               sortedStrings(models),
		Years:                sortedInts(years),
		Drivetrains:          sortedStrings(drivetrains),
		Trims:                sortedStrings(trims),
		EngineDisplacementsL: sortedFloats(engines),
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
