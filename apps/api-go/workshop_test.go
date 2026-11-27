package main

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"regexp"
	"slices"
	"strings"
	"testing"
)

const expectedWorkshopEntryCache = "private, max-age=30, must-revalidate"

func TestWorkshopRootEntry(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	for _, method := range []string{http.MethodGet, http.MethodHead} {
		t.Run(method, func(t *testing.T) {
			response := httptest.NewRecorder()
			server.Handler().ServeHTTP(response, httptest.NewRequest(method, "/", nil))
			if response.Code != http.StatusFound || response.Header().Get("Location") != "/workshop" {
				t.Fatalf("%s root redirect = %d %q", method, response.Code, response.Header().Get("Location"))
			}
		})
	}
	t.Run("unknown path", func(t *testing.T) {
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/missing-root-route", nil))
		if response.Code != http.StatusNotFound {
			t.Fatalf("unknown root route = %d, want %d", response.Code, http.StatusNotFound)
		}
	})
}

func TestWorkshopEntryMarksPublicSelectors(t *testing.T) {
	request := func(public bool, tag string) *httptest.ResponseRecorder {
		recorder := httptest.NewRecorder()
		r := httptest.NewRequest(http.MethodGet, "/workshop", nil)
		r.Header.Set("If-None-Match", tag)
		workshopAssetsHandler(recorder, r, workshopEntryOptions{publicSelectors: public})
		return recorder
	}
	legacy := request(false, "")
	public := request(true, legacy.Header().Get("ETag"))
	if legacy.Code != http.StatusOK || public.Code != http.StatusOK ||
		!strings.Contains(legacy.Body.String(), `data-public-selectors="false"`) ||
		!strings.Contains(public.Body.String(), `data-public-selectors="true"`) {
		t.Fatal("entry variants did not bind selector visibility")
	}
	if cached := request(true, public.Header().Get("ETag")); cached.Code != http.StatusNotModified {
		t.Fatalf("public entry validator returned %d", cached.Code)
	}
	if len(public.Header().Values("Link")) != 0 {
		t.Fatal("entry response tried to infer the browser route")
	}
}

type workshopInitialYearsStore struct {
	CatalogStore
	items    []CatalogYear
	complete bool
	timeout  bool
	reads    int
}

func (s *workshopInitialYearsStore) Years(ctx context.Context, _ Principal) ([]CatalogYear, *bool, error) {
	s.reads++
	if s.timeout {
		<-ctx.Done()
		return nil, nil, ctx.Err()
	}
	return s.items, &s.complete, nil
}

func TestWorkshopEntryCarriesOnlyCompletePublicYears(t *testing.T) {
	server, store, _ := paidHTTPServer()
	years := &workshopInitialYearsStore{CatalogStore: store, items: []CatalogYear{{Year: 2024}}, complete: true}
	server.catalog = years
	handler := server.Handler()
	request := func(method, path, tag string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, path, nil)
		req.Header.Set("If-None-Match", tag)
		out := httptest.NewRecorder()
		handler.ServeHTTP(out, req)
		return out
	}
	const entry = "/workshop?year=2024"
	const yearData = `<script id="workshop-initial-years" type="application/json">`
	first := request(http.MethodGet, entry, "")
	tag := first.Header().Get("ETag")
	expected := strings.TrimSpace(request(http.MethodGet, "/v1/catalog/years", "").Body.String())
	if first.Code != http.StatusOK || !strings.Contains(first.Body.String(), yearData+expected+"</script>") ||
		first.Header().Get("Cache-Control") != expectedWorkshopEntryCache || tag != fmt.Sprintf(`W/"%x"`, sha256.Sum256(first.Body.Bytes())) {
		t.Fatal("entry did not carry the exact public snapshot and its own validator")
	}
	for _, method := range []string{http.MethodGet, http.MethodHead} {
		if cached := request(method, entry, tag); cached.Code != http.StatusNotModified || cached.Body.Len() != 0 {
			t.Fatalf("conditional %s = %d with %d bytes", method, cached.Code, cached.Body.Len())
		}
	}
	years.items = append(years.items, CatalogYear{Year: 2025})
	if updated := request(http.MethodGet, entry, tag); updated.Code != http.StatusOK ||
		updated.Header().Get("ETag") == tag || !strings.Contains(updated.Body.String(), `{"year":2025}`) {
		t.Fatal("changed years did not invalidate the entry page")
	}
	reads := years.reads
	for _, path := range []string{
		"/workshop?view=library", "/workshop?article=owned", "/workshop?configuration=selected",
		"/workshop?order=return", "/workshop?demo=1", "/workshop?sample=1", "/workshop?region=CA",
		"/workshop/styles.css",
	} {
		if got := request(http.MethodGet, path, ""); got.Code != http.StatusOK || strings.Contains(got.Body.String(), yearData) {
			t.Errorf("%s received model years or failed", path)
		}
	}
	if years.reads != reads {
		t.Fatal("unrelated routes queried the year store")
	}
	for _, tc := range []struct {
		name              string
		items             []CatalogYear
		complete, timeout bool
	}{
		{name: "partial", items: []CatalogYear{{Year: 2024}}},
		{name: "empty", complete: true},
		{name: "deadline", timeout: true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			years.items, years.complete, years.timeout = tc.items, tc.complete, tc.timeout
			if got := request(http.MethodGet, entry, tag); got.Code != http.StatusOK || strings.Contains(got.Body.String(), yearData) {
				t.Fatal("entry did not remain available without a complete public year snapshot")
			}
		})
	}
	server.customerAuth = nil
	reads = years.reads
	legacy := request(http.MethodGet, entry, "")
	if legacy.Code != http.StatusOK || strings.Contains(legacy.Body.String(), yearData) || years.reads != reads {
		t.Fatal("legacy private catalog did not keep its normal entry")
	}
}

