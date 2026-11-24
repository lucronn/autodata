package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestWorkshopTestNotices(t *testing.T) {
	for _, enabled := range []bool{false, true} {
		s := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
		s.workshopTestCheckout = enabled
		for _, name := range []string{"terms", "privacy", "refund", "contact"} {
			for _, method := range []string{"GET", "HEAD"} {
				w := httptest.NewRecorder()
				s.Handler().ServeHTTP(w, httptest.NewRequest(method, "/workshop/test-notices/"+name, nil))
				want := 404
				if enabled {
					want = 200
				}
				if w.Code != want {
					t.Fatalf("enabled=%v %s %s status=%d", enabled, method, name, w.Code)
				}
				if enabled && (w.Header().Get("Cache-Control") != "no-store" || w.Header().Get("Content-Security-Policy") == "") {
					t.Fatal("missing notice security headers")
				}
				if enabled && method == "GET" && (!strings.Contains(w.Body.String(), "No real money") || !strings.Contains(w.Body.String(), "<main>") || strings.Count(w.Body.String(), "<h1>") != 1) {
					t.Fatal("missing honest accessible notice")
				}
				if enabled && method == "GET" && !strings.Contains(w.Body.String(), `href="/workshop?demo=1"`) {
					t.Fatal("test notice does not return to the canonical Workshop entry")
				}
				if enabled && method == "HEAD" && w.Body.Len() != 0 {
					t.Fatal("HEAD returned body")
				}
			}
		}
		for _, path := range []string{"/workshop/test-notices/missing", "/workshop/test-notices/", "/workshop/test-notices/terms/extra", "/workshop/test-notices/%74erms", "/workshop/test-notices/terms?next=https://example.com"} {
			w := httptest.NewRecorder()
			s.Handler().ServeHTTP(w, httptest.NewRequest("GET", path, nil))
			if w.Code != 404 {
				t.Fatalf("unexpected notice %q: %d", path, w.Code)
			}
		}
		w := httptest.NewRecorder()
		s.Handler().ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/workshop/test-notices/terms", nil))
		if enabled && w.Code != 405 {
			t.Fatal("accepted POST")
		}
	}
}
