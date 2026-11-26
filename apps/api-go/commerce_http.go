package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

const libraryCatalogEmptyPreference = "workshop-library-catalog-empty"
const checkoutArticleIndexPreference = "workshop-checkout-article-index"
const libraryDefaultLimit = 20
const firstWorkshopArticleIndexTimeout = 80 * time.Millisecond

type commerceCheckoutWithIndex struct {
	commerceCheckout
	ArticleIndex CatalogArticlesResponse `json:"article_index"`
}

func (s *Server) mountCommerceRoutes(mux *http.ServeMux) {
	mountPublicRead(mux, "/v1/workshop/quote", s.commerceQuoteHTTP)
	mux.HandleFunc("POST /v1/workshop/checkout-sessions", s.commerceCheckoutHTTP)
	mux.HandleFunc("GET /v1/workshop/orders/{order_id}", s.commerceOrderHTTP)
	mux.HandleFunc("GET /v1/workshop/library", s.commerceLibraryHTTP)
	mux.HandleFunc("POST /v1/payments/stripe/webhook", s.commerceWebhookHTTP)
}
func commerceInvalid(w http.ResponseWriter, r *http.Request, status int) {
	w.Header().Set("Cache-Control", "no-store")
	writeAPIError(w, r, status, "INVALID_REQUEST", "Invalid commerce request.", false)
}
func commerceQuery(r *http.Request, allowed ...string) (url.Values, bool) {
	q, e := url.ParseQuery(r.URL.RawQuery)
	if e != nil || len(r.URL.RawQuery) > 4096 {
		return nil, false
	}
	for k, v := range q {
		found := false
		for _, a := range allowed {
			if a == k {
				found = true
			}
		}
		if !found || len(v) != 1 {
			return nil, false
		}
	}
	return q, true
}
func (s *Server) commercePrincipal(w http.ResponseWriter, r *http.Request) (Principal, bool) {
	w.Header().Set("Cache-Control", "no-store")
	if s.customerAuth == nil {
		writeAPIError(w, r, 401, "UNAUTHENTICATED", "Authentication is required.", false)
		return Principal{}, false
	}
	p, err := s.customerAuth.Authenticate(r)
	if err != nil {
		s.customerAuth.writeError(w, r, err)
		return Principal{}, false
	}
	if !commerceUUID(p.CustomerAccountID) || !commerceUUID(p.OrganizationID) {
		s.customerAuth.writeError(w, r, ErrCustomerDependency)
		return Principal{}, false
	}
	return p, true
}
func commerceOwner(p Principal) map[string]any {
	return map[string]any{"customer_account_id": p.CustomerAccountID, "organization_id": p.OrganizationID}
}
func (s *Server) commerceQuoteHTTP(w http.ResponseWriter, r *http.Request) {
	q, ok := commerceQuery(r, "configuration_id", "region")
	if !ok || !commerceScopeValid(q.Get("configuration_id"), q.Get("region")) {
		commerceInvalid(w, r, 400)
		return
	}
	p, _ := s.workshopSimulationOwner(r)
	s.commerceCall(w, r, "quote", s.workshopQuoteInput(q.Get("configuration_id"), q.Get("region"), p), nil, "", nil)
}
func (s *Server) commerceCheckoutHTTP(w http.ResponseWriter, r *http.Request) {
	p, ok := s.commercePrincipal(w, r)
	if !ok {
		return
	}
	if len(r.Header.Values("Origin")) != 1 || len(r.Header.Values("X-CSRF-Token")) != 1 {
		w.Header().Set("Cache-Control", "no-store")
		s.customerAuth.writeError(w, r, ErrCustomerCSRF)
		return
	}
	if _, ok := commerceQuery(r); !ok || len(r.Header.Values("Idempotency-Key")) != 1 || !commerceUUID(r.Header.Get("Idempotency-Key")) {
		commerceInvalid(w, r, 400)
		return
	}
	media, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || media != "application/json" {
		commerceInvalid(w, r, 415)
		return
	}
	b, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 16*1024))
	if err != nil {
		status := 400
		var large *http.MaxBytesError
		if errors.As(err, &large) {
			status = 413
		}
		commerceInvalid(w, r, status)
		return
	}
	input, ok := commerceCheckoutInput(b)
	if !ok {
		commerceInvalid(w, r, 400)
		return
	}
	expected, _ := input["expected_mode"].(string)
	if (expected == workshopSimulationMode) != (s.workshopSimulation) || expected == "stripe_test" && !s.workshopTestCheckout {
		w.Header().Set("Cache-Control", "no-store")
		writeAPIError(w, r, 503, "COMMERCE_UNAVAILABLE", "Commerce is temporarily unavailable.", true)
		return
	}
	input["customer_account_id"], input["organization_id"], input["idempotency_key"] = p.CustomerAccountID, p.OrganizationID, r.Header.Get("Idempotency-Key")
	if s.workshopTestCheckout {
		input["expected_mode"] = "stripe_test"
	}
	s.commerceCall(w, r, "checkouts", input, nil, "", &p)
}