type workshopInitialMakesStore struct {
	*workshopInitialYearsStore
	requestedYears []int
	largeOlderList bool
}

func (s *workshopInitialMakesStore) catalogMakeLists(_ context.Context, years []int, region string, completeOnly bool) (map[int][]CatalogMake, error) {
	s.requestedYears = years
	if region != "US" || !completeOnly {
		return nil, fmt.Errorf("expected only complete US make lists")
	}
	makeChoice := CatalogMake{ID: "quoted", Name: "A < B", MarketUnverified: true}
	verified := makeChoice
	verified.MarketUnverified = false
	lists := map[int][]CatalogMake{2016: {makeChoice}, 2023: {verified}, 2024: {makeChoice}}
	if s.largeOlderList {
		lists[2021] = []CatalogMake{{ID: "large", Name: strings.Repeat("b", workshopInitialMakesMaxBytes)}}
	}
	return lists, nil
}

func TestWorkshopEntryCarriesBoundedPublicMakeLists(t *testing.T) {
	server, store, _ := paidHTTPServer()
	initial := &workshopInitialMakesStore{workshopInitialYearsStore: &workshopInitialYearsStore{
		CatalogStore: store, complete: true,
		items: []CatalogYear{{Year: 2027}, {Year: 2016}, {Year: 2021}, {Year: 2022}, {Year: 2023}, {Year: 2024}, {Year: 2025}, {Year: 2026}},
	}}
	server.catalog = initial
	handler := server.Handler()
	get := func(path string) string {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest(http.MethodGet, path, nil))
		if w.Code != http.StatusOK {
			t.Fatalf("%s returned %d", path, w.Code)
		}
		return w.Body.String()
	}
	const marker = `<script id="workshop-initial-makes" type="application/json">`
	if body := get("/workshop"); !strings.Contains(body, marker+`{"options":[{"id":"quoted","name":"A \u003c B","market_unverified":true},{"id":"quoted","name":"A \u003c B"}],"years":{"2016":[0],"2023":[1],"2024":[0]}}</script>`) ||
		!slices.Equal(initial.requestedYears, []int{2016, 2021, 2022, 2023, 2024, 2025, 2026, 2027}) {
		t.Fatalf("unexpected public make lists for %v", initial.requestedYears)
	}
	initial.largeOlderList = true
	if body := get("/workshop"); !strings.Contains(body,
		marker+`{"options":[{"id":"quoted","name":"A \u003c B"},{"id":"quoted","name":"A \u003c B","market_unverified":true}],"years":{"2023":[0],"2024":[1]}}</script>`) {
		t.Fatal("the oversized payload did not retain the recent make lists")
	}
	initial.requestedYears = nil
	if body := get("/workshop?view=library"); strings.Contains(body, marker) || initial.requestedYears != nil {
		t.Fatal("Library requested public make lists")
	}
}

func TestWorkshopEntryMarksOpenDemoForConfiguredHost(t *testing.T) {
	server, _, _ := paidHTTPServer()
	server.workshopOpenDemoHost = "demo.cars.tk"
	handler := server.Handler()
	request := func(host, tag string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(http.MethodGet, "/workshop", nil)
		r.Host = host
		r.Header.Set("If-None-Match", tag)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		return w
	}
	demo := request("demo.cars.tk", "")
	tag := demo.Header().Get("ETag")
	if demo.Code != http.StatusOK || tag == "" ||
		!strings.Contains(demo.Body.String(), `data-workshop-open-demo="true"`) ||
		!strings.Contains(demo.Body.String(), `data-public-selectors="true"`) {
		t.Fatalf("open demo entry = %d, tag %q", demo.Code, tag)
	}
	if cached := request("demo.cars.tk", tag); cached.Code != http.StatusNotModified {
		t.Fatalf("open demo entry validator returned %d", cached.Code)
	}
	regular := request("another.example", tag)
	if regular.Code != http.StatusOK || !strings.Contains(regular.Body.String(), `data-workshop-open-demo="false"`) {
		t.Fatalf("other host entry = %d", regular.Code)
	}
	server.workshopOpenDemoHost = ""
	if disabled := request("demo.cars.tk", tag); disabled.Code != http.StatusOK ||
		!strings.Contains(disabled.Body.String(), `data-workshop-open-demo="false"`) {
		t.Fatalf("disabled demo entry = %d", disabled.Code)
	}
}

