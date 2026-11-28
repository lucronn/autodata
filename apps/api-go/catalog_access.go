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
	return s.resolveCatalogScope(ctx, p, configurationID, requestedRegion, true)
}
func (s *Server) resolveCatalogScope(ctx context.Context, p Principal, configurationID, requestedRegion string, requireGrant bool) (CatalogConfiguration, error) {
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
	if requireGrant {
		if err = s.checkPaidCatalogGrant(ctx, p, configuration); err != nil {
			return CatalogConfiguration{}, err
		}
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
	s.writePaidCatalogErrorDetails(w, r, err, nil)
}

func (s *Server) writePaidCatalogErrorDetails(w http.ResponseWriter, r *http.Request, err error, details map[string]any) {
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
	writeAPIErrorDetails(w, r, status, code, message, retryable, details)
}

// The scope key and provider are constrained by the canonical article schema.
// Together they let PostgreSQL select a configuration's articles by index.
const paidArticleScopeSQL = `a.scope_key='configuration:'||$1 AND a.provider_slug IN ('bankone','banktwo')`

// Keep the lookup of an existing projection within the selected article.
const paidArticleCurrentJoinSQL = `JOIN LATERAL (
	SELECT * FROM catalog_article_current WHERE canonical_article_id=a.canonical_article_id LIMIT 1
) c ON true`

const paidArticleAvailabilitySQL = `COALESCE(c.availability,
	CASE WHEN j.status IN ('pending','processing') OR (j.status='failed' AND j.retryable)
	THEN 'pending' ELSE 'unavailable' END)`

func catalogServiceScheduleSQL(sourceRevision string) string {
	return `CASE WHEN a.provider_slug='banktwo' AND ` + sourceRevision + ` IS NOT NULL THEN COALESCE((
		SELECT artifact.metadata->>'banktwo_service_schedule'
		FROM canonical_article_source_revisions source
		JOIN source_snapshots body ON body.source_snapshot_id=source.body_source_snapshot_id
		JOIN source_artifacts artifact ON artifact.source_snapshot_id=body.source_snapshot_id
		WHERE source.source_revision_id=` + sourceRevision + `
		  AND body.takedown_status='active' AND artifact.extraction_status<>'quarantined'
		  AND artifact.metadata->>'banktwo_service_schedule' IN ('Normal Service','Severe Service')
	), '') ELSE '' END`
}

func catalogPreviewReadAllowed(ctx context.Context, configurationID string) bool {
	scope, scoped := ctx.Value(paidCatalogContextKey{}).(paidCatalogContext)
	return scoped && !scope.openDemo && scope.configuration.ID == configurationID
}

func setCatalogPreviewDescriptor(article *CatalogArticle, wrapper, linked []byte) {
	if article.SourceRevisionID == nil && article.Availability != "available" &&
		catalogSourcePreviewDocument(wrapper, linked) != nil {
		article.Availability = "available"
		article.ContentStatus = "content_partial"
		article.ContentOrigin = stringPointer("source")
		article.SourceBodyPreview = true
	}
}

// Paid descriptors return only metadata, including readiness of a licensed preview.
func (s *postgresCatalogStore) PaidArticleDescriptors(ctx context.Context, _ Principal, configurationID string) ([]CatalogArticle, error) {
	if !commerceUUID(configurationID) {
		return nil, ErrCatalogNotFound
	}
	tx, err := s.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(ctx)
	// PostgreSQL's estimate prices the article view for every descriptor, even
	// though the inner scan runs only for entries with a stored source revision.
	if _, err = tx.Exec(ctx, `SET LOCAL jit = off`); err != nil {
		return nil, err
	}
	rows, err := tx.Query(ctx, `SELECT a.canonical_article_id::text,COALESCE(a.title,''),COALESCE(a.kind,''),COALESCE(a.component,''),
		c.source_revision_id::text,c.canonical_revision_id::text,c.content_origin,
		`+paidArticleAvailabilitySQL+`,COALESCE(c.review_status,'UNREVIEWED'),`+catalogServiceScheduleSQL("c.source_revision_id")+`,
		CASE WHEN $2::boolean AND j.checkpoint ? 'source_body_preview' THEN
			(SELECT to_jsonb(early) FROM (`+catalogSourceBodyPreviewSQL+`) early)
		END
		FROM canonical_articles a
		LEFT JOIN LATERAL (
		    SELECT source_revision_id,canonical_revision_id,content_origin,availability,review_status,takedown_status
		    FROM catalog_article_current
		    WHERE a.current_source_revision_id IS NOT NULL AND canonical_article_id=a.canonical_article_id LIMIT 1
		) c ON true
		LEFT JOIN source_fetch_jobs j ON j.source_fetch_job_id=a.current_job_id AND a.current_source_revision_id IS NULL
		JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id
		WHERE `+paidArticleScopeSQL+` AND `+lifecycleEligibleSQL+` AND `+lifecycleListedArticleSQL+` AND a.takedown_status='active'
		  AND (a.current_source_revision_id IS NULL OR c.takedown_status='active') AND descriptor.takedown_status='active'
		ORDER BY CASE a.provider_slug WHEN 'bankone' THEN 0 ELSE 1 END,a.source_sort_order NULLS LAST,a.canonical_article_id`, configurationID, catalogPreviewReadAllowed(ctx, configurationID))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogArticle{}
	for rows.Next() {
		var article CatalogArticle
		var preview []byte
		if err = rows.Scan(&article.ID, &article.Title, &article.Kind, &article.Component, &article.SourceRevisionID, &article.CanonicalRevisionID, &article.ContentOrigin, &article.Availability, &article.ReviewStatus, &article.ServiceSchedule, &preview); err != nil {
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
		if len(preview) > 0 {
			var source struct {
				Document       json.RawMessage `json:"document"`
				LinkedDocument json.RawMessage `json:"linked_document"`
			}
			if json.Unmarshal(preview, &source) == nil {
				setCatalogPreviewDescriptor(&article, source.Document, source.LinkedDocument)
			}
		}
		result = append(result, article)
	}
	if err = rows.Err(); err != nil {
		return nil, err
	}
	return result, tx.Commit(ctx)
}

// Paid search keeps the descriptor response metadata-only while comparing the
// current selected projection inside the protected server boundary.
func (s *postgresCatalogStore) PaidArticleSearchDescriptors(ctx context.Context, _ Principal, configurationID, query string) ([]CatalogArticle, error) {
	if !commerceUUID(configurationID) {
		return nil, ErrCatalogNotFound
	}
	tx, err := s.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(ctx)
	if _, err = tx.Exec(ctx, `SET LOCAL jit = off`); err != nil {
		return nil, err
	}
	includeSource := catalogPreviewReadAllowed(ctx, configurationID)
	// Search the displayed article first, including an early source preview
	// when available. The current Original shares the effective view's source
	// pin, takedown checks and lifecycle eligibility.
	rows, err := tx.Query(ctx, `SELECT a.canonical_article_id::text,COALESCE(a.title,''),COALESCE(a.kind,''),COALESCE(a.component,''),
		c.source_revision_id::text,c.canonical_revision_id::text,c.content_origin,`+paidArticleAvailabilitySQL+`,
		COALESCE(c.review_status,'UNREVIEWED'),
		COALESCE(c.document,early.document),COALESCE(c.body,''),c.steps,c.images,sr.source_images,early.linked_document,
		CASE WHEN $2::boolean AND c.canonical_revision_id IS NOT NULL
		  AND sr.canonical_article_id=a.canonical_article_id THEN sr.source_document END,
		`+catalogServiceScheduleSQL("c.source_revision_id")+`
		FROM canonical_articles a
		LEFT JOIN LATERAL (
			SELECT * FROM catalog_article_current
			WHERE a.current_source_revision_id IS NOT NULL AND canonical_article_id=a.canonical_article_id LIMIT 1
		) c ON true
		LEFT JOIN source_fetch_jobs j ON j.source_fetch_job_id=a.current_job_id AND a.current_source_revision_id IS NULL
		LEFT JOIN LATERAL (`+catalogSourceBodyPreviewSQL+`) early ON $2::boolean
		JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id
		LEFT JOIN canonical_article_source_revisions sr ON sr.source_revision_id=c.source_revision_id
		WHERE `+paidArticleScopeSQL+` AND `+lifecycleEligibleSQL+` AND `+lifecycleListedArticleSQL+`
		  AND a.takedown_status='active' AND descriptor.takedown_status='active'
		  AND (a.current_source_revision_id IS NULL OR (c.availability='available' AND c.takedown_status='active'))
		ORDER BY CASE a.provider_slug WHEN 'bankone' THEN 0 ELSE 1 END,a.source_sort_order NULLS LAST,a.canonical_article_id`, configurationID, includeSource)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogArticle{}
	words := strings.Fields(strings.ToLower(query))
	for rows.Next() {
		article, matched, err := scanPaidArticleSearchRow(rows, configurationID, words)
		if err != nil {
			return nil, err
		}
		if matched {
			result = append(result, article)
		}
	}
	if err = rows.Err(); err != nil {
		return nil, err
	}
	return result, tx.Commit(ctx)
}

// The returned descriptor remains metadata-only even when its content matched.
func scanPaidArticleSearchRow(row interface{ Scan(...any) error }, configurationID string, words []string) (CatalogArticle, bool, error) {
	var article CatalogArticle
	var projection paidSearchProjection
	var original []byte
	if err := row.Scan(&article.ID, &article.Title, &article.Kind, &article.Component, &article.SourceRevisionID, &article.CanonicalRevisionID, &article.ContentOrigin, &article.Availability, &article.ReviewStatus, &projection.document, &projection.body, &projection.steps, &projection.images, &projection.sourceImages, &projection.linkedPreview, &original, &article.ServiceSchedule); err != nil {
		return CatalogArticle{}, false, err
	}
	if !catalogSearchWordsMatch(strings.Join([]string{article.Title, article.Component, article.Kind, article.ServiceSchedule}, " "), words) {
		matched, err := projection.matchesContent(article, words)
		if err != nil {
			return CatalogArticle{}, false, err
		}
		if !matched && len(original) > 0 {
			matched = projection.matchesOriginal(article, original, words)
		}
		if !matched {
			return CatalogArticle{}, false, nil
		}
	}
	article.CanonicalArticleID = stringPointer(article.ID)
	article.VehicleID = configurationID
	article.Images = []CatalogImage{}
	article.Complete = article.CanonicalRevisionID != nil
	article.ContentStatus = "list_only"
	if article.Complete {
		article.ContentStatus = "content_complete"
	}
	setCatalogPreviewDescriptor(&article, projection.document, projection.linkedPreview)
	return article, true, nil
}

type paidSearchProjection struct {
	document, steps, images, sourceImages []byte
	linkedPreview                         []byte
	body                                  string
}

func (projection paidSearchProjection) matchesContent(searchable CatalogArticle, words []string) (bool, error) {
	if searchable.SourceRevisionID == nil {
		searchable.Document = parseLinkedSourceBodyPreview(projection.linkedPreview)
	}
	if searchable.Document == nil && len(projection.document) > 0 {
		var parsed CatalogDocument
		if err := json.Unmarshal(projection.document, &parsed); err != nil {
			// An unreadable early preview must not break descriptor searches.
			if searchable.SourceRevisionID == nil {
				return false, nil
			}
			return false, err
		}
		searchable.Document = &parsed
	}
	if len(projection.images) > 0 {
		if err := json.Unmarshal(projection.images, &searchable.Images); err != nil {
			return false, err
		}
	}
	if searchable.Document != nil && len(searchable.Document.Blocks) > 0 {
		// Ordered documents still resolve figures stored on compatibility steps.
		// Their legacy action, body and evidence fields are hidden in this view.
		if len(projection.steps) > 0 {
			var steps []struct {
				Images []CatalogImage `json:"images"`
			}
			if err := json.Unmarshal(projection.steps, &steps); err != nil {
				return false, err
			}
			for _, step := range steps {
				searchable.Images = append(searchable.Images, step.Images...)
			}
		}
	} else {
		searchable.Body = projection.body
		if len(projection.steps) > 0 {
			if err := json.Unmarshal(projection.steps, &searchable.Steps); err != nil {
				return false, err
			}
		}
	}
	if err := projection.scopeImages(&searchable); err != nil {
		return false, err
	}
	return catalogSearchWordsMatch(catalogArticleSearchText(searchable, true), words), nil
}

func (projection paidSearchProjection) matchesOriginal(searchable CatalogArticle, original []byte, words []string) bool {
	if err := json.Unmarshal(original, &searchable.Document); err != nil || searchable.Document == nil {
		return false
	}
	if len(projection.sourceImages) > 0 && json.Unmarshal(projection.sourceImages, &searchable.Images) != nil {
		return false
	}
	scopePaidSearchImages(&searchable, searchable.Images)
	return catalogSearchWordsMatch(catalogArticleSearchText(searchable, true), words)
}

func (projection paidSearchProjection) scopeImages(article *CatalogArticle) error {
	var sourceImages []CatalogImage
	if len(projection.sourceImages) > 0 {
		if err := json.Unmarshal(projection.sourceImages, &sourceImages); err != nil {
			return err
		}
	}
	scopePaidSearchImages(article, sourceImages)
	return nil
}

func scopePaidSearchImages(article *CatalogArticle, sourceImages []CatalogImage) {
	assets := indexPaidCatalogAssets(sourceImages)
	// A paid detail only mints media URLs for assets still present in the
	// selected source. Preserve that boundary while comparing text privately.
	clearUnproven := func(images []CatalogImage) {
		for i := range images {
			image := &images[i]
			// JSON decoding projects asset_id and image_id. Match the paid
			// reader's public alias for the legacy id field as well.
			image.ID = publicCatalogAssetID(image.ID)
			asset := paidCatalogImageAssetID(*image)
			_, present := assets[paidCatalogAssetKey{asset, image.StorageKey}]
			image.URL = ""
			if !present || !paidCatalogAssetPattern.MatchString(asset) || !localCatalogImageKeyPattern.MatchString(image.StorageKey) {
				image.StorageKey = ""
			}
		}
	}
	clearUnproven(article.Images)
	for _, step := range article.Steps {
		if step.Images != nil {
			clearUnproven(*step.Images)
		}
	}
}

func (s *postgresCatalogStore) PaidArticleIdentity(ctx context.Context, configurationID, articleID string) (PaidArticleIdentity, error) {
	var identity PaidArticleIdentity
	if !commerceUUID(configurationID) || !commerceUUID(articleID) {
		return identity, ErrCatalogNotFound
	}
	var articleRights, descriptorRights string
	err := s.pool.QueryRow(ctx, `SELECT a.vehicle_configuration_id::text,a.canonical_article_id::text,a.vehicle_id::text,a.provider_slug,a.source_vehicle_ref,a.source_article_ref,a.current_source_revision_id::text,a.takedown_status,descriptor.takedown_status FROM canonical_articles a JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id WHERE a.vehicle_configuration_id=$1::uuid AND a.canonical_article_id=$2::uuid AND `+lifecycleEligibleSQL, configurationID, articleID).Scan(&identity.ConfigurationID, &identity.CanonicalArticleID, &identity.VehicleID, &identity.ProviderSlug, &identity.SourceVehicleRef, &identity.SourceArticleRef, &identity.CurrentSourceRevisionID, &articleRights, &descriptorRights)
	if errors.Is(err, pgx.ErrNoRows) {
		return PaidArticleIdentity{}, ErrCatalogNotFound
	}
	if err == nil && (articleRights != "active" || descriptorRights != "active") {
		return PaidArticleIdentity{}, ErrCatalogWithdrawn
	}
	return identity, err
}

type paidCatalogContextKey struct{}
type selectedIndexSessionContextKey struct{}
type paidCatalogContext struct {
	configuration CatalogConfiguration
	identity      *PaidArticleIdentity
	openDemo      bool
}

const (
	catalogArticleIndexPattern     = "GET /v1/catalog/vehicles/{vehicle_id}/articles"
	catalogArticleDetailPattern    = "GET /v1/catalog/vehicles/{vehicle_id}/articles/{article_id}"
	purchaseQuotePreference        = "workshop-purchase-quote"
	selectedIndexSessionPreference = "workshop-confirm-session"
)

func (s *Server) selectedIndexAuth() *customerAuthService {
	if customer, ok := s.auth.(*customerAuthService); ok && customer == s.customerAuth {
		return customer
	}
	return nil
}

func wantsSelectedIndexSession(r *http.Request) bool {
	if r.Method != http.MethodGet || r.Pattern != catalogArticleIndexPattern ||
		!catalogReadPreferenceRequested(r, selectedIndexSessionPreference) {
		return false
	}
	query, ok := commerceQuery(r, "region")
	return ok && commerceScopeValid(r.PathValue("vehicle_id"), query.Get("region"))
}

func wantsRetainedReaderSession(r *http.Request) bool {
	return r.Method == http.MethodGet && r.Pattern == catalogArticleDetailPattern &&
		catalogReadPreferenceRequested(r, retainedReaderSessionPreference)
}

func wantsCatalogPurchaseQuote(r *http.Request, configuration CatalogConfiguration) bool {
	if r.Method != http.MethodGet || r.Pattern != catalogArticleIndexPattern {
		return false
	}
	query, ok := commerceQuery(r, "region")
	if !ok || !commerceRegion(configuration.Region) || query.Get("region") != configuration.Region {
		return false
	}
	return catalogReadPreferenceRequested(r, purchaseQuotePreference)
}

func (s *Server) catalogPurchaseQuote(ctx context.Context, configuration CatalogConfiguration, p Principal) *commerceQuote {
	input := s.workshopQuoteInput(configuration.ID, configuration.Region, p)
	status, body, err := s.doCommerce(ctx, "quote", input, nil, "")
	if err != nil {
		return nil
	}
	public, ok := commercePublicResult("quote", status, body, input, s.commerceClient)
	if !ok {
		return nil
	}
	quote, ok := public.(commerceQuote)
	if !ok || !quote.Purchasable {
		return nil
	}
	return &quote
}

func (s *Server) mountCatalogSelector(mux *http.ServeMux, path string, next authenticatedHandler) {
	if !s.paidCatalogEnabled() {
		mux.Handle("GET "+path, s.requireRole("dataset_viewer", next))
		return
	}
	mountPublicRead(mux, path, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		next(w, r, Principal{})
	})
}

func (s *Server) cacheCompleteCatalogSelector(w http.ResponseWriter, r *http.Request, ready bool) {
	if ready && s.paidCatalogEnabled() && !catalogStoredSelector(r) {
		w.Header().Set("Cache-Control", "private, max-age=30")
	}
}

func (s *Server) catalogProtected(next authenticatedHandler, article bool) http.Handler {
	if !s.paidCatalogEnabled() {
		return s.requireRole("dataset_viewer", next)
	}
	serve := func(w http.ResponseWriter, r *http.Request, p Principal, openDemo bool) {
		w.Header().Set("Cache-Control", "private, no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		regions := r.URL.Query()["region"]
		if len(regions) > 1 {
			s.writePaidCatalogError(w, r, ErrCatalogNotFound)
			return
		}
		configuration, err := s.resolveCatalogScope(r.Context(), p, r.PathValue("vehicle_id"), r.URL.Query().Get("region"), false)
		if err != nil {
			s.writePaidCatalogError(w, r, err)
			return
		}
		if expires, ok := r.Context().Value(selectedIndexSessionContextKey{}).(time.Time); ok {
			w.Header().Add("Preference-Applied", selectedIndexSessionPreference)
			w.Header().Set("Workshop-Session-Expires", expires.UTC().Format(time.RFC3339))
		}
		if !openDemo {
			if err := s.checkPaidCatalogGrant(r.Context(), p, configuration); err != nil {
				if errors.Is(err, ErrVehicleGrantRequired) && wantsCatalogPurchaseQuote(r, configuration) {
					w.Header().Add("Preference-Applied", purchaseQuotePreference)
					s.writePaidCatalogErrorDetails(w, r, err, map[string]any{
						"purchase_quote": s.catalogPurchaseQuote(r.Context(), configuration, p),
					})
					return
				}
				s.writePaidCatalogError(w, r, err)
				return
			}
		}
		scope := paidCatalogContext{configuration: configuration, openDemo: openDemo}
		if article {
			identity, err := s.loadPaidArticleIdentity(r.Context(), configuration, r.PathValue("article_id"))
			if err != nil {
				s.writePaidCatalogError(w, r, err)
				return
			}
			scope.identity = &identity
		}
		next(w, r.WithContext(context.WithValue(r.Context(), paidCatalogContextKey{}, scope)), p)
	}
	paid := s.paidCatalogAuthenticated(func(w http.ResponseWriter, r *http.Request, p Principal) { serve(w, r, p, false) })
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if s.workshopOpenDemoRequest(r) {
			serve(w, r, Principal{}, true)
			return
		}
		paid.ServeHTTP(w, r)
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
		var p Principal
		var expires time.Time
		var err error
		if customer := s.selectedIndexAuth(); customer != nil && wantsSelectedIndexSession(r) {
			p, expires, err = customer.authenticate(r, true)
		} else {
			p, err = s.auth.Authenticate(r)
		}
		if err != nil {
			s.customerAuth.writeError(w, r, err)
			return
		}
		if !commerceUUID(p.CustomerAccountID) || !commerceUUID(p.OrganizationID) {
			s.customerAuth.writeError(w, r, ErrCustomerDependency)
			return
		}
		if !expires.IsZero() {
			r = r.WithContext(context.WithValue(r.Context(), selectedIndexSessionContextKey{}, expires))
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
