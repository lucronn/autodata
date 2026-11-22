package main

import (
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/minio/minio-go/v7"
)

func paidCatalogSourceHash(value string) string {
	return fmt.Sprintf("%x", sha256.Sum256([]byte(value)))
}
func samePaidCatalogID(a, b *string) bool {
	return a == nil && b == nil || a != nil && b != nil && *a == *b
}

func paidCatalogImageAssetID(image CatalogImage) string {
	for _, id := range []string{image.ImageID, image.AssetID, image.ID} {
		if id != "" {
			return publicCatalogAssetID(id)
		}
	}
	return ""
}
func paidCatalogHasAsset(images []CatalogImage, asset, key string) bool {
	for _, image := range images {
		if image.Status != "unavailable" && paidCatalogImageAssetID(image) == asset && image.StorageKey == key {
			return true
		}
	}
	return false
}
func paidCatalogArticleHasAsset(article CatalogArticle, asset, key string) bool {
	if paidCatalogHasAsset(article.Images, asset, key) {
		return true
	}
	for _, step := range article.Steps {
		if step.Images != nil && paidCatalogHasAsset(*step.Images, asset, key) {
			return true
		}
	}
	return false
}
func validPaidCatalogIdentity(identity PaidArticleIdentity, configuration CatalogConfiguration, articleID string) bool {
	return identity.ConfigurationID == configuration.ID && identity.CanonicalArticleID == articleID && commerceUUID(identity.CanonicalArticleID) && identity.VehicleID == configuration.VehicleID && commerceUUID(identity.VehicleID) && (identity.ProviderSlug == "bankone" || identity.ProviderSlug == "banktwo") && identity.SourceVehicleRef != "" && identity.SourceArticleRef != ""
}
func paidCatalogViewMatches(view CatalogArticleView, identity PaidArticleIdentity) bool {
	return view.Article.CanonicalArticleID != nil && *view.Article.CanonicalArticleID == identity.CanonicalArticleID && view.Article.ID == identity.CanonicalArticleID
}
func (s *Server) paidMediaIdentity(ctx context.Context, configuration CatalogConfiguration, articleID string) (PaidArticleIdentity, error) {
	store, ok := s.catalog.(paidArticleIdentityStore)
	if !ok {
		return PaidArticleIdentity{}, ErrVehicleGrantUnavailable
	}
	identity, err := store.PaidArticleIdentity(ctx, configuration.ID, articleID)
	if err != nil {
		return PaidArticleIdentity{}, err
	}
	if !validPaidCatalogIdentity(identity, configuration, articleID) {
		return PaidArticleIdentity{}, ErrCatalogNotFound
	}
	return identity, nil
}

// Clone all image-bearing slices before inserting short-lived URLs. Neither
// persisted source JSON nor the stable view-hash inputs are mutated.
func clonePaidCatalogArticleImages(article *CatalogArticle) {
	article.Images = append([]CatalogImage{}, article.Images...)
	article.Steps = append([]CatalogStep(nil), article.Steps...)
	for i := range article.Images {
		article.Images[i].URL = ""
	}
	for i := range article.Steps {
		if article.Steps[i].Images != nil {
			images := append([]CatalogImage{}, (*article.Steps[i].Images)...)
			for j := range images {
				images[j].URL = ""
			}
			article.Steps[i].Images = &images
		}
	}
}
func paidCatalogHasImages(article CatalogArticle) bool {
	if len(article.Images) > 0 {
		return true
	}
	for _, step := range article.Steps {
		if step.Images != nil && len(*step.Images) > 0 {
			return true
		}
	}
	return false
}
func paidCatalogProjectionReference(p Principal, configuration CatalogConfiguration, identity PaidArticleIdentity, view CatalogArticleView, sourceID, projection string, now time.Time) paidCatalogImageReference {
	ref := paidCatalogImageReference{Version: 2, IssuedAt: now.Unix(), ExpiresAt: now.Unix() + 300, CustomerAccountID: p.CustomerAccountID, ConfigurationID: configuration.ID, Region: configuration.Region, CanonicalArticleID: identity.CanonicalArticleID, ProviderSlug: identity.ProviderSlug, SourceVehicleRefSHA256: paidCatalogSourceHash(identity.SourceVehicleRef), SourceArticleRefSHA256: paidCatalogSourceHash(identity.SourceArticleRef), SelectedSourceRevisionID: sourceID, AnchorCanonicalRevisionID: view.Article.CanonicalRevisionID, Projection: projection}
	if identity.CurrentSourceRevisionID != nil {
		ref.AnchorSourceRevisionID = *identity.CurrentSourceRevisionID
	}
	return ref
}

type paidCatalogAssetKey struct {
	assetID, objectKey string
}

// Build the membership index once for this response. Its signed URLs can be
// reused by identical placements because the account and revision anchors agree.
func paidCatalogAssetURLs(source []CatalogImage) map[paidCatalogAssetKey]string {
	urls := make(map[paidCatalogAssetKey]string, len(source))
	for _, image := range source {
		if image.Status != "unavailable" {
			urls[paidCatalogAssetKey{paidCatalogImageAssetID(image), image.StorageKey}] = ""
		}
	}
	return urls
}