func TestWorkshopPublicDemoEntryBindsTheBrowserOriginsThroughTheProxy(t *testing.T) {
	server, _, _ := paidHTTPServer()
	server.workshopOpenDemoHost = workshopPublicOpenDemoHost("1", "production", workshopPublicDemoOrigin)
	handler := server.Handler()
	request := func(path, tag string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(http.MethodGet, "http://proxy.internal"+path, nil)
		r.Header.Set("If-None-Match", tag)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		return w
	}
	entry := request("/workshop", "")
	tag := entry.Header().Get("ETag")
	if entry.Code != http.StatusOK || tag == "" || !strings.Contains(entry.Body.String(),
		`data-workshop-demo-origins="https://autodata.cars.tk https://autodata.curtis.click"`) {
		t.Fatalf("public demo entry = %d, tag %q", entry.Code, tag)
	}
	if mode := request("/workshop/demo-mode.json", ""); strings.TrimSpace(mode.Body.String()) != `{"enabled":false}` {
		t.Fatalf("the readiness API accepted the proxy Host: %s", mode.Body)
	}
	server.workshopOpenDemoHost = ""
	if disabled := request("/workshop", tag); disabled.Code != http.StatusOK ||
		strings.Contains(disabled.Body.String(), "data-workshop-demo-origins") {
		t.Fatalf("disabled demo entry = %d", disabled.Code)
	}
}

func TestWorkshopAssetsAvailableWithoutCatalogCredentials(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	for _, asset := range []struct{ path, contentType string }{
		{"/workshop/", "text/html"},
		{"/workshop/styles.css", "text/css"},
		{"/workshop/app.mjs", "javascript"},
		{"/workshop/bootstrap.mjs", "javascript"},
		{"/workshop/demo.mjs", "javascript"},
		{"/workshop/auth.mjs", "javascript"},
		{"/workshop/commerce.mjs", "javascript"},
		{"/workshop/article-read.mjs", "javascript"},
		{"/workshop/purchase-config.json", "application/json"},
		{"/workshop/catalog.mjs", "javascript"},
		{"/workshop/firebase-web.mjs", "javascript"},
		{"/workshop/firebase-web.mjs.LEGAL.txt", "text/plain"},
		{"/workshop/firebase-web.provenance.json", "application/json"},
		{"/workshop/fonts/InstrumentSans.ttf", "font/ttf"},
		{"/workshop/fonts/InstrumentSans.woff2", "font/woff2"},
	} {
		t.Run(asset.path, func(t *testing.T) {
			response := httptest.NewRecorder()
			server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, asset.path, nil))
			if response.Code != http.StatusOK || response.Body.Len() == 0 {
				t.Fatalf("asset unavailable: status=%d bytes=%d", response.Code, response.Body.Len())
			}
			if !strings.Contains(response.Header().Get("Content-Type"), asset.contentType) {
				t.Fatalf("wrong MIME type: %s", response.Header().Get("Content-Type"))
			}
		})
	}
	for _, path := range []string{"/workshop/missing-file.js", "/workshop/missing-page"} {
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, path, nil))
		if response.Code != http.StatusNotFound {
			t.Fatalf("missing asset %s returned %d", path, response.Code)
		}
	}
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/", nil))
	for _, marker := range []string{"source-review", "source-review-frame", "View stored source", "Load beside article"} {
		if !strings.Contains(response.Body.String(), marker) {
			t.Fatalf("workshop HTML is missing source review marker %q", marker)
		}
	}
}

