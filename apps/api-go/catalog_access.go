package main

import (
	"context"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// PaidArticleIdentity contains server-only provider context. Never serialize it.
type PaidArticleIdentity struct {
	ConfigurationID         string
	CanonicalArticleID      string
	VehicleID               string
	ProviderSlug            string
	SourceVehicleRef        string
	SourceArticleRef        string
	CurrentSourceRevisionID *string
}
type paidArticleIdentityStore interface {
	PaidArticleIdentity(context.Context, string, string) (PaidArticleIdentity, error)
}

func (s *Server) paidCatalogEnabled() bool {
	return s.customerAuth != nil && s.customerAuth.config.Mode == "firebase"
}

// Resolve only metadata before checking the current exact grant. Legacy vehicle
// aliases deliberately cannot select one of several purchased configurations.
func (s *Server) resolvePaidCatalogScope(ctx context.Context, p Principal, configurationID, requestedRegion string) (CatalogConfiguration, error) {
	id := strings.ToLower(configurationID)
	if configurationID != strings.TrimSpace(configurationID) || !commerceUUID(id) || s.catalog == nil {
		return CatalogConfiguration{}, ErrCatalogNotFound
	}
	configuration, err := s.catalog.ConfigurationByVehicle(ctx, p, id)
	if err != nil {
		return CatalogConfiguration{}, err
	}
	if configuration.ID != id || !commerceRegion(configuration.Region) || (requestedRegion != "" && requestedRegion != configuration.Region) {
		return CatalogConfiguration{}, ErrCatalogNotFound
	}
	if err = s.checkPaidCatalogGrant(ctx, p, configuration); err != nil {
		return CatalogConfiguration{}, err
	}
	return configuration, nil
}
func (s *Server) checkPaidCatalogGrant(ctx context.Context, p Principal, configuration CatalogConfiguration) error {
	if !commerceUUID(p.CustomerAccountID) || !commerceUUID(p.OrganizationID) || !commerceUUID(configuration.ID) || !commerceRegion(configuration.Region) {
		return ErrVehicleGrantUnavailable
	}
	checker, ok := s.commerceClient.(VehicleGrantChecker)
	if !ok {
		return ErrVehicleGrantUnavailable
	}
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	grant, err := checker.CheckVehicleGrant(ctx, p.CustomerAccountID, p.OrganizationID, configuration.ID, configuration.Region)
	if err != nil {
		return err
	}
	if grant.ConfigurationID != configuration.ID || grant.Region != configuration.Region {
		return ErrVehicleGrantUnavailable
	}
	return nil
}
func (s *Server) writePaidCatalogError(w http.ResponseWriter, r *http.Request, err error) {
	w.Header().Set("Cache-Control", "private, no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	status, code, message, retryable := 503, "CATALOG_UNAVAILABLE", "Catalog is temporarily unavailable.", true
	switch {
	case errors.Is(err, ErrVehicleGrantRequired):
		status, code, message, retryable = 403, "ENTITLEMENT_REQUIRED", "Purchase access to this vehicle configuration.", false
	case errors.Is(err, ErrVehicleGrantRevoked):
		status, code, message, retryable = 403, "ENTITLEMENT_REVOKED", "Access to this vehicle configuration was revoked.", false
	case errors.Is(err, ErrCatalogNotFound), errors.Is(err, ErrCatalogInvalid):
		status, code, message, retryable = 404, "CATALOG_NOT_FOUND", "Catalog resource was not found.", false
	case errors.Is(err, ErrCatalogWithdrawn):
		status, code, message, retryable = 410, "CATALOG_WITHDRAWN", "Catalog content is withdrawn.", false
	}
	// Do not send raw paths/errors to catalog logging: media paths contain tokens.
	writeAPIError(w, r, status, code, message, retryable)
}
func (s *postgresCatalogStore) PaidArticleIdentity(ctx context.Context, configurationID, articleID string) (PaidArticleIdentity, error) {
	var identity PaidArticleIdentity
	if !commerceUUID(configurationID) || !commerceUUID(articleID) {
		return identity, ErrCatalogNotFound
	}
	err := s.pool.QueryRow(ctx, `SELECT vehicle_configuration_id::text,canonical_article_id::text,vehicle_id::text,provider_slug,source_vehicle_ref,source_article_ref,current_source_revision_id::text FROM canonical_articles WHERE vehicle_configuration_id::text=$1 AND canonical_article_id::text=$2`, configurationID, articleID).Scan(&identity.ConfigurationID, &identity.CanonicalArticleID, &identity.VehicleID, &identity.ProviderSlug, &identity.SourceVehicleRef, &identity.SourceArticleRef, &identity.CurrentSourceRevisionID)
	if errors.Is(err, pgx.ErrNoRows) {
		return PaidArticleIdentity{}, ErrCatalogNotFound
	}
	return identity, err
}