func (s *Server) rewritePaidCatalogImages(images []CatalogImage, urls map[paidCatalogAssetKey]string, ref paidCatalogImageReference, now time.Time) {
	for i := range images {
		image := &images[i]
		image.URL = ""
		image.ID = publicCatalogAssetID(image.ID)
		image.ImageID = publicCatalogAssetID(image.ImageID)
		image.AssetID = publicCatalogAssetID(image.AssetID)
		key := paidCatalogAssetKey{paidCatalogImageAssetID(*image), image.StorageKey}
		url, permitted := urls[key]
		if image.Status == "unavailable" || !permitted {
			continue
		}
		if url == "" {
			ref.AssetID, ref.ObjectKey = key.assetID, key.objectKey
			token, err := sealPaidCatalogImageReference(ref, s.catalogImageKey, now)
			if err != nil {
				continue
			}
			url = "/v1/catalog/images/" + token
			urls[key] = url
		}
		image.URL = url
	}
}

func (s *Server) paidCatalogSourceImages(ctx context.Context, p Principal, configuration, article, revision string) ([]CatalogImage, error) {
	if store, ok := s.catalog.(interface {
		paidCatalogSourceImages(context.Context, string, string, string) ([]CatalogImage, error)
	}); ok {
		return store.paidCatalogSourceImages(ctx, configuration, article, revision)
	}
	source, err := s.catalog.ArticleSourceRevision(ctx, p, configuration, article, revision)
	if err != nil {
		return nil, err
	}
	if source.SourceRevisionID == nil || *source.SourceRevisionID != revision {
		return nil, ErrCatalogNotFound
	}
	return source.Images, nil
}

type paidCatalogImageViewStore interface {
	paidCatalogImageView(context.Context, string, string, string, bool) (CatalogArticleView, []CatalogImage, error)
}

// The article can acquire a source after the request authorized its identity.
// Refresh once, and mint only when the response and current image view agree.
func (s *Server) refreshPaidCatalogArticleImageContext(ctx context.Context, p Principal, configuration CatalogConfiguration, previous PaidArticleIdentity, view CatalogArticleView) (PaidArticleIdentity, []CatalogImage, error) {
	if err := ctx.Err(); err != nil {
		return PaidArticleIdentity{}, nil, err
	}
	currentConfiguration, err := s.resolveCatalogScope(ctx, p, configuration.ID, configuration.Region, false)
	if err != nil {
		return PaidArticleIdentity{}, nil, err
	}
	current, err := s.paidMediaIdentity(ctx, currentConfiguration, previous.CanonicalArticleID)
	if err != nil {
		return PaidArticleIdentity{}, nil, err
	}
	if current.VehicleID != previous.VehicleID || current.ProviderSlug != previous.ProviderSlug ||
		current.SourceVehicleRef != previous.SourceVehicleRef || current.SourceArticleRef != previous.SourceArticleRef ||
		!samePaidCatalogID(current.CurrentSourceRevisionID, view.Article.SourceRevisionID) {
		return PaidArticleIdentity{}, nil, ErrCatalogNotFound
	}
	store, ok := s.catalog.(paidCatalogImageViewStore)
	if !ok {
		return PaidArticleIdentity{}, nil, ErrVehicleGrantUnavailable
	}
	projection, images, err := store.paidCatalogImageView(ctx, currentConfiguration.ID, current.CanonicalArticleID, *view.Article.SourceRevisionID, false)
	if err != nil {
		return PaidArticleIdentity{}, nil, err
	}
	if projection.Withdrawn {
		return PaidArticleIdentity{}, nil, ErrCatalogWithdrawn
	}
	if !paidCatalogViewMatches(projection, current) || !samePaidCatalogID(projection.Article.SourceRevisionID, view.Article.SourceRevisionID) ||
		!samePaidCatalogID(projection.Article.CanonicalRevisionID, view.Article.CanonicalRevisionID) {
		return PaidArticleIdentity{}, nil, ErrCatalogNotFound
	}
	if err := ctx.Err(); err != nil {
		return PaidArticleIdentity{}, nil, err
	}
	if err := s.checkPaidCatalogGrant(ctx, p, currentConfiguration); err != nil {
		return PaidArticleIdentity{}, nil, err
	}
	return current, images, ctx.Err()
}

