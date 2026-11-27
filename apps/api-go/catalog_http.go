package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"log"
	"net/http"
	"net/url"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

// Catalog selector reads must remain responsive while a missing scope is
// hydrated from the external providers. The worker owns durable idempotency;
// this process-level gate prevents repeated browser polling from opening
// duplicate long-running requests before the worker has persisted its result.
var catalogHydrationInFlight sync.Map
var catalogDiscoveryInstance = rand.Text()

// Discovery status is supplementary to stored catalog rows. Bound its
// database read so it can't keep otherwise usable data waiting indefinitely.
const catalogStatusReadTimeout = 250 * time.Millisecond
const ownedIndexStatusReadTimeout = 25 * time.Millisecond
const catalogDemoReadableIndexPreference = "workshop-demo-readable-index"
const catalogDemoFitmentPreference = "workshop-demo-fitment"

type CatalogYearsResponse struct {
	Version string        `json:"version"`
	Items   []CatalogYear `json:"items"`
	CatalogHydrationResponse
}
type CatalogHydrationResponse struct {
	Complete          bool   `json:"complete"`
	Hydrating         bool   `json:"hydrating"`
	DiscoveryInstance string `json:"discovery_instance,omitempty"`
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
	Version     string                 `json:"version"`
	Items       []CatalogConfiguration `json:"items"`
	Discovering bool                   `json:"discovering,omitempty"`
	CatalogHydrationResponse
}
type CatalogArticlesResponse struct {
	Version       string                   `json:"version"`
	Items         []CatalogArticle         `json:"items"`
	Complete      bool                     `json:"complete"`
	Hydrating     bool                     `json:"hydrating"`
	Progress      *CatalogArticleProgress  `json:"progress,omitempty"`
	Configuration *CatalogConfiguration    `json:"configuration,omitempty"`
	Page          *CatalogArticleIndexPage `json:"page,omitempty"`
	IndexedCount  *int                     `json:"indexed_count,omitempty"`
}
type CatalogArticleResponse struct {
	Version       string                `json:"version"`
	Article       CatalogArticle        `json:"article"`
	Configuration *CatalogConfiguration `json:"configuration,omitempty"`
}

func (s *Server) readCatalogYears(ctx context.Context, principal Principal) (CatalogYearsResponse, error) {
	items, coverage, err := s.catalog.Years(ctx, principal)
	if err != nil {
		return CatalogYearsResponse{}, err
	}
	complete := len(items) != 0 || s.ingestionClient == nil
	if coverage != nil {
		complete = *coverage
	}
	return CatalogYearsResponse{
		Version: "v1", Items: items,
		CatalogHydrationResponse: CatalogHydrationResponse{Complete: complete, Hydrating: !complete && s.ingestionClient != nil},
	}, nil
}

func (s *Server) listCatalogYears(response http.ResponseWriter, request *http.Request, principal Principal) {
	years, err := s.readCatalogYears(request.Context(), principal)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	if years.Hydrating && !catalogStoredSelector(request) {
		s.scheduleCatalogHydration(request, map[string]any{"scope": "years"})
	}
	s.cacheCompleteCatalogSelector(response, request, years.Complete && len(years.Items) > 0)
	writeJSON(response, http.StatusOK, years)
}

func (s *Server) listCatalogMakes(response http.ResponseWriter, request *http.Request, principal Principal) {
	year, ok := catalogYearPath(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "year is invalid", false)
		return
	}
	region := request.URL.Query().Get("region")
	payload := map[string]any{"scope": "makes", "year": year, "region": catalogRegion(request)}
	running := s.catalogHydrationRunning(payload)
	// Read the marker before the rows. A concurrent completion can otherwise
	// make an older partial row set appear complete to the caller.
	complete, statusErr := s.catalogSelectorCoverage(request, principal, "makes", year, "", "", region)
	items, err := s.catalog.Makes(request.Context(), principal, year, region)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	if !s.catalogCanServeRows(response, request, len(items), statusErr) {
		return
	}
	hydration := s.initialSelectorHydration(request, payload, complete, running)
	s.cacheCompleteCatalogSelector(response, request, complete && len(items) > 0)
	writeJSON(response, http.StatusOK, CatalogMakesResponse{
		Version: "v1", Items: items, CatalogHydrationResponse: hydration,
	})
}