func TestWorkshopPublicAssetsRevalidateByContent(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	handler := server.Handler()
	request := func(method, path, tag string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(method, path, nil)
		if tag != "" {
			r.Header.Set("If-None-Match", tag)
		}
		r.Header.Set("X-Request-ID", "workshop-asset-caller")
		r.Header.Set("Traceparent", "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		return w
	}
	for _, tc := range []struct{ path, cache string }{
		{"/workshop/?view=library", expectedWorkshopEntryCache},
		{"/workshop/app.mjs", "no-cache"},
		{"/workshop/styles.css", "no-cache"},
		{"/workshop/fonts/InstrumentSans.woff2", "no-cache"},
	} {
		path := tc.path
		t.Run(path, func(t *testing.T) {
			first := request(http.MethodGet, path, "")
			digest := sha256.Sum256(first.Body.Bytes())
			wantTag := `W/"` + hex.EncodeToString(digest[:]) + `"`
			if first.Code != http.StatusOK || first.Header().Get("ETag") != wantTag || first.Header().Get("Cache-Control") != tc.cache ||
				first.Header().Get("Vercel-CDN-Cache-Control") != "" {
				t.Fatalf("first read = %d, tag %q, cache %q", first.Code, first.Header().Get("ETag"), first.Header().Get("Cache-Control"))
			}
			for _, method := range []string{http.MethodGet, http.MethodHead} {
				warm := request(method, path, wantTag)
				if warm.Code != http.StatusNotModified || warm.Body.Len() != 0 || warm.Header().Get("ETag") != wantTag || warm.Header().Get("Cache-Control") != tc.cache {
					t.Fatalf("%s warm read = %d with %d bytes, tag %q, cache %q", method, warm.Code, warm.Body.Len(), warm.Header().Get("ETag"), warm.Header().Get("Cache-Control"))
				}
			}
			stale := request(http.MethodGet, path, `W/"previous-build"`)
			if stale.Code != http.StatusOK || stale.Header().Get("ETag") != wantTag || !bytes.Equal(stale.Body.Bytes(), first.Body.Bytes()) {
				t.Fatalf("read after changed asset = %d, tag %q", stale.Code, stale.Header().Get("ETag"))
			}
		})
	}
	t.Run("legacy versioned bootstrap", func(t *testing.T) {
		const path = "/workshop/bootstrap.mjs"
		const cache = "private, max-age=31536000, immutable"
		first := request(http.MethodGet, path, "")
		digest := sha256.Sum256(first.Body.Bytes())
		version := hex.EncodeToString(digest[:])
		versioned := path + "?v=" + version
		tag := `W/"` + version + `"`
		for _, method := range []string{http.MethodGet, http.MethodHead} {
			response := request(method, versioned, "")
			if response.Code != http.StatusOK || response.Header().Get("ETag") != tag || response.Header().Get("Cache-Control") != cache {
				t.Fatalf("%s versioned bootstrap = %d, tag %q, cache %q", method, response.Code, response.Header().Get("ETag"), response.Header().Get("Cache-Control"))
			}
			if (method == http.MethodHead && response.Body.Len() != 0) || (method == http.MethodGet && !bytes.Equal(response.Body.Bytes(), first.Body.Bytes())) {
				t.Fatalf("%s versioned bootstrap has unexpected contents", method)
			}
			warm := request(method, versioned, tag)
			if warm.Code != http.StatusNotModified || warm.Body.Len() != 0 || warm.Header().Get("Cache-Control") != cache {
				t.Fatalf("%s conditional versioned bootstrap = %d with %d bytes, cache %q", method, warm.Code, warm.Body.Len(), warm.Header().Get("Cache-Control"))
			}
		}
		for _, alias := range []string{path, path + "?v=previous-build", versioned + "&v=previous-build"} {
			response := request(http.MethodGet, alias, "")
			if response.Code != http.StatusOK || response.Header().Get("Cache-Control") != "no-cache" || !bytes.Equal(response.Body.Bytes(), first.Body.Bytes()) {
				t.Fatalf("bootstrap alias %s = %d, cache %q", alias, response.Code, response.Header().Get("Cache-Control"))
			}
		}
	})
	t.Run("immutable release assets", func(t *testing.T) {
		index := request(http.MethodGet, "/workshop/?view=library", "").Body.String()
		match := regexp.MustCompile(`src="(/workshop/assets/[a-f0-9]{64}/)bootstrap\.mjs"`).FindStringSubmatch(index)
		if len(match) != 2 {
			t.Fatal("Workshop entry page is missing the versioned bootstrap")
		}
		for _, name := range []string{"catalog.mjs", "styles.css", "fonts/InstrumentSans.woff2"} {
			if !strings.Contains(index, `href="`+match[1]+name+`"`) {
				t.Fatalf("Workshop entry page is missing the versioned %s", name)
			}
		}
		const immutable = "private, max-age=31536000, immutable, no-transform"
		const edgeCache = "public, max-age=86400, immutable, no-transform"
		for _, name := range []string{"bootstrap.mjs", "app.mjs", "auth.mjs", "article-read.mjs", "progress.mjs",
			"catalog.mjs", "commerce.mjs", "firebase-web.mjs", "demo.mjs", "styles.css", "fonts/InstrumentSans.woff2"} {
			fresh := request(http.MethodGet, match[1]+name, "")
			legacy := request(http.MethodGet, "/workshop/"+name, "")
			if fresh.Code != http.StatusOK || fresh.Header().Get("Cache-Control") != immutable || fresh.Header().Get("Vary") != "Accept-Encoding" ||
				fresh.Header().Get("Vercel-CDN-Cache-Control") != edgeCache || fresh.Header().Get("X-Request-ID") != "" ||
				fresh.Header().Get("Traceparent") != "" ||
				fresh.Header().Get("ETag") != legacy.Header().Get("ETag") ||
				fresh.Header().Get("Content-Type") != legacy.Header().Get("Content-Type") ||
				!bytes.Equal(fresh.Body.Bytes(), legacy.Body.Bytes()) {
				t.Errorf("versioned %s returned status %d or different content/headers", name, fresh.Code)
			}
			warm := request(http.MethodHead, match[1]+name, fresh.Header().Get("ETag"))
			if warm.Code != http.StatusNotModified || warm.Body.Len() != 0 || warm.Header().Get("Vercel-CDN-Cache-Control") != edgeCache {
				t.Errorf("conditional HEAD for %s = %d", name, warm.Code)
			}
		}
		otherVersion := strings.Repeat("e", 64)
		previous := request(http.MethodGet, "/workshop/assets/"+otherVersion+"/firebase-web.mjs", "")
		if previous.Code != http.StatusTemporaryRedirect || previous.Header().Get("Location") != "/workshop/firebase-web.mjs" ||
			previous.Header().Get("Cache-Control") != "no-store" || previous.Header().Get("Vercel-CDN-Cache-Control") != "" {
			t.Fatal("an old release URL must resolve without caching newer bytes at the old URL")
		}
		for _, name := range []string{"", "missing.mjs", "purchase-config.json", "demo-mode.json"} {
			missing := request(http.MethodGet, match[1]+name, "")
			if missing.Code != http.StatusNotFound || missing.Header().Get("Cache-Control") == immutable ||
				missing.Header().Get("Vercel-CDN-Cache-Control") != "" {
				t.Errorf("unknown versioned asset %q = %d with %q", name, missing.Code, missing.Header().Get("Cache-Control"))
			}
		}
		query := request(http.MethodGet, match[1]+"bootstrap.mjs?probe=1", "")
		if query.Code != http.StatusOK || query.Header().Get("Vercel-CDN-Cache-Control") != "" {
			t.Fatal("a noncanonical asset URL must not be shared")
		}
		partial := httptest.NewRecorder()
		rangeRequest := httptest.NewRequest(http.MethodGet, match[1]+"bootstrap.mjs", nil)
		rangeRequest.Header.Set("Range", "bytes=0-15")
		handler.ServeHTTP(partial, rangeRequest)
		if partial.Code != http.StatusPartialContent || partial.Header().Get("Vercel-CDN-Cache-Control") != "" {
			t.Fatal("a partial static asset must not be shared")
		}
	})
	for _, path := range []string{"/workshop/purchase-config.json", "/workshop/demo-mode.json"} {
		live := request(http.MethodGet, path, "*")
		if live.Code != http.StatusOK || live.Body.Len() == 0 || live.Header().Get("ETag") != "" || live.Header().Get("Cache-Control") != "no-store" ||
			live.Header().Get("Vercel-CDN-Cache-Control") != "" {
			t.Fatalf("dynamic %s returned %d, tag %q, cache %q", path, live.Code, live.Header().Get("ETag"), live.Header().Get("Cache-Control"))
		}
	}
	missing := request(http.MethodGet, "/workshop/missing.mjs", "*")
	if missing.Code != http.StatusNotFound || missing.Header().Get("ETag") != "" {
		t.Fatalf("missing file read = %d, tag %q", missing.Code, missing.Header().Get("ETag"))
	}
}

func TestWorkshopVersionedAssetEncoding(t *testing.T) {
	request := func(method, path string, headers http.Header) *httptest.ResponseRecorder {
		r := httptest.NewRequest(method, path, nil)
		r.Header = headers
		w := httptest.NewRecorder()
		workshopAssetsHandler(w, r, workshopEntryOptions{})
		return w
	}
	entry := request(http.MethodGet, "/workshop", nil)
	root := regexp.MustCompile(`/workshop/assets/[a-f0-9]{64}/`).FindString(entry.Body.String())
	if root == "" {
		t.Fatal("entry is missing the asset release path")
	}
	for _, name := range []string{"app.mjs", "styles.css", "fonts/InstrumentSans.woff2"} {
		path := root + name
		identity := request(http.MethodGet, path, nil)
		for _, tc := range []struct {
			name     string
			accepted []string
			encoding string
		}{
			{"implicit identity", nil, ""},
			{"listed gzip", []string{"br, GZip"}, "gzip"},
			{"wildcard gzip", []string{"custom;q=1, *;q=0.4"}, "gzip"},
			{"gzip veto", []string{"gzip;q=0", "*;q=1"}, ""},
			{"identity preferred", []string{"identity; q=1, gzip;q=0.3"}, ""},
			{"invalid weight", []string{"gzip;q=NaN"}, ""},
		} {
			t.Run(name+"/"+tc.name, func(t *testing.T) {
				want := tc.encoding
				if strings.HasSuffix(name, ".woff2") {
					want = ""
				}
				headers := http.Header{"Accept-Encoding": tc.accepted}
				body := request(http.MethodGet, path, headers)
				if body.Code != http.StatusOK || body.Header().Get("Content-Encoding") != want {
					t.Fatalf("encoding response %d %q, want 200 %q", body.Code, body.Header().Get("Content-Encoding"), want)
				}
				for _, key := range []string{"Content-Type", "ETag", "Vary", "Cache-Control", "Vercel-CDN-Cache-Control"} {
					if body.Header().Get(key) != identity.Header().Get(key) {
						t.Errorf("unexpected %s %q", key, body.Header().Get(key))
					}
				}
				var payload io.Reader = body.Body
				if want == "gzip" {
					if body.Body.Len() >= identity.Body.Len() {
						t.Fatal("compressed asset did not shrink")
					}
					decoder, err := gzip.NewReader(body.Body)
					if err != nil {
						t.Fatal(err)
					}
					defer decoder.Close()
					payload = decoder
				}
				decoded, err := io.ReadAll(payload)
				if err != nil || !bytes.Equal(identity.Body.Bytes(), decoded) {
					t.Fatalf("decoded asset mismatch: %v", err)
				}
				head := request(http.MethodHead, path, headers)
				if head.Code != http.StatusOK || head.Body.Len() != 0 || head.Header().Get("Content-Encoding") != want {
					t.Fatal("HEAD representation did not match GET")
				}
				headers.Set("If-None-Match", identity.Header().Get("ETag"))
				cached := request(http.MethodGet, path, headers)
				if cached.Code != http.StatusNotModified || cached.Body.Len() != 0 || cached.Header().Get("Vary") != "Accept-Encoding" {
					t.Fatal("asset revalidation lost its shared validator or negotiation")
				}
			})
		}
	}
	part := request(http.MethodGet, root+"app.mjs", http.Header{"Accept-Encoding": {"gzip"}, "Range": {"bytes=0-15"}})
	if part.Code != http.StatusPartialContent || part.Body.Len() != 16 || part.Header().Get("Content-Encoding") != "" ||
		part.Header().Get("Vercel-CDN-Cache-Control") != "" {
		t.Fatal("identity range contract changed")
	}
}

func TestWorkshopPurchaseConfigDisabledByDefault(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/purchase-config.json", nil))
	if response.Code != http.StatusOK {
		t.Fatalf("purchase config status=%d", response.Code)
	}
	var config map[string]any
	if err := json.Unmarshal(response.Body.Bytes(), &config); err != nil {
		t.Fatal(err)
	}
	if config["enabled"] != false || config["terms_version"] != "workshop-v1" {
		t.Fatal("default purchase config must remain disabled at workshop-v1")
	}
	for _, field := range []string{"terms_url", "privacy_url", "refund_url", "contact_url", "tax_notice"} {
		value, present := config[field]
		if !present || value != nil {
			t.Fatalf("default %s must be present and null", field)
		}
	}
}

func TestWorkshopRealDemoRequiresEnabledNonProductionStripeTest(t *testing.T) {
	cases := []struct {
		name, mode, environment, authMode, origin, config string
		client, enabled                                   bool
	}{
		{"test ready", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, true},
		{"test disabled purchase", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":false}`, true, false},
		{"mismatched private live mode", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_live","purchase_enabled":true}`, true, false},
		{"test invalid response", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true,"extra":1}`, true, false},
		{"test duplicate private mode", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_live","mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"test trailing private JSON", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}{}`, true, false},
		{"test no client", "stripe_test", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, false, false},
		{"local auth unavailable", "stripe_test", "test", "local", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"public production origin", "stripe_test", "staging", "firebase", "https://autodata.cars.tk", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"public apex origin", "stripe_test", "staging", "firebase", "https://cars.tk", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"live mode", "stripe_live", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"production", "stripe_test", "production", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"unknown environment", "stripe_test", "unknown", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
		{"disabled mode", "disabled", "staging", "firebase", "https://demo.example", `{"mode":"stripe_test","purchase_enabled":true}`, true, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			calls := 0
			s := NewServer(staticReadiness{})
			s.workshopTestCheckout = workshopTestCheckoutMode(tc.mode, tc.environment, tc.authMode, tc.origin)
			if tc.client {
				s.commerceClient = commerceFixture(func(_ context.Context, op string, body []byte, signature string) (int, []byte, error) {
					calls++
					if op != "demo-mode" || string(body) != "{}" || signature != "" {
						t.Fatal("unexpected private commerce request", op, string(body), signature)
					}
					return 200, []byte(tc.config), nil
				})
			}
			response := httptest.NewRecorder()
			s.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/demo-mode.json", nil))
			if response.Code != 200 || response.Header().Get("Cache-Control") != "no-store" || !strings.Contains(response.Header().Get("Content-Type"), "application/json") {
				t.Fatalf("demo mode response = %d %q", response.Code, response.Body.String())
			}
			var payload map[string]any
			if json.Unmarshal(response.Body.Bytes(), &payload) != nil || !reflect.DeepEqual(payload, map[string]any{"enabled": tc.enabled}) {
				t.Fatalf("demo readiness = %#v, want %v", payload, tc.enabled)
			}
			if want := 0; tc.client && workshopTestCheckoutMode(tc.mode, tc.environment, tc.authMode, tc.origin) {
				want = 1
				if calls != want {
					t.Fatalf("private calls=%d, want %d", calls, want)
				}
			} else if calls != 0 {
				t.Fatalf("non-test mode contacted private commerce: %d", calls)
			}
		})
	}
}

func TestWorkshopRealDemoReadinessMethodAndQuery(t *testing.T) {
	s := NewServer(staticReadiness{})
	for _, tc := range []struct {
		method, path string
		status       int
	}{
		{http.MethodHead, "/workshop/demo-mode.json", 200},
		{http.MethodGet, "/workshop/demo-mode.json?x=1", 400},
		{http.MethodPost, "/workshop/demo-mode.json", 405},
	} {
		response := httptest.NewRecorder()
		s.Handler().ServeHTTP(response, httptest.NewRequest(tc.method, tc.path, nil))
		if response.Code != tc.status || (tc.method == http.MethodHead && response.Body.Len() != 0) {
			t.Fatalf("%s %s = %d %q", tc.method, tc.path, response.Code, response.Body.String())
		}
	}
}

func TestWorkshopRealDemoPrivateModeHandshakeHTTP(t *testing.T) {
	calls := 0
	private := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var body map[string]any
		if r.Method != http.MethodPost || r.URL.Path != "/internal/commerce/demo-mode" ||
			r.Header.Get("X-Autodata-Internal-Token") != "fixture-token" ||
			r.Header.Get("Cookie") != "" || json.NewDecoder(r.Body).Decode(&body) != nil || len(body) != 0 {
			t.Error("demo mode did not use the bounded private authority")
		}
		_, _ = w.Write([]byte(`{"mode":"stripe_test","purchase_enabled":true}`))
	}))
	defer private.Close()
	client, err := NewHTTPCommerceClient(private.URL, "fixture-token")
	if err != nil {
		t.Fatal(err)
	}
	s := NewServer(staticReadiness{})
	s.commerceClient = client
	s.workshopTestCheckout = true
	response := httptest.NewRecorder()
	s.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/demo-mode.json", nil))
	if response.Code != 200 || response.Body.String() != "{\"enabled\":true}\n" || calls != 1 {
		t.Fatalf("public signal = %d %q; private calls=%d", response.Code, response.Body.String(), calls)
	}
}

