package main

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/lucronn/autodata/packages/contracts/go"
)

var (
	ErrUnauthenticated     = errors.New("authentication is required")
	ErrEntitlementRequired = errors.New("active organization entitlement is required")
	ErrRequestNotFound     = errors.New("dataset request not found")
	ErrInvalidRequest      = errors.New("dataset request is invalid")
)

type Principal struct {
	OrganizationID string
	Roles          []string
}

func (p Principal) HasRole(role string) bool {
	for _, candidate := range p.Roles {
		if candidate == role || candidate == "platform_admin" {
			return true
		}
	}
	return false
}

type Authenticator interface {
	Authenticate(*http.Request) (Principal, error)
}

// HeaderAuthenticator is a provider-neutral local boundary. Production identity
// adapters can implement Authenticator without changing request handlers.
type HeaderAuthenticator struct{}

func (HeaderAuthenticator) Authenticate(request *http.Request) (Principal, error) {
	value := strings.TrimSpace(request.Header.Get("Authorization"))
	if !strings.HasPrefix(value, "Bearer local:") {
		return Principal{}, ErrUnauthenticated
	}
	parts := strings.Split(strings.TrimPrefix(value, "Bearer local:"), ":")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return Principal{}, ErrUnauthenticated
	}
	roles := strings.Split(parts[1], ",")
	for _, role := range roles {
		if strings.TrimSpace(role) == "" {
			return Principal{}, ErrUnauthenticated
		}
	}
	return Principal{OrganizationID: parts[0], Roles: roles}, nil
}

type DatasetRequestInput struct {
	ProductID  string `json:"product_id"`
	VehicleKey string `json:"vehicle_key"`
	Region     string `json:"region"`
}

type DatasetRequestRecord struct {
	DatasetRequestID string                     `json:"dataset_request_id"`
	ProductID        string                     `json:"product_id"`
	VehicleKey       string                     `json:"vehicle_key"`
	Region           string                     `json:"region"`
	Status           string                     `json:"status"`
	Sections         []contracts.DatasetSection `json:"sections"`
	OrganizationID   string                     `json:"-"`
}

type RequestStore interface {
	Create(Principal, DatasetRequestInput, string) (DatasetRequestRecord, bool, error)
	Get(string, Principal) (DatasetRequestRecord, error)
}

type memoryRequestStore struct {
	mu            sync.Mutex
	byID          map[string]DatasetRequestRecord
	byIdempotency map[string]DatasetRequestRecord
}

func newMemoryRequestStore() *memoryRequestStore {
	return &memoryRequestStore{
		byID:          make(map[string]DatasetRequestRecord),
		byIdempotency: make(map[string]DatasetRequestRecord),
	}
}

func (s *memoryRequestStore) Create(
	principal Principal, input DatasetRequestInput, idempotencyKey string,
) (DatasetRequestRecord, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if existing, ok := s.byIdempotency[idempotencyKey]; ok {
		if existing.OrganizationID != principal.OrganizationID {
			return DatasetRequestRecord{}, false, ErrEntitlementRequired
		}
		return existing, true, nil
	}
	requestID, err := newRequestID()
	if err != nil {
		return DatasetRequestRecord{}, false, err
	}
	now := time.Now().UTC().Format(time.RFC3339)
	record := DatasetRequestRecord{
		DatasetRequestID: requestID,
		ProductID:        input.ProductID,
		VehicleKey:       input.VehicleKey,
		Region:           input.Region,
		Status:           "fast_lane_processing",
		Sections: []contracts.DatasetSection{
			{Name: "vehicle_identity", Status: "pending", UpdatedAt: now},
			{Name: "source_metadata", Status: "pending", UpdatedAt: now},
			{Name: "specifications", Status: "pending", UpdatedAt: now},
		},
		OrganizationID: principal.OrganizationID,
	}
	s.byID[requestID] = record
	s.byIdempotency[idempotencyKey] = record
	return record, false, nil
}

func (s *memoryRequestStore) Get(id string, principal Principal) (DatasetRequestRecord, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	record, ok := s.byID[id]
	if !ok {
		return DatasetRequestRecord{}, ErrRequestNotFound
	}
	if record.OrganizationID != principal.OrganizationID {
		return DatasetRequestRecord{}, ErrEntitlementRequired
	}
	return record, nil
}

func newRequestID() (string, error) {
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	encoded := hex.EncodeToString(bytes)
	return encoded[0:8] + "-" + encoded[8:12] + "-" + encoded[12:16] + "-" + encoded[16:20] + "-" + encoded[20:32], nil
}
