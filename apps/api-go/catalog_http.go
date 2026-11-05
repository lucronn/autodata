package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"strconv"
	"strings"
	"sync"
)

// Catalog selector reads must remain responsive while a missing scope is
// hydrated from the external providers. The worker owns durable idempotency;
// this process-level gate prevents repeated browser polling from opening
// duplicate long-running requests before the worker has persisted its result.
var catalogHydrationInFlight sync.Map

type CatalogYearsResponse struct {
	Version string        `json:"version"`
	Items   []CatalogYear `json:"items"`
}
type CatalogHydrationResponse struct {
	Complete  bool `json:"complete"`
	Hydrating bool `json:"hydrating"`
}
type CatalogMakesResponse struct {
	Version string        `json:"version"`
	Items   []CatalogMake `json:"items"`
	CatalogHydrationResponse
}
type CatalogModelsResponse struct {
	Version string         `json:"version"`
	Items   []CatalogModel `json:"items"`
	CatalogHydrationResponse
}
type CatalogConfigurationsResponse struct {
	Version string                 `json:"version"`
	Items   []CatalogConfiguration `json:"items"`
	CatalogHydrationResponse
}
type CatalogArticlesResponse struct {
	Version   string                  `json:"version"`
	Items     []CatalogArticle        `json:"items"`
	Complete  bool                    `json:"complete"`
	Hydrating bool                    `json:"hydrating"`
	Progress  *CatalogArticleProgress `json:"progress,omitempty"`
}
type CatalogArticleResponse struct {
	Version string         `json:"version"`
	Article CatalogArticle `json:"article"`
}

func (s *Server) listCatalogYears(response http.ResponseWriter, request *http.Request, principal Principal) {
	items, err := s.catalog.Years(request.Context(), principal)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	if len(items) == 0 && s.ingestionClient != nil {
		if err := s.ensureCatalogHydrated(request, map[string]any{"scope": "years"}); err != nil {
			s.writeCatalogError(response, request, err)
			return
		}
		items, err = s.catalog.Years(request.Context(), principal)
		if err != nil {
			s.writeCatalogError(response, request, err)
			return
		}
	}
	writeJSON(response, http.StatusOK, CatalogYearsResponse{Version: "v1", Items: items})
}

func (s *Server) listCatalogMakes(response http.ResponseWriter, request *http.Request, principal Principal) {
	year, ok := catalogYearPath(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "year is invalid", false)
		return
	}
	items, err := s.catalog.Makes(request.Context(), principal, year, request.URL.Query().Get("region"))
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	complete, err := s.catalog.CatalogScopeComplete(request.Context(), principal, "makes", year, "", "", request.URL.Query().Get("region"))
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	hydrating := (!complete || len(items) == 0) && s.ingestionClient != nil
	if hydrating {
		s.scheduleCatalogHydration(request, map[string]any{
			"scope": "makes", "year": year, "region": catalogRegion(request),
		})
	}
	writeJSON(response, http.StatusOK, CatalogMakesResponse{
		Version: "v1", Items: items,
		CatalogHydrationResponse: CatalogHydrationResponse{Complete: complete && len(items) > 0, Hydrating: hydrating},
	})
}

func (s *Server) listCatalogModels(response http.ResponseWriter, request *http.Request, principal Principal) {
	year, ok := catalogYearPath(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "year is invalid", false)
		return
	}
	makeName := catalogPathValue(request.PathValue("make"))
	items, err := s.catalog.Models(request.Context(), principal, year, makeName, request.URL.Query().Get("region"))
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	complete, err := s.catalog.CatalogScopeComplete(request.Context(), principal, "models", year, makeName, "", request.URL.Query().Get("region"))
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	hydrating := (!complete || len(items) == 0) && s.ingestionClient != nil
	if hydrating {
		s.scheduleCatalogHydration(request, map[string]any{
			"scope": "models", "year": year, "make": makeName, "region": catalogRegion(request),
		})
	}
	writeJSON(response, http.StatusOK, CatalogModelsResponse{
		Version: "v1", Items: items,
		CatalogHydrationResponse: CatalogHydrationResponse{Complete: complete && len(items) > 0, Hydrating: hydrating},
	})
}

