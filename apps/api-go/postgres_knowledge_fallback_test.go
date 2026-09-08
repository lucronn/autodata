package main

import (
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgconn"
	"github.com/lucronn/autodata/packages/contracts/go"
)

type fakePublicationEventDB struct {
	query string
	args  []any
}

func (d *fakePublicationEventDB) Exec(_ context.Context, query string, args ...any) (pgconn.CommandTag, error) {
	d.query = query
	d.args = args
	return pgconn.CommandTag{}, nil
}

func TestPostgresKnowledgeFallbackPublisherWritesExactEnvelopeToLinkedOutbox(t *testing.T) {
	db := &fakePublicationEventDB{}
	publisher := &postgresKnowledgeFallbackPublisher{db: db}
	event := contracts.EventEnvelope{
		EventID:        "71000000-0000-0000-0000-000000000001",
		EventType:      "dataset.knowledge.fallback.requested",
		EventVersion:   1,
		OccurredAt:     "2026-09-03T12:00:00Z",
		Producer:       "autodata-api",
		RequestID:      "72000000-0000-0000-0000-000000000001",
		ProjectionID:   "73000000-0000-0000-0000-000000000001",
		RevisionID:     stringPtr("74000000-0000-0000-0000-000000000001"),
		CorrelationID:  "75000000-0000-0000-0000-000000000001",
		IdempotencyKey: "knowledge-fallback:v1:test",
		Payload: map[string]any{
			"vehicle_key": "toyota-corolla-2024-us",
			"region":      "US",
			"query":       "brake caliper",
			"keywords":    []string{"brake", "caliper"},
			"kind":        "article",
			"dataset_id":  "73000000-0000-0000-0000-000000000001",
			"revision_id": "74000000-0000-0000-0000-000000000001",
		},
	}

	if err := publisher.Publish(context.Background(), event); err != nil {
		t.Fatalf("Publish() error = %v", err)
	}
	if !strings.Contains(db.query, "dp.dataset_request_id") || !strings.Contains(db.query, "ON CONFLICT (idempotency_key) DO NOTHING") {
		t.Fatalf("outbox SQL does not link the request or deduplicate: %s", db.query)
	}
	if len(db.args) != 10 || db.args[0] != event.EventID || db.args[1] != event.EventType || db.args[2] != event.EventVersion || db.args[3] != event.ProjectionID || db.args[4] != *event.RevisionID || db.args[5] != event.CorrelationID || db.args[6] != event.IdempotencyKey || db.args[8] != event.OccurredAt || db.args[9] != event.Producer {
		t.Fatalf("outbox arguments = %#v, want exact envelope fields", db.args)
	}
	var payload map[string]any
	if err := json.Unmarshal(db.args[7].([]byte), &payload); err != nil {
		t.Fatalf("outbox payload is not JSON: %v", err)
	}
	if payload["event_id"] != nil || payload["vehicle_key"] != event.Payload["vehicle_key"] {
		t.Fatalf("outbox payload = %#v, want exact fallback payload without envelope duplication", payload)
	}
}