// An optional first page uses the same exact grant as the index route.
// A slow or empty index leaves the primary response usable.
func (s *Server) firstWorkshopArticleIndex(ctx context.Context, p Principal, configurationID, region string) (CatalogArticlesResponse, bool) {
	ctx, cancel := context.WithTimeout(ctx, firstWorkshopArticleIndexTimeout)
	defer cancel()
	configuration, err := s.resolvePaidCatalogScope(ctx, p, configurationID, region)
	if err != nil {
		return CatalogArticlesResponse{}, false
	}
	progressCtx, stopProgress := context.WithTimeout(ctx, ownedIndexStatusReadTimeout)
	progress, progressErr := s.catalog.CatalogArticleProgress(progressCtx, p, configuration.ID)
	stopProgress()
	if progressErr != nil {
		progress = nil
	}
	items, err := s.catalogIndexRows(ctx, p, configuration.ID, "", "")
	if err != nil || len(items) == 0 || ctx.Err() != nil {
		return CatalogArticlesResponse{}, false
	}
	readableArticlesFirst(items)
	var page *CatalogArticleIndexPage
	if len(items) > catalogIndexPageSize {
		items, page = (catalogIndexPageRequest{}).selectPage(items)
	}
	return CatalogArticlesResponse{
		Version: "v1", Items: items, Configuration: &configuration, Page: page,
		Complete: progress != nil && progress.Complete, Hydrating: catalogIndexHydrating(progress), Progress: progress,
	}, ctx.Err() == nil
}

// Reject duplicate, unknown, missing, nonstring and trailing JSON fields.
func commerceCheckoutInput(b []byte) (map[string]any, bool) {
	d := json.NewDecoder(bytes.NewReader(b))
	token, err := d.Token()
	if err != nil || token != json.Delim('{') {
		return nil, false
	}
	input := map[string]any{}
	for d.More() {
		k, e := d.Token()
		if e != nil {
			return nil, false
		}
		key, ok := k.(string)
		if !ok {
			return nil, false
		}
		if _, exists := input[key]; exists {
			return nil, false
		}
		switch key {
		case "configuration_id", "region", "terms_version", "expected_mode":
		default:
			return nil, false
		}
		var v string
		if d.Decode(&v) != nil {
			return nil, false
		}
		input[key] = v
	}
	if t, e := d.Token(); e != nil || t != json.Delim('}') {
		return nil, false
	}
	var trailing any
	if d.Decode(&trailing) != io.EOF {
		return nil, false
	}
	id, _ := input["configuration_id"].(string)
	region, _ := input["region"].(string)
	if expected, present := input["expected_mode"]; present && expected != "stripe_test" && expected != workshopSimulationMode {
		return nil, false
	}
	return input, (len(input) == 3 || len(input) == 4) && commerceScopeValid(id, region) && input["terms_version"] == "workshop-v1"
}
func (s *Server) commerceOrderHTTP(w http.ResponseWriter, r *http.Request) {
	p, ok := s.commercePrincipal(w, r)
	if !ok {
		return
	}
	if _, ok := commerceQuery(r); !ok || !commerceUUID(r.PathValue("order_id")) {
		commerceInvalid(w, r, 400)
		return
	}
	input := commerceOwner(p)
	input["order_id"] = r.PathValue("order_id")
	s.commerceCall(w, r, "orders/status", input, nil, "", nil)
}
func (s *Server) commerceLibraryHTTP(w http.ResponseWriter, r *http.Request) {
	p, ok := s.commercePrincipal(w, r)
	if !ok {
		return
	}
	q, ok := commerceQuery(r, "cursor", "limit")
	if !ok || len(q.Get("cursor")) > 2048 {
		commerceInvalid(w, r, 400)
		return
	}
	limit := libraryDefaultLimit
	if _, exists := q["limit"]; exists {
		var e error
		limit, e = strconv.Atoi(q.Get("limit"))
		if e != nil || limit < 1 || limit > 50 {
			commerceInvalid(w, r, 400)
			return
		}
	}
	input := commerceOwner(p)
	input["cursor"], input["limit"] = q.Get("cursor"), limit
	s.commerceCall(w, r, "library", input, nil, "", nil)
}
func (s *Server) firstWorkshopLibrary(ctx context.Context, session customerSession) *commerceLibrary {
	if !commerceUUID(session.AccountID) || !commerceUUID(session.OrganizationID) {
		return nil
	}
	input := commerceOwner(Principal{CustomerAccountID: session.AccountID, OrganizationID: session.OrganizationID})
	input["cursor"], input["limit"] = "", libraryDefaultLimit
	status, body, err := s.doCommerce(ctx, "library", input, nil, "")
	if err != nil || status != http.StatusOK {
		return nil
	}
	public, _ := commercePublicResult("library", status, body, input, s.commerceClient)
	library, ok := public.(commerceLibrary)
	if !ok {
		return nil
	}
	return &library
}
func (s *Server) commerceWebhookHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	sig := r.Header.Get("Stripe-Signature")
	if len(r.Header.Values("Stripe-Signature")) != 1 || len(sig) == 0 || len(sig) > 4096 {
		commerceInvalid(w, r, 400)
		return
	}
	b, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20))
	if err != nil || len(b) == 0 {
		status := 400
		var large *http.MaxBytesError
		if errors.As(err, &large) {
			status = 413
		}
		commerceInvalid(w, r, status)
		return
	}
	s.commerceCall(w, r, "stripe/webhook", nil, b, sig, nil)
}
func (s *Server) doCommerce(ctx context.Context, operation string, input map[string]any, body []byte, signature string) (int, []byte, error) {
	if s.commerceClient == nil {
		return 0, nil, errors.New("commerce client unavailable")
	}
	if body == nil {
		var err error
		body, err = json.Marshal(input)
		if err != nil {
			return 0, nil, err
		}
	}
	ctx, cancel := context.WithTimeout(ctx, commerceTimeout(operation))
	defer cancel()
	return s.commerceClient.Do(ctx, operation, body, signature)
}