func (s *Server) listCatalogConfigurations(response http.ResponseWriter, request *http.Request, principal Principal) {
	year, ok := catalogYearPath(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "year is invalid", false)
		return
	}
	makeName := catalogPathValue(request.PathValue("make"))
	modelName := catalogPathValue(request.PathValue("model"))
	items, err := s.catalog.Configurations(request.Context(), principal, year, makeName, modelName, request.URL.Query().Get("region"))
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	complete, err := s.catalog.CatalogScopeComplete(request.Context(), principal, "configurations", year, makeName, modelName, request.URL.Query().Get("region"))
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	usable := !catalogConfigurationsIncomplete(items)
	// Usable complete rows must stay selectable even when the durable scope
	// marker is still missing. Keep background ensure running until the marker
	// lands, but do not hide the list behind hydrating:true.
	hydrating := !usable && s.ingestionClient != nil
	if (!complete || !usable) && s.ingestionClient != nil {
		s.scheduleCatalogHydration(request, map[string]any{
			"scope": "configurations", "year": year, "make": makeName,
			"model": modelName, "region": catalogRegion(request),
		})
	}
	writeJSON(response, http.StatusOK, CatalogConfigurationsResponse{
		Version: "v1", Items: items,
		CatalogHydrationResponse: CatalogHydrationResponse{Complete: complete && usable, Hydrating: hydrating},
	})
}

func (s *Server) listCatalogArticles(response http.ResponseWriter, request *http.Request, principal Principal) {
	vehicleID := request.PathValue("vehicle_id")
	var items []CatalogArticle
	var err error
	if s.paidCatalogEnabled() {
		repository, ok := s.catalog.(paidArticleDescriptorStore)
		if !ok {
			s.writePaidCatalogError(response, request, ErrVehicleGrantUnavailable)
			return
		}
		items, err = repository.PaidArticleDescriptors(request.Context(), principal, vehicleID)
	} else {
		items, err = s.catalog.Articles(request.Context(), principal, vehicleID)
	}
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	progress, err := s.catalog.CatalogArticleProgress(request.Context(), principal, vehicleID)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	hydrating := progress != nil && !progress.Complete &&
		(progress.Status == "pending" || progress.Status == "running" ||
			(progress.Status == "failed" && progress.Retryable))
	if !s.paidCatalogEnabled() && (progress == nil || !progress.Complete) && s.ingestionClient != nil {
		configuration, configurationErr := s.catalog.ConfigurationByVehicle(request.Context(), principal, vehicleID)
		if configurationErr != nil && !errors.Is(configurationErr, ErrCatalogNotFound) {
			s.writeCatalogError(response, request, configurationErr)
			return
		}
		if configurationErr == nil {
			s.scheduleCatalogHydration(request, map[string]any{
				"scope": "articles", "vehicle_id": vehicleID,
				"year": configuration.Year, "make": configuration.Make, "model": configuration.Model,
				"region": configuration.Region, "trim": configuration.Trim, "engine": configuration.Engine,
			})
		}
	}
	if s.paidCatalogEnabled() {
		descriptors := make([]CatalogArticle, 0, len(items))
		for _, item := range items {
			if item.CanonicalArticleID == nil || item.ID != *item.CanonicalArticleID {
				continue
			}
			item.Document, item.Body, item.Steps, item.Images = nil, "", nil, []CatalogImage{}
			item.SourceReview = nil
			descriptors = append(descriptors, item)
		}
		items = descriptors
	} else {
		for index := range items {
			rewriteCatalogImageURLs(&items[index], s.catalogImageKey)
		}
	}
	writeJSON(response, http.StatusOK, CatalogArticlesResponse{
		Version: "v1", Items: items, Complete: progress != nil && progress.Complete,
		Hydrating: hydrating, Progress: progress,
	})
}

