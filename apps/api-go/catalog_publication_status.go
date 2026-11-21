package main

import (
	"context"
	"errors"
	"net/http"
	"strconv"

	"github.com/jackc/pgx/v5"
)

const (
	publicationStatusPreference = "workshop-publication-status"
	publicationCheckHeader      = "Workshop-Publication-Check"
	publicationJobHeader        = "X-Workshop-Publication-Job"
	publicationSourceHeader     = "X-Workshop-Source-Revision"
)

type catalogPublicationStatusResponse struct {
	Version           string `json:"version"`
	ArticleID         string `json:"article_id"`
	JobID             string `json:"job_id"`
	SourceRevisionID  string `json:"source_revision_id"`
	State             string `json:"state"`
	RetryAfterSeconds *int   `json:"retry_after_seconds,omitempty"`
}

type paidPublicationStatusStore interface {
	paidPublicationStatus(ctx context.Context, configuration, article, job, source string) (*catalogPublicationStatusResponse, error)
}

func activeArticlePublication(state string) bool {
	switch state {
	case "normalizing", "rewriting", "validating", "publishing":
		return true
	default:
		return false
	}
}

func (s *Server) canCheckCatalogPublication(article CatalogArticle) bool {
	_, supported := s.catalog.(paidPublicationStatusStore)
	return supported && article.Availability == "available" && article.ContentOrigin != nil && *article.ContentOrigin == "source" &&
		article.CanonicalRevisionID == nil && article.SourceRevisionID != nil && commerceUUID(*article.SourceRevisionID) &&
		article.Document != nil && len(article.Document.Blocks) > 0 && article.Processing != nil &&
		commerceUUID(article.Processing.JobID) && activeArticlePublication(article.Processing.State)
}

func (s *Server) respondCatalogPublicationStatus(w http.ResponseWriter, r *http.Request) bool {
	if r.Method != http.MethodGet || !catalogReadPreferenceRequested(r, publicationStatusPreference) {
		return false
	}
	scope, ok := r.Context().Value(paidCatalogContextKey{}).(paidCatalogContext)
	if !ok || scope.openDemo || scope.identity == nil {
		return false
	}
	store, ok := s.catalog.(paidPublicationStatusStore)
	jobs, sources := r.Header.Values(publicationJobHeader), r.Header.Values(publicationSourceHeader)
	if !ok || len(jobs) != 1 || !commerceUUID(jobs[0]) || len(sources) != 1 || !commerceUUID(sources[0]) ||
		scope.identity.CurrentSourceRevisionID == nil || *scope.identity.CurrentSourceRevisionID != sources[0] {
		return false
	}
	status, err := store.paidPublicationStatus(r.Context(), scope.configuration.ID, scope.identity.CanonicalArticleID, jobs[0], sources[0])
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return true
	}
	if status == nil || status.ArticleID != scope.identity.CanonicalArticleID || status.JobID != jobs[0] ||
		status.SourceRevisionID != sources[0] || !activeArticlePublication(status.State) {
		return false
	}
	result := *status
	result.Version = "v1"
	if result.RetryAfterSeconds != nil {
		seconds := max(1, *result.RetryAfterSeconds)
		result.RetryAfterSeconds = &seconds
		w.Header().Set("Retry-After", strconv.Itoa(seconds))
	}
	w.Header().Set("Preference-Applied", publicationStatusPreference)
	writeJSON(w, http.StatusOK, result)
	return true
}

func (s *postgresCatalogStore) paidPublicationStatus(ctx context.Context, configuration, article, job, source string) (*catalogPublicationStatusResponse, error) {
	var descriptorRights, articleRights, availability string
	var currentJob, currentSource, state, origin *string
	var retry *int
	err := s.pool.QueryRow(ctx, `SELECT descriptor.takedown_status,c.takedown_status,c.availability,
		c.job_id::text,c.source_revision_id::text,c.processing_state,c.content_origin,c.retry_after_seconds
		FROM canonical_articles a `+paidArticleCurrentJoinSQL+`
		JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id
		WHERE a.vehicle_configuration_id=$1::uuid AND a.canonical_article_id=$2::uuid AND `+lifecycleEligibleSQL,
		configuration, article).Scan(&descriptorRights, &articleRights, &availability, &currentJob, &currentSource, &state, &origin, &retry)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrCatalogNotFound
	}
	if err != nil {
		return nil, err
	}
	if descriptorRights != "active" || articleRights != "active" {
		return nil, ErrCatalogWithdrawn
	}
	if availability != "available" || origin == nil || *origin != "source" || state == nil || !activeArticlePublication(*state) ||
		currentJob == nil || *currentJob != job || currentSource == nil || *currentSource != source {
		return nil, nil
	}
	return &catalogPublicationStatusResponse{ArticleID: article, JobID: *currentJob, SourceRevisionID: *currentSource, State: *state, RetryAfterSeconds: retry}, nil
}
