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
func (s *Server) rewritePaidCatalogImages(images []CatalogImage, source CatalogSourceContent, ref paidCatalogImageReference, now time.Time) {
	for i := range images {
		image := &images[i]
		image.URL = ""
		image.ID = publicCatalogAssetID(image.ID)
		image.ImageID = publicCatalogAssetID(image.ImageID)
		image.AssetID = publicCatalogAssetID(image.AssetID)
		asset := paidCatalogImageAssetID(*image)
		if image.Status == "unavailable" || !paidCatalogHasAsset(source.Images, asset, image.StorageKey) {
			continue
		}
		ref.AssetID, ref.ObjectKey = asset, image.StorageKey
		token, err := sealPaidCatalogImageReference(ref, s.catalogImageKey, now)
		if err != nil {
			continue
		}
		image.URL = "/v1/catalog/images/" + token
	}
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
	if view.Article.SourceRevisionID == nil || identity.CurrentSourceRevisionID == nil {
		return nil
	}
	selected := *view.Article.SourceRevisionID
	if !commerceUUID(selected) || !commerceUUID(*identity.CurrentSourceRevisionID) {
		return nil
	}
	source, err := s.catalog.ArticleSourceRevision(ctx, p, configuration.ID, identity.CanonicalArticleID, selected)
	if err != nil {
		return err
	}
	if source.SourceRevisionID == nil || *source.SourceRevisionID != selected {
		return ErrCatalogNotFound
	}
	now := time.Now()
	ref := paidCatalogProjectionReference(p, configuration, identity, *view, selected, "article", now)
	s.rewritePaidCatalogImages(view.Article.Images, source, ref, now)
	for i := range view.Article.Steps {
		if view.Article.Steps[i].Images != nil {
			s.rewritePaidCatalogImages(*view.Article.Steps[i].Images, source, ref, now)
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
	view, err := s.catalog.ArticleView(ctx, p, configuration.ID, identity.CanonicalArticleID)
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	if view.Withdrawn {
		s.writePaidCatalogError(w, r, ErrCatalogWithdrawn)
		return
	}
	if !paidCatalogViewMatches(view, identity) || !samePaidCatalogID(view.Article.CanonicalRevisionID, ref.AnchorCanonicalRevisionID) || (ref.Projection == "article" && (view.Article.SourceRevisionID == nil || *view.Article.SourceRevisionID != ref.SelectedSourceRevisionID)) {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	source, err := s.catalog.ArticleSourceRevision(ctx, p, configuration.ID, identity.CanonicalArticleID, ref.SelectedSourceRevisionID)
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	if source.SourceRevisionID == nil || *source.SourceRevisionID != ref.SelectedSourceRevisionID || !paidCatalogHasAsset(source.Images, ref.AssetID, ref.ObjectKey) || (ref.Projection == "article" && !paidCatalogArticleHasAsset(view.Article, ref.AssetID, ref.ObjectKey)) {
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
