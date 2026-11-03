package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type r3Fixture struct {
	t                                                 *testing.T
	pool                                              *pgxpool.Pool
	client                                            *HTTPIngestionClient
	servers                                           []*httptest.Server
	vehicle, article, other, provider, control, token string
	phases                                            map[string]any
	views                                             []CatalogArticle
	assertions                                        map[string]bool
	extra                                             map[string]any
}

func r3Setup(t *testing.T) *r3Fixture {
	t.Helper()
	if os.Getenv("AUTODATA_CATALOG_INTEGRATION_REQUIRED") != "1" {
		t.Skip("required fixture acceptance is a separate explicit run")
	}
	if os.Getenv("AUTODATA_LIFECYCLE_TEST") != "1" {
		t.Fatal("lifecycle fixture flag required")
	}
	dsn := os.Getenv("AUTODATA_CATALOG_TEST_DSN")
	u, err := url.Parse(dsn)
	if err != nil || u.Scheme != "postgres" || u.Host != "postgres:5432" || u.User == nil || u.User.Username() != "lifecycle_test" || u.Query().Get("sslmode") != "disable" || len(u.Query()) != 1 || !regexp.MustCompile(`^/lifecycle_test_[a-f0-9]{32}$`).MatchString(u.Path) {
		t.Fatal("invalid isolated database target")
	}
	password, ok := u.User.Password()
	if !ok || password != "lifecycle_test_only" {
		t.Fatal("invalid fixture credential")
	}
	f := &r3Fixture{t: t, vehicle: os.Getenv("AUTODATA_CATALOG_TEST_VEHICLE_ID"), article: os.Getenv("AUTODATA_CATALOG_TEST_ARTICLE_ID"), other: os.Getenv("AUTODATA_CATALOG_TEST_OTHER_ARTICLE_ID"), provider: os.Getenv("AUTODATA_CATALOG_TEST_PROVIDER"), control: os.Getenv("AUTODATA_CATALOG_TEST_CONTROL_URL"), token: os.Getenv("AUTODATA_CATALOG_TEST_CONTROL_TOKEN"), phases: map[string]any{}, assertions: map[string]bool{}, extra: map[string]any{}}
	uuidPattern := regexp.MustCompile(`^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`)
	for _, id := range []string{f.vehicle, f.article, f.other} {
		if !uuidPattern.MatchString(id) {
			t.Fatal("fixture UUID required")
		}
	}
	if f.provider != "bankone" && f.provider != "banktwo" {
		t.Fatal("fixture provider required")
	}
	if f.token == "" {
		t.Fatal("control token required")
	}
	if !regexp.MustCompile(`^[a-f0-9]{40}$`).MatchString(os.Getenv("AUTODATA_CATALOG_TEST_CANDIDATE_SHA")) {
		t.Fatal("candidate SHA required")
	}
	ensureURL := os.Getenv("AUTODATA_CATALOG_TEST_ENSURE_URL")
	for _, raw := range []string{ensureURL, f.control} {
		v, e := url.Parse(raw)
		if e != nil || v.Scheme != "http" || v.Hostname() != "127.0.0.1" || v.Port() == "" || v.User != nil || v.RawQuery != "" || v.Fragment != "" || v.Path != "" {
			t.Fatal("only explicit loopback fixture URLs allowed")
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	f.pool, err = pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(f.pool.Close)
	if err = f.pool.Ping(ctx); err != nil {
		t.Fatal(err)
	}
	f.client, err = NewHTTPIngestionClient(ensureURL, "fixture-r3-internal", 2*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	for range 2 {
		server := NewServerWithCatalogStore(staticReadiness{}, &fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}}, newMemoryRequestStore(), newPostgresCatalogStore(f.pool))
		server.ingestionClient = f.client
		api := httptest.NewServer(server.Handler())
		f.servers = append(f.servers, api)
		t.Cleanup(api.Close)
	}
	t.Cleanup(func() {
		views := f.views
		if t.Name() == "TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP" {
			views = nil
			for _, a := range f.views {
				if r3Origin(a, "source") {
					views = append(views, a)
				}
			}
		}
		observations := []map[string]any{}
		for _, a := range views {
			observations = append(observations, r3EvidenceArticle(a))
		}
		payload := map[string]any{"phase_snapshots": f.phases, "observed_views": observations, "assertion_results": f.assertions}
		for k, v := range f.extra {
			payload[k] = v
		}
		raw, _ := json.MarshalIndent(payload, "", "  ")
		if err := os.WriteFile(filepath.Join(os.Getenv("AUTODATA_CATALOG_TEST_CASE_DIR"), "go-measurement.json"), raw, 0644); err != nil {
			t.Error(err)
		}
	})
	return f
}
func (f *r3Fixture) check(key string, ok bool) {
	f.t.Helper()
	f.assertions[key] = ok
	if !ok {
		f.t.Fatalf("invariant failed: %s", key)
	}
}
func (f *r3Fixture) controlCall(method, path string) map[string]any {
	f.t.Helper()
	r, err := http.NewRequest(method, f.control+"/r3-fixture/"+path, nil)
	if err != nil {
		f.t.Fatal(err)
	}
	r.Header.Set("X-R3-Fixture-Token", f.token)
	c := &http.Client{Timeout: 2 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	resp, err := c.Do(r)
	if err != nil {
		f.t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil || resp.StatusCode != 200 {
		f.t.Fatalf("control %s: status %d %s %v", path, resp.StatusCode, raw, err)
	}
	var body map[string]any
	if json.Unmarshal(raw, &body) != nil {
		f.t.Fatal("control JSON")
	}
	return body
}
func (f *r3Fixture) wait(path string, predicate func(map[string]any) bool) map[string]any {
	f.t.Helper()
	deadline := time.Now().Add(15 * time.Second)
	for time.Now().Before(deadline) {
		snapshot := f.controlCall("GET", path)
		if predicate(snapshot) {
			return snapshot
		}
		time.Sleep(20 * time.Millisecond)
	}
	f.t.Fatalf("deadline waiting for %s", path)
	return nil
}
func (f *r3Fixture) get(server int, suffix string) (int, CatalogArticle, []byte) {
	f.t.Helper()
	r, _ := http.NewRequest("GET", f.servers[server%2].URL+"/v1/catalog/vehicles/"+f.vehicle+"/articles"+suffix, nil)
	r.Header.Set("Accept", "application/json")
	c := &http.Client{Timeout: 3 * time.Second}
	started := time.Now()
	resp, err := c.Do(r)
	if err != nil {
		f.t.Fatal(err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		f.t.Fatal(err)
	}
	if time.Since(started) > 3*time.Second {
		f.t.Fatal("read exceeded bound")
	}
	var envelope CatalogArticleResponse
	json.Unmarshal(body, &envelope)
	if suffix != "" && resp.Header.Get("Cache-Control") != "private, no-store" {
		f.t.Fatalf("missing no-store: %s", body)
	}
	return resp.StatusCode, envelope.Article, body
}
func (f *r3Fixture) detail() CatalogArticle {
	status, a, body := f.get(0, "/"+f.article)
	if status != 200 {
		f.t.Fatalf("detail %d %s", status, body)
	}
	f.views = append(f.views, a)
	return a
}
func (f *r3Fixture) snapshot(phase string, a CatalogArticle) map[string]any {
	s := f.controlCall("GET", "snapshot")
	if a.ID != "" {
		s["article"] = r3EvidenceArticle(a)
	}
	f.phases[phase] = s
	return s
}
func r3Int(m map[string]any, key string) int {
	if n, ok := m[key].(float64); ok {
		return int(n)
	}
	return -1
}
func r3Map(m map[string]any, key string) map[string]any { v, _ := m[key].(map[string]any); return v }
func r3Origin(a CatalogArticle, origin string) bool {
	return a.ContentOrigin != nil && *a.ContentOrigin == origin
}
func r3EvidenceArticle(a CatalogArticle) map[string]any {
	raw, _ := json.Marshal(a)
	var evidence map[string]any
	json.Unmarshal(raw, &evidence)
	// Evidence retains optional public fields explicitly and separately records
	// the durable job identity for comparison with PostgreSQL snapshots.
	for key, value := range r3Projection(a) {
		evidence[key] = value
	}
	if a.Processing != nil {
		evidence["job_id"] = a.Processing.JobID
		evidence["processing_state"] = a.Processing.State
	}
	return evidence
}
func r3Projection(a CatalogArticle) map[string]any {
	return map[string]any{"document": a.Document, "body": a.Body, "steps": a.Steps, "images": a.Images}
}
func r3ZeroDelta(before, after map[string]any) bool {
	for _, key := range []string{"provider_calls", "source_calls", "asset_calls"} {
		for _, p := range []string{"bankone", "banktwo"} {
			if r3Int(r3Map(before, key), p) != r3Int(r3Map(after, key), p) {
				return false
			}
		}
	}
	for _, key := range []string{"entered", "completed"} {
		if r3Int(r3Map(before, "ensure"), key) != r3Int(r3Map(after, "ensure"), key) {
			return false
		}
	}
	return r3Int(before, "model_calls") == r3Int(after, "model_calls") && r3Int(r3Map(before, "proxy"), "request_received") == r3Int(r3Map(after, "proxy"), "request_received") && r3Int(r3Map(after, "ensure"), "active") == 0
}
func (f *r3Fixture) schedule() CatalogArticle {
	status, a, body := f.get(0, "/"+f.article)
	if status != 202 || a.Processing == nil || a.Processing.JobID == "" || a.Document != nil || a.Complete {
		f.t.Fatalf("cold scheduling: %d %s", status, body)
	}
	return a
}
func (f *r3Fixture) published() CatalogArticle {
	f.wait("publication", func(m map[string]any) bool { return r3Map(m, "article")["canonical_revision_id"] != nil })
	return f.detail()
}
func TestPostgresCatalogLifecycleColdHTTPRaceOneJob(t *testing.T) {
	f := r3Setup(t)
	f.snapshot("initial", CatalogArticle{})
	start := make(chan struct{})
	var wg sync.WaitGroup
	results := make(chan CatalogArticle, 20)
	for i := range 20 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			status, a, body := f.get(i, "/"+f.article)
			if status != 202 {
				t.Errorf("cold %d %s", status, body)
				return
			}
			results <- a
		}()
	}
	close(start)
	wg.Wait()
	close(results)
	job := ""
	count := 0
	for a := range results {
		count++
		f.views = append(f.views, a)
		if a.Processing == nil || a.Processing.JobID == "" || a.Document != nil || a.Body != "" || a.Complete || a.ContentOrigin != nil || a.Availability != "pending" {
			t.Fatalf("invalid pending article %#v", a)
		}
		if job == "" {
			job = a.Processing.JobID
		}
		if job != a.Processing.JobID {
			t.Fatal("different durable jobs")
		}
	}
	f.check("cold_public_202", count == 20)
	f.check("cold_same_job_id", job != "")
	payload, _ := json.Marshal(map[string]any{"scope": "article", "vehicle_id": f.vehicle, "canonical_article_id": f.article, "idempotency_key": "r3-direct:" + f.article})
	for range 20 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			incoming := httptest.NewRequest("POST", "/", bytes.NewReader(payload)).WithContext(ctx)
			status, raw, err := f.client.Do(incoming, "/v1/catalog/ensure", payload, "r3-direct:"+f.article)
			var ack CatalogScheduleResult
			json.Unmarshal(raw, &ack)
			if err != nil || (status != 200 && status != 202) || ack.JobID != job {
				t.Errorf("internal race status %d job %s error %v", status, ack.JobID, err)
			}
		}()
	}
	wg.Wait()
	s := f.snapshot("cold_done", f.views[0])
	counts := r3Map(s, "counts")
	f.check("one_durable_article_job", r3Int(counts, "article_jobs") == 1)
	f.check("twenty_real_internal_ensures", r3Int(r3Map(s, "ensure"), "entered") >= 21)
	f.check("zero_cold_external_calls", r3Int(s, "model_calls") == 0 && r3Int(r3Map(s, "source_calls"), "bankone") == 0 && r3Int(r3Map(s, "source_calls"), "banktwo") == 0 && r3Int(counts, "source_revisions") == 0)
	f.verifyScopeAndLegacyDescriptors()
	f.verifyConfigurationScope()
}
func TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP(t *testing.T) {
	f := r3Setup(t)
	initial := f.schedule()
	f.controlCall("POST", "start-workers")
	f.wait("model-held", func(m map[string]any) bool {
		return r3Int(m, "downstream_waiting") == 1 && r3Int(m, "upstream_completed") == 1 && m["response_captured"] == true && r3Int(m, "downstream_completed") == 0
	})
	source := f.detail()
	before := f.snapshot("model_held", source)
	f.check("actual_model_response_held", r3Int(before, "model_calls") == 1 && source.Processing.State == "rewriting" && source.CanonicalRevisionID == nil && source.SourceRevisionID != nil)
	var wg sync.WaitGroup
	observed := make(chan CatalogArticle, 20)
	for i := range 20 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			status, a, body := f.get(i, "/"+f.article)
			if status != 200 || !r3Origin(a, "source") || a.Complete || a.ViewRevision == nil || *a.ViewRevision != *source.ViewRevision || a.SourceRevisionID == nil || *a.SourceRevisionID != *source.SourceRevisionID || a.Processing.JobID != initial.Processing.JobID || !strings.Contains(string(body), "Remove the pump.") {
				t.Errorf("held source invalid %d %s", status, body)
				return
			}
			observed <- a
		}()
	}
	wg.Wait()
	close(observed)
	reads := 0
	for a := range observed {
		f.views = append(f.views, a)
		reads++
	}
	if reads != 20 {
		t.Fatal("missing source observations")
	}

	_, _, raw := f.get(0, "/"+f.article+"/source?source_revision_id="+*source.SourceRevisionID)
	if !strings.Contains(string(raw), "Remove the pump.") {
		t.Fatal("missing ordered source")
	}
	status, _, _ := f.get(0, "")
	if status != 200 {
		t.Fatal("list failed")
	}
	after := f.snapshot("source_reads_done", source)
	f.check("readable_source_during_hold", r3Int(r3Map(after, "proxy"), "downstream_waiting") == 1 && len(source.Images) == 1 && source.Images[0].ImageID != "" && source.Images[0].AssetID == source.Images[0].ImageID && (strings.HasPrefix(source.Images[0].URL, "/v1/catalog/images/") || source.Images[0].URL == "" && strings.Contains(string(raw), "Image unavailable")))
	f.check("active_read_zero_ensure_provider_model_delta", r3ZeroDelta(before, after))
	f.controlCall("POST", "release-model")
	canonical := f.published()
	s := f.snapshot("published", canonical)
	f.check("validated_canonical_after_release", canonical.Complete && r3Origin(canonical, "canonical") && canonical.Processing.JobID == initial.Processing.JobID && strings.Contains(canonical.Body, "Take off the pump.") && r3Int(r3Map(s, "counts"), "published_revisions") == 1 && r3Int(r3Map(s, "counts"), "publication_events") == 1)
	f.verifyManagedQuarantine()
}
func TestPostgresCatalogLifecycleAtomicPublication(t *testing.T) {
	f := r3Setup(t)
	f.schedule()
	f.controlCall("POST", "start-workers")
	f.wait("publication-barrier", func(m map[string]any) bool { return m["arrived"] == true })
	defer f.controlCall("POST", "release-publication")
	source := f.detail()
	before := f.snapshot("precommit", source)
	var sourceDoc, sourceSteps, sourceImages []byte
	var sourceBody string
	if err := f.pool.QueryRow(context.Background(), `SELECT source_document,source_body,source_steps,source_images FROM canonical_article_source_revisions WHERE source_revision_id::text=$1`, *source.SourceRevisionID).Scan(&sourceDoc, &sourceBody, &sourceSteps, &sourceImages); err != nil {
		t.Fatal(err)
	}
	var sd CatalogDocument
	var ss []CatalogStep
	var si []CatalogImage
	json.Unmarshal(sourceDoc, &sd)
	json.Unmarshal(sourceSteps, &ss)
	json.Unmarshal(sourceImages, &si)
	expectedSource := map[string]any{"document": &sd, "body": sourceBody, "steps": ss, "images": si}
	sraw, _ := json.Marshal(expectedSource)
	observedSource, _ := json.Marshal(r3Projection(source))
	if !bytes.Equal(sraw, observedSource) {
		t.Fatalf("source tuple differs from persisted source: expected=%s observed=%s", sraw, observedSource)
	}
	expectedSource["canonical_article_id"] = f.article
	expectedSource["source_revision_id"] = *source.SourceRevisionID
	f.extra["expected_source_projection"] = expectedSource
	f.check("precommit_source_visible", r3Origin(source, "source") && !source.Complete && source.CanonicalRevisionID == nil && source.SourceRevisionID != nil && r3Int(r3Map(before, "counts"), "published_revisions") == 0 && r3Int(r3Map(before, "counts"), "publication_events") == 0)
	f.controlCall("POST", "release-publication")
	canonical := f.published()
	for range 10 {
		a := f.detail()
		if !r3Origin(a, "canonical") || a.CanonicalRevisionID == nil || *a.CanonicalRevisionID != *canonical.CanonicalRevisionID {
			t.Fatal("canonical regressed")
		}
	}
	s := f.snapshot("published", canonical)

	var rawDoc, rawSteps, rawImages []byte
	var body string
	err := f.pool.QueryRow(context.Background(), `SELECT canonical_document,canonical_body,canonical_steps,canonical_images FROM canonical_article_revisions WHERE canonical_article_revision_id::text=$1`, *canonical.CanonicalRevisionID).Scan(&rawDoc, &body, &rawSteps, &rawImages)
	if err != nil {
		t.Fatal(err)
	}
	var dbDoc CatalogDocument
	var steps []CatalogStep
	var images []CatalogImage
	json.Unmarshal(rawDoc, &dbDoc)
	json.Unmarshal(rawSteps, &steps)
	json.Unmarshal(rawImages, &images)
	actual, _ := json.Marshal(r3Projection(canonical))
	expected, _ := json.Marshal(map[string]any{"document": &dbDoc, "body": body, "steps": steps, "images": images})
	f.extra["expected_canonical_projection"] = map[string]any{"canonical_article_id": f.article, "source_revision_id": *canonical.SourceRevisionID, "canonical_revision_id": *canonical.CanonicalRevisionID, "document": &dbDoc, "body": body, "steps": steps, "images": images}
	f.check("atomic_projection_tuples", bytes.Equal(actual, expected) && canonical.SourceRevisionID != nil && *source.SourceRevisionID == *canonical.SourceRevisionID && *source.ViewRevision != *canonical.ViewRevision)
	f.check("monotonic_canonical_after_commit", true)
	f.check("one_publication", r3Int(r3Map(s, "counts"), "published_revisions") == 1 && r3Int(r3Map(s, "counts"), "publication_events") == 1 && r3Int(r3Map(s, "counts"), "article_jobs") == 1)
}
func TestPostgresCatalogLifecycleWarmReadsNoExternalCalls(t *testing.T) {
	f := r3Setup(t)
	f.schedule()
	f.controlCall("POST", "start-workers")
	canonical := f.published()
	f.get(0, "/"+f.article+"/source")
	_, _, list := f.get(0, "")
	var descriptors CatalogArticlesResponse
	json.Unmarshal(list, &descriptors)
	ids := map[string]bool{}
	for _, a := range descriptors.Items {
		ids[a.ID] = true
	}
	f.check("distinct_provider_descriptor_ids", len(descriptors.Items) == 2 && ids[f.article] && ids[f.other] && descriptors.Complete)
	before := f.snapshot("warm_before", canonical)
	for i := range 100 {
		detailStatus, a, detailBody := f.get(i, "/"+f.article)
		if detailStatus != 200 {
			t.Fatalf("warm detail %d %s", detailStatus, detailBody)
		}
		f.views = append(f.views, a)
		if !a.Complete || *a.CanonicalRevisionID != *canonical.CanonicalRevisionID || *a.SourceRevisionID != *canonical.SourceRevisionID {
			t.Fatal("warm revision changed")
		}
		status, _, raw := f.get(i, "/"+f.article+"/source?source_revision_id="+*canonical.SourceRevisionID)
		if status != 200 || !strings.Contains(string(raw), "Remove the pump.") {
			t.Fatal("source identity changed")
		}
		status, _, _ = f.get(i, "")
		if status != 200 {
			t.Fatal("warm list")
		}
	}
	r, _ := http.NewRequest("GET", f.servers[1].URL+"/v1/catalog/vehicles/"+f.vehicle+"/articles/"+f.article+"/source", nil)
	r.Header.Set("Accept", "text/html")
	c := &http.Client{Timeout: 3 * time.Second}
	resp, err := c.Do(r)
	if err != nil {
		t.Fatal(err)
	}
	html, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 || !strings.Contains(string(html), "Remove the pump.") {
		t.Fatal("HTML source")
	}
	after := f.snapshot("warm_after", canonical)
	time.Sleep(300 * time.Millisecond)
	settled := f.snapshot("warm_settled", canonical)
	f.check("warm_http_reads_complete", true)
	f.check("warm_zero_ensure_provider_model_delta", r3ZeroDelta(before, after) && r3ZeroDelta(before, settled))
	b, _ := json.Marshal(r3Map(before, "counts"))
	a, _ := json.Marshal(r3Map(settled, "counts"))
	f.check("warm_immutable_rows_unchanged", bytes.Equal(a, b) && before["immutable_sha256"] == settled["immutable_sha256"])
	f.extra["descriptor_ids"] = map[string]string{f.provider: f.article, map[string]string{"bankone": "banktwo", "banktwo": "bankone"}[f.provider]: f.other}
	f.extra["warm_cycles"] = 100
	f.extra["settle_seconds"] = 0.3
	f.extra["immutable_before_rows"] = before["immutable_rows"]
	f.extra["immutable_after_rows"] = settled["immutable_rows"]
	f.extra["immutable_before_sha256"] = before["immutable_sha256"]
	f.extra["immutable_after_sha256"] = settled["immutable_sha256"]
}

