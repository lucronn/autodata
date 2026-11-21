package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

const minioImageTestStorageKey = "procedure-images/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

func TestMinioCatalogImageReaderReadsOnlyValidatedLocalObject(t *testing.T) {
	const storageKey = minioImageTestStorageKey
	const expected = "\x89PNG\r\n\x1a\nfixture-localized"
	var getCount atomic.Int32
	var headCount atomic.Int32
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
		response.Header().Set("Content-Length", strconv.Itoa(len(expected)))
		response.Header().Set("Last-Modified", time.Now().UTC().Format(http.TimeFormat))
		response.Header().Set("ETag", `"local-test-etag"`)
		if request.Method == http.MethodGet {
			getCount.Add(1)
			_, _ = io.WriteString(response, expected)
			return
		}
		if request.Method != http.MethodHead {
			response.WriteHeader(http.StatusMethodNotAllowed)
		} else {
			headCount.Add(1)
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
	if headCount.Load() != 0 {
		t.Fatalf("object store HEAD count = %d, want 0", headCount.Load())
	}
	if strings.Contains(token, "procedure-images") {
		t.Fatal("API image token exposes the object key")
	}
}

func TestMinioCatalogImageReaderValidatesGetResponse(t *testing.T) {
	const png = "\x89PNG\r\n\x1a\nfixture"
	for _, test := range []struct {
		name, media, payload, contentRange, wantError, storageCode string
		length, status                                             int
	}{
		{name: "valid MIME parameters", media: "IMAGE/PNG; filename=fixture.png", payload: png, length: len(png)},
		{name: "invalid MIME claim", media: "image/png", payload: "not a PNG", length: 9, wantError: "catalog image media type is invalid"},
		{name: "unsupported MIME", media: "application/octet-stream", payload: png, length: len(png), wantError: "catalog image media type is invalid"},
		{name: "empty", media: "image/png", wantError: "catalog image size is invalid"},
		{name: "oversized", media: "image/png", length: catalogImageMaxBytes + 1, wantError: "catalog image size is invalid"},
		{name: "missing length", media: "image/png", payload: png, length: -1, wantError: "catalog image size is invalid"},
		{name: "truncated", media: "image/png", payload: png, length: len(png) + 1, wantError: "catalog image could not be read"},
		{name: "partial", media: "image/png", payload: png, length: len(png), status: http.StatusPartialContent, contentRange: "bytes 0-14/4000", wantError: "catalog image could not be read"},
		{name: "missing object", status: http.StatusNotFound, storageCode: "NoSuchKey"},
		{name: "missing bucket", status: http.StatusNotFound, storageCode: "NoSuchBucket"},
		{name: "storage denied", status: http.StatusForbidden, storageCode: "AccessDenied"},
	} {
		t.Run(test.name, func(t *testing.T) {
			var requests atomic.Int32
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests.Add(1)
				if r.Method != http.MethodGet || r.URL.Path != "/autodata-sources/"+minioImageTestStorageKey || r.Header.Get("Range") != "" {
					t.Errorf("unexpected object request: %s %s with range %q", r.Method, r.URL.Path, r.Header.Get("Range"))
					w.WriteHeader(http.StatusMethodNotAllowed)
					return
				}
				if test.storageCode != "" {
					w.Header().Set("Content-Type", "application/xml")
					w.WriteHeader(test.status)
					_, _ = fmt.Fprintf(w, "<Error><Code>%s</Code><Message>Fixture storage error</Message></Error>", test.storageCode)
					return
				}
				w.Header().Set("Content-Type", test.media)
				w.Header().Set("Last-Modified", time.Now().UTC().Format(http.TimeFormat))
				if test.length >= 0 {
					w.Header().Set("Content-Length", strconv.Itoa(test.length))
				}
				if test.contentRange != "" {
					w.Header().Set("Content-Range", test.contentRange)
					w.WriteHeader(test.status)
				}
				if test.length < 0 {
					w.(http.Flusher).Flush()
				}
				_, _ = io.WriteString(w, test.payload)
			}))
			defer server.Close()
			reader := newMinioImageTestReader(t, server.Listener.Addr().String(), nil)
			body, media, err := reader.ReadImage(context.Background(), minioImageTestStorageKey)
			if requests.Load() != 1 {
				t.Fatalf("object requests = %d, want one GET", requests.Load())
			}
			switch {
			case test.storageCode != "":
				if code := minio.ToErrorResponse(err).Code; code != test.storageCode || len(body) != 0 || media != "" {
					t.Fatalf("storage code = %q, want %q", code, test.storageCode)
				}
			case test.wantError != "":
				if err == nil || err.Error() != test.wantError || len(body) != 0 || media != "" {
					t.Fatalf("invalid response returned %d bytes, %q, %v", len(body), media, err)
				}
			default:
				if err != nil || string(body) != test.payload || media != "image/png" {
					t.Fatalf("valid response returned %q, %q, %v", body, media, err)
				}
			}
		})
	}
}

