package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

func TestWorkshopAssetsAvailableWithoutCatalogCredentials(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	for _, asset := range []struct{ path, contentType string }{
		{"/workshop/", "text/html"},
		{"/workshop/styles.css", "text/css"},
		{"/workshop/app.mjs", "javascript"},
		{"/workshop/catalog.mjs", "javascript"},
		{"/workshop/firebase-web.mjs", "javascript"},
		{"/workshop/firebase-web.mjs.LEGAL.txt", "text/plain"},
		{"/workshop/firebase-web.provenance.json", "application/json"},
		{"/workshop/fonts/InstrumentSans.ttf", "font/ttf"},
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

func TestWorkshopRedirectPreservesSeparateEntryPoint(t *testing.T) {
	server := NewServerWithDependencies(staticReadiness{}, &fakeAuthenticator{err: ErrUnauthenticated}, newMemoryRequestStore())
	response := httptest.NewRecorder()
	server.Handler().ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/workshop", nil))
	if response.Code != http.StatusMovedPermanently || response.Header().Get("Location") != "/workshop/" {
		t.Fatalf("unexpected redirect: %d %s", response.Code, response.Header().Get("Location"))
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
		Inputs  []artifact `json:"inputs"`
		Outputs []artifact `json:"outputs"`
		Exports []string   `json:"exports"`
	}
	if err := json.Unmarshal(serve("firebase-web.provenance.json"), &provenance); err != nil {
		t.Fatal(err)
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
