package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"mime"
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
type paidArticleDescriptorStore interface {
	PaidArticleDescriptors(context.Context, Principal, string) ([]CatalogArticle, error)
}
type paidArticleSearchStore interface {
	PaidArticleSearchDescriptors(context.Context, Principal, string, string) ([]CatalogArticle, error)
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

// Paid descriptors use one metadata-only query, including descriptor rights.
// Do not call the legacy union or load documents/individual article projections.
func (s *postgresCatalogStore) PaidArticleDescriptors(ctx context.Context, _ Principal, configurationID string) ([]CatalogArticle, error) {
	if !commerceUUID(configurationID) {
		return nil, ErrCatalogNotFound
	}
	rows, err := s.pool.Query(ctx, `SELECT a.canonical_article_id::text,COALESCE(a.title,''),COALESCE(a.kind,''),COALESCE(a.component,''),c.source_revision_id::text,c.canonical_revision_id::text,c.content_origin,c.availability,c.review_status FROM canonical_articles a JOIN catalog_article_current c USING(canonical_article_id) JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id WHERE a.vehicle_configuration_id::text=$1 AND `+lifecycleEligibleSQL+` AND c.takedown_status='active' AND descriptor.takedown_status='active' ORDER BY CASE a.provider_slug WHEN 'bankone' THEN 0 ELSE 1 END,a.source_sort_order NULLS LAST,a.canonical_article_id`, configurationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogArticle{}
	for rows.Next() {
		var article CatalogArticle
		if err = rows.Scan(&article.ID, &article.Title, &article.Kind, &article.Component, &article.SourceRevisionID, &article.CanonicalRevisionID, &article.ContentOrigin, &article.Availability, &article.ReviewStatus); err != nil {
			return nil, err
		}
		article.CanonicalArticleID = stringPointer(article.ID)
		article.VehicleID = configurationID
		article.Images = []CatalogImage{}
		article.Complete = article.CanonicalRevisionID != nil
		article.ContentStatus = "list_only"
		if article.Complete {
			article.ContentStatus = "content_complete"
		}
		result = append(result, article)
	}
	return result, rows.Err()
}

// Paid search keeps the descriptor response metadata-only while comparing the
// current selected projection inside the protected server boundary.
func (s *postgresCatalogStore) PaidArticleSearchDescriptors(ctx context.Context, _ Principal, configurationID, query string) ([]CatalogArticle, error) {
	if !commerceUUID(configurationID) {
		return nil, ErrCatalogNotFound
	}
	rows, err := s.pool.Query(ctx, `SELECT a.canonical_article_id::text,COALESCE(a.title,''),COALESCE(a.kind,''),COALESCE(a.component,''),c.source_revision_id::text,c.canonical_revision_id::text,c.content_origin,c.availability,c.review_status,c.document,COALESCE(c.body,''),c.steps FROM canonical_articles a JOIN catalog_article_current c USING(canonical_article_id) JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id WHERE a.vehicle_configuration_id::text=$1 AND `+lifecycleEligibleSQL+` AND c.takedown_status='active' AND descriptor.takedown_status='active' ORDER BY CASE a.provider_slug WHEN 'bankone' THEN 0 ELSE 1 END,a.source_sort_order NULLS LAST,a.canonical_article_id`, configurationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogArticle{}
	for rows.Next() {
		var article CatalogArticle
		var document, steps []byte
		var body string
		if err = rows.Scan(&article.ID, &article.Title, &article.Kind, &article.Component, &article.SourceRevisionID, &article.CanonicalRevisionID, &article.ContentOrigin, &article.Availability, &article.ReviewStatus, &document, &body, &steps); err != nil {
			return nil, err
		}
		searchable := CatalogArticle{Title: article.Title, Kind: article.Kind, Component: article.Component, Body: body}
		if len(document) > 0 {
			var parsed CatalogDocument
			if err = json.Unmarshal(document, &parsed); err != nil {
				return nil, err
			}
			searchable.Document = &parsed
		}
		if len(steps) > 0 {
			if err = json.Unmarshal(steps, &searchable.Steps); err != nil {
				return nil, err
			}
		}
		if len(filterCatalogArticleSearch([]CatalogArticle{searchable}, query)) == 0 {
			continue
		}
		article.CanonicalArticleID = stringPointer(article.ID)
		article.VehicleID = configurationID
		article.Images = []CatalogImage{}
		article.Complete = article.CanonicalRevisionID != nil
		article.ContentStatus = "list_only"
		if article.Complete {
			article.ContentStatus = "content_complete"
		}
		result = append(result, article)
	}
	return result, rows.Err()
}

func (s *postgresCatalogStore) PaidArticleIdentity(ctx context.Context, configurationID, articleID string) (PaidArticleIdentity, error) {
	var identity PaidArticleIdentity
	if !commerceUUID(configurationID) || !commerceUUID(articleID) {
		return identity, ErrCatalogNotFound
	}
	var articleRights, descriptorRights string
	err := s.pool.QueryRow(ctx, `SELECT a.vehicle_configuration_id::text,a.canonical_article_id::text,a.vehicle_id::text,a.provider_slug,a.source_vehicle_ref,a.source_article_ref,a.current_source_revision_id::text,a.takedown_status,descriptor.takedown_status FROM canonical_articles a JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id WHERE a.vehicle_configuration_id::text=$1 AND a.canonical_article_id::text=$2 AND `+lifecycleEligibleSQL, configurationID, articleID).Scan(&identity.ConfigurationID, &identity.CanonicalArticleID, &identity.VehicleID, &identity.ProviderSlug, &identity.SourceVehicleRef, &identity.SourceArticleRef, &identity.CurrentSourceRevisionID, &articleRights, &descriptorRights)
	if errors.Is(err, pgx.ErrNoRows) {
		return PaidArticleIdentity{}, ErrCatalogNotFound
	}
	if err == nil && (articleRights != "active" || descriptorRights != "active") {
		return PaidArticleIdentity{}, ErrCatalogWithdrawn
	}
	return identity, err
}

type paidCatalogContextKey struct{}
type paidCatalogContext struct {
	configuration CatalogConfiguration
	identity      *PaidArticleIdentity
}

func (s *Server) catalogSelector(next authenticatedHandler) http.Handler {
	if !s.paidCatalogEnabled() {
		return s.requireRole("dataset_viewer", next)
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { next(w, r, Principal{}) })
}
func (s *Server) catalogProtected(next authenticatedHandler, article bool) http.Handler {
	if !s.paidCatalogEnabled() {
		return s.requireRole("dataset_viewer", next)
	}
	return s.paidCatalogAuthenticated(func(w http.ResponseWriter, r *http.Request, p Principal) {
		regions := r.URL.Query()["region"]
		if len(regions) > 1 {
			s.writePaidCatalogError(w, r, ErrCatalogNotFound)
			return
		}
		configuration, err := s.resolvePaidCatalogScope(r.Context(), p, r.PathValue("vehicle_id"), r.URL.Query().Get("region"))
		if err != nil {
			s.writePaidCatalogError(w, r, err)
			return
		}
		scope := paidCatalogContext{configuration: configuration}
		if article {
			identity, err := s.loadPaidArticleIdentity(r.Context(), configuration, r.PathValue("article_id"))
			if err != nil {
				s.writePaidCatalogError(w, r, err)
				return
			}
			scope.identity = &identity
		}
		next(w, r.WithContext(context.WithValue(r.Context(), paidCatalogContextKey{}, scope)), p)
	})
}
func (s *Server) paidCatalogAuthenticated(next authenticatedHandler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "private, no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
		defer cancel()
		r = r.WithContext(ctx)
		if r.Method == http.MethodPost && (len(r.Header.Values("Origin")) != 1 || len(r.Header.Values("X-CSRF-Token")) != 1 || !s.customerAuth.validOrigin(r)) {
			s.customerAuth.writeError(w, r, ErrCustomerCSRF)
			return
		}
		p, err := s.auth.Authenticate(r)
		if err != nil {
			s.customerAuth.writeError(w, r, err)
			return
		}
		if !commerceUUID(p.CustomerAccountID) || !commerceUUID(p.OrganizationID) {
			s.customerAuth.writeError(w, r, ErrCustomerDependency)
			return
		}
		next(w, r, p)
	})
}
func (s *Server) loadPaidArticleIdentity(ctx context.Context, c CatalogConfiguration, id string) (PaidArticleIdentity, error) {
	if !commerceUUID(id) {
		return PaidArticleIdentity{}, ErrCatalogNotFound
	}
	repository, ok := s.catalog.(paidArticleIdentityStore)
	if !ok {
		return PaidArticleIdentity{}, ErrVehicleGrantUnavailable
	}
	identity, err := repository.PaidArticleIdentity(ctx, c.ID, id)
	if err != nil {
		return PaidArticleIdentity{}, err
	}
	if identity.ConfigurationID != c.ID || identity.CanonicalArticleID != id || identity.VehicleID != c.VehicleID || (identity.ProviderSlug != "bankone" && identity.ProviderSlug != "banktwo") || identity.SourceVehicleRef == "" || identity.SourceArticleRef == "" {
		return PaidArticleIdentity{}, ErrCatalogNotFound
	}
	return identity, nil
}
func (s *Server) validatePaidCatalogDependencies() error {
	if !s.paidCatalogEnabled() {
		return nil
	}
	catalog, ok := s.catalog.(*postgresCatalogStore)
	if !ok || catalog == nil || catalog.pool == nil {
		return ErrVehicleGrantUnavailable
	}
	if _, ok := s.commerceClient.(VehicleGrantChecker); !ok {
		return ErrVehicleGrantUnavailable
	}
	if len(s.catalogImageKey) != 32 || s.catalogImageReader == nil || s.customerAuth.store == nil {
		return ErrVehicleGrantUnavailable
	}
	return nil
}

func (s *Server) preparePaidCatalogArticle(w http.ResponseWriter, r *http.Request, p Principal) {
	media, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || media != "application/json" {
		writeAPIError(w, r, 415, "INVALID_REQUEST", "A JSON object is required.", false)
		return
	}
	raw, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 2048))
	if err != nil {
		var large *http.MaxBytesError
		status := 400
		if errors.As(err, &large) {
			status = 413
		}
		writeAPIError(w, r, status, "INVALID_REQUEST", "An empty JSON object is required.", false)
		return
	}
	var body map[string]json.RawMessage
	decoder := json.NewDecoder(strings.NewReader(string(raw)))
	if decoder.Decode(&body) != nil || body == nil || len(body) != 0 || decoder.Decode(new(any)) != io.EOF {
		writeAPIError(w, r, 400, "INVALID_REQUEST", "An empty JSON object is required.", false)
		return
	}
	scope, ok := r.Context().Value(paidCatalogContextKey{}).(paidCatalogContext)
	if !ok || scope.identity == nil {
		s.writePaidCatalogError(w, r, ErrVehicleGrantUnavailable)
		return
	}
	view, err := s.catalog.ArticleView(r.Context(), p, scope.configuration.ID, scope.identity.CanonicalArticleID)
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	if view.Withdrawn {
		s.writePaidCatalogError(w, r, ErrCatalogWithdrawn)
		return
	}
	if view.CanSchedule {
		if err = s.checkPaidCatalogGrant(r.Context(), p, scope.configuration); err != nil {
			s.writePaidCatalogError(w, r, err)
			return
		}
		_, scheduleErr := s.ensureCatalogArticleScheduled(r, map[string]any{"scope": "article", "vehicle_id": scope.identity.VehicleID, "vehicle_configuration_id": scope.configuration.ID, "canonical_article_id": scope.identity.CanonicalArticleID})
		view, err = s.catalog.ArticleView(r.Context(), p, scope.configuration.ID, scope.identity.CanonicalArticleID)
		if err != nil {
			s.writePaidCatalogError(w, r, err)
			return
		}
		if scheduleErr != nil && view.Article.Processing == nil && view.Article.Document == nil {
			s.writeCatalogLifecycleError(w, r, 503, "CATALOG_SCHEDULING_UNAVAILABLE", true, view.Article)
			return
		}
	}
	s.respondCatalogArticleView(w, r, p, view)
}