func TestWorkshopEntryAliasesShareContentAndValidators(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	handler := server.Handler()
	request := func(method, path, tag string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(method, path, nil)
		if tag != "" {
			r.Header.Set("If-None-Match", tag)
		}
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		return w
	}
	entry := request(http.MethodGet, "/workshop", "")
	tag := entry.Header().Get("ETag")
	if entry.Code != http.StatusOK || tag == "" || !strings.Contains(entry.Body.String(), `class="wordmark" href="/workshop"`) {
		t.Fatal("canonical Workshop entry unavailable")
	}
	for _, path := range []string{"/workshop", "/workshop/"} {
		for _, query := range []string{"", "?year=2024&make=buick-truck&model=envision-awd&region=US", "?view=library", "?sample=1", "?demo=1", "?order=22222222-2222-4222-8222-222222222222&q=brake%2Bline"} {
			for _, method := range []string{http.MethodGet, http.MethodHead} {
				fresh := request(method, path+query, "")
				if fresh.Code != http.StatusOK || fresh.Header().Get("Location") != "" || fresh.Header().Get("ETag") != tag ||
					fresh.Header().Get("Cache-Control") != expectedWorkshopEntryCache ||
					fresh.Header().Get("Vercel-CDN-Cache-Control") != "" || fresh.Header().Get("Set-Cookie") != "" {
					t.Fatalf("%s %s: unexpected entry response %d %v", method, path+query, fresh.Code, fresh.Header())
				}
				if method == http.MethodGet && !bytes.Equal(fresh.Body.Bytes(), entry.Body.Bytes()) || method == http.MethodHead && fresh.Body.Len() != 0 {
					t.Fatalf("%s %s: unexpected entry body", method, path+query)
				}
				warm := request(method, path+query, tag)
				if warm.Code != http.StatusNotModified || warm.Body.Len() != 0 || warm.Header().Get("ETag") != tag ||
					warm.Header().Get("Cache-Control") != expectedWorkshopEntryCache {
					t.Fatalf("%s %s: unexpected conditional response %d %v", method, path+query, warm.Code, warm.Header())
				}
			}
		}
		unsupported := request(http.MethodPost, path, "")
		if unsupported.Code != http.StatusMethodNotAllowed || unsupported.Header().Get("Allow") != "GET, HEAD" {
			t.Fatalf("POST %s: unexpected response %d %v", path, unsupported.Code, unsupported.Header())
		}
	}
}