func (s *Server) commerceCall(w http.ResponseWriter, r *http.Request, operation string, input map[string]any, raw []byte, signature string, checkoutPrincipal *Principal) {
	w.Header().Set("Cache-Control", "no-store")
	unavailable := func() { writeAPIError(w, r, 503, "COMMERCE_UNAVAILABLE", "Commerce is temporarily unavailable.", true) }
	status, result, err := s.doCommerce(r.Context(), operation, input, raw, signature)
	if err != nil {
		unavailable()
		return
	}
	if status < 200 || status >= 300 {
		code := commerceErrorCode(result)
		switch {
		case status == 400 && (code == "INVALID_REQUEST" || code == "INVALID_STRIPE_SIGNATURE" || code == "INVALID_CURSOR" || code == "INVALID_PAYMENT_EVENT"):
		case status == 404 && (code == "NOT_FOUND" || code == "CONFIGURATION_NOT_FOUND" || code == "ORDER_NOT_FOUND"):
		case status == 403 && (code == "ENTITLEMENT_REVOKED" || code == "CUSTOMER_ACCESS_REQUIRED" || code == "ENTITLEMENT_REQUIRED"):
		case status == 409 && (code == "IDEMPOTENCY_CONFLICT" || code == "TERMS_VERSION_REQUIRED" || code == "PAYMENT_FINANCIAL_CONFLICT" || code == "PAYMENT_EVENT_CONFLICT" || code == "PAYMENT_MODE_CONFLICT"):
		case status == 409 && operation == "checkouts" && code == "CONFIGURATION_MARKET_UNVERIFIED":
			writeAPIError(w, r, status, code, "The source market for this engine is unverified.", false)
			return
		case status == 409 && operation == "checkouts" && code == "CONFIGURATION_UNRESOLVED":
			writeAPIError(w, r, status, code, "Article coverage for this configuration is unverified.", false)
			return
		case status == 413 && code == "REQUEST_TOO_LARGE":
		default:
			unavailable()
			return
		}
		writeAPIError(w, r, status, code, "Commerce request could not be completed.", false)
		return
	}
	public, ok := commercePublicResult(operation, status, result, input, s.commerceClient)
	if !ok {
		unavailable()
		return
	}
	if checkout, isCheckout := public.(commerceCheckout); isCheckout && checkout.State == "owned" &&
		checkoutPrincipal != nil && input["expected_mode"] == workshopSimulationMode && s.paidCatalogEnabled() &&
		catalogReadPreferenceRequested(r, checkoutArticleIndexPreference) {
		if index, ready := s.firstWorkshopArticleIndex(r.Context(), *checkoutPrincipal, checkout.ConfigurationID, checkout.Region); ready {
			public = commerceCheckoutWithIndex{commerceCheckout: checkout, ArticleIndex: index}
			w.Header().Set("Preference-Applied", checkoutArticleIndexPreference)
		}
	}
	if library, isLibrary := public.(commerceLibrary); isLibrary {
		// The existing v1 schema is closed. Only clients opting in can
		// receive the extra catalog marker.
		if catalogReadPreferenceRequested(r, libraryCatalogEmptyPreference) {
			w.Header().Set("Preference-Applied", libraryCatalogEmptyPreference)
		} else {
			for index := range library.Items {
				library.Items[index].CatalogEmpty = nil
			}
		}
	}
	if status == 202 {
		w.Header().Set("Retry-After", "2")
	}
	writeJSON(w, status, public)
}