func (s *Server) listCatalogModels(response http.ResponseWriter, request *http.Request, principal Principal) {
	year, ok := catalogYearPath(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "year is invalid", false)
		return
	}
	makeName := catalogPathValue(request.PathValue("make"))
	region := request.URL.Query().Get("region")
	payload := map[string]any{"scope": "models", "year": year, "make": makeName, "region": catalogRegion(request)}
	running := s.catalogHydrationRunning(payload)
	complete, statusErr := s.catalogSelectorCoverage(request, principal, "models", year, makeName, "", region)
	items, err := s.catalog.Models(request.Context(), principal, year, makeName, region)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	if !s.catalogCanServeRows(response, request, len(items), statusErr) {
		return
	}
	hydration := s.initialSelectorHydration(request, payload, complete, running)
	s.cacheCompleteCatalogSelector(response, request, complete && len(items) > 0)
	writeJSON(response, http.StatusOK, CatalogModelsResponse{
		Version: "v1", Items: items, CatalogHydrationResponse: hydration,
	})
}

func (s *Server) initialSelectorHydration(request *http.Request, payload map[string]any, complete, running bool) CatalogHydrationResponse {
	if complete || s.ingestionClient == nil {
		return CatalogHydrationResponse{Complete: complete}
	}
	if !running && !catalogStoredSelector(request) {
		running = s.scheduleCatalogHydration(request, payload)
	}
	return CatalogHydrationResponse{Hydrating: running, DiscoveryInstance: catalogDiscoveryInstance}
}

func (s *Server) listCatalogConfigurations(response http.ResponseWriter, request *http.Request, principal Principal) {
	year, ok := catalogYearPath(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "year is invalid", false)
		return
	}
	makeName := catalogPathValue(request.PathValue("make"))
	modelName := catalogPathValue(request.PathValue("model"))
	region := request.URL.Query().Get("region")
	payload := map[string]any{
		"scope": "configurations", "year": year, "make": makeName,
		"model": modelName, "region": catalogRegion(request),
	}
	storedOnly := catalogStoredSelector(request)
	// Check before reading the rows. In-flight work can finish and persist rows
	// while this request is reading, in which case another stored read is safe.
	running := s.catalogHydrationRunning(payload)
	complete, providerComplete, statusErr := s.catalogConfigurationCoverage(request, principal, year, makeName, modelName, region)
	items, err := s.catalog.Configurations(request.Context(), principal, year, makeName, modelName, region)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	if !s.catalogCanServeRows(response, request, len(items), statusErr) {
		return
	}
	rowsComplete := !catalogConfigurationsIncomplete(items)
	usable := rowsComplete && slices.ContainsFunc(items, func(item CatalogConfiguration) bool {
		return !item.ConfigurationUnresolved && !item.EngineVariantMarketUnverified
	})
	// Keep recorded rows visible, and let current provider coverage settle a
	// raw-only picker even when discovery finds no additional configuration.
	scopeComplete := complete && (usable || len(items) == 0 || (rowsComplete && providerComplete))
	// A new choice from the first provider must not let a legacy completion
	// marker hide an in-flight check of the remaining providers.
	if running && !providerComplete {
		scopeComplete = false
	}
	discoveryInstance := ""
	if !scopeComplete && s.ingestionClient != nil {
		discoveryInstance = catalogDiscoveryInstance
	}
	if !scopeComplete && !storedOnly {
		running = s.scheduleCatalogHydration(request, payload)
	}
	s.cacheCompleteCatalogSelector(response, request, scopeComplete && usable && !running)
	writeJSON(response, http.StatusOK, CatalogConfigurationsResponse{
		Version: "v1", Items: items, Discovering: usable && !scopeComplete && running,
		CatalogHydrationResponse: CatalogHydrationResponse{
			Complete: scopeComplete, Hydrating: !usable && running, DiscoveryInstance: discoveryInstance,
		},
	})
}