// Catches missing/stale embedded artifacts and provenance that describes different
// bytes from the SDK and license actually returned to an unauthenticated client.
func TestWorkshopFirebaseServedProvenance(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	serve := func(path string) []byte {
		t.Helper()
		response := httptest.NewRecorder()
		server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop/"+path, nil))
		if response.Code != http.StatusOK {
			t.Fatalf("%s: status=%d", path, response.Code)
		}
		return response.Body.Bytes()
	}
	type artifact struct {
		Path   string `json:"path"`
		SHA256 string `json:"sha256"`
		Bytes  int    `json:"bytes"`
	}
	var provenance struct {
		Schema  string `json:"schema"`
		Version int    `json:"version"`
		SDK     struct {
			Name    string `json:"name"`
			Version string `json:"version"`
		} `json:"sdk"`
		Dependencies map[string]string `json:"dependencies"`
		Build        struct {
			Tool    string `json:"tool"`
			Version string `json:"version"`
			Options struct {
				Bundle        bool   `json:"bundle"`
				Format        string `json:"format"`
				Platform      string `json:"platform"`
				Target        string `json:"target"`
				Minify        bool   `json:"minify"`
				LegalComments string `json:"legalComments"`
				Sourcemap     bool   `json:"sourcemap"`
			} `json:"options"`
		} `json:"build"`
		Inputs   []artifact `json:"inputs"`
		Outputs  []artifact `json:"outputs"`
		Exports  []string   `json:"exports"`
		Licenses []struct {
			ID     string `json:"id"`
			Source string `json:"source"`
			SHA256 string `json:"sha256"`
			Bytes  int    `json:"bytes"`
		} `json:"licenses"`
	}

	const apacheSHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
	const apacheBytes = 11358
	legal := string(serve("firebase-web.mjs.LEGAL.txt"))
	_, terms, found := strings.Cut(legal, "===== Apache-2.0 full license =====\n")
	if !found {
		t.Fatal("served legal asset is missing full Apache-2.0 terms")
	}
	terms, _, found = strings.Cut(terms, "===== End Apache-2.0 full license =====")
	digest := sha256.Sum256([]byte(terms))
	if !found || len(terms) != apacheBytes || hex.EncodeToString(digest[:]) != apacheSHA256 {
		t.Fatal("served Apache-2.0 terms are truncated or altered")
	}
	if !strings.Contains(legal, "Copyright 2017 Google LLC") || !strings.Contains(legal, "Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted") {
		t.Fatal("served legal asset lost extracted headers or ISC terms")
	}
	if err := json.Unmarshal(serve("firebase-web.provenance.json"), &provenance); err != nil {
		t.Fatal(err)
	}
	if len(provenance.Licenses) != 1 || provenance.Licenses[0].ID != "Apache-2.0" || provenance.Licenses[0].Source != "https://www.apache.org/licenses/LICENSE-2.0.txt" || provenance.Licenses[0].SHA256 != apacheSHA256 || provenance.Licenses[0].Bytes != apacheBytes {
		t.Fatalf("unexpected official license provenance: %+v", provenance.Licenses)
	}
	if provenance.Schema != "autodata.firebase-web.provenance" || provenance.Version != 1 || provenance.SDK.Name != "firebase" || provenance.SDK.Version != "12.19.0" {
		t.Fatalf("unexpected provenance identity: %+v", provenance)
	}
	if provenance.Dependencies["@firebase/app"] != "0.16.2" || provenance.Dependencies["@firebase/auth"] != "1.13.6" {
		t.Fatalf("unexpected app/auth versions: %v", provenance.Dependencies)
	}
	options := provenance.Build.Options
	if provenance.Build.Tool != "esbuild" || provenance.Build.Version != "0.28.2" || !options.Bundle || options.Format != "esm" || options.Platform != "browser" || options.Target != "es2022" || !options.Minify || options.LegalComments != "external" || options.Sourcemap {
		t.Fatalf("unexpected build contract: %+v", provenance.Build)
	}
	wantExports := []string{"GoogleAuthProvider", "browserPopupRedirectResolver", "getIdTokenResult", "inMemoryPersistence", "initializeApp", "initializeAuth", "reauthenticateWithPopup", "setPersistence", "signInWithPopup", "signOut"}
	if !reflect.DeepEqual(provenance.Exports, wantExports) {
		t.Fatalf("unexpected exports: %v", provenance.Exports)
	}
	wantInputs := []string{"apps/api-go/workshop-client/build.mjs", "apps/api-go/workshop-client/firebase-entry.mjs", "apps/api-go/workshop-client/package-lock.json", "apps/api-go/workshop-client/package.json"}
	if len(provenance.Inputs) != len(wantInputs) {
		t.Fatalf("unexpected inputs: %+v", provenance.Inputs)
	}
	for i, input := range provenance.Inputs {
		digest, err := hex.DecodeString(input.SHA256)
		if input.Path != wantInputs[i] || input.Bytes <= 0 || err != nil || len(digest) != sha256.Size {
			t.Fatalf("invalid input: %+v", input)
		}
	}
	wantOutputs := []string{"apps/api-go/workshop/firebase-web.mjs", "apps/api-go/workshop/firebase-web.mjs.LEGAL.txt"}
	if len(provenance.Outputs) != len(wantOutputs) {
		t.Fatalf("unexpected outputs: %+v", provenance.Outputs)
	}
	for i, output := range provenance.Outputs {
		if output.Path != wantOutputs[i] {
			t.Fatalf("unexpected artifact path: %s", output.Path)
		}
		data := serve(strings.TrimPrefix(output.Path, "apps/api-go/workshop/"))
		digest := sha256.Sum256(data)
		if len(data) == 0 || output.Bytes != len(data) || output.SHA256 != hex.EncodeToString(digest[:]) {
			t.Fatalf("served bytes differ from provenance: %+v", output)
		}
	}
}
