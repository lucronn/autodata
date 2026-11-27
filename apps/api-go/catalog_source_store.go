package main

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
)

type paidCatalogSourceViewStore interface {
	paidCatalogSourceView(context.Context, string, string, string, bool) (PaidArticleIdentity, CatalogArticleView, CatalogSourceContent, error)
}

const catalogSourceObservationVersionSQL = `COALESCE((
	SELECT observation.body_provider_revision FROM canonical_article_source_observations observation
	WHERE observation.source_revision_id=sr.source_revision_id AND observation.canonical_article_id=sr.canonical_article_id
	ORDER BY observation.request_generation DESC,observation.captured_at DESC,observation.source_observation_id DESC LIMIT 1
),snap.source_version,'')`

// Resolve the current anchors and the selected source under one statement snapshot.
// Only the selected revision supplies a full document or any associated media.
func (s *postgresCatalogStore) paidCatalogSourceView(ctx context.Context, configuration, article, revision string, allowStagedOriginal bool) (PaidArticleIdentity, CatalogArticleView, CatalogSourceContent, error) {
	var identity PaidArticleIdentity
	var view CatalogArticleView
	var source CatalogSourceContent
	if !commerceUUID(configuration) || !commerceUUID(article) {
		return identity, view, source, ErrCatalogNotFound
	}
	validSelector := revision == "" || commerceUUID(revision)
	var requested *string
	if validSelector && revision != "" {
		requested = &revision
	}
	var takedown string
	var doc, images, steps []byte
	var body string
	err := s.pool.QueryRow(ctx, `SELECT a.vehicle_configuration_id::text,a.canonical_article_id::text,a.vehicle_id::text,
		a.provider_slug,a.source_vehicle_ref,a.source_article_ref,a.current_source_revision_id::text,
		CASE WHEN descriptor.takedown_status<>'active' THEN descriptor.takedown_status ELSE view_row.takedown_status END,
		view_row.source_revision_id::text,view_row.canonical_revision_id::text,
		selected.source_revision_id::text,COALESCE(selected.body_source_snapshot_id::text,''),
		COALESCE(selected.content_sha256::text,''),COALESCE(selected.source_version,''),
		selected.source_document,selected.source_images,COALESCE(selected.source_body,''),selected.source_steps
		FROM canonical_articles a
		JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id
		CROSS JOIN LATERAL (
			SELECT takedown_status,source_revision_id,canonical_revision_id FROM catalog_article_current
			WHERE canonical_article_id=a.canonical_article_id LIMIT 1
		) view_row
		LEFT JOIN LATERAL (`+catalogStagedOriginalSQL+` AND $5 AND candidate.source_revision_id=$3::uuid) original ON true
		LEFT JOIN LATERAL (
			SELECT sr.source_revision_id,sr.body_source_snapshot_id,snap.content_sha256,
				COALESCE(original.body_provider_revision,`+catalogSourceObservationVersionSQL+`) AS source_version,
				sr.source_document,`+catalogSourceImagesWithDimensionsSQL+` AS source_images,sr.source_body,sr.source_steps
			FROM canonical_article_source_revisions sr
			JOIN source_snapshots snap ON snap.source_snapshot_id=sr.body_source_snapshot_id
			WHERE $4 AND sr.canonical_article_id=a.canonical_article_id
			AND sr.source_revision_id=COALESCE($3::uuid,view_row.source_revision_id)
			AND CASE WHEN sr.source_revision_id=view_row.source_revision_id AND view_row.canonical_revision_id IS NOT NULL
				THEN TRUE ELSE original.source_revision_id=sr.source_revision_id OR `+catalogSourceRevisionPublicationSQL+` END
			AND `+catalogSourceRevisionEligibleSQL+`
		) selected ON view_row.takedown_status='active' AND descriptor.takedown_status='active'
		WHERE a.vehicle_configuration_id=$1::uuid AND a.canonical_article_id=$2::uuid AND `+lifecycleEligibleSQL,
		configuration, article, requested, validSelector, allowStagedOriginal).Scan(
		&identity.ConfigurationID, &identity.CanonicalArticleID, &identity.VehicleID, &identity.ProviderSlug,
		&identity.SourceVehicleRef, &identity.SourceArticleRef, &identity.CurrentSourceRevisionID, &takedown,
		&view.Article.SourceRevisionID, &view.Article.CanonicalRevisionID,
		&source.SourceRevisionID, &source.SnapshotID, &source.ContentSHA256, &source.Version, &doc, &images, &body, &steps,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		err = ErrCatalogNotFound
	}
	if err != nil {
		return PaidArticleIdentity{}, CatalogArticleView{}, CatalogSourceContent{}, err
	}
	if takedown != "active" {
		return PaidArticleIdentity{}, CatalogArticleView{}, CatalogSourceContent{}, ErrCatalogWithdrawn
	}
	if revision == "" && view.Article.SourceRevisionID == nil {
		return PaidArticleIdentity{}, CatalogArticleView{}, CatalogSourceContent{}, ErrVehicleGrantUnavailable
	}
	if source.SourceRevisionID == nil {
		return PaidArticleIdentity{}, CatalogArticleView{}, CatalogSourceContent{}, ErrCatalogNotFound
	}
	view.Article.ID = identity.CanonicalArticleID
	view.Article.CanonicalArticleID = &identity.CanonicalArticleID
	var links catalogArticleLinkProjection
	links.resolve = s.authoredArticleLinkResolver(ctx, identity, !allowStagedOriginal)
	if links.resolve != nil && view.Article.SourceRevisionID != nil && *view.Article.SourceRevisionID == *source.SourceRevisionID {
		links.retained, links.inline = s.retainedArticleLinkBindings(ctx, article, source.SourceRevisionID,
			view.Article.CanonicalRevisionID, source.ContentSHA256)
	}
	source, err = decodeCatalogSourceProjection(source, doc, images, body, steps, links)
	return identity, view, source, err
}
