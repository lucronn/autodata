package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

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