var _ = fmt.Sprintf

// Runs within each required cold case, using real persisted aliases/coverage.
// It performs store reads only and leaves worker/provider counters untouched.
func (f *r3Fixture) verifyScopeAndLegacyDescriptors() {
	t := f.t
	ctx := context.Background()
	store := newPostgresCatalogStore(f.pool)
	p := Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}
	items, err := store.Articles(ctx, p, f.vehicle)
	if err != nil || len(items) != 2 {
		t.Fatalf("canonical descriptors missing: %v %#v", err, items)
	}
	if items[0].ID != map[string]string{"bankone": f.article, "banktwo": f.other}[f.provider] { // map below checks bank order explicitly through SQL
		var provider string
		f.pool.QueryRow(ctx, "SELECT provider_slug FROM canonical_articles WHERE canonical_article_id::text=$1", items[0].ID).Scan(&provider)
		if provider != "bankone" {
			t.Fatal("bank order lost")
		}
	}
	for _, a := range items {
		view, e := store.ArticleView(ctx, p, f.vehicle, a.ID)
		if e != nil || view.Article.ID != a.ID {
			t.Fatal("list UUID does not resolve", e)
		}
	}
	if _, e := store.ArticleView(ctx, p, f.vehicle, "same/article"); !errors.Is(e, ErrCatalogNotFound) {
		t.Fatal("ambiguous raw alias accepted")
	}
	var mapped, unmapped, blocked, foreign, wrongVehicle string
	exec := func(sql string, args ...any) {
		t.Helper()
		if _, e := f.pool.Exec(ctx, sql, args...); e != nil {
			t.Fatal(e)
		}
	}
	if e := f.pool.QueryRow(ctx, `INSERT INTO vehicles(vehicle_key,make,model,model_year,region,source_snapshot_id,source_watermark) SELECT gen_random_uuid()::text,make,model,model_year,region,source_snapshot_id,source_watermark FROM vehicles WHERE vehicle_id::text=$1 RETURNING vehicle_id::text`, f.vehicle).Scan(&wrongVehicle); e != nil {
		t.Fatal(e)
	}
	insert := func(title, vehicle string) string {
		var id string
		e := f.pool.QueryRow(ctx, `INSERT INTO catalog_articles(vehicle_id,article_id,title,source_snapshot_id,evidence_locator,evidence_confidence,body,source_original) SELECT $1::uuid,gen_random_uuid()::text,$2,descriptor_source_snapshot_id,'fixture',1,'Legacy pump source','{"text":"Legacy pump source"}'::jsonb FROM canonical_articles WHERE canonical_article_id::text=$3 RETURNING catalog_article_id::text`, vehicle, title, f.article).Scan(&id)
		if e != nil {
			t.Fatal(e)
		}
		return id
	}
	mapped = insert("Mapped pump", f.vehicle)
	unmapped = insert("Unmapped pump", f.vehicle)
	blocked = insert("Blocked pump", f.vehicle)
	foreign = insert("Wrong vehicle alias", wrongVehicle)
	exec(`INSERT INTO canonical_article_aliases(catalog_article_id,canonical_article_id,proof) VALUES($1::uuid,$2::uuid,'{"identity":"fixture"}'),($3::uuid,$2::uuid,'{"identity":"wrong-vehicle-regression"}')`, mapped, f.article, foreign)
	var blockedSnapshot string
	if e := f.pool.QueryRow(ctx, `INSERT INTO source_snapshots(adapter_name,source_uri,source_version,content_sha256,object_key,license_metadata,retrieved_at) VALUES('fixture','fixture://quarantine','v1',encode(digest(gen_random_uuid()::text,'sha256'),'hex'),'fixture-quarantine','{}',now()) RETURNING source_snapshot_id::text`).Scan(&blockedSnapshot); e != nil {
		t.Fatal(e)
	}
	exec(`UPDATE catalog_articles SET source_snapshot_id=$1::uuid WHERE catalog_article_id::text=$2`, blockedSnapshot, blocked)
	exec(`INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids) VALUES(gen_random_uuid(),gen_random_uuid()::text,'quarantine','FIXTURE',jsonb_build_array($1::text))`, blockedSnapshot)
	items, err = store.Articles(ctx, p, f.vehicle)
	if err != nil || len(items) != 3 || items[2].ID != unmapped {
		t.Fatalf("legacy descriptor union: %v %#v", err, items)
	}
	if view, e := store.ArticleView(ctx, p, f.vehicle, mapped); e != nil || view.Article.ID != f.article {
		t.Fatal("proven alias failed", e)
	}
	for _, id := range []string{blocked, foreign} {
		if _, e := store.ArticleView(ctx, p, f.vehicle, id); !errors.Is(e, ErrCatalogNotFound) {
			t.Fatal("quarantine or wrong-vehicle alias leak", id, e)
		}
	}
	ownLegacy, ownErr := store.Articles(ctx, p, wrongVehicle)
	if ownErr != nil || len(ownLegacy) != 1 || ownLegacy[0].ID != foreign {
		t.Fatal("foreign alias suppressed rightful legacy owner", ownErr, ownLegacy)
	}
	if ownView, e := store.ArticleView(ctx, p, wrongVehicle, foreign); e != nil || ownView.Article.CanonicalArticleID != nil || ownView.Article.ID != foreign {
		t.Fatal("foreign alias did not remain unmanaged in its own scope", e)
	}
	exec(`UPDATE canonical_articles SET takedown_status='takedown' WHERE canonical_article_id::text=$1`, f.other)
	items, err = store.Articles(ctx, p, f.vehicle)
	if err != nil || len(items) != 2 {
		t.Fatal("withdrawn descriptor leaked", err)
	}
	if view, e := store.ArticleView(ctx, p, f.vehicle, f.other); e != nil || !view.Withdrawn {
		t.Fatal("withdrawn known identity not preserved", e)
	}
	exec(`UPDATE canonical_articles SET takedown_status='active' WHERE canonical_article_id::text=$1`, f.other)
	exec(`UPDATE catalog_article_provider_scopes SET status='partial' WHERE vehicle_id::text=$1 AND provider_slug='banktwo'`, f.vehicle)
	progress, err := store.CatalogArticleProgress(ctx, p, f.vehicle)
	if err != nil || progress.Complete || !progress.Retryable || progress.Status != "failed" {
		t.Fatal("nonempty partial index falsely complete", progress, err)
	}
	exec(`UPDATE catalog_article_provider_scopes SET status='complete' WHERE vehicle_id::text=$1 AND provider_slug='banktwo'`, f.vehicle)
}

