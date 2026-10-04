package main

import (
	"context"
	"errors"
	"io"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"
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
	hydrating := (!complete || catalogConfigurationsIncomplete(items)) && s.ingestionClient != nil
	if hydrating {
		s.scheduleCatalogHydration(request, map[string]any{
			"scope": "configurations", "year": year, "make": makeName,
			"model": modelName, "region": catalogRegion(request),
		})
	}
	writeJSON(response, http.StatusOK, CatalogConfigurationsResponse{
		Version: "v1", Items: items,
		CatalogHydrationResponse: CatalogHydrationResponse{Complete: complete && !catalogConfigurationsIncomplete(items), Hydrating: hydrating},
	})
}

func (s *Server) listCatalogArticles(response http.ResponseWriter, request *http.Request, principal Principal) {
	vehicleID := request.PathValue("vehicle_id")
	items, err := s.catalog.Articles(request.Context(), principal, vehicleID)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	progress, err := s.catalog.CatalogArticleProgress(request.Context(), principal, vehicleID)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	hydrating := progress != nil && progress.Status == "running"
	if catalogArticlesIncomplete(items) && s.ingestionClient != nil {
		configuration, configurationErr := s.catalog.ConfigurationByVehicle(request.Context(), principal, vehicleID)
		if configurationErr != nil && !errors.Is(configurationErr, ErrCatalogNotFound) {
			s.writeCatalogError(response, request, configurationErr)
			return
		}
		if configurationErr == nil {
			hydrating = true
			s.scheduleCatalogHydration(request, map[string]any{
				"scope": "articles", "vehicle_id": vehicleID,
				"year": configuration.Year, "make": configuration.Make, "model": configuration.Model,
				"region": configuration.Region, "trim": configuration.Trim, "engine": configuration.Engine,
			})
		}
	}
	for index := range items {
		rewriteCatalogImageURLs(&items[index], s.catalogImageKey)
	}
	writeJSON(response, http.StatusOK, CatalogArticlesResponse{
		Version: "v1", Items: items, Complete: len(items) > 0 && !hydrating,
		Hydrating: hydrating, Progress: progress,
	})
}

func (s *Server) getCatalogArticle(response http.ResponseWriter, request *http.Request, principal Principal) {
	article, err := s.catalog.Article(request.Context(), principal, request.PathValue("vehicle_id"), request.PathValue("article_id"))
	needsHydration := err != nil || !article.Complete || article.Document == nil
	// A catalog index row and its hydrated detail row have different local
	// IDs. Resolve the provider article ID before contacting a source so a
	// previously hydrated article is served from the database on every later
	// read instead of being fetched again through the index-row alias.
	if needsHydration && err == nil && article.sourceArticleID != "" {
		if cached, cacheErr := s.catalog.Article(
			request.Context(), principal, request.PathValue("vehicle_id"), article.sourceArticleID,
		); cacheErr == nil && cached.Complete && cached.Document != nil {
			article = cached
			needsHydration = false
		}
	}
	if needsHydration && s.ingestionClient != nil {
		configuration, configurationErr := s.catalog.ConfigurationByVehicle(request.Context(), principal, request.PathValue("vehicle_id"))
		if configurationErr != nil {
			s.writeCatalogError(response, request, configurationErr)
			return
		}
		if hydrationErr := s.ensureCatalogHydrated(request, map[string]any{
			"scope": "article", "vehicle_id": request.PathValue("vehicle_id"), "article_id": request.PathValue("article_id"),
			"year": configuration.Year, "make": configuration.Make, "model": configuration.Model,
			"region": configuration.Region, "trim": configuration.Trim, "engine": configuration.Engine,
			"title":             article.Title,
			"source_article_id": article.sourceArticleID,
		}); hydrationErr != nil {
			s.writeCatalogError(response, request, hydrationErr)
			return
		}
		lookupID := request.PathValue("article_id")
		if article.sourceArticleID != "" {
			lookupID = article.sourceArticleID
		}
		article, err = s.catalog.Article(request.Context(), principal, request.PathValue("vehicle_id"), lookupID)
	}
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	rewriteCatalogImageURLs(&article, s.catalogImageKey)
	article.SourceReview = sourceReviewForArticle(article, request.PathValue("vehicle_id"), article.ID)
	writeJSON(response, http.StatusOK, CatalogArticleResponse{Version: "v1", Article: article})
}