func (s *Server) getCatalogArticle(response http.ResponseWriter, request *http.Request, principal Principal) {
	response.Header().Set("Cache-Control", "private, no-store")
	vehicleID, articleID := request.PathValue("vehicle_id"), request.PathValue("article_id")
	view, err := s.catalog.ArticleView(request.Context(), principal, vehicleID, articleID)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	if view.Withdrawn {
		s.writeCatalogLifecycleError(response, request, http.StatusGone, "CATALOG_WITHDRAWN", false, view.Article)
		return
	}
	if view.CanSchedule && !s.paidCatalogEnabled() {
		payload := map[string]any{"scope": "article", "vehicle_id": vehicleID, "canonical_article_id": *view.Article.CanonicalArticleID}
		if view.Article.canonicalVehicleID != "" {
			payload["vehicle_id"] = view.Article.canonicalVehicleID
		}
		if view.Article.canonicalConfigurationID != nil {
			payload["vehicle_configuration_id"] = *view.Article.canonicalConfigurationID
		}
		_, scheduleErr := s.ensureCatalogArticleScheduled(request, payload)
		// Only a final durable snapshot establishes accepted work or publication.
		reread, readErr := s.catalog.ArticleView(request.Context(), principal, vehicleID, articleID)
		if readErr != nil {
			s.writeCatalogError(response, request, readErr)
			return
		}
		view = reread
		if view.Withdrawn {
			s.writeCatalogLifecycleError(response, request, 410, "CATALOG_WITHDRAWN", false, view.Article)
			return
		}
		if scheduleErr != nil && view.Article.Processing == nil && view.Article.Document == nil {
			s.writeCatalogLifecycleError(response, request, 503, "CATALOG_SCHEDULING_UNAVAILABLE", true, view.Article)
			return
		}
	}
	s.respondCatalogArticleView(response, request, principal, view)
}

func (s *Server) respondCatalogArticleView(response http.ResponseWriter, request *http.Request, principal Principal, view CatalogArticleView) {
	if view.Withdrawn {
		s.writePaidCatalogError(response, request, ErrCatalogWithdrawn)
		return
	}
	vehicleID := request.PathValue("vehicle_id")
	article := view.Article
	if article.Processing != nil && article.Processing.RetryAfterSeconds != nil {
		response.Header().Set("Retry-After", strconv.Itoa(*article.Processing.RetryAfterSeconds))
	}
	status := http.StatusOK
	if article.Availability != "available" {
		if article.Processing != nil && (article.Processing.State == "needs_review" || article.Processing.State == "failed" && !article.Processing.Retryable) {
			code := "CATALOG_PROCESSING_FAILED"
			if article.Processing.State == "needs_review" {
				code = "CATALOG_REVIEW_REQUIRED"
			}
			s.writeCatalogLifecycleError(response, request, 409, code, false, article)
			return
		}
		if article.Processing == nil {
			s.writeCatalogLifecycleError(response, request, 503, "CATALOG_SOURCE_UNAVAILABLE", true, article)
			return
		}
		status = http.StatusAccepted
	}
	if s.paidCatalogEnabled() {
		scope, ok := request.Context().Value(paidCatalogContextKey{}).(paidCatalogContext)
		if !ok || scope.identity == nil || article.CanonicalArticleID == nil || *article.CanonicalArticleID != scope.identity.CanonicalArticleID {
			s.writePaidCatalogError(response, request, ErrCatalogNotFound)
			return
		}
		view.Article = article
		if err := s.rewritePaidCatalogArticleImages(request.Context(), principal, scope.configuration, *scope.identity, &view); err != nil {
			s.writePaidCatalogError(response, request, err)
			return
		}
		article = view.Article
	} else {
		rewriteCatalogImageURLs(&article, s.catalogImageKey)
	}
	article.SourceReview = sourceReviewForArticle(article, vehicleID, article.ID)
	writeJSON(response, status, CatalogArticleResponse{Version: "v1", Article: article})
}

const catalogImageMaxBytes = 12 << 20

// rewriteCatalogImageURLs exposes only references to already-localized
// objects. A source URL without a stored object key is not displayable.
func rewriteCatalogImageURLs(article *CatalogArticle, key []byte) {
	if article.Images == nil {
		article.Images = []CatalogImage{}
	}
	rewriteCatalogImages(article.Images, key)
	for index := range article.Steps {
		if article.Steps[index].Images != nil {
			rewriteCatalogImages(*article.Steps[index].Images, key)
		}
	}
}

func rewriteCatalogImages(images []CatalogImage, key []byte) {
	for index := range images {
		image := &images[index]
		if image.Status == "unavailable" || !localCatalogImageKeyPattern.MatchString(image.StorageKey) || len(key) != 32 {
			image.URL = ""
			continue
		}
		token, err := sealCatalogImageReference(image.StorageKey, key)
		if err != nil {
			image.URL = ""
			continue
		}
		image.URL = "/v1/catalog/images/" + token
	}
}

