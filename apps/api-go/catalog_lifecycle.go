package main

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

var ErrCatalogWithdrawn = errors.New("catalog article withdrawn")

type CatalogProcessing struct {
	JobID               string  `json:"job_id"`
	State               string  `json:"state"`
	Retryable           bool    `json:"retryable"`
	RetryAfterSeconds   *int    `json:"retry_after_seconds"`
	ErrorCode           *string `json:"error_code"`
	UpdatedAt           string  `json:"updated_at"`
	shortReadPreference string
}
type CatalogArticleView struct {
	Article           CatalogArticle
	CanSchedule       bool
	Withdrawn         bool
	sourceBodyPreview *CatalogDocument
}
type CatalogScheduleResult struct {
	JobID              string  `json:"job_id"`
	State              string  `json:"state"`
	CanonicalArticleID *string `json:"canonical_article_id"`
	SourceRevisionID   *string `json:"source_revision_id"`
	RetryAfterSeconds  *int    `json:"retry_after_seconds"`
}

func lifecycleArticle(article CatalogArticle) CatalogArticle {
	if article.Images == nil {
		article.Images = []CatalogImage{}
	}
	article.Document = publicCatalogDocument(article.Document)
	readable := article.Document != nil && len(article.Document.Blocks) > 0
	if article.CanonicalArticleID == nil {
		article.Complete = false
		if readable || article.Body != "" || len(article.Steps) > 0 {
			article.ContentOrigin = stringPointer("source")
			article.Availability = "available"
			article.ContentStatus = "content_partial"
		} else {
			article.Availability = "unavailable"
			article.ContentStatus = "list_only"
		}
	}
	if article.Availability == "" {
		article.Availability = "unavailable"
	}
	if readable {
		// Hash only immutable public projection and policy. Expiring media URLs and
		// processing timestamps are deliberately excluded from display identity.
		images := append([]CatalogImage{}, article.Images...)
		for i := range images {
			images[i].URL = ""
			images[i].StorageKey = ""
		}
		steps := append([]CatalogStep(nil), article.Steps...)
		for i := range steps {
			if steps[i].Images != nil {
				stepImages := append([]CatalogImage{}, (*steps[i].Images)...)
				for j := range stepImages {
					stepImages[j].URL = ""
					stepImages[j].StorageKey = ""
				}
				steps[i].Images = &stepImages
			}
		}
		raw, _ := json.Marshal(struct {
			Policy            string
			Source, Canonical *string
			Origin            *string
			Document          *CatalogDocument
			Body              string
			Steps             []CatalogStep
			Images            []CatalogImage
		}{"source-display-v1", article.SourceRevisionID, article.CanonicalRevisionID, article.ContentOrigin, article.Document, article.Body, steps, images})
		sum := sha256.Sum256(raw)
		article.ViewRevision = stringPointer(fmt.Sprintf("view-%x", sum[:]))
	}
	if article.Processing != nil {
		processing := *article.Processing
		article.Processing = &processing
		active := article.Processing.State != "completed" && article.Processing.State != "needs_review" && article.Processing.State != "failed"
		if active && article.Processing.RetryAfterSeconds == nil {
			seconds := 2
			if !readable || (article.ContentOrigin != nil && *article.ContentOrigin == "source") {
				// Give the reader an earlier check for retained source or its
				// first publication. Explicit delays and canonical refreshes
				// keep their normal cadence.
				seconds = 1
			}
			state := processing.State
			switch {
			case !readable && (state == "queued" || state == "fetching_source"):
				processing.shortReadPreference = shortSourceCheckPreference
			case readable && article.Availability == "available" && article.ContentOrigin != nil && *article.ContentOrigin == "source" &&
				(state == "normalizing" || state == "rewriting" || state == "validating" || state == "publishing"):
				processing.shortReadPreference = shortPublicationCheckPreference
			}
			processing.RetryAfterSeconds = &seconds
		}
		if article.Processing.RetryAfterSeconds != nil && *article.Processing.RetryAfterSeconds < 1 {
			n := 1
			article.Processing.RetryAfterSeconds = &n
		}
	}
	return article
}
func (s *memoryCatalogStore) ArticleView(ctx context.Context, p Principal, v, id string) (CatalogArticleView, error) {
	article, err := s.Article(ctx, p, v, id)
	if err != nil {
		return CatalogArticleView{}, err
	}
	if article.Document == nil && article.sourceArticleID != "" {
		if cached, e := s.Article(ctx, p, v, article.sourceArticleID); e == nil && cached.Document != nil {
			article = cached
		}
	}
	article = lifecycleArticle(article)
	return CatalogArticleView{Article: article, CanSchedule: article.CanonicalArticleID != nil && article.Processing == nil}, nil
}
func (s *memoryCatalogStore) ArticleSourceRevision(ctx context.Context, p Principal, v, id, revision string) (CatalogSourceContent, error) {
	if revision != "" {
		return CatalogSourceContent{}, ErrCatalogNotFound
	}
	return s.ArticleSource(ctx, p, v, id)
}