const catalogImageMaxBytes = 12 << 20

var catalogImageClient = &http.Client{
	Timeout:       20 * time.Second,
	CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse },
}

// rewriteCatalogImageURLs keeps provider URLs out of the public article
// payload. The browser loads the same-origin proxy, which also means the
// article reader can keep provider credentials and redirects out of markup.
func rewriteCatalogImageURLs(article *CatalogArticle, key []byte) {
	for index := range article.Images {
		image := &article.Images[index]
		source, ok := catalogImageSourceURL(image.URL)
		if !ok || len(key) != 32 {
			image.URL = ""
			continue
		}
		token, err := sealCatalogImageURL(source, key)
		if err != nil {
			image.URL = ""
			continue
		}
		image.URL = "/v1/catalog/images/" + token
	}
}

func isCatalogImageURL(value string) bool {
	parsed, err := url.Parse(strings.TrimSpace(value))
	if err != nil || parsed.Scheme != "https" || parsed.User != nil || parsed.Port() != "" || parsed.Fragment != "" {
		return false
	}
	return strings.EqualFold(parsed.Host, "autoapitwo.vercel.app")
}

func catalogImageSourceURL(value string) (string, bool) {
	value = strings.TrimSpace(value)
	if isCatalogImageURL(value) {
		return value, true
	}
	parsed, err := url.Parse(value)
	if err != nil || parsed.IsAbs() || parsed.Host != "" || parsed.Path != "/v1/catalog/images" {
		return "", false
	}
	source := strings.TrimSpace(parsed.Query().Get("src"))
	return source, isCatalogImageURL(source)
}

func catalogImageProxyURL(source string) string {
	return "/v1/catalog/images?src=" + url.QueryEscape(source)
}

// serveCatalogImage is deliberately limited to the provider host that the
// ingestion pipeline records today. It is an image-only, read-only proxy, so
// arbitrary URL fetching cannot be turned into an SSRF endpoint.
func serveCatalogImage(response http.ResponseWriter, request *http.Request, key []byte) {
	if len(key) != 32 {
		http.Error(response, "catalog image references are unavailable", http.StatusServiceUnavailable)
		return
	}
	source, err := openCatalogImageURL(request.PathValue("token"), key)
	if err != nil || !isCatalogImageURL(source) {
		http.Error(response, "catalog image not found", http.StatusNotFound)
		return
	}
	upstreamRequest, err := http.NewRequestWithContext(request.Context(), http.MethodGet, source, nil)
	if err != nil {
		http.Error(response, "catalog image could not be requested", http.StatusBadRequest)
		return
	}
	upstreamRequest.Header.Set("Accept", "image/avif,image/webp,image/png,image/jpeg,image/gif;q=0.9,*/*;q=0.1")
	upstream, err := catalogImageClient.Do(upstreamRequest)
	if err != nil {
		http.Error(response, "catalog image could not be loaded", http.StatusBadGateway)
		return
	}
	defer upstream.Body.Close()
	if upstream.StatusCode < http.StatusOK || upstream.StatusCode >= http.StatusMultipleChoices {
		http.Error(response, "catalog image could not be loaded", http.StatusBadGateway)
		return
	}
	contentType := strings.ToLower(strings.TrimSpace(strings.Split(upstream.Header.Get("Content-Type"), ";")[0]))
	if !strings.HasPrefix(contentType, "image/") {
		http.Error(response, "catalog image returned an invalid media type", http.StatusBadGateway)
		return
	}
	body, err := io.ReadAll(io.LimitReader(upstream.Body, catalogImageMaxBytes+1))
	if err != nil || len(body) > catalogImageMaxBytes {
		http.Error(response, "catalog image is too large", http.StatusBadGateway)
		return
	}
	response.Header().Set("Content-Type", contentType)
	response.Header().Set("Cache-Control", "private, max-age=300")
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
	case errors.Is(err, ErrCatalogNotFound):
		writeAPIError(response, request, http.StatusNotFound, "CATALOG_NOT_FOUND", err.Error(), false)
	case errors.Is(err, ErrCatalogInvalid):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
	default:
		writeAPIError(response, request, http.StatusInternalServerError, "CATALOG_UNAVAILABLE", "catalog could not be read", true)
	}
}
