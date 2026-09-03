package main

import (
	"context"
	"errors"
	"reflect"
	"testing"

	"github.com/jackc/pgx/v5"
)

type fakeRequestRow struct {
	values []any
	err    error
}

func (r fakeRequestRow) Scan(dest ...any) error {
	if r.err != nil {
		return r.err
	}
	if len(dest) != len(r.values) {
		return errors.New("fake row column count mismatch")
	}
	for index, destination := range dest {
		target := reflect.ValueOf(destination)
		if target.Kind() != reflect.Pointer || target.IsNil() {
			return errors.New("fake row destination must be a non-nil pointer")
		}
		target = target.Elem()
		if r.values[index] == nil {
			target.Set(reflect.Zero(target.Type()))
			continue
		}
		value := reflect.ValueOf(r.values[index])
		if !value.Type().AssignableTo(target.Type()) {
			return errors.New("fake row value type mismatch")
		}
		target.Set(value)
	}
	return nil
}

type fakeRequestTx struct {
	rows       []fakeRequestRow
	execSQL    []string
	queryArgs  [][]any
	committed  bool
	rolledBack bool
}

func (t *fakeRequestTx) QueryRow(_ context.Context, _ string, args ...any) pgx.Row {
	t.queryArgs = append(t.queryArgs, args)
	if len(t.rows) == 0 {
		return fakeRequestRow{err: errors.New("fake transaction has no scripted row")}
	}
	row := t.rows[0]
	t.rows = t.rows[1:]
	return row
}

func (t *fakeRequestTx) Exec(_ context.Context, query string, _ ...any) error {
	t.execSQL = append(t.execSQL, query)
	return nil
}

func (t *fakeRequestTx) Commit(_ context.Context) error {
	t.committed = true
	return nil
}

func (t *fakeRequestTx) Rollback(_ context.Context) error {
	t.rolledBack = true
	return nil
}

type fakeRequestDB struct {
	tx        *fakeRequestTx
	rows      []fakeRequestRow
	queryArgs [][]any
}

func (d *fakeRequestDB) Begin(_ context.Context) (requestTx, error) {
	return d.tx, nil
}

func (d *fakeRequestDB) QueryRow(_ context.Context, _ string, args ...any) pgx.Row {
	d.queryArgs = append(d.queryArgs, args)
	if len(d.rows) == 0 {
		return fakeRequestRow{err: errors.New("fake database has no scripted row")}
	}
	row := d.rows[0]
	d.rows = d.rows[1:]
	return row
}

type fakeProjectionOpener func(context.Context) (*postgresProjectionStore, error)

func TestPostgresRequestStorePersistsNewRequestAndReturnsProductSections(t *testing.T) {
	created := &fakeRequestTx{rows: []fakeRequestRow{
		{values: []any{
			"30000000-0000-0000-0000-000000000099",
			"10000000-0000-0000-0000-000000000001",
			"toyota-corolla-2024", "US", "fast_lane_processing",
			"41000000-0000-0000-0000-000000000001", "2026-09-03T00:00:00Z",
		}},
		{values: []any{[]byte(`[
            "vehicle_identity",
            "source_metadata",
            "specifications"
        ]`)}},
	}}
	store := &postgresRequestStore{db: &fakeRequestDB{tx: created}}

	record, duplicate, err := store.Create(
		Principal{OrganizationID: "41000000-0000-0000-0000-000000000001"},
		DatasetRequestInput{
			ProductID:  "10000000-0000-0000-0000-000000000001",
			VehicleKey: "toyota-corolla-2024",
			Region:     "US",
		},
		"request-unique-1",
	)
	if err != nil {
		t.Fatalf("Create() error = %v", err)
	}
	if duplicate {
		t.Fatal("new request reported as duplicate")
	}
	if record.DatasetRequestID != "30000000-0000-0000-0000-000000000099" {
		t.Fatalf("request ID = %q", record.DatasetRequestID)
	}
	if len(record.Sections) != 3 || record.Sections[0].Status != "pending" {
		t.Fatalf("sections = %#v, want three pending sections", record.Sections)
	}
	if !created.committed {
		t.Fatal("new request transaction was not committed")
	}
	if len(created.execSQL) != 0 {
		t.Fatalf("unexpected section writes before projection: %v", created.execSQL)
	}
}