// serveCatalogImage reads only from the configured local object store. It
// never fetches an upstream provider URL.
func serveCatalogImage(response http.ResponseWriter, request *http.Request, key []byte, reader catalogImageObjectReader) {
	if len(key) != 32 {
		http.Error(response, "catalog image references are unavailable", http.StatusServiceUnavailable)
		return
	}
	objectKey, err := openCatalogImageReference(request.PathValue("token"), key)
	if err != nil || !localCatalogImageKeyPattern.MatchString(objectKey) {
		http.Error(response, "catalog image not found", http.StatusNotFound)
		return
	}
	if reader == nil {
		http.Error(response, "catalog image storage is unavailable", http.StatusServiceUnavailable)
		return
	}
	body, contentType, err := reader.ReadImage(request.Context(), objectKey)
	contentType = strings.ToLower(strings.TrimSpace(strings.Split(contentType, ";")[0]))
	if err != nil || len(body) == 0 || len(body) > catalogImageMaxBytes || !validCatalogImageMedia(body, contentType) {
		http.Error(response, "catalog image not found", http.StatusNotFound)
		return
	}
	response.Header().Set("Content-Type", contentType)
	response.Header().Set("Cache-Control", "private, no-store")
	response.Header().Set("Content-Security-Policy", "sandbox; default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
	response.Header().Set("Cross-Origin-Resource-Policy", "same-origin")
	response.Header().Set("Referrer-Policy", "no-referrer")
	response.Header().Set("X-Content-Type-Options", "nosniff")
	response.WriteHeader(http.StatusOK)
	_, _ = response.Write(body)
}

func catalogConfigurationsIncomplete(items []CatalogConfiguration) bool {
	if len(items) == 0 {
		return true
	}
	for _, item := range items {
		if !item.Complete {
			return true
		}
	}
	return false
}

func catalogArticlesIncomplete(items []CatalogArticle) bool {
	// Article discovery and article-body hydration are separate stages. A
	// list-only row is enough to publish the vehicle's article catalog; the
	// selected detail endpoint hydrates the individual article on demand.
	return len(items) == 0
}

func catalogYearPath(request *http.Request) (int, bool) {
	year, err := strconv.Atoi(request.PathValue("year"))
	return year, err == nil && year >= 1886 && year <= 2100
}

func catalogPathValue(value string) string {
	return strings.ReplaceAll(strings.TrimSpace(value), "-", " ")
}

func catalogRegion(request *http.Request) string {
	if value := strings.TrimSpace(request.URL.Query().Get("region")); value != "" {
		return value
	}
	return "US"
}

func (s *Server) scheduleCatalogHydration(request *http.Request, payload map[string]any) {
	if s.ingestionClient == nil {
		return
	}
	key, _, err := catalogHydrationRequest(payload)
	if err != nil {
		log.Printf("catalog hydration could not be scheduled: %v", err)
		return
	}
	if _, alreadyRunning := catalogHydrationInFlight.LoadOrStore(key, struct{}{}); alreadyRunning {
		return
	}
	backgroundRequest := request.Clone(context.Background())
	go func() {
		defer catalogHydrationInFlight.Delete(key)
		if err := s.ensureCatalogHydrated(backgroundRequest, payload); err != nil {
			log.Printf("catalog hydration %s failed: %v", key, err)
		}
	}()
}

func (s *Server) writeCatalogError(response http.ResponseWriter, request *http.Request, err error) {
	if err != nil {
		log.Printf("catalog request %s %s failed: %v", request.Method, request.URL.Path, err)
	}
	switch {
	case errors.Is(err, ErrCatalogWithdrawn):
		s.writeCatalogLifecycleError(response, request, 410, "CATALOG_WITHDRAWN", false, CatalogArticle{})
	case errors.Is(err, ErrCatalogNotFound):
		writeAPIError(response, request, http.StatusNotFound, "CATALOG_NOT_FOUND", err.Error(), false)
	case errors.Is(err, ErrCatalogInvalid):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
	default:
		writeAPIError(response, request, http.StatusServiceUnavailable, "CATALOG_UNAVAILABLE", "catalog could not be read", true)
	}
}
