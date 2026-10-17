package main

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

func TestMinioCatalogImageReaderReadsOnlyValidatedLocalObject(t *testing.T) {
	const storageKey = "procedure-images/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	const expected = "localized-image-bytes"
	var getCount atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		if request.URL.Query().Has("location") {
			response.Header().Set("Content-Type", "application/xml")
			_, _ = io.WriteString(response, `<LocationConstraint xmlns="http://s3.amazonaws.com/doc/2006-03-01/">us-east-1</LocationConstraint>`)
			return
		}
		if request.URL.Path != "/autodata-sources/"+storageKey {
			t.Errorf("object-store request = %s %q?%s", request.Method, request.URL.Path, request.URL.RawQuery)
		}
		if request.Header.Get("Authorization") == "" {
			t.Error("S3-compatible request was not signed")
		}
		response.Header().Set("Content-Type", "image/png")
		response.Header().Set("Content-Length", "21")
		response.Header().Set("Last-Modified", time.Now().UTC().Format(http.TimeFormat))
		response.Header().Set("ETag", `"local-test-etag"`)
		if request.Method == http.MethodGet {
			getCount.Add(1)
			_, _ = io.WriteString(response, expected)
			return
		}
		if request.Method != http.MethodHead {
			response.WriteHeader(http.StatusMethodNotAllowed)
		}
	}))
	defer server.Close()

	client, err := minio.New(server.Listener.Addr().String(), &minio.Options{
		Creds:        credentials.NewStaticV4("local-test-access", "local-test-secret", ""),
		Secure:       false,
		BucketLookup: minio.BucketLookupPath,
	})
	if err != nil {
		t.Fatal(err)
	}
	reader := &minioCatalogImageReader{client: client, bucket: "autodata-sources"}
	body, contentType, err := reader.ReadImage(context.Background(), storageKey)
	if err != nil {
		t.Fatalf("ReadImage() error = %v", err)
	}
	if string(body) != expected || contentType != "image/png" {
		t.Fatalf("ReadImage() = %q, %q", body, contentType)
	}
	if _, _, err := reader.ReadImage(context.Background(), "../../provider.example/image.png"); err == nil {
		t.Fatal("invalid key must not reach object storage")
	}

	t.Setenv("AUTODATA_IMAGE_URL_KEY", testCatalogImageSecret)
	api := catalogServer(newMemoryCatalogStore())
	api.catalogImageKey = deriveCatalogImageReferenceKey(testCatalogImageSecret)
	api.catalogImageReader = reader
	token, err := sealCatalogImageReference(storageKey, api.catalogImageKey)
	if err != nil {
		t.Fatal(err)
	}
	for read := 0; read < 2; read++ {
		request := httptest.NewRequest(http.MethodGet, "/v1/catalog/images/"+token, nil)
		response := httptest.NewRecorder()
		api.Handler().ServeHTTP(response, request)
		if response.Code != http.StatusOK || response.Body.String() != expected || response.Header().Get("Content-Type") != "image/png" {
			t.Fatalf("cold/warm API image read %d = %d %q", read, response.Code, response.Body.String())
		}
	}
	if getCount.Load() != 3 { // one direct reader check, plus API cold and warm reads
		t.Fatalf("object store GET count = %d, want 3", getCount.Load())
	}
	if strings.Contains(token, "procedure-images") {
		t.Fatal("API image token exposes the object key")
	}
}