func TestPostgresRequestStoreReplaysIdempotencyAndRejectsOtherOrganization(t *testing.T) {
	existing := fakeRequestRow{values: []any{
		"30000000-0000-0000-0000-000000000099",
		"10000000-0000-0000-0000-000000000001",
		"toyota-corolla-2024", "US", "fast_lane_processing",
		"41000000-0000-0000-0000-000000000001", "2026-09-03T00:00:00Z",
		[]byte(`[]`), []byte(`[]`),
	}}
	for _, test := range []struct {
		name    string
		org     string
		wantDup bool
		wantErr error
	}{
		{name: "same organization replay", org: "41000000-0000-0000-0000-000000000001", wantDup: true},
		{name: "different organization", org: "42000000-0000-0000-0000-000000000001", wantErr: ErrEntitlementRequired},
	} {
		t.Run(test.name, func(t *testing.T) {
			tx := &fakeRequestTx{rows: []fakeRequestRow{{err: pgx.ErrNoRows}, existing}}
			store := &postgresRequestStore{db: &fakeRequestDB{tx: tx}}
			_, duplicate, err := store.Create(
				Principal{OrganizationID: test.org},
				DatasetRequestInput{
					ProductID:  "10000000-0000-0000-0000-000000000001",
					VehicleKey: "toyota-corolla-2024",
					Region:     "US",
				},
				"request-unique-1",
			)
			if !errors.Is(err, test.wantErr) {
				t.Fatalf("Create() error = %v, want %v", err, test.wantErr)
			}
			if duplicate != test.wantDup {
				t.Fatalf("duplicate = %t, want %t", duplicate, test.wantDup)
			}
			if len(tx.queryArgs) != 2 || len(tx.queryArgs[1]) != 1 || tx.queryArgs[1][0] != "request-unique-1" {
				t.Fatalf("idempotency replay args = %#v, want the idempotency key", tx.queryArgs)
			}
		})
	}
}

func TestPostgresRequestStoreReadsDurableSectionsAndOwnership(t *testing.T) {
	db := &fakeRequestDB{rows: []fakeRequestRow{{values: []any{
		"30000000-0000-0000-0000-000000000099",
		"10000000-0000-0000-0000-000000000001",
		"toyota-corolla-2024", "US", "viewable",
		"41000000-0000-0000-0000-000000000001", "2026-09-03T00:00:00Z",
		[]byte(`["vehicle_identity"]`), []byte(`[{"name":"vehicle_identity","status":"viewable","last_published_revision":"60000000-0000-0000-0000-000000000001","updated_at":"2026-09-03T00:00:00Z"}]`),
	}}}}
	store := &postgresRequestStore{db: db}
	record, err := store.Get("30000000-0000-0000-0000-000000000099", Principal{OrganizationID: "41000000-0000-0000-0000-000000000001"})
	if err != nil {
		t.Fatalf("Get() error = %v", err)
	}
	if record.Status != "viewable" || len(record.Sections) != 1 || record.Sections[0].Status != "viewable" {
		t.Fatalf("record = %#v", record)
	}
	if len(db.queryArgs) != 1 || len(db.queryArgs[0]) != 2 ||
		db.queryArgs[0][0] != "30000000-0000-0000-0000-000000000099" ||
		db.queryArgs[0][1] != "41000000-0000-0000-0000-000000000001" {
		t.Fatalf("request read args = %#v, want request and organization IDs", db.queryArgs)
	}
}

func TestPostgresRequestStoreRejectsInvalidIdentifiers(t *testing.T) {
	store := &postgresRequestStore{db: &fakeRequestDB{}}
	_, _, err := store.Create(
		Principal{OrganizationID: "41000000-0000-0000-0000-000000000001"},
		DatasetRequestInput{ProductID: "not-a-uuid", VehicleKey: "vehicle", Region: "US"},
		"request-unique-1",
	)
	if !errors.Is(err, ErrInvalidRequest) {
		t.Fatalf("Create() error = %v, want ErrInvalidRequest", err)
	}
	_, err = store.Get("not-a-uuid", Principal{OrganizationID: "41000000-0000-0000-0000-000000000001"})
	if !errors.Is(err, ErrInvalidRequest) {
		t.Fatalf("Get() error = %v, want ErrInvalidRequest", err)
	}
}

func TestConfiguredStoresUseOnePostgresBoundary(t *testing.T) {
	old := configuredProjectionStoreOpener
	defer func() { configuredProjectionStoreOpener = old }()
	configuredProjectionStoreOpener = func(context.Context) (*postgresProjectionStore, error) {
		return &postgresProjectionStore{}, nil
	}
	t.Setenv("AUTODATA_PROJECTION_STORE", "postgres")

	requests, projections, cleanup, err := configuredStores(context.Background())
	if err != nil {
		t.Fatalf("configuredStores() error = %v", err)
	}
	defer cleanup()
	if _, ok := requests.(*postgresRequestStore); !ok {
		t.Fatalf("request store type = %T, want *postgresRequestStore", requests)
	}
	if _, ok := projections.(*postgresProjectionStore); !ok {
		t.Fatalf("projection store type = %T, want *postgresProjectionStore", projections)
	}
}