// A configuration selector has an exact configuration scope; an unconfigured
// vehicle selector addresses only its vehicle scope. Scope precedes alias lookup.
const lifecycleScopeSQL = `(a.vehicle_id::text=$1 AND a.vehicle_configuration_id IS NULL OR a.vehicle_configuration_id::text=$1)`
const lifecycleEligibleSQL = `a.membership_status='active' AND NOT EXISTS(SELECT 1 FROM source_review_items quarantine WHERE quarantine.item_kind='quarantine' AND quarantine.status<>'approved' AND (quarantine.source_snapshot_ids ? a.descriptor_source_snapshot_id::text OR EXISTS(SELECT 1 FROM canonical_article_source_revisions source WHERE source.source_revision_id=a.current_source_revision_id AND (quarantine.source_snapshot_ids ? source.body_source_snapshot_id::text OR EXISTS(SELECT 1 FROM jsonb_array_elements(source.resource_manifest) resource JOIN source_snapshots asset ON asset.content_sha256::text=resource->>'sha256' WHERE quarantine.source_snapshot_ids ? asset.source_snapshot_id::text))))) AND (a.vehicle_configuration_id IS NULL OR EXISTS (SELECT 1 FROM vehicle_configurations vc JOIN vehicle_identity_bases vb USING(vehicle_identity_base_id) WHERE vc.vehicle_configuration_id=a.vehicle_configuration_id AND vc.reviewer_state<>'rejected' AND vb.reviewer_state<>'rejected'))`

// Search and detail use the same exact job and source rights for the first
// supplier body. Callers still check current descriptor and configuration rights.
const catalogSourceBodyPreviewSQL = `
	SELECT j.checkpoint->'source_body_preview'->'document' AS document
	FROM source_fetch_jobs j
	JOIN source_snapshots snap ON snap.source_snapshot_id=CASE
		WHEN j.checkpoint->'source_body_preview'->>'snapshot_id' ~ '^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$'
		THEN (j.checkpoint->'source_body_preview'->>'snapshot_id')::uuid END
	WHERE a.vehicle_configuration_id::text=$1 AND a.current_source_revision_id IS NULL AND a.takedown_status='active'
	AND j.source_fetch_job_id=a.current_job_id
	AND j.job_kind='article' AND j.canonical_article_id=a.canonical_article_id
	AND j.request_generation=a.request_generation AND j.canonical_vehicle_id=a.vehicle_id
	AND j.provider_slug=a.provider_slug AND j.source_vehicle_ref=a.source_vehicle_ref
	AND j.source_article_ref=a.source_article_ref AND snap.takedown_status='active'
	AND j.checkpoint->'source_body_preview'->>'descriptor_snapshot_id'=a.descriptor_source_snapshot_id::text
	AND NOT EXISTS (
		SELECT 1 FROM source_review_items quarantine
		WHERE quarantine.item_kind='quarantine' AND quarantine.status<>'approved'
		AND quarantine.source_snapshot_ids ? snap.source_snapshot_id::text
	)`