func (s *Server) catalogConfigurationCoverage(request *http.Request, principal Principal, year int, makeName, model, region string) (bool, bool, error) {
	if store, ok := s.catalog.(interface {
		configurationCoverage(context.Context, int, string, string, string) (bool, bool, error)
	}); ok {
		ctx, cancel := context.WithTimeout(request.Context(), catalogStatusReadTimeout)
		defer cancel()
		complete, providerComplete, err := store.configurationCoverage(ctx, year, makeName, model, region)
		return complete && err == nil, providerComplete && err == nil, err
	}
	complete, err := s.catalogSelectorCoverage(request, principal, "configurations", year, makeName, model, region)
	return complete, false, err
}

func (s *Server) catalogSelectorCoverage(request *http.Request, principal Principal, scope string, year int, makeName, model, region string) (bool, error) {
	ctx, cancel := context.WithTimeout(request.Context(), catalogStatusReadTimeout)
	defer cancel()
	complete, err := s.catalog.CatalogScopeComplete(ctx, principal, scope, year, makeName, model, region)
	return complete && err == nil, err
}

func (s *Server) catalogCanServeRows(response http.ResponseWriter, request *http.Request, count int, statusErr error) bool {
	if statusErr == nil {
		return true
	}
	if count == 0 || request.Context().Err() != nil ||
		errors.Is(statusErr, ErrCatalogNotFound) || errors.Is(statusErr, ErrCatalogInvalid) || errors.Is(statusErr, ErrCatalogWithdrawn) {
		s.writeCatalogError(response, request, statusErr)
		return false
	}
	log.Printf("catalog discovery status unavailable; returning stored rows: %v", statusErr)
	return true
}

