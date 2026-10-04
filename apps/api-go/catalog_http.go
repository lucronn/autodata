package main

import (
	"bytes"
	"context"
	"encoding/json"
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

type catalogCompositionRequest struct {
	Query string `json:"query"`
}

type catalogCompositionVehicle struct {
	VehicleID       string `json:"vehicle_id"`
	ConfigurationID string `json:"configuration_id"`
	Year            int    `json:"year"`
	Make            string `json:"make"`
	Model           string `json:"model"`
	Region          string `json:"region,omitempty"`
	Trim            string `json:"trim,omitempty"`
	Engine          string `json:"engine,omitempty"`
}

type catalogCompositionJobPlan struct {
	Vehicle catalogCompositionVehicle `json:"vehicle"`
	Query   string                    `json:"query"`
}

// composeCatalogProcedure binds the composition request to the canonical
// catalog vehicle and forwards it through the existing job-plan worker path.
func (s *Server) composeCatalogProcedure(response http.ResponseWriter, request *http.Request, principal Principal) {
	body, err := io.ReadAll(io.LimitReader(request.Body, maxIngestionProxyBytes+1))
	if err != nil || len(body) > maxIngestionProxyBytes {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "composition request is invalid or too large", false)
		return
	}
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.DisallowUnknownFields()
	var input catalogCompositionRequest
	if err := decoder.Decode(&input); err != nil || decoder.Decode(&struct{}{}) != io.EOF || strings.TrimSpace(input.Query) == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "composition requires only a non-empty query; vehicle identity comes from the catalog path", false)
		return
	}
	configuration, err := s.catalog.ConfigurationByVehicle(request.Context(), principal, request.PathValue("vehicle_id"))
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	jobPlan := catalogCompositionJobPlan{
		Vehicle: catalogCompositionVehicle{
			VehicleID: configuration.VehicleID, ConfigurationID: configuration.ID,
			Year: configuration.Year, Make: configuration.Make, Model: configuration.Model,
			Region: configuration.Region, Trim: configuration.Trim, Engine: configuration.Engine,
		},
		Query: strings.TrimSpace(input.Query),
	}
	workerBody, err := json.Marshal(jobPlan)
	if err != nil {
		writeAPIError(response, request, http.StatusInternalServerError, "INTERNAL_ERROR", "composition request could not be encoded", false)
		return
	}
	request.Body = io.NopCloser(bytes.NewReader(workerBody))
	request.ContentLength = int64(len(workerBody))
	if strings.TrimSpace(request.Header.Get("Idempotency-Key")) == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "Idempotency-Key is required", false)
		return
	}
	if s.ingestionClient == nil {
		writeAPIError(response, request, http.StatusServiceUnavailable, "INGESTION_UNAVAILABLE", "ingestion service is not configured", true)
		return
	}
	status, responseBody, err := s.ingestionClient.Do(request, "/v1/job-plans", workerBody, request.Header.Get("Idempotency-Key"))
	if err != nil {
		writeAPIError(response, request, http.StatusBadGateway, "INGESTION_UNAVAILABLE", "ingestion service request failed", true)
		return
	}
	if status < http.StatusOK || status >= http.StatusMultipleChoices {
		writeAPIError(response, request, status, "COMPOSITION_UNAVAILABLE", "a source-backed procedure could not be produced for this vehicle", status >= http.StatusInternalServerError)
		return
	}
	// Public composition responses must not expose provider URLs, storage keys,
	// raw source snapshots, or internal artifact references.
	var result map[string]any
	if err := json.Unmarshal(responseBody, &result); err != nil || result == nil {
		writeAPIError(response, request, http.StatusBadGateway, "INVALID_INGESTION_RESPONSE", "composition service returned an invalid response", false)
		return
	}
	projectCompositionResponse(result, s.catalogImageKey)
	encoded, err := json.Marshal(result)
	if err != nil {
		writeAPIError(response, request, http.StatusBadGateway, "INVALID_INGESTION_RESPONSE", "composition response could not be encoded", false)
		return
	}
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_, _ = response.Write(encoded)
}