func (s *Server) rewritePaidCatalogArticleImages(ctx context.Context, p Principal, configuration CatalogConfiguration, identity PaidArticleIdentity, view *CatalogArticleView) error {
	if view == nil {
		return ErrCatalogNotFound
	}
	clonePaidCatalogArticleImages(&view.Article)
	if view.Withdrawn {
		return ErrCatalogWithdrawn
	}
	if !paidCatalogHasImages(view.Article) {
		return nil
	}
	if !validPaidCatalogIdentity(identity, configuration, identity.CanonicalArticleID) || !paidCatalogViewMatches(*view, identity) {
		return ErrCatalogNotFound
	}
	// A cold lifecycle projection may have no source yet. It cannot mint URLs.
	if view.Article.SourceRevisionID == nil || !commerceUUID(*view.Article.SourceRevisionID) {
		return nil
	}
	selected := *view.Article.SourceRevisionID
	var sourceImages []CatalogImage
	var err error
	if samePaidCatalogID(identity.CurrentSourceRevisionID, view.Article.SourceRevisionID) {
		sourceImages, err = s.paidCatalogSourceImages(ctx, p, configuration.ID, identity.CanonicalArticleID, selected)
	} else {
		identity, sourceImages, err = s.refreshPaidCatalogArticleImageContext(ctx, p, configuration, identity, *view)
	}
	if err != nil {
		return err
	}
	urls := paidCatalogAssetURLs(sourceImages)
	now := time.Now()
	ref := paidCatalogProjectionReference(p, configuration, identity, *view, selected, "article", now)
	s.rewritePaidCatalogImages(view.Article.Images, urls, ref, now)
	for i := range view.Article.Steps {
		if view.Article.Steps[i].Images != nil {
			s.rewritePaidCatalogImages(*view.Article.Steps[i].Images, urls, ref, now)
		}
	}
	return nil
}

func (s *Server) servePaidCatalogImage(w http.ResponseWriter, r *http.Request, p Principal) {
	w.Header().Set("Cache-Control", "private, no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	r = r.WithContext(ctx)
	if len(s.catalogImageKey) != 32 {
		s.writePaidCatalogError(w, r, ErrVehicleGrantUnavailable)
		return
	}
	ref, err := openPaidCatalogImageReference(r.PathValue("token"), s.catalogImageKey, time.Now())
	if err != nil || ref.CustomerAccountID != p.CustomerAccountID {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	configuration, err := s.resolvePaidCatalogScope(ctx, p, ref.ConfigurationID, ref.Region)
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	identity, err := s.paidMediaIdentity(ctx, configuration, ref.CanonicalArticleID)
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	if identity.ProviderSlug != ref.ProviderSlug || paidCatalogSourceHash(identity.SourceVehicleRef) != ref.SourceVehicleRefSHA256 || paidCatalogSourceHash(identity.SourceArticleRef) != ref.SourceArticleRefSHA256 || identity.CurrentSourceRevisionID == nil || *identity.CurrentSourceRevisionID != ref.AnchorSourceRevisionID {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	store, narrow := s.catalog.(paidCatalogImageViewStore)
	articleProjection := ref.Projection == "article"
	var view CatalogArticleView
	var sourceImages []CatalogImage
	if narrow {
		view, sourceImages, err = store.paidCatalogImageView(ctx, configuration.ID, identity.CanonicalArticleID, ref.SelectedSourceRevisionID, articleProjection)
	} else {
		view, err = s.catalog.ArticleView(ctx, p, configuration.ID, identity.CanonicalArticleID)
	}
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	if view.Withdrawn {
		s.writePaidCatalogError(w, r, ErrCatalogWithdrawn)
		return
	}
	if !paidCatalogViewMatches(view, identity) || !samePaidCatalogID(view.Article.CanonicalRevisionID, ref.AnchorCanonicalRevisionID) ||
		view.Article.SourceRevisionID == nil || *view.Article.SourceRevisionID != ref.AnchorSourceRevisionID ||
		(articleProjection && *view.Article.SourceRevisionID != ref.SelectedSourceRevisionID) {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	if !narrow {
		sourceImages, err = s.paidCatalogSourceImages(ctx, p, configuration.ID, identity.CanonicalArticleID, ref.SelectedSourceRevisionID)
		if err != nil {
			s.writePaidCatalogError(w, r, err)
			return
		}
	}
	if !paidCatalogHasAsset(sourceImages, ref.AssetID, ref.ObjectKey) || (articleProjection && !paidCatalogArticleHasAsset(view.Article, ref.AssetID, ref.ObjectKey)) {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	if s.catalogImageReader == nil {
		s.writePaidCatalogError(w, r, ErrVehicleGrantUnavailable)
		return
	}
	if err = s.checkPaidCatalogGrant(ctx, p, configuration); err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	readCtx, readCancel := context.WithTimeout(ctx, 4*time.Second)
	defer readCancel()
	body, contentType, err := s.catalogImageReader.ReadImage(readCtx, ref.ObjectKey)
	if err != nil {
		if errors.Is(err, ErrCatalogNotFound) || os.IsNotExist(err) || minio.ToErrorResponse(err).Code == "NoSuchKey" {
			s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		} else {
			s.writePaidCatalogError(w, r, ErrVehicleGrantUnavailable)
		}
		return
	}
	contentType = strings.ToLower(strings.TrimSpace(strings.Split(contentType, ";")[0]))
	if len(body) == 0 || len(body) > catalogImageMaxBytes || !validCatalogImageMedia(body, contentType) {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Security-Policy", "sandbox; default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
	w.Header().Set("Cross-Origin-Resource-Policy", "same-origin")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(body)
}