func (s *Server) listCatalogArticles(response http.ResponseWriter, request *http.Request, principal Principal) {
	vehicleID := request.PathValue("vehicle_id")
	filters, parseErr := url.ParseQuery(request.URL.RawQuery)
	queryValues, titleValues := filters["q"], filters["title"]
	if parseErr != nil || len(queryValues) > 1 || len(titleValues) > 1 || (len(queryValues) != 0 && len(titleValues) != 0) {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "article search query is invalid", false)
		return
	}
	var pagePreference string
	switch {
	case catalogReadPreferenceRequested(request, catalogIndexLivePagesPreference):
		pagePreference = catalogIndexLivePagesPreference
	case catalogReadPreferenceRequested(request, catalogIndexPagesPreference):
		pagePreference = catalogIndexPagesPreference
	}
	var pageRequest catalogIndexPageRequest
	if pagePreference != "" {
		var valid bool
		pageRequest, valid = parseCatalogIndexPageRequest(filters)
		if !valid {
			writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "article index page query is invalid", false)
			return
		}
	}
	query := ""
	if len(queryValues) == 1 {
		query = strings.TrimSpace(queryValues[0])
		if len([]rune(query)) > 120 || len(strings.Fields(query)) > 8 {
			writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "article search query is invalid", false)
			return
		}
	}
	title := ""
	if len(titleValues) == 1 {
		title = strings.TrimSpace(titleValues[0])
		if title == "" || !utf8.ValidString(title) || utf8.RuneCountInString(title) > 1000 || strings.ContainsRune(title, 0) {
			writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "article search title is invalid", false)
			return
		}
	}
	ctx := request.Context()
	paid := s.paidCatalogEnabled()
	scope, scoped := ctx.Value(paidCatalogContextKey{}).(paidCatalogContext)
	statusBudget := catalogStatusReadTimeout
	if paid && scoped && !scope.openDemo && pagePreference != catalogIndexPagesPreference {
		// The exact grant has already been checked. Do not make owned rows
		// wait for preparation metadata when its read stalls. The older
		// paging preference still needs that metadata to choose its shape.
		statusBudget = ownedIndexStatusReadTimeout
	}
	readProgress := func(budget time.Duration) (*CatalogArticleProgress, error) {
		statusCtx, cancel := context.WithTimeout(ctx, budget)
		defer cancel()
		return s.catalog.CatalogArticleProgress(statusCtx, principal, vehicleID)
	}
	// Read progress before the rows. A completion committed after the row
	// snapshot must not make that older snapshot look complete.
	progress, statusErr := readProgress(statusBudget)
	items, err := s.catalogIndexRows(ctx, principal, vehicleID, query, title)
	if err == nil && len(items) == 0 && statusBudget < catalogStatusReadTimeout &&
		errors.Is(statusErr, context.DeadlineExceeded) && ctx.Err() == nil {
		// An empty read needs progress to distinguish waiting from an empty
		// catalog. Preserve the rest of the budget, then take a new snapshot.
		progress, statusErr = readProgress(catalogStatusReadTimeout - statusBudget)
		if statusErr == nil {
			items, err = s.catalogIndexRows(ctx, principal, vehicleID, query, title)
		}
	}
	if err != nil {
		if errors.Is(err, ErrVehicleGrantUnavailable) {
			s.writePaidCatalogError(response, request, err)
		} else {
			s.writeCatalogError(response, request, err)
		}
		return
	}
	if !s.catalogCanServeRows(response, request, len(items), statusErr) {
		return
	}
	if statusErr != nil {
		progress = nil
	}
	if !paid && (progress == nil || !progress.Complete) && s.ingestionClient != nil {
		ctx, cancel := context.WithTimeout(request.Context(), catalogStatusReadTimeout)
		configuration, configurationErr := s.catalog.ConfigurationByVehicle(ctx, principal, vehicleID)
		cancel()
		if configurationErr != nil && !errors.Is(configurationErr, ErrCatalogNotFound) &&
			!s.catalogCanServeRows(response, request, len(items), configurationErr) {
			return
		}
		if configurationErr == nil && configuration.EngineVariant == "" {
			// The legacy hydration request has no engine-variant field.
			s.scheduleCatalogHydration(request, map[string]any{
				"scope": "articles", "vehicle_id": vehicleID,
				"year": configuration.Year, "make": configuration.Make, "model": configuration.Model,
				"region": configuration.Region, "trim": configuration.Trim, "engine": configuration.Engine,
			})
		}
	}
	var configuration *CatalogConfiguration
	var page *CatalogArticleIndexPage
	var indexedCount *int
	if scoped {
		configuration = &scope.configuration
		if paid && scope.openDemo && query == "" && title == "" &&
			catalogReadPreferenceRequested(request, catalogDemoReadableIndexPreference) {
			total := len(items)
			indexedCount = &total
			items = slices.DeleteFunc(items, func(article CatalogArticle) bool { return article.Availability != "available" })
			response.Header().Add("Preference-Applied", catalogDemoReadableIndexPreference)
		}
		settled := progress != nil && (progress.Complete || (progress.Status == "failed" && !progress.Retryable))
		if paid && !scope.openDemo && pagePreference != "" && !filters.Has("q") && !filters.Has("title") {
			if pagePreference == catalogIndexLivePagesPreference {
				readableArticlesFirst(items)
			}
			if len(items) > catalogIndexPageSize && (pagePreference == catalogIndexLivePagesPreference || settled) {
				items, page = pageRequest.selectPage(items)
				response.Header().Add("Preference-Applied", pagePreference)
			}
		}
	}
	writeJSON(response, http.StatusOK, CatalogArticlesResponse{
		Version: "v1", Items: items, Complete: progress != nil && progress.Complete,
		Hydrating: catalogIndexHydrating(progress), Progress: progress, Configuration: configuration, Page: page, IndexedCount: indexedCount,
	})
}

func catalogIndexHydrating(progress *CatalogArticleProgress) bool {
	return progress != nil && !progress.Complete &&
		(progress.Status == "pending" || progress.Status == "running" || progress.Status == "failed" && progress.Retryable)
}