func (s *postgresCatalogStore) ArticleView(ctx context.Context, p Principal, v, id string) (CatalogArticleView, error) {
	if !commerceUUID(id) {
		return CatalogArticleView{}, ErrCatalogNotFound
	}
	var raw, preview []byte
	// Resolve the direct ID and at most one proven alias before evaluating the
	// effective article view. Direct IDs take precedence within the same scope.
	err := s.pool.QueryRow(ctx, `SELECT to_jsonb(view_row), early.document FROM canonical_articles a
		JOIN LATERAL (
			SELECT * FROM catalog_article_current WHERE canonical_article_id=a.canonical_article_id LIMIT 1
		) view_row ON true
		LEFT JOIN LATERAL (`+catalogSourceBodyPreviewSQL+`) early ON view_row.takedown_status='active'
		WHERE a.canonical_article_id IN ($2::uuid, (
			SELECT alias.canonical_article_id FROM canonical_article_aliases alias
			JOIN catalog_articles legacy USING(catalog_article_id)
			JOIN canonical_articles owner ON owner.canonical_article_id=alias.canonical_article_id
			WHERE alias.catalog_article_id=$2::uuid AND legacy.vehicle_id=owner.vehicle_id
			AND legacy.vehicle_configuration_id IS NOT DISTINCT FROM owner.vehicle_configuration_id
		)) AND `+lifecycleScopeSQL+` AND `+lifecycleEligibleSQL+`
		ORDER BY (a.canonical_article_id=$2::uuid) DESC LIMIT 1`, v, id).Scan(&raw, &preview)
	if errors.Is(err, pgx.ErrNoRows) {
		legacy, e := s.legacyArticle(ctx, p, v, id)
		if e != nil {
			if errors.Is(e, ErrCatalogNotFound) {
				var withdrawn bool
				probeErr := s.pool.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM catalog_articles ca JOIN source_snapshots ss USING(source_snapshot_id) WHERE ca.catalog_article_id=$2::uuid AND (ca.vehicle_id::text=$1 AND ca.vehicle_configuration_id IS NULL OR ca.vehicle_configuration_id::text=$1) AND ss.takedown_status<>'active')`, v, id).Scan(&withdrawn)
				if probeErr != nil {
					return CatalogArticleView{}, probeErr
				}
				if withdrawn {
					return CatalogArticleView{}, ErrCatalogWithdrawn
				}
			}
			return CatalogArticleView{}, e
		}
		legacy = lifecycleArticle(legacy)
		return CatalogArticleView{Article: legacy}, nil
	}
	if err != nil {
		return CatalogArticleView{}, err
	}
	var row struct {
		CanonicalArticleID  string           `json:"canonical_article_id"`
		VehicleID           string           `json:"vehicle_id"`
		ConfigurationID     *string          `json:"vehicle_configuration_id"`
		Title               string           `json:"title"`
		Kind                string           `json:"kind"`
		Component           string           `json:"component"`
		SourceRevisionID    *string          `json:"source_revision_id"`
		CanonicalRevisionID *string          `json:"canonical_revision_id"`
		ContentOrigin       *string          `json:"content_origin"`
		Availability        string           `json:"availability"`
		Document            *CatalogDocument `json:"document"`
		Images              []CatalogImage   `json:"images"`
		Body                string           `json:"body"`
		Steps               []CatalogStep    `json:"steps"`
		JobID               *string          `json:"job_id"`
		State               *string          `json:"processing_state"`
		Retryable           bool             `json:"retryable"`
		Retry               *int             `json:"retry_after_seconds"`
		Error               *string          `json:"processing_error_code"`
		Review              *string          `json:"review_status"`
		Updated             string           `json:"updated_at"`
		Takedown            string           `json:"takedown_status"`
		Snapshot            *string          `json:"source_snapshot_id"`
		Hash                *string          `json:"source_content_sha256"`
		Version             *string          `json:"source_version"`
	}
	if err = json.Unmarshal(raw, &row); err != nil {
		return CatalogArticleView{}, err
	}
	article := CatalogArticle{ID: row.CanonicalArticleID, VehicleID: v, CanonicalArticleID: &row.CanonicalArticleID, Title: row.Title, Kind: row.Kind, Component: row.Component, SourceRevisionID: row.SourceRevisionID, CanonicalRevisionID: row.CanonicalRevisionID, ContentOrigin: row.ContentOrigin, Availability: row.Availability, Document: row.Document, Images: row.Images, Body: row.Body, Steps: row.Steps, ReviewStatus: row.Review, ContentStatus: "list_only"}
	if row.JobID != nil && row.State != nil {
		article.Processing = &CatalogProcessing{JobID: *row.JobID, State: *row.State, Retryable: row.Retryable, RetryAfterSeconds: row.Retry, ErrorCode: publicProcessingError(row.Error), UpdatedAt: row.Updated}
	}
	article.Complete = row.CanonicalRevisionID != nil && row.ContentOrigin != nil && *row.ContentOrigin == "canonical" && row.Document != nil && len(row.Document.Blocks) > 0
	if article.Complete {
		article.ContentStatus = "content_complete"
	} else if row.Document != nil && len(row.Document.Blocks) > 0 {
		article.ContentStatus = "content_partial"
	}
	if row.SourceRevisionID != nil {
		article.sourceAvailable = true
		article.sourceFormat = "html"
		if row.Snapshot != nil {
			article.sourceSnapshotID = *row.Snapshot
		}
		if row.Hash != nil {
			article.sourceContentSHA256 = *row.Hash
		}
		if row.Version != nil {
			article.sourceVersion = *row.Version
		}
	}
	article.canonicalVehicleID = row.VehicleID
	article.canonicalConfigurationID = row.ConfigurationID
	article = lifecycleArticle(article)
	view := CatalogArticleView{Article: article, Withdrawn: row.Takedown != "active", CanSchedule: row.JobID == nil && row.Takedown == "active"}
	if len(preview) != 0 && !view.Withdrawn {
		var document CatalogDocument
		// A failed preview read must not prevent the current article view.
		if json.Unmarshal(preview, &document) == nil && len(document.Blocks) != 0 {
			view.sourceBodyPreview = &document
		}
	}
	return view, nil
}
func publicProcessingError(code *string) *string {
	if code == nil {
		return nil
	}
	var safe string
	switch *code {
	case "CANONICAL_REVIEW_REJECTED":
		safe = "CATALOG_REVIEW_REQUIRED"
	case "CATALOG_SOURCE_UNAVAILABLE":
		safe = *code
	case "CATALOG_REWRITE_REJECTED":
		safe = *code
	default:
		safe = "CATALOG_REWRITE_UNAVAILABLE"
		if strings.HasPrefix(*code, "SOURCE_") || strings.HasPrefix(*code, "RESOURCE_") {
			safe = "CATALOG_SOURCE_UNAVAILABLE"
		}
	}
	return &safe
}
func (s *postgresCatalogStore) Article(ctx context.Context, p Principal, v, id string) (CatalogArticle, error) {
	view, err := s.ArticleView(ctx, p, v, id)
	if view.Withdrawn {
		return CatalogArticle{}, ErrCatalogWithdrawn
	}
	return view.Article, err
}
func (s *Server) ensureCatalogArticleScheduled(request *http.Request, payload map[string]any) (CatalogScheduleResult, error) {
	var result CatalogScheduleResult
	if s.ingestionClient == nil {
		return result, errors.New("scheduling unavailable")
	}
	key, body, err := catalogHydrationRequest(payload)
	if err != nil {
		return result, err
	}
	ctx, cancel := context.WithTimeout(request.Context(), 2*time.Second)
	defer cancel()
	status, raw, err := s.ingestionClient.Do(request.Clone(ctx), "/v1/catalog/ensure", body, key)
	if err != nil {
		return result, err
	}
	if status != 200 && status != 202 && status != 409 {
		return result, errors.New("scheduling unavailable")
	}
	if err = json.Unmarshal(raw, &result); err != nil {
		return result, err
	}
	if result.JobID == "" {
		return result, errors.New("missing durable job")
	}
	return result, nil
}
func (s *Server) writeCatalogLifecycleError(w http.ResponseWriter, r *http.Request, status int, code string, retry bool, article CatalogArticle) {
	details := map[string]any{}
	if retry {
		seconds := 2
		if article.Processing != nil && article.Processing.RetryAfterSeconds != nil {
			seconds = *article.Processing.RetryAfterSeconds
		}
		w.Header().Set("Retry-After", strconv.Itoa(seconds))
		details["retry_after_seconds"] = seconds
	}
	if article.ID != "" {
		details["article_id"] = article.ID
	}
	if article.Processing != nil {
		details["job_id"] = article.Processing.JobID
		if article.Processing.RetryAfterSeconds != nil {
			details["retry_after_seconds"] = *article.Processing.RetryAfterSeconds
		}
	}
	writeJSON(w, status, map[string]any{"error": map[string]any{"code": code, "message": catalogErrorMessage(code), "request_id": requestIDFrom(r), "retryable": retry, "details": details}})
}
func catalogErrorMessage(code string) string {
	switch code {
	case "CATALOG_REVIEW_REQUIRED":
		return "Article review is required."
	case "CATALOG_PROCESSING_FAILED":
		return "Article preparation could not finish."
	case "CATALOG_WITHDRAWN":
		return "Article is no longer available."
	default:
		return "Article is temporarily unavailable."
	}
}

func (s *postgresCatalogStore) Articles(ctx context.Context, p Principal, v string) ([]CatalogArticle, error) {
	// Descriptor-only selection never reads a source document or performs work.
	rows, err := s.pool.Query(ctx, `SELECT a.canonical_article_id::text,COALESCE(a.title,''),COALESCE(a.kind,''),COALESCE(a.component,''), c.source_revision_id::text,c.canonical_revision_id::text,c.content_origin,c.availability,c.review_status FROM canonical_articles a JOIN catalog_article_current c USING(canonical_article_id) WHERE `+lifecycleScopeSQL+` AND `+lifecycleEligibleSQL+` AND c.takedown_status='active' ORDER BY CASE a.provider_slug WHEN 'bankone' THEN 0 ELSE 1 END,a.source_sort_order NULLS LAST,a.canonical_article_id`, v)
	if err != nil {
		return nil, err
	}
	result := []CatalogArticle{}
	for rows.Next() {
		var a CatalogArticle
		err = rows.Scan(&a.ID, &a.Title, &a.Kind, &a.Component, &a.SourceRevisionID, &a.CanonicalRevisionID, &a.ContentOrigin, &a.Availability, &a.ReviewStatus)
		if err != nil {
			rows.Close()
			return nil, err
		}
		a.CanonicalArticleID = stringPointer(a.ID)
		a.VehicleID = v
		a.Complete = a.CanonicalRevisionID != nil
		a.ContentStatus = "list_only"
		if a.Complete {
			a.ContentStatus = "content_complete"
		}
		result = append(result, a)
	}
	rows.Close()
	if rows.Err() != nil {
		return nil, rows.Err()
	}
	legacy, err := s.pool.Query(ctx, `SELECT ca.catalog_article_id::text,COALESCE(ca.title,''),COALESCE(ca.content_kind,''),COALESCE(ca.component,'') FROM catalog_articles ca JOIN source_snapshots ss USING(source_snapshot_id) WHERE (ca.vehicle_id::text=$1 AND ca.vehicle_configuration_id IS NULL OR ca.vehicle_configuration_id::text=$1 AND EXISTS(SELECT 1 FROM vehicle_configurations vc JOIN vehicle_identity_bases vb USING(vehicle_identity_base_id) WHERE vc.vehicle_configuration_id=ca.vehicle_configuration_id AND vc.reviewer_state<>'rejected' AND vb.reviewer_state<>'rejected')) AND ca.article_id NOT LIKE 'L:%' AND ss.takedown_status='active' AND NOT EXISTS(SELECT 1 FROM source_review_items review WHERE review.item_kind='quarantine' AND review.status<>'approved' AND review.source_snapshot_ids ? ca.source_snapshot_id::text) AND NOT EXISTS (SELECT 1 FROM canonical_article_aliases x JOIN canonical_articles owner ON owner.canonical_article_id=x.canonical_article_id WHERE x.catalog_article_id=ca.catalog_article_id AND owner.vehicle_id=ca.vehicle_id AND owner.vehicle_configuration_id IS NOT DISTINCT FROM ca.vehicle_configuration_id) ORDER BY ca.title COLLATE "C",ca.catalog_article_id`, v)
	if err != nil {
		return nil, err
	}
	defer legacy.Close()
	for legacy.Next() {
		var a CatalogArticle
		if err = legacy.Scan(&a.ID, &a.Title, &a.Kind, &a.Component); err != nil {
			return nil, err
		}
		a.VehicleID = v
		a.ContentStatus = "list_only"
		a.Availability = "unavailable"
		result = append(result, a)
	}
	return result, legacy.Err()
}
func (s *postgresCatalogStore) ArticleSource(ctx context.Context, p Principal, v, id string) (CatalogSourceContent, error) {
	return s.ArticleSourceRevision(ctx, p, v, id, "")
}

// Staged media refreshes keep a private source revision before publishing.
// The job marker survives failure and supersession. A published canonical
// record for the exact revision makes it eligible for historical review.
const catalogSourceRevisionPublicationSQL = `NOT EXISTS (
	SELECT 1 FROM source_fetch_jobs staged
	WHERE staged.job_kind='article'
	  AND staged.canonical_article_id=sr.canonical_article_id
	  AND staged.source_revision_id=sr.source_revision_id
	  AND staged.checkpoint ? 'staged_media_refresh'
	  AND NOT EXISTS (
		SELECT 1 FROM canonical_article_revisions published
		WHERE published.canonical_article_id=sr.canonical_article_id
		  AND published.source_revision_id=sr.source_revision_id
		  AND published.status='published'
	  )
)`

// Selected revisions, including historical revisions, cannot expose any of their
// retained resources while the body or a resource in the manifest is blocked.
const catalogSourceRevisionEligibleSQL = `NOT EXISTS (
	SELECT 1 FROM (
		SELECT source_snapshot_id,takedown_status FROM source_snapshots WHERE source_snapshot_id=sr.body_source_snapshot_id
		UNION ALL
		SELECT asset.source_snapshot_id,asset.takedown_status
		FROM jsonb_array_elements(sr.resource_manifest) entry JOIN source_snapshots asset
		ON asset.content_sha256=(entry->>'sha256')::bpchar AND asset.content_sha256::text=entry->>'sha256'
	) retained
	WHERE retained.takedown_status<>'active' OR EXISTS (
		SELECT 1 FROM source_review_items quarantine
		WHERE quarantine.item_kind='quarantine' AND quarantine.status<>'approved'
		AND quarantine.source_snapshot_ids ? retained.source_snapshot_id::text
	)
)`

func (s *postgresCatalogStore) paidCatalogSourceImages(ctx context.Context, configuration, article, revision string) ([]CatalogImage, error) {
	_, images, err := s.paidCatalogImageView(ctx, configuration, article, revision, false)
	return images, err
}

// Read current anchors and selected revision rights in one database snapshot.
// The image route only needs the image records, including those nested in steps.
func (s *postgresCatalogStore) paidCatalogImageView(ctx context.Context, configuration, article, revision string, includeArticleImages bool) (CatalogArticleView, []CatalogImage, error) {
	view := CatalogArticleView{Article: CatalogArticle{ID: article, CanonicalArticleID: &article}}
	var takedown string
	var rawArticleImages, rawSourceImages []byte
	err := s.pool.QueryRow(ctx, `SELECT
		CASE WHEN descriptor.takedown_status<>'active' THEN descriptor.takedown_status ELSE view_row.takedown_status END,
		view_row.source_revision_id::text,view_row.canonical_revision_id::text,
		CASE WHEN $4 THEN COALESCE(view_row.images,'[]'::jsonb) || COALESCE((
			SELECT jsonb_agg(image.value) FROM jsonb_array_elements(view_row.steps) step
			CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(step.value->'images')='array' THEN step.value->'images' ELSE '[]'::jsonb END) image
		),'[]'::jsonb) END,
		selected.source_images
		FROM canonical_articles a
		JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id
		CROSS JOIN LATERAL (
			SELECT takedown_status,source_revision_id,canonical_revision_id,images,steps FROM catalog_article_current
			WHERE canonical_article_id=a.canonical_article_id LIMIT 1
		) view_row
		LEFT JOIN LATERAL (
			SELECT sr.source_images FROM canonical_article_source_revisions sr
			JOIN source_snapshots snap ON snap.source_snapshot_id=sr.body_source_snapshot_id
			WHERE sr.canonical_article_id=a.canonical_article_id AND sr.source_revision_id=$3::uuid
			AND CASE WHEN sr.source_revision_id=view_row.source_revision_id AND view_row.canonical_revision_id IS NOT NULL
				THEN TRUE ELSE `+catalogSourceRevisionPublicationSQL+` END
			AND `+catalogSourceRevisionEligibleSQL+`
		) selected ON view_row.takedown_status='active' AND descriptor.takedown_status='active'
		WHERE a.vehicle_configuration_id=$1::uuid AND a.canonical_article_id=$2::uuid AND `+lifecycleEligibleSQL,
		configuration, article, revision, includeArticleImages).Scan(&takedown, &view.Article.SourceRevisionID, &view.Article.CanonicalRevisionID, &rawArticleImages, &rawSourceImages)
	if errors.Is(err, pgx.ErrNoRows) {
		return CatalogArticleView{}, nil, ErrCatalogNotFound
	}
	if err != nil {
		return CatalogArticleView{}, nil, err
	}
	if takedown != "active" {
		return CatalogArticleView{}, nil, ErrCatalogWithdrawn
	}
	if rawSourceImages == nil {
		return CatalogArticleView{}, nil, ErrCatalogNotFound
	}
	if includeArticleImages {
		if err = json.Unmarshal(rawArticleImages, &view.Article.Images); err != nil {
			return CatalogArticleView{}, nil, err
		}
	}
	var sourceImages []CatalogImage
	if err = json.Unmarshal(rawSourceImages, &sourceImages); err != nil {
		return CatalogArticleView{}, nil, err
	}
	return view, sourceImages, nil
}

func (s *postgresCatalogStore) ArticleSourceRevision(ctx context.Context, p Principal, v, id, revision string) (CatalogSourceContent, error) {
	view, err := s.ArticleView(ctx, p, v, id)
	if err != nil {
		return CatalogSourceContent{}, err
	}
	if view.Withdrawn {
		return CatalogSourceContent{}, ErrCatalogWithdrawn
	}
	if view.Article.CanonicalArticleID == nil {
		if revision != "" {
			return CatalogSourceContent{}, ErrCatalogNotFound
		}
		return s.legacyArticleSource(ctx, p, v, id)
	}
	if revision == "" && view.Article.SourceRevisionID != nil {
		revision = *view.Article.SourceRevisionID
	}
	if !commerceUUID(revision) {
		return CatalogSourceContent{}, ErrCatalogNotFound
	}
	var result CatalogSourceContent
	var doc, images []byte
	var sourceID string
	var body string
	var steps []byte
	// Requested revision must belong to this authorized identity. Any resource
	// takedown suppresses the immutable revision, including historical review.
	err = s.pool.QueryRow(ctx, `SELECT sr.source_revision_id::text,sr.body_source_snapshot_id::text,snap.content_sha256::text,
		`+catalogSourceObservationVersionSQL+`,sr.source_document,sr.source_images,sr.source_body,sr.source_steps
		FROM canonical_article_source_revisions sr
		JOIN source_snapshots snap ON snap.source_snapshot_id=sr.body_source_snapshot_id
		WHERE sr.canonical_article_id=$1::uuid AND sr.source_revision_id=$2::uuid
		AND `+catalogSourceRevisionPublicationSQL+`
		AND `+catalogSourceRevisionEligibleSQL, *view.Article.CanonicalArticleID, revision).Scan(&sourceID, &result.SnapshotID, &result.ContentSHA256, &result.Version, &doc, &images, &body, &steps)
	if errors.Is(err, pgx.ErrNoRows) {
		return CatalogSourceContent{}, ErrCatalogNotFound
	}
	if err != nil {
		return CatalogSourceContent{}, err
	}
	result.SourceRevisionID = &sourceID
	return decodeCatalogSourceProjection(result, doc, images, body, steps)
}

func decodeCatalogSourceProjection(result CatalogSourceContent, doc, images []byte, body string, steps []byte) (CatalogSourceContent, error) {
	var document CatalogDocument
	if err := json.Unmarshal(doc, &document); err != nil {
		return CatalogSourceContent{}, err
	}
	if err := json.Unmarshal(images, &result.Images); err != nil {
		return CatalogSourceContent{}, err
	}
	article := CatalogArticle{SourceRevisionID: result.SourceRevisionID, ContentOrigin: stringPointer("source"), Document: &document, Images: result.Images, Body: body}
	_ = json.Unmarshal(steps, &article.Steps)
	article = lifecycleArticle(article)
	result.Document = article.Document
	result.ViewRevision = article.ViewRevision
	return result, nil
}

// A stable public asset ID is never a storage path or provider URL. R2 normally
// supplies image_id as a digest; older source shapes are domain-separated here.
func publicCatalogAssetID(value string) string {
	if value == "" {
		return ""
	}
	if strings.Contains(value, "/") || strings.Contains(value, "?") || strings.Contains(value, ":") {
		sum := sha256.Sum256([]byte("catalog-asset-v1:" + value))
		return fmt.Sprintf("asset-%x", sum[:])
	}
	return value
}
func publicCatalogDocument(document *CatalogDocument) *CatalogDocument {
	if document == nil {
		return nil
	}
	raw, err := json.Marshal(document)
	if err != nil {
		return nil
	}
	var value any
	if json.Unmarshal(raw, &value) != nil {
		return nil
	}
	var project func(any) any
	project = func(value any) any {
		switch node := value.(type) {
		case []any:
			out := make([]any, len(node))
			for i, child := range node {
				out[i] = project(child)
			}
			return out
		case map[string]any:
			out := map[string]any{}
			for key, child := range node {
				switch key {
				case "schema_version", "normalization_version", "blocks", "block_id", "source_order", "type", "level", "number", "text", "label", "caption", "columns", "rows", "cells", "items", "images", "alt", "status", "unavailable_reason", "evidence_ids", "source_locator":
					out[key] = project(child)
				case "start":
					if _, ok := catalogJSONListNumber(child); ok && node["type"] == "ordered_list" {
						out[key] = child
					}
				case "rowspan", "colspan":
					if _, ok := catalogJSONTableSpan(key, child); ok {
						out[key] = child
					}
				case "asset_id", "image_id":
					if text, ok := child.(string); ok {
						out[key] = publicCatalogAssetID(text)
					}
				case "href":
					if text, ok := child.(string); ok {
						parsed, err := url.Parse(text)
						if err == nil && parsed.Scheme == "" && parsed.Host == "" && strings.HasPrefix(text, "#") {
							out[key] = text
						}
					}
				}
			}
			if id, ok := out["image_id"].(string); ok && id != "" {
				out["asset_id"] = id
			}
			return out
		default:
			return value
		}
	}
	raw, err = json.Marshal(project(value))
	if err != nil {
		return nil
	}
	var projected CatalogDocument
	if json.Unmarshal(raw, &projected) != nil {
		return nil
	}
	return &projected
}
