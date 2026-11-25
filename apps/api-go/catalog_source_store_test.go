package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
	"time"
)

type paidSourceViewFixture struct {
	*paidMediaCatalog
	reads int
}

func (s *paidSourceViewFixture) paidCatalogSourceView(_ context.Context, configuration, article, revision string, _ bool) (PaidArticleIdentity, CatalogArticleView, CatalogSourceContent, error) {
	s.reads++
	if configuration != s.configuration.ID || article != s.identity.CanonicalArticleID || revision != *s.source.SourceRevisionID {
		return PaidArticleIdentity{}, CatalogArticleView{}, CatalogSourceContent{}, ErrCatalogNotFound
	}
	return s.identity, s.view, s.source, nil
}

func TestPaidCatalogSourceUsesSelectedProjectionAndRechecksGrant(t *testing.T) {
	for _, revoked := range []bool{false, true} {
		name := "authorized source"
		if revoked {
			name = "grant revoked during read"
		}
		t.Run(name, func(t *testing.T) {
			s, c, grant, _, p, ref := paidMediaFixture()
			currentRevision := "99999999-9999-4999-8999-999999999999"
			c.identity.CurrentSourceRevisionID = &currentRevision
			c.view.Article.SourceRevisionID = &currentRevision
			store := &paidSourceViewFixture{paidMediaCatalog: c}
			s.catalog = store
			if revoked {
				grant.errorAfterFirst = ErrVehicleGrantRevoked
			}
			path := catalogPinnedSourceURL(ref.ConfigurationID, ref.CanonicalArticleID, c.source.SourceRevisionID)
			request := httptest.NewRequest(http.MethodGet, path, nil)
			request.SetPathValue("vehicle_id", ref.ConfigurationID)
			request.SetPathValue("article_id", ref.CanonicalArticleID)
			request.Header.Set("Accept", "application/json")
			response := httptest.NewRecorder()
			s.serveCatalogSource(response, request, p)
			if store.reads != 1 || c.viewCalls.Load() != 0 || c.identityCalls.Load() != 0 || c.sourceCalls.Load() != 0 || grant.calls.Load() != 2 {
				t.Fatalf("narrow=%d, full=%d, identity=%d, source=%d, grants=%d", store.reads, c.viewCalls.Load(), c.identityCalls.Load(), c.sourceCalls.Load(), grant.calls.Load())
			}
			if revoked {
				if response.Code != http.StatusForbidden || strings.Contains(response.Body.String(), ref.AssetID) || strings.Contains(response.Body.String(), "/v1/catalog/images/") {
					t.Fatal("revoked source response", response.Code, response.Body.String())
				}
				return
			}
			var result CatalogSourceContentResponse
			if response.Code != http.StatusOK || json.Unmarshal(response.Body.Bytes(), &result) != nil || len(result.Images) != 1 || result.Source.URL != path {
				t.Fatal("invalid pinned source response", response.Code, response.Body.String())
			}
			token := strings.TrimPrefix(result.Images[0].URL, "/v1/catalog/images/")
			got, err := openPaidCatalogImageReference(token, s.catalogImageKey, time.Now())
			if err != nil || got.SelectedSourceRevisionID != *c.source.SourceRevisionID || got.AnchorSourceRevisionID != currentRevision || !samePaidCatalogID(got.AnchorCanonicalRevisionID, c.view.Article.CanonicalRevisionID) {
				t.Fatal("source capability changed the selected or current anchor", got, err)
			}
		})
	}
}

func TestCatalogSourceProjectionPreservesDisplayIdentity(t *testing.T) {
	document := []byte(`{"schema_version":1,"normalization_version":"ordered-article-v1","blocks":[{"type":"ordered_list","block_id":"steps","start":3,"items":[{"number":4,"text":"Check the pump.","blocks":[{"type":"image","block_id":"figure-4","image_id":"private/image/4","source_locator":"page:2","evidence_ids":["source:fixture"],"url":"https://private.invalid/figure"}]}]}]}`)
	images := []byte(`[{"image_id":"private/image/4","storage_key":"private/key","alt":"Pump figure"}]`)
	steps := []byte(`[{"action":"Check the pump.","images":[{"image_id":"private/image/4","storage_key":"private/key"}]}]`)
	source := CatalogSourceContent{SourceRevisionID: stringPointer("44444444-4444-4444-8444-444444444444")}
	const text = "Check the pump."
	var before CatalogArticle
	if err := json.Unmarshal(document, &before.Document); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(images, &before.Images); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(steps, &before.Steps); err != nil {
		t.Fatal(err)
	}
	before.Body, before.SourceRevisionID, before.ContentOrigin = text, source.SourceRevisionID, stringPointer("source")
	before.Document = publicCatalogDocument(before.Document)
	view := lifecycleArticle(before)
	result, err := decodeCatalogSourceProjection(source, document, images, text, steps, nil)
	if err != nil || result.ViewRevision == nil || !samePaidCatalogID(result.ViewRevision, view.ViewRevision) || !reflect.DeepEqual(result.Document, before.Document) {
		t.Fatal("scoped decoding changed source document or view revision", err)
	}
	raw, err := json.Marshal(result.Document)
	if err != nil || !strings.Contains(string(raw), `"block_id":"figure-4"`) || !strings.Contains(string(raw), `"source_locator":"page:2"`) || strings.Contains(string(raw), "https://private.invalid") {
		t.Fatal("scoped decoding lost figure focus or exposed a provider URL", err)
	}
}