func (s *Server) catalogIndexRows(ctx context.Context, principal Principal, vehicleID, query, title string) ([]CatalogArticle, error) {
	var items []CatalogArticle
	var err error
	paid := s.paidCatalogEnabled()
	if paid {
		if query == "" {
			repository, ok := s.catalog.(paidArticleDescriptorStore)
			if !ok {
				return nil, ErrVehicleGrantUnavailable
			}
			items, err = repository.PaidArticleDescriptors(ctx, principal, vehicleID)
		} else {
			repository, ok := s.catalog.(paidArticleSearchStore)
			if !ok {
				return nil, ErrVehicleGrantUnavailable
			}
			items, err = repository.PaidArticleSearchDescriptors(ctx, principal, vehicleID, query)
		}
	} else {
		items, err = s.catalog.Articles(ctx, principal, vehicleID)
		if err == nil && query != "" {
			items = filterCatalogArticleSearch(items, query)
		}
	}
	if err != nil {
		return nil, err
	}
	if title != "" {
		items = filterCatalogArticleTitle(items, title)
	}
	if scope, ok := ctx.Value(paidCatalogContextKey{}).(paidCatalogContext); ok && scope.openDemo && (query != "" || title != "") {
		available := make([]CatalogArticle, 0, len(items))
		for _, item := range items {
			if item.Availability == "available" {
				available = append(available, item)
			}
		}
		items = available
	}
	if paid || title != "" {
		descriptors := make([]CatalogArticle, 0, len(items))
		for _, item := range items {
			if paid && (item.CanonicalArticleID == nil || item.ID != *item.CanonicalArticleID) {
				continue
			}
			item.Document, item.Body, item.Steps, item.Images = nil, "", nil, []CatalogImage{}
			item.SourceReview, item.OriginalSourceReview = nil, nil
			descriptors = append(descriptors, item)
		}
		items = descriptors
	} else {
		for index := range items {
			rewriteCatalogImageURLs(&items[index], s.catalogImageKey)
		}
	}
	return items, nil
}

