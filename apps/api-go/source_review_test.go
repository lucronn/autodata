package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestStoredCatalogSourceJSONProjectionRecursivelyRedactsUnsafeFields(t *testing.T) {
	raw := json.RawMessage(`{
  "title": "Replace the filter",
  "steps": [{"text": "Remove the cover", "images": [{"alt": "safe figure", "url": "https://autoapitwo.vercel.app/figure.png"}]}],
  "nested": {"headers": {"Authorization": "Bearer synthetic-secret", "X-Api-Key": "synthetic-key"}, "safe": {"value": "keep this"}},
  "request": {"request_headers": {"Cookie": "session=synthetic-cookie"}, "signed_url": "https://autoapitwo.vercel.app/figure.png?X-Amz-Signature=synthetic-signature"},
  "navigation": {"href": "https://autoapitwo.vercel.app/provider/article/7", "next": "https://autoapitwo.vercel.app/provider/article/8"},
  "array": [{"content": "See https://autoapitwo.vercel.app/provider/article/9", "credentials": {"password": "synthetic-password"}}, {"value": "retained", "notes": "Bearer synthetic-bearer-secret"}]
}`)
	original := append(json.RawMessage(nil), raw...)

	format, content, err := renderStoredCatalogSource(raw, "", nil)
	if err != nil {
		t.Fatal(err)
	}
	if format != "json" {
		t.Fatalf("format = %q, want json", format)
	}
	for _, forbidden := range []string{
		"Authorization", "synthetic-secret", "X-Api-Key", "synthetic-key", "Cookie", "synthetic-cookie",
		"signed_url", "synthetic-signature", "autoapitwo.vercel.app", "provider/article", "synthetic-password", "synthetic-bearer-secret",
		"\"url\"", "\"href\"", "\"headers\"", "\"navigation\"",
	} {
		if strings.Contains(content, forbidden) {
			t.Fatalf("redacted source contains %q: %s", forbidden, content)
		}
	}
	for _, retained := range []string{"Replace the filter", "Remove the cover", "keep this", "retained", "safe figure"} {
		if !strings.Contains(content, retained) {
			t.Fatalf("redacted source lost safe value %q: %s", retained, content)
		}
	}
	if string(raw) != string(original) {
		t.Fatalf("source original mutated: got %s want %s", raw, original)
	}
}

func TestStoredCatalogSourceHTMLProjectionRedactsTextAndUnsafeAttributes(t *testing.T) {
	key := deriveCatalogImageReferenceKey("0123456789abcdef0123456789abcdef-test")
	localToken, err := sealCatalogImageStorageKey("procedure-images/source-figure", key)
	if err != nil {
		t.Fatal(err)
	}
	raw := json.RawMessage(`{"_embedded":{"data":{"article":{"content":"<html><body><p>See https://autoapitwo.vercel.app/provider/article/9</p><p>Bearer synthetic-html-secret</p><img src='/v1/catalog/images/` + localToken + `' alt='https://autoapitwo.vercel.app/provider/figure' onerror='fetch(https://autoapitwo.vercel.app/secret)'><a href='https://autoapitwo.vercel.app/provider/article/10'>provider link</a></body></html>"}}}}`)

	format, content, err := renderStoredCatalogSource(raw, "https://autoapitwo.vercel.app/article/1", key)
	if err != nil {
		t.Fatal(err)
	}
	if format != "html" {
		t.Fatalf("format = %q, want html", format)
	}
	for _, forbidden := range []string{"autoapitwo.vercel.app", "provider/article", "synthetic-html-secret", "onerror=", "fetch(", "href='https://"} {
		if strings.Contains(content, forbidden) {
			t.Fatalf("sanitized source contains %q: %s", forbidden, content)
		}
	}
	if !strings.Contains(content, `/v1/catalog/images/`+localToken) || !strings.Contains(content, "provider link") {
		t.Fatalf("sanitized source lost safe content or local image path: %s", content)
	}
}

func TestStoredCatalogSourceOmitsUnlocalizedImages(t *testing.T) {
	raw := json.RawMessage(`{"_embedded":{"data":{"article":{"content":"<html><body><p>Keep this paragraph</p><img src='/api/v1/content/carids/1/figure.png'><img src='data:image/png;base64,AA=='></body></html>"}}}}`)
	key := deriveCatalogImageReferenceKey("0123456789abcdef0123456789abcdef-test")
	_, content, err := renderStoredCatalogSource(raw, "https://autoapitwo.vercel.app/article/1", key)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(content, "Keep this paragraph") || strings.Contains(content, "<img") || strings.Contains(content, "/v1/catalog/images/") || strings.Contains(content, "autoapitwo.vercel.app") {
		t.Fatalf("unlocalized source image was retained or provider token was minted: %s", content)
	}
}

func TestStoredCatalogSourceProjectionReturnsErrorForMalformedJSON(t *testing.T) {
	if _, _, err := renderStoredCatalogSource(json.RawMessage(`{"broken"`), "", nil); err == nil {
		t.Fatal("malformed stored source must fail closed")
	}
}

func TestStoredCatalogSourceRequiresAuthentication(t *testing.T) {
	server := NewServerWithCatalogStore(staticReadiness{}, HeaderAuthenticator{}, newMemoryRequestStore(), sourceReviewCatalogFixtureStore())
	request := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/vehicle-1/articles/article-1/source", nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnauthorized)
	}
}

