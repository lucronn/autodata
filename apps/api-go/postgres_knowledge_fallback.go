package main

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/lucronn/autodata/packages/contracts/go"
)

// publicationEventDatabase is the narrow SQL boundary used by the durable
// fallback publisher. Keeping it separate from pgxpool makes the exact outbox
// insert testable without a running database.
type publicationEventDatabase interface {
	Exec(context.Context, string, ...any) (pgconn.CommandTag, error)
}

type postgresKnowledgeFallbackPublisher struct {
	db publicationEventDatabase
}

func newPostgresKnowledgeFallbackPublisher(pool *pgxpool.Pool) *postgresKnowledgeFallbackPublisher {
	return &postgresKnowledgeFallbackPublisher{db: pool}
}

func (p *postgresKnowledgeFallbackPublisher) Publish(ctx context.Context, event contracts.EventEnvelope) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if p == nil || p.db == nil {
		return fmt.Errorf("knowledge fallback outbox database is unavailable")
	}
	if strings.TrimSpace(event.EventID) == "" || strings.TrimSpace(event.EventType) == "" || event.EventVersion < 1 {
		return fmt.Errorf("knowledge fallback event identity is invalid")
	}
	if strings.TrimSpace(event.ProjectionID) == "" || strings.TrimSpace(event.CorrelationID) == "" || strings.TrimSpace(event.IdempotencyKey) == "" {
		return fmt.Errorf("knowledge fallback event routing is invalid")
	}
	payload, err := json.Marshal(event.Payload)
	if err != nil {
		return fmt.Errorf("marshal knowledge fallback payload: %w", err)
	}
	var revisionID any
	if event.RevisionID != nil {
		revisionID = *event.RevisionID
	}
	_, err = p.db.Exec(ctx, `
INSERT INTO publication_events
    (publication_event_id, event_type, event_version, dataset_request_id,
     dataset_projection_id, dataset_revision_id, correlation_id,
     idempotency_key, payload, published_at, producer)
SELECT $1::uuid, $2, $3, dp.dataset_request_id,
       $4::uuid, $5::uuid, $6::uuid, $7, $8::jsonb, $9::timestamptz, $10
FROM dataset_projections dp
WHERE dp.dataset_projection_id = $4::uuid
ON CONFLICT (idempotency_key) DO NOTHING`,
		event.EventID,
		event.EventType,
		event.EventVersion,
		event.ProjectionID,
		revisionID,
		event.CorrelationID,
		event.IdempotencyKey,
		payload,
		event.OccurredAt,
		event.Producer,
	)
	return err
}
