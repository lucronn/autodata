package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"sync"
	"testing"
	"time"
)

// Explicit test-only process entry point. It always serves the production
// embedded assets, over TLS; DTO interception belongs to the browser harness.
func TestWorkshopBrowserFixtureHTTP(t *testing.T) {
	if os.Getenv("AUTODATA_WORKSHOP_BROWSER_FIXTURE") != "1" {
		return
	}
	output := os.Getenv("AUTODATA_WORKSHOP_BROWSER_READY")
	if output == "" {
		t.Fatal("owned fixture ready-file path is required")
	}
	firebase := newFirebaseSDKFixture(t)
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	stopped := make(chan struct{})
	var once sync.Once
	mux := http.NewServeMux()
	mux.HandleFunc("GET /__fixture/token", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		token := firebase.token(t, func(claims map[string]any) {
			if r.URL.Query().Get("stale") == "1" {
				claims["auth_time"] = firebase.now.Unix() - 301
			}
		})
		writeJSON(w, 200, map[string]any{"idToken": token, "refreshToken": "synthetic-refresh-never-persist", "expiresIn": "3600", "localId": "fixture-user", "email": "fixture@example.invalid", "providerId": "google.com"})
	})
	mux.HandleFunc("POST /__fixture/stop", func(w http.ResponseWriter, r *http.Request) { once.Do(func() { close(stopped) }); w.WriteHeader(204) })
	mux.Handle("/", server.Handler())
	tlsServer := httptest.NewTLSServer(mux)
	defer tlsServer.Close()
	digest := sha256.Sum256(tlsServer.Certificate().Raw)
	sdk, err := dashboardFiles.ReadFile("workshop/firebase-web.mjs")
	if err != nil {
		t.Fatal(err)
	}
	sdkHash := sha256.Sum256(sdk)
	body, _ := json.Marshal(map[string]any{"version": "v1", "kind": "dto-fixture", "origin": tlsServer.URL, "certificate_sha256": hex.EncodeToString(digest[:]), "sdk_sha256": hex.EncodeToString(sdkHash[:])})
	if err = os.WriteFile(output, body, 0600); err != nil {
		t.Fatal(err)
	}
	select {
	case <-stopped:
	case <-time.After(4400 * time.Second):
		t.Fatal("browser fixture hard deadline exceeded")
	}
}
