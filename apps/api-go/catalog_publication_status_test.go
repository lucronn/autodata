package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

const publicationTestJob = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const publicationOtherAnchor = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

type publicationStatusFixture struct {
	*paidMediaCatalog
	status *catalogPublicationStatusResponse
	err    error
	calls  int
	scope  [4]string
}

func (s *publicationStatusFixture) paidPublicationStatus(_ context.Context, config, article, job, source string) (*catalogPublicationStatusResponse, error) {
	s.calls++
	s.scope = [4]string{config, article, job, source}
	return s.status, s.err
}

func publicationStatusRequest(t *testing.T, s *Server, p Principal, ref paidCatalogImageReference) *http.Request {
	t.Helper()
	r := paidMediaRaceRequest(t, s, p, ref, http.MethodGet)
	r.Header.Set("Prefer", publicationStatusPreference+", "+finishPublishedBodyPreference)
	r.Header.Set(publicationJobHeader, publicationTestJob)
	r.Header.Set(publicationSourceHeader, ref.SelectedSourceRevisionID)
	return r
}

func TestPaidCatalogPublicationStatusNegotiation(t *testing.T) {
	for _, tc := range []struct {
		name, variant, preference, retry, support string
		compact                                   bool
		metadata, fullReads, grantCalls           int
		code                                      int
	}{
		{name: "advertised on ordinary source detail", variant: "ordinary", retry: "1", support: "supported", fullReads: 1, grantCalls: 1, code: 200},
		{name: "matching active source avoids full view and media reads", preference: publicationStatusPreference, compact: true, metadata: 1, grantCalls: 1, code: 200},
		{name: "preserves actual retry hint", variant: "retry", preference: publicationStatusPreference, retry: "7", compact: true, metadata: 1, grantCalls: 1, code: 200},
		{name: "published response follows ordinary delivery", variant: "published", preference: finishPublishedBodyPreference, metadata: 1, fullReads: 1, grantCalls: 1, code: 200},
		{name: "changed job falls back", variant: "new job", retry: "1", support: "supported", metadata: 1, fullReads: 1, grantCalls: 1, code: 200},
		{name: "changed source falls back", variant: "new source", retry: "1", support: "supported", fullReads: 1, grantCalls: 1, code: 200},
		{name: "duplicate job header falls back", variant: "duplicate job", retry: "1", support: "supported", fullReads: 1, grantCalls: 1, code: 200},
		{name: "noncanonical job header falls back", variant: "uppercase", retry: "1", support: "supported", fullReads: 1, grantCalls: 1, code: 200},
		{name: "unsupported store falls back", variant: "unsupported", retry: "1", fullReads: 1, grantCalls: 1, code: 200},
		{name: "OpenDemo uses normal detail", variant: "demo", retry: "1", fullReads: 1, code: 200},
		{name: "missing session denies before lookup", variant: "anonymous", code: 401},
		{name: "wrong region denies before lookup", variant: "wrong region", code: 404},
		{name: "revoked grant denies before lookup", variant: "revoked grant", grantCalls: 1, code: 403},
		{name: "withdrawal during lookup denies without body", variant: "withdrawn", metadata: 1, grantCalls: 1, code: 410},
		{name: "quarantine during lookup denies without body", variant: "quarantined", metadata: 1, grantCalls: 1, code: 404},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, catalog, grant, reader, principal, ref := paidMediaFixture()
			article := catalog.view.Article
			article.ContentOrigin = stringPointer("source")
			article.CanonicalRevisionID = nil
			article.Document = &CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "paragraph", Text: "Inspect the pump."}}}
			article.Processing = &CatalogProcessing{JobID: publicationTestJob, State: "rewriting"}
			store := &publicationStatusFixture{paidMediaCatalog: catalog, status: &catalogPublicationStatusResponse{
				ArticleID: ref.CanonicalArticleID, JobID: publicationTestJob, SourceRevisionID: ref.SelectedSourceRevisionID, State: "rewriting",
			}}
			s.catalog = store
			request := publicationStatusRequest(t, s, principal, ref)
			switch tc.variant {
			case "ordinary":
				request.Header.Del("Prefer")
			case "retry":
				seconds := 7
				store.status.RetryAfterSeconds = &seconds
			case "published":
				store.status = nil
				article.ContentOrigin = stringPointer("canonical")
				article.CanonicalRevisionID = ref.AnchorCanonicalRevisionID
				article.Processing.State = "completed"
			case "new job":
				store.status.JobID = publicationOtherAnchor
				article.Processing.JobID = publicationOtherAnchor
			case "new source":
				request.Header.Set(publicationSourceHeader, publicationOtherAnchor)
			case "duplicate job":
				request.Header.Add(publicationJobHeader, publicationTestJob)
			case "uppercase":
				request.Header.Set(publicationJobHeader, strings.ToUpper(publicationTestJob))
			case "unsupported":
				s.catalog = catalog
			case "demo":
				request.URL.RawQuery = "demo=1"
				s.workshopOpenDemoHost = request.Host
				request.Header.Del("Cookie")
			case "anonymous":
				request.Header.Del("Cookie")
			case "wrong region":
				request.URL.RawQuery = "region=CA"
			case "revoked grant":
				grant.err = ErrVehicleGrantRevoked
			case "withdrawn":
				store.err = ErrCatalogWithdrawn
			case "quarantined":
				store.err = ErrCatalogNotFound
			}
			catalog.view.Article = lifecycleArticle(article)
			response := httptest.NewRecorder()
			s.Handler().ServeHTTP(response, request)
			if response.Code != tc.code || response.Header().Get("Preference-Applied") != tc.preference ||
				response.Header().Get("Retry-After") != tc.retry || response.Header().Get(publicationCheckHeader) != tc.support ||
				response.Header().Get("Cache-Control") != "private, no-store" {
				t.Fatalf("unexpected status and headers: %d %v", response.Code, response.Header())
			}
			if store.calls != tc.metadata || int(catalog.viewCalls.Load()) != tc.fullReads || int(grant.calls.Load()) != tc.grantCalls || reader.calls.Load() != 0 {
				t.Fatalf("unexpected metadata=%d view=%d grant=%d image=%d calls", store.calls, catalog.viewCalls.Load(), grant.calls.Load(), reader.calls.Load())
			}
			if store.calls == 1 && store.scope != [4]string{ref.ConfigurationID, ref.CanonicalArticleID, publicationTestJob, ref.SelectedSourceRevisionID} {
				t.Fatalf("metadata lookup escaped exact scope: %v", store.scope)
			}
			body := response.Body.String()
			if tc.compact {
				expected := map[string]any{"version": "v1", "article_id": ref.CanonicalArticleID, "job_id": publicationTestJob, "source_revision_id": ref.SelectedSourceRevisionID, "state": "rewriting"}
				if tc.retry != "" {
					expected["retry_after_seconds"] = 7
				}
				var fields map[string]json.RawMessage
				if err := json.Unmarshal(response.Body.Bytes(), &fields); err != nil || len(fields) != len(expected) {
					t.Fatalf("unexpected compact payload: %s (%v)", body, err)
				}
				for key, value := range expected {
					want, _ := json.Marshal(value)
					if string(fields[key]) != string(want) {
						t.Fatalf("compact field %s: %s != %s", key, fields[key], want)
					}
				}
				if catalog.sourceCalls.Load() != 0 {
					t.Fatal("compact response loaded source media membership")
				}
			} else if tc.fullReads == 1 {
				if !strings.Contains(body, "Inspect the pump.") || (tc.variant != "demo" && !strings.Contains(body, "/v1/catalog/images/v2.")) {
					t.Fatalf("ordinary response lost content or authorized media: %s", body)
				}
			} else if strings.Contains(body, publicationTestJob) || strings.Contains(body, "Inspect the pump.") || strings.Contains(body, "/v1/catalog/images/v2.") {
				t.Fatalf("denial leaked protected detail: %s", body)
			}
		})
	}
}