func (s *Server) getCatalogArticle(response http.ResponseWriter, request *http.Request, principal Principal) {
	response.Header().Set("Cache-Control", "private, no-store")
	if s.respondCatalogPublicationStatus(response, request) {
		return
	}
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

const (
	shortSourceCheckPreference      = "workshop-short-source-check"
	previewSourceCheckPreference    = "workshop-preview-source-check"
	shortPublicationCheckPreference = "workshop-short-publication-check"
	finishPublishedBodyPreference   = "workshop-finish-published-body"
	retainedReaderSessionPreference = "workshop-retained-reader-session"
)

func catalogReadPreferenceRequested(request *http.Request, preference string) bool {
	for _, value := range request.Header.Values("Prefer") {
		for token := range strings.SplitSeq(value, ",") {
			if strings.TrimSpace(token) == preference {
				return true
			}
		}
	}
	return false
}

func (s *Server) respondCatalogArticleView(response http.ResponseWriter, request *http.Request, principal Principal, view CatalogArticleView) {
	if view.Withdrawn {
		s.writePaidCatalogError(response, request, ErrCatalogWithdrawn)
		return
	}
	vehicleID := request.PathValue("vehicle_id")
	article := view.Article
	var configuration *CatalogConfiguration
	var scope paidCatalogContext
	paid := s.paidCatalogEnabled()
	if paid {
		var ok bool
		scope, ok = request.Context().Value(paidCatalogContextKey{}).(paidCatalogContext)
		if !ok || scope.identity == nil || article.CanonicalArticleID == nil || *article.CanonicalArticleID != scope.identity.CanonicalArticleID {
			s.writePaidCatalogError(response, request, ErrCatalogNotFound)
			return
		}
		if !scope.openDemo && scope.identity.CurrentSourceRevisionID == nil &&
			article.SourceRevisionID == nil && article.Availability != "available" && view.sourceBodyPreview != nil {
			article.Document = view.sourceBodyPreview
			article.ContentOrigin = stringPointer("source")
			article.Availability = "available"
			article.ContentStatus = "content_partial"
			article.SourceBodyPreview = true
			article = lifecycleArticle(article)
		}
	}
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
	if paid {
		view.Article = article
		if scope.openDemo {
			if err := s.rewriteOpenDemoCatalogArticleImages(request.Context(), scope.configuration, *scope.identity, &view); err != nil {
				s.writePaidCatalogError(response, request, err)
				return
			}
		} else {
			if err := s.rewritePaidCatalogArticleImages(request.Context(), principal, scope.configuration, *scope.identity, &view); err != nil {
				s.writePaidCatalogError(response, request, err)
				return
			}
			configuration = &scope.configuration
		}
		article = view.Article
	} else {
		rewriteCatalogImageURLs(&article, s.catalogImageKey)
	}
	if current := article.Processing; current != nil {
		preference := current.shortReadPreference
		applicable := preference == shortSourceCheckPreference && status == http.StatusAccepted ||
			preference == shortPublicationCheckPreference && status == http.StatusOK
		// A paid preview can opt into an earlier check for the persisted source.
		if preference == shortSourceCheckPreference && status == http.StatusOK &&
			paid && !scope.openDemo && request.Method == http.MethodGet && article.SourceBodyPreview &&
			article.SourceRevisionID == nil && article.CanonicalRevisionID == nil &&
			current.JobID != "" && current.State == "fetching_source" {
			preference, applicable = previewSourceCheckPreference, true
		}
		if applicable && catalogReadPreferenceRequested(request, preference) {
			// Only replace the default read cadence when the client opts in.
			processing := *current
			processing.RetryAfterSeconds = nil
			article.Processing = &processing
			response.Header().Del("Retry-After")
			response.Header().Set("Preference-Applied", preference)
		}
	}
	if configuration != nil && request.Method == http.MethodGet && status == http.StatusOK &&
		article.CanonicalRevisionID != nil && article.ContentOrigin != nil && *article.ContentOrigin == "canonical" &&
		article.Document != nil && len(article.Document.Blocks) > 0 &&
		(article.Processing == nil || article.Processing.State == "completed" && article.Processing.RetryAfterSeconds == nil) &&
		catalogReadPreferenceRequested(request, finishPublishedBodyPreference) {
		response.Header().Set("Preference-Applied", finishPublishedBodyPreference)
	}
	if configuration != nil && status == http.StatusOK && s.canCheckCatalogPublication(article) {
		response.Header().Set(publicationCheckHeader, "supported")
	}
	if configuration != nil && status == http.StatusOK &&
		article.SourceRevisionID != nil && !article.SourceBodyPreview && s.selectedIndexAuth() != nil &&
		wantsRetainedReaderSession(request) {
		// Bind the authorized body to the cookie checked by /auth/session.
		if token, _, err := customerRequestToken(request); err == nil {
			digest := sha256.Sum256([]byte(customerCSRF(token)))
			response.Header().Set("Workshop-Reader-Session", hex.EncodeToString(digest[:]))
		}
	}
	article.SourceReview = sourceReviewForArticle(article, vehicleID, article.ID)
	if paid && !scope.openDemo {
		article.OriginalSourceReview = view.originalSourceReview
	}
	if paid && scope.openDemo && status == http.StatusOK && request.Method == http.MethodGet &&
		catalogReadPreferenceRequested(request, catalogDemoFitmentPreference) {
		// Use the same fitment already included in the public index. This response
		// can open a saved article before the user asks to see that index.
		configuration = &scope.configuration
		response.Header().Add("Preference-Applied", catalogDemoFitmentPreference)
	}
	writeJSON(response, status, CatalogArticleResponse{Version: "v1", Article: article, Configuration: configuration})
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

// Saved picker links can pre-read stored descendants before their parent is
// validated. Only a regular selector read may schedule supplier hydration.
func catalogStoredSelector(request *http.Request) bool {
	return request.URL.Query().Get("stored_only") == "1"
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

func (s *Server) catalogHydrationRunning(payload map[string]any) bool {
	if s.ingestionClient == nil {
		return false
	}
	key, _, err := catalogHydrationRequest(payload)
	if err != nil {
		return false
	}
	_, running := catalogHydrationInFlight.Load(key)
	return running
}

func (s *Server) scheduleCatalogHydration(request *http.Request, payload map[string]any) bool {
	if s.ingestionClient == nil {
		return false
	}
	key, _, err := catalogHydrationRequest(payload)
	if err != nil {
		log.Printf("catalog hydration could not be scheduled: %v", err)
		return false
	}
	if _, alreadyRunning := catalogHydrationInFlight.LoadOrStore(key, struct{}{}); alreadyRunning {
		return true
	}
	backgroundRequest := request.Clone(context.Background())
	go func() {
		defer catalogHydrationInFlight.Delete(key)
		if err := s.ensureCatalogHydrated(backgroundRequest, payload); err != nil {
			log.Printf("catalog hydration %s failed: %v", key, err)
		}
	}()
	return true
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