func projectCompositionResponse(value any, imageKey []byte) {
	switch current := value.(type) {
	case map[string]any:
		for key, nested := range current {
			switch key {
			case "source_visual_refs", "derived_visual_refs", "source_watermarks", "source_original", "source_snapshot", "visual_artifacts", "source_uri", "source_url", "storage_key", "artifact_key":
				delete(current, key)
			case "images":
				if images, ok := nested.([]any); ok {
					current[key] = projectCompositionImageList(images, imageKey)
				}
			}
			if retained, exists := current[key]; exists {
				projectCompositionResponse(retained, imageKey)
			}
		}
	case []any:
		for _, nested := range current {
			projectCompositionResponse(nested, imageKey)
		}
	}
}

func projectCompositionImageList(images []any, imageKey []byte) []any {
	projected := make([]any, 0, len(images))
	for _, raw := range images {
		image, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		imageURL, _ := image["url"].(string)
		tokenPath := strings.TrimPrefix(imageURL, "/v1/catalog/images/")
		if tokenPath != imageURL && tokenPath != "" && !strings.ContainsAny(tokenPath, "/?#") && !strings.Contains(tokenPath, "..") {
			// Existing opaque same-origin references are already safe.
		} else {
			storageKey, _ := image["storage_key"].(string)
			if len(imageKey) != 32 || strings.TrimSpace(storageKey) == "" {
				continue
			}
			token, err := sealCatalogImageStorageKey(strings.TrimSpace(storageKey), imageKey)
			if err != nil {
				continue
			}
			imageURL = "/v1/catalog/images/" + token
		}
		image["url"] = imageURL
		for key := range image {
			if key != "url" && key != "alt" && key != "article_id" && key != "evidence_id" {
				delete(image, key)
			}
		}
		projected = append(projected, image)
	}
	return projected
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

// catalogImageClient is retained as a compatibility seam for the source
// review tests while that renderer migrates to local asset mappings. No
// catalog image serving path uses this provider client.
var catalogImageClient = &http.Client{
	Timeout:       20 * time.Second,
	CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse },
}

// rewriteCatalogImageURLs projects only localized AutoData object keys into
// opaque same-origin paths. Unlocalized provider URLs are omitted.
func rewriteCatalogImageURLs(article *CatalogArticle, key []byte) {
	for index := range article.Images {
		image := &article.Images[index]
		storageKey := strings.TrimSpace(image.StorageKey)
		if storageKey == "" || len(key) != 32 {
			image.URL = ""
			continue
		}
		token, err := sealCatalogImageStorageKey(storageKey, key)
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

// serveCatalogImage resolves only opaque tokens for localized AutoData
// objects. Provider URLs and legacy source-bearing tokens are never fetched.
func serveCatalogImage(response http.ResponseWriter, request *http.Request, key []byte) {
	if len(key) != 32 {
		http.Error(response, "catalog image references are unavailable", http.StatusServiceUnavailable)
		return
	}
	token := request.PathValue("token")
	if storageKey, err := openCatalogImageStorageKey(token, key); err == nil {
		stored, err := catalogImageObjectReader(request.Context(), storageKey)
		if err != nil || !safeCatalogImageContentType(strings.ToLower(stored.ContentType)) || len(stored.Body) == 0 || len(stored.Body) > catalogImageMaxBytes {
			http.Error(response, "catalog image not found", http.StatusNotFound)
			return
		}
		response.Header().Set("Content-Type", stored.ContentType)
		response.Header().Set("Content-Security-Policy", "sandbox")
		response.Header().Set("Cache-Control", "private, max-age=300")
		response.Header().Set("Referrer-Policy", "no-referrer")
		response.Header().Set("X-Content-Type-Options", "nosniff")
		response.WriteHeader(http.StatusOK)
		_, _ = response.Write(stored.Body)
		return
	}

	http.Error(response, "catalog image not found", http.StatusNotFound)
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
