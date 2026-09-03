package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/lucronn/autodata/packages/contracts/go"
)

const knowledgeFallbackEventType = "dataset.knowledge.fallback.requested"

// KnowledgeFallbackPublisher is the provider-neutral boundary for handing a
// cache-miss request to asynchronous processing. Implementations must treat
// IdempotencyKey as a durable deduplication key.
type KnowledgeFallbackPublisher interface {
	Publish(context.Context, contracts.EventEnvelope) error
}

type memoryKnowledgeFallbackPublisher struct {
	mu     sync.Mutex
	events map[string]contracts.EventEnvelope
	order  []string
}

func newMemoryKnowledgeFallbackPublisher() *memoryKnowledgeFallbackPublisher {
	return &memoryKnowledgeFallbackPublisher{events: make(map[string]contracts.EventEnvelope)}
}

func (p *memoryKnowledgeFallbackPublisher) Publish(ctx context.Context, event contracts.EventEnvelope) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if strings.TrimSpace(event.IdempotencyKey) == "" {
		return fmt.Errorf("knowledge fallback event idempotency key is required")
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	if _, exists := p.events[event.IdempotencyKey]; exists {
		return nil
	}
	p.events[event.IdempotencyKey] = event
	p.order = append(p.order, event.IdempotencyKey)
	return nil
}

func (p *memoryKnowledgeFallbackPublisher) Events() []contracts.EventEnvelope {
	p.mu.Lock()
	defer p.mu.Unlock()
	events := make([]contracts.EventEnvelope, 0, len(p.order))
	for _, key := range p.order {
		events = append(events, p.events[key])
	}
	return events
}

func newKnowledgeFallbackEvent(request *http.Request, result KnowledgeSearchResponse, query, kind string, limit int) (contracts.EventEnvelope, error) {
	vehicleKey := firstKnowledgeString(result.VehicleIdentity, "vehicle_key")
	region := strings.ToUpper(firstKnowledgeString(result.VehicleIdentity, "region"))
	if vehicleKey == "" || region == "" {
		return contracts.EventEnvelope{}, fmt.Errorf("knowledge fallback requires vehicle_key and region")
	}
	keywords := knowledgeTokens(query)
	identity := knowledgeFallbackIdentity{
		DatasetID:  result.DatasetID,
		RevisionID: result.RevisionID,
		Query:      query,
		Keywords:   keywords,
		Kind:       kind,
		Limit:      limit,
	}
	idempotencyKey, err := identity.idempotencyKey()
	if err != nil {
		return contracts.EventEnvelope{}, err
	}
	eventID := deterministicKnowledgeFallbackUUID("event:" + idempotencyKey)
	revisionID := result.RevisionID
	return contracts.EventEnvelope{
		EventID:        eventID,
		EventType:      knowledgeFallbackEventType,
		EventVersion:   1,
		OccurredAt:     time.Now().UTC().Format(time.RFC3339),
		Producer:       "autodata-api",
		RequestID:      requestIDFrom(request),
		ProjectionID:   result.DatasetID,
		RevisionID:     &revisionID,
		CorrelationID:  deterministicKnowledgeFallbackUUID("correlation:" + idempotencyKey),
		IdempotencyKey: idempotencyKey,
		Payload: map[string]any{
			"vehicle_key": vehicleKey,
			"region":      region,
			"query":       query,
			"keywords":    keywords,
			"kind":        kind,
			"dataset_id":  result.DatasetID,
			"revision_id": result.RevisionID,
		},
	}, nil
}

type knowledgeFallbackIdentity struct {
	DatasetID  string
	RevisionID string
	Query      string
	Keywords   []string
	Kind       string
	Limit      int
}

func (i knowledgeFallbackIdentity) idempotencyKey() (string, error) {
	serialized, err := json.Marshal(i)
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256(serialized)
	return "knowledge-fallback:v1:" + hex.EncodeToString(digest[:]), nil
}

func deterministicKnowledgeFallbackUUID(seed string) string {
	digest := sha256.Sum256([]byte(seed))
	bytes := digest[:16]
	bytes[6] = (bytes[6] & 0x0f) | 0x50
	bytes[8] = (bytes[8] & 0x3f) | 0x80
	return fmt.Sprintf("%s-%s-%s-%s-%s",
		hex.EncodeToString(bytes[0:4]),
		hex.EncodeToString(bytes[4:6]),
		hex.EncodeToString(bytes[6:8]),
		hex.EncodeToString(bytes[8:10]),
		hex.EncodeToString(bytes[10:16]),
	)
}
