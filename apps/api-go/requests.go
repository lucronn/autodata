package main

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
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
	Subject        string
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

// HeaderAuthenticator is an explicitly local-development authenticator. It is
// retained for in-memory API tests and is never selected by normal startup.
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

const (
	serviceKeyAuthMode = "service_key"
	localAuthMode      = "local"
)

var ErrAuthenticatorConfiguration = errors.New("service-key authentication is not configured")

// ServiceKeyCredential is the secret-managed, non-secret projection of one
// service identity. Only the SHA-256 digest is stored in configuration.
type ServiceKeyCredential struct {
	KeySHA256      string    `json:"key_sha256"`
	Subject        string    `json:"subject"`
	OrganizationID string    `json:"organization_id"`
	Roles          []string  `json:"roles"`
	ExpiresAt      time.Time `json:"expires_at"`
}

type serviceKeyIdentity struct {
	digest         []byte
	subject        string
	organizationID string
	roles          []string
	expiresAt      time.Time
}

// ServiceKeyAuthenticator verifies opaque bearer keys against configured
// SHA-256 digests and returns only the configured identity projection.
type ServiceKeyAuthenticator struct {
	identities []serviceKeyIdentity
	now        func() time.Time
}

func NewServiceKeyAuthenticator(rawConfig string) (*ServiceKeyAuthenticator, error) {
	if strings.TrimSpace(rawConfig) == "" {
		return nil, ErrAuthenticatorConfiguration
	}
	decoder := json.NewDecoder(strings.NewReader(rawConfig))
	decoder.DisallowUnknownFields()
	var credentials []ServiceKeyCredential
	if err := decoder.Decode(&credentials); err != nil {
		return nil, fmt.Errorf("%w: invalid credential set", ErrAuthenticatorConfiguration)
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		return nil, fmt.Errorf("%w: credential set must contain one JSON array", ErrAuthenticatorConfiguration)
	}
	if len(credentials) == 0 {
		return nil, fmt.Errorf("%w: credential set is empty", ErrAuthenticatorConfiguration)
	}

	identities := make([]serviceKeyIdentity, 0, len(credentials))
	seenDigests := make(map[string]struct{}, len(credentials))
	for _, credential := range credentials {
		digestText := strings.TrimSpace(credential.KeySHA256)
		digest, err := hex.DecodeString(digestText)
		if err != nil || len(digest) != sha256.Size {
			return nil, fmt.Errorf("%w: key_sha256 must be a 64-character hexadecimal digest", ErrAuthenticatorConfiguration)
		}
		digestKey := hex.EncodeToString(digest)
		if _, exists := seenDigests[digestKey]; exists {
			return nil, fmt.Errorf("%w: duplicate key_sha256", ErrAuthenticatorConfiguration)
		}
		seenDigests[digestKey] = struct{}{}
		if strings.TrimSpace(credential.Subject) == "" || strings.TrimSpace(credential.OrganizationID) == "" || credential.ExpiresAt.IsZero() {
			return nil, fmt.Errorf("%w: subject, organization_id, and expires_at are required", ErrAuthenticatorConfiguration)
		}
		roles := make([]string, len(credential.Roles))
		if len(roles) == 0 {
			return nil, fmt.Errorf("%w: at least one role is required", ErrAuthenticatorConfiguration)
		}
		for index, role := range credential.Roles {
			roles[index] = strings.TrimSpace(role)
			if roles[index] == "" {
				return nil, fmt.Errorf("%w: roles cannot contain empty values", ErrAuthenticatorConfiguration)
			}
		}
		identities = append(identities, serviceKeyIdentity{
			digest:         digest,
			subject:        strings.TrimSpace(credential.Subject),
			organizationID: strings.TrimSpace(credential.OrganizationID),
			roles:          roles,
			expiresAt:      credential.ExpiresAt,
		})
	}
	return &ServiceKeyAuthenticator{identities: identities, now: time.Now}, nil
}

func (a *ServiceKeyAuthenticator) Authenticate(request *http.Request) (Principal, error) {
	if a == nil || request == nil {
		return Principal{}, ErrUnauthenticated
	}
	value := strings.TrimSpace(request.Header.Get("Authorization"))
	const bearerPrefix = "Bearer "
	if len(value) <= len(bearerPrefix) || !strings.EqualFold(value[:len(bearerPrefix)], bearerPrefix) {
		return Principal{}, ErrUnauthenticated
	}
	presentedKey := strings.TrimSpace(value[len(bearerPrefix):])
	if presentedKey == "" {
		return Principal{}, ErrUnauthenticated
	}
	presentedDigest := sha256.Sum256([]byte(presentedKey))
	matched := -1
	for index := range a.identities {
		if subtle.ConstantTimeCompare(a.identities[index].digest, presentedDigest[:]) == 1 {
			matched = index
		}
	}
	if matched < 0 {
		return Principal{}, ErrUnauthenticated
	}
	now := time.Now
	if a.now != nil {
		now = a.now
	}
	identity := a.identities[matched]
	if !identity.expiresAt.After(now().UTC()) {
		return Principal{}, ErrUnauthenticated
	}
	return Principal{
		Subject:        identity.subject,
		OrganizationID: identity.organizationID,
		Roles:          append([]string(nil), identity.roles...),
	}, nil
}

func configuredAuthenticator() (Authenticator, error) {
	mode := strings.ToLower(strings.TrimSpace(os.Getenv("AUTODATA_AUTH_MODE")))
	switch mode {
	case localAuthMode, "local_dev", "local-development":
		return HeaderAuthenticator{}, nil
	case "", serviceKeyAuthMode, "service-key":
		return NewServiceKeyAuthenticator(os.Getenv("AUTODATA_SERVICE_KEYS_JSON"))
	default:
		return nil, fmt.Errorf("%w: unsupported AUTODATA_AUTH_MODE %q", ErrAuthenticatorConfiguration, mode)
	}
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