type minioImageTestTransport func(*http.Request) (*http.Response, error)

func (f minioImageTestTransport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

type minioImageTestBody struct {
	io.Reader
	read   int
	closed bool
}

func (b *minioImageTestBody) Read(data []byte) (int, error) {
	n, err := b.Reader.Read(data)
	b.read += n
	return n, err
}

func (b *minioImageTestBody) Close() error {
	b.closed = true
	return nil
}

func TestMinioCatalogImageReaderBoundsBytesWhenBodyExceedsDeclaredLength(t *testing.T) {
	const size = 8
	stream := &minioImageTestBody{Reader: strings.NewReader("\x89PNG\r\n\x1a\nextra bytes")}
	reader := newMinioImageTestReader(t, "127.0.0.1:1", minioImageTestTransport(func(r *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode:    http.StatusOK,
			ContentLength: size,
			Header: http.Header{
				"Content-Length": {strconv.Itoa(size)},
				"Content-Type":   {"image/png"},
				"Last-Modified":  {time.Now().UTC().Format(http.TimeFormat)},
			},
			Body:    stream,
			Request: r,
		}, nil
	}))
	if payload, media, err := reader.ReadImage(context.Background(), minioImageTestStorageKey); err == nil || len(payload) != 0 || media != "" {
		t.Fatalf("excess body returned %d bytes, %q, %v", len(payload), media, err)
	}
	if stream.read != size+1 || !stream.closed {
		t.Fatalf("excess body read = %d bytes, closed = %v", stream.read, stream.closed)
	}
}

func TestMinioCatalogImageReaderCancelsBodyRead(t *testing.T) {
	started := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		w.Header().Set("Content-Type", "image/png")
		w.Header().Set("Content-Length", "64")
		w.Header().Set("Last-Modified", time.Now().UTC().Format(http.TimeFormat))
		w.(http.Flusher).Flush()
		close(started)
		<-request.Context().Done()
	}))
	defer server.Close()
	reader := newMinioImageTestReader(t, server.Listener.Addr().String(), nil)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	result := make(chan error, 1)
	go func() {
		_, _, err := reader.ReadImage(ctx, minioImageTestStorageKey)
		result <- err
	}()
	select {
	case <-started:
		cancel()
	case <-ctx.Done():
		t.Fatal("GET did not start")
	}
	select {
	case err := <-result:
		if err == nil {
			t.Fatal("canceled image body was accepted")
		}
	case <-time.After(time.Second):
		t.Fatal("GET body did not observe cancellation")
	}
}

func newMinioImageTestReader(t *testing.T, endpoint string, transport http.RoundTripper) *minioCatalogImageReader {
	t.Helper()
	client, err := minio.New(endpoint, &minio.Options{
		Creds:        credentials.NewStaticV4("local-test-access", "local-test-secret", ""),
		Region:       "us-east-1",
		BucketLookup: minio.BucketLookupPath,
		Transport:    transport,
	})
	if err != nil {
		t.Fatal(err)
	}
	return &minioCatalogImageReader{client: client, bucket: "autodata-sources"}
}