func (f *r3Fixture) verifyManagedQuarantine() {
	ctx := context.Background()
	store := newPostgresCatalogStore(f.pool)
	p := Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}
	rows, err := f.pool.Query(ctx, `SELECT snapshot.source_snapshot_id::text FROM canonical_articles a JOIN canonical_article_source_revisions revision ON revision.source_revision_id=a.current_source_revision_id JOIN source_snapshots snapshot ON snapshot.source_snapshot_id=revision.body_source_snapshot_id OR EXISTS(SELECT 1 FROM jsonb_array_elements(revision.resource_manifest) asset WHERE asset->>'sha256'=snapshot.content_sha256::text) WHERE a.canonical_article_id::text=$1 ORDER BY snapshot.source_snapshot_id`, f.article)
	if err != nil {
		f.t.Fatal(err)
	}
	var snapshots []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			f.t.Fatal(err)
		}
		snapshots = append(snapshots, id)
	}
	rows.Close()
	if rows.Err() != nil || len(snapshots) < 2 {
		f.t.Fatal("body/resource quarantine fixture missing", rows.Err(), snapshots)
	}
	for _, snapshot := range snapshots {
		var review string
		err := f.pool.QueryRow(ctx, `INSERT INTO source_review_items(source_review_item_id,item_key,item_kind,reason_code,source_snapshot_ids) VALUES(gen_random_uuid(),gen_random_uuid()::text,'quarantine','FIXTURE',jsonb_build_array($1::text)) RETURNING source_review_item_id::text`, snapshot).Scan(&review)
		if err != nil {
			f.t.Fatal(err)
		}

		if _, err = store.ArticleView(ctx, p, f.vehicle, f.article); !errors.Is(err, ErrCatalogNotFound) {
			f.t.Fatal("managed quarantine exposed detail", err)
		}
		items, err := store.Articles(ctx, p, f.vehicle)
		if err != nil {
			f.t.Fatal(err)
		}
		for _, item := range items {
			if item.ID == f.article {
				f.t.Fatal("managed quarantine exposed descriptor")
			}
		}
		if _, err = store.ArticleSourceRevision(ctx, p, f.vehicle, f.article, ""); !errors.Is(err, ErrCatalogNotFound) {
			f.t.Fatal("managed quarantine exposed source", err)
		}
		for _, suffix := range []string{"/" + f.article, "/" + f.article + "/source"} {
			status, _, body := f.get(0, suffix)
			if status != 404 {
				f.t.Fatalf("managed quarantine HTTP leak %d %s", status, body)
			}
		}
		if _, err = f.pool.Exec(ctx, `UPDATE source_review_items SET status='approved' WHERE source_review_item_id::text=$1`, review); err != nil {
			f.t.Fatal(err)
		}
	}

}
func (f *r3Fixture) verifyConfigurationScope() {
	ctx := context.Background()
	t := f.t
	store := newPostgresCatalogStore(f.pool)
	p := Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}
	var evidence, base, configuration, otherConfiguration, configuredArticle string
	err := f.pool.QueryRow(ctx, `INSERT INTO extraction_evidence(source_snapshot_id,locator,artifact_key,extracted_text,confidence,reviewer_state) SELECT descriptor_source_snapshot_id,'fixture','fixture','configuration',1,'approved' FROM canonical_articles WHERE canonical_article_id::text=$1 RETURNING extraction_evidence_id::text`, f.article).Scan(&evidence)
	if err != nil {
		t.Fatal(err)
	}
	err = f.pool.QueryRow(ctx, `INSERT INTO vehicle_identity_bases(canonical_base_key,vehicle_id,make,model,model_year,region,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state) SELECT gen_random_uuid()::text,vehicle_id,'Example','Car',2024,'US',descriptor_source_snapshot_id,$2::uuid,'fixture','fixture',1,'approved' FROM canonical_articles WHERE canonical_article_id::text=$1 RETURNING vehicle_identity_base_id::text`, f.article, evidence).Scan(&base)
	if err != nil {
		t.Fatal(err)
	}
	for _, target := range []*string{&configuration, &otherConfiguration} {
		err = f.pool.QueryRow(ctx, `INSERT INTO vehicle_configurations(configuration_key,vehicle_identity_base_id,vehicle_id,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,reviewer_state) SELECT gen_random_uuid()::text,$2::uuid,vehicle_id,descriptor_source_snapshot_id,$3::uuid,'fixture','fixture',1,'approved' FROM canonical_articles WHERE canonical_article_id::text=$1 RETURNING vehicle_configuration_id::text`, f.article, base, evidence).Scan(target)
		if err != nil {
			t.Fatal(err)
		}
	}
	err = f.pool.QueryRow(ctx, `INSERT INTO canonical_articles(canonical_article_id,provider_slug,vehicle_id,vehicle_configuration_id,scope_key,source_vehicle_ref,source_article_ref,identity_key,descriptor,descriptor_source_snapshot_id,title) SELECT gen_random_uuid(),provider_slug,vehicle_id,$2::uuid,'configuration:'||($2::uuid)::text,source_vehicle_ref,source_article_ref,encode(digest(gen_random_uuid()::text,'sha256'),'hex'),descriptor,descriptor_source_snapshot_id,title FROM canonical_articles WHERE canonical_article_id::text=$1 RETURNING canonical_article_id::text`, f.article, configuration).Scan(&configuredArticle)
	if err != nil {
		t.Fatal(err)
	}
	items, err := store.Articles(ctx, p, configuration)
	if err != nil || len(items) != 1 || items[0].ID != configuredArticle {
		t.Fatal("configuration descriptor scope", err, items)
	}
	view, err := store.ArticleView(ctx, p, configuration, configuredArticle)
	if err != nil || view.Article.canonicalVehicleID != f.vehicle || view.Article.canonicalConfigurationID == nil || *view.Article.canonicalConfigurationID != configuration {
		t.Fatal("configuration scheduling identity lost", err)
	}
	for _, scope := range []string{f.vehicle, otherConfiguration} {
		if _, err := store.ArticleView(ctx, p, scope, configuredArticle); !errors.Is(err, ErrCatalogNotFound) {
			t.Fatal("configuration crossed vehicle or sibling scope", err)
		}
	}
	if _, err := f.pool.Exec(ctx, `UPDATE vehicle_configurations SET reviewer_state='rejected' WHERE vehicle_configuration_id::text=$1`, configuration); err != nil {
		t.Fatal(err)
	}
	items, err = store.Articles(ctx, p, configuration)
	if err != nil || len(items) != 0 {
		t.Fatal("rejected configuration leaked", err, items)
	}
}