func TestStoredCatalogSourceHTMLMetadataRedactsProviderLocatorAndSecrets(t *testing.T) {
	server := catalogServerForSourceReview(sourceReviewCatalogFixtureStore())
	request := httptest.NewRequest(http.MethodGet, "/v1/catalog/vehicles/vehicle-1/articles/article-1/source?evidence_id=Bearer%20synthetic-evidence-secret&source_locator=https%3A%2F%2Fautoapitwo.vercel.app%2Fprovider%2Farticle%2F1", nil)
	request.Header.Set("Authorization", "Bearer local:org-1:dataset_viewer")
	request.Header.Set("Accept", "text/html")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d: %s", response.Code, http.StatusOK, response.Body.String())
	}
	for _, forbidden := range []string{"autoapitwo.vercel.app", "synthetic-evidence-secret"} {
		if strings.Contains(response.Body.String(), forbidden) {
			t.Fatalf("HTML metadata leaked %q: %s", forbidden, response.Body.String())
		}
	}
}

func catalogServerForSourceReview(store CatalogStore) *Server {
	return NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{
		principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}},
	}, newMemoryRequestStore(), store)
}

func sourceReviewCatalogFixtureStore() *memoryCatalogStore {
	store := newMemoryCatalogStore()
	store.PutArticle(CatalogArticle{
		ID: "article-1", VehicleID: "vehicle-1", ContentStatus: "content_complete",
		SourceOriginal: json.RawMessage(`{"title":"stored"}`),
		Provenance:     []CatalogProvenance{{ID: "source-1", Version: "v1"}},
	})
	return store
}

func TestSourceReviewQueueRequiresReviewerRole(t *testing.T) {
	store := newMemorySourceReviewStore()
	store.put(SourceReviewItemRecord{SourceReviewItemID: "review-1", ItemKey: "source-review:one", ItemKind: "conflict", ReasonCode: "article_similarity", Status: "pending"})
	server := NewServerWithSourceReviewStore(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		store,
	)

	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/source-review-items", nil))

	if response.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusForbidden)
	}
}

func TestSourceReviewQueueListsPendingItemsAndReviewsThemIdempotently(t *testing.T) {
	store := newMemorySourceReviewStore()
	store.put(SourceReviewItemRecord{
		SourceReviewItemID: "review-1",
		ItemKey:            "source-review:one",
		ItemKind:           "conflict",
		ReasonCode:         "article_similarity",
		Status:             "pending",
		SourceSnapshotIDs:  []string{"snapshot-1"},
		EvidenceIDs:        []string{"evidence-1"},
		Payload:            map[string]any{"similarity": 0.987},
	})
	auth := &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"data_reviewer"}}}
	server := NewServerWithSourceReviewStore(staticReadiness{}, auth, newMemoryRequestStore(), store)

	listResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(listResponse, httptest.NewRequest(http.MethodGet, "/source-review-items?status=pending&limit=10", nil))
	if listResponse.Code != http.StatusOK {
		t.Fatalf("list status = %d, want %d", listResponse.Code, http.StatusOK)
	}
	var list struct {
		Items []SourceReviewItemRecord `json:"items"`
	}
	if err := json.NewDecoder(listResponse.Body).Decode(&list); err != nil {
		t.Fatal(err)
	}
	if len(list.Items) != 1 || list.Items[0].SourceReviewItemID != "review-1" {
		t.Fatalf("list = %#v, want review-1", list.Items)
	}

	body := bytes.NewBufferString(`{"decision":"approve","reason":"confirmed same article"}`)
	reviewRequest := httptest.NewRequest(http.MethodPost, "/source-review-items/review-1/review", body)
	reviewRequest.Header.Set("Content-Type", "application/json")
	reviewResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(reviewResponse, reviewRequest)
	if reviewResponse.Code != http.StatusOK {
		t.Fatalf("review status = %d, want %d", reviewResponse.Code, http.StatusOK)
	}

	replayBody := bytes.NewBufferString(`{"decision":"approve","reason":"same decision"}`)
	replayRequest := httptest.NewRequest(http.MethodPost, "/source-review-items/review-1/review", replayBody)
	replayRequest.Header.Set("Content-Type", "application/json")
	replayResponse := httptest.NewRecorder()
	server.Handler().ServeHTTP(replayResponse, replayRequest)
	if replayResponse.Code != http.StatusOK {
		t.Fatalf("replay status = %d, want %d", replayResponse.Code, http.StatusOK)
	}

	item, err := store.Get("review-1", Principal{OrganizationID: "org-1", Roles: []string{"data_reviewer"}})
	if err != nil {
		t.Fatal(err)
	}
	if item.Status != "approved" || item.ReviewReason != "confirmed same article" {
		t.Fatalf("reviewed item = %#v", item)
	}
}

func TestSourceReviewStoreNormalizesDecisionAliases(t *testing.T) {
	store := newMemorySourceReviewStore()
	store.put(SourceReviewItemRecord{SourceReviewItemID: "review-1", Status: "pending"})

	item, err := store.Review("review-1", SourceReviewReviewInput{Decision: "approve"}, Principal{OrganizationID: "org-1"})
	if err != nil {
		t.Fatal(err)
	}
	if item.Status != "approved" {
		t.Fatalf("status = %q, want approved", item.Status)
	}
}
