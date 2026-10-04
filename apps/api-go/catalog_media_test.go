package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"
)

const testCatalogImageSecret = "0123456789abcdef0123456789abcdef-test"

func TestCatalogImageReferenceIsOpaqueUniqueAndAuthenticated(t *testing.T) {
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	source := "https://autoapitwo.vercel.app/api/v1/content/carids/123/images/figure-7.png"
	first, err := sealCatalogImageURL(source, key)
	if err != nil {
		t.Fatal(err)
	}
	second, err := sealCatalogImageURL(source, key)
	if err != nil {
		t.Fatal(err)
	}
	if first == second {
		t.Fatal("repeated references must use unique randomized paths")
	}
	for _, token := range []string{first, second} {
		if strings.Contains(token, "autoapitwo") || strings.Contains(token, "figure-7") || strings.Contains(token, "carids") {
			t.Fatalf("opaque token reveals source path: %q", token)
		}
		decoded, err := openCatalogImageURL(token, key)
		if err != nil || decoded != source {
			t.Fatalf("openCatalogImageURL() = %q, %v", decoded, err)
		}
	}
	data, err := base64.RawURLEncoding.DecodeString(first)
	if err != nil {
		t.Fatal(err)
	}
	data[len(data)-1] ^= 1
	if _, err := openCatalogImageURL(base64.RawURLEncoding.EncodeToString(data), key); err == nil {
		t.Fatal("modified token must fail authentication")
	}
}

func TestCatalogImageProjectionDropsUnlocalizedProviderURL(t *testing.T) {
	article := CatalogArticle{Images: []CatalogImage{
		{ID: "image-1", URL: "/v1/catalog/images?src=https%3A%2F%2Fautoapitwo.vercel.app%2Ffig%2Fbrake.png"},
		{ID: "image-2", URL: "https://autoapitwo.vercel.app/fig/brake.png"},
	}}
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	rewriteCatalogImageURLs(&article, key)
	for _, image := range article.Images {
		if image.URL != "" {
			t.Fatalf("unlocalized provider image must be omitted: %#v", article.Images)
		}
	}
}

func TestCatalogImageProjectionUsesStoredObjectKeyInsteadOfProviderURL(t *testing.T) {
	article := CatalogArticle{Images: []CatalogImage{{
		ID:         "image-1",
		URL:        "https://autoapitwo.vercel.app/fig/brake.png",
		StorageKey: "procedure-images/abc123",
	}}}
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	rewriteCatalogImageURLs(&article, key)
	if !strings.HasPrefix(article.Images[0].URL, "/v1/catalog/images/") {
		t.Fatalf("stored image was not projected to an opaque path: %#v", article.Images[0])
	}
	if strings.Contains(article.Images[0].URL, "autoapitwo") || strings.Contains(article.Images[0].URL, "procedure-images") {
		t.Fatalf("stored image path leaked provider or object key: %q", article.Images[0].URL)
	}
	token := strings.TrimPrefix(article.Images[0].URL, "/v1/catalog/images/")
	opened, err := openCatalogImageStorageKey(token, key)
	if err != nil || opened != "procedure-images/abc123" {
		t.Fatalf("openCatalogImageStorageKey() = %q, %v", opened, err)
	}
}

func TestCatalogImageDecodesInternalStorageKeyWithoutPublishingIt(t *testing.T) {
	var image CatalogImage
	if err := json.Unmarshal([]byte(`{"id":"image-1","storage_key":"procedure-images/abc123","media_type":"image/png"}`), &image); err != nil {
		t.Fatal(err)
	}
	if image.StorageKey != "procedure-images/abc123" || image.MediaType != "image/png" {
		t.Fatalf("decoded image = %#v", image)
	}
	encoded, err := json.Marshal(image)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(encoded), "storage_key") || strings.Contains(string(encoded), "procedure-images") {
		t.Fatalf("internal storage key was published: %s", encoded)
	}
}

func TestArticleIndexDoesNotExposeSourceImagePaths(t *testing.T) {
	t.Setenv("AUTODATA_IMAGE_URL_KEY", testCatalogImageSecret)
	response := catalogRequest(catalogServer(catalogFixtureStore()), "/v1/catalog/vehicles/vehicle-1/articles")
	if response.Code != http.StatusOK {
		t.Fatalf("article index status = %d: %s", response.Code, response.Body.String())
	}
	if strings.Contains(response.Body.String(), "autoapitwo.vercel.app") || strings.Contains(response.Body.String(), "?src=") || strings.Contains(response.Body.String(), "storage_key") || strings.Contains(response.Body.String(), "private/source-object/key") {
		t.Fatalf("article index exposed source image data or an internal storage key: %s", response.Body.String())
	}
}

func TestOpaqueCatalogImageEndpointServesAllowlistedImageAndRejectsLegacyURL(t *testing.T) {
	secret := testCatalogImageSecret
	t.Setenv("AUTODATA_IMAGE_URL_KEY", secret)
	server := catalogServer(catalogFixtureStore())
	source := "https://autoapitwo.vercel.app/diagram.png"
	key := deriveCatalogImageReferenceKey(secret)
	token, err := sealCatalogImageURL(source, key)
	if err != nil {
		t.Fatal(err)
	}
	response := catalogRequest(server, "/v1/catalog/images/"+token)
	if response.Code != http.StatusNotFound || strings.Contains(response.Body.String(), source) {
		t.Fatalf("legacy provider token response = %d %q", response.Code, response.Body.String())
	}

	legacy := catalogRequest(server, "/v1/catalog/images?src="+url.QueryEscape(source))
	if legacy.Code == http.StatusOK || strings.Contains(legacy.Body.String(), source) {
		t.Fatalf("legacy source-bearing URL was accepted or echoed: %d %s", legacy.Code, legacy.Body.String())
	}
}

func TestOpaqueCatalogImageEndpointServesStoredObjectWithoutProviderFetch(t *testing.T) {
	secret := testCatalogImageSecret
	t.Setenv("AUTODATA_IMAGE_URL_KEY", secret)
	server := catalogServer(catalogFixtureStore())
	key := deriveCatalogImageReferenceKey(secret)
	token, err := sealCatalogImageStorageKey("procedure-images/abc123", key)
	if err != nil {
		t.Fatal(err)
	}
	previousReader := catalogImageObjectReader
	catalogImageObjectReader = func(_ context.Context, storageKey string) (catalogImageObject, error) {
		if storageKey != "procedure-images/abc123" {
			t.Fatalf("storage key = %q", storageKey)
		}
		return catalogImageObject{Body: []byte("png-bytes"), ContentType: "image/png"}, nil
	}
	previousClient := catalogImageClient
	catalogImageClient = &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		t.Fatal("stored image path must not call a provider")
		return nil, nil
	})}
	t.Cleanup(func() {
		catalogImageObjectReader = previousReader
		catalogImageClient = previousClient
	})

	response := catalogRequest(server, "/v1/catalog/images/"+token)
	if response.Code != http.StatusOK || response.Body.String() != "png-bytes" || response.Header().Get("Content-Type") != "image/png" {
		t.Fatalf("stored image response = %d %q %#v", response.Code, response.Body.String(), response.Header())
	}
}

func TestOpaqueCatalogImageEndpointFailsSafelyForMissingStoredObject(t *testing.T) {
	t.Setenv("AUTODATA_IMAGE_URL_KEY", testCatalogImageSecret)
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	token, err := sealCatalogImageStorageKey("procedure-images/missing", key)
	if err != nil {
		t.Fatal(err)
	}
	previousReader := catalogImageObjectReader
	catalogImageObjectReader = func(context.Context, string) (catalogImageObject, error) {
		return catalogImageObject{}, os.ErrNotExist
	}
	t.Cleanup(func() { catalogImageObjectReader = previousReader })

	response := catalogRequest(catalogServer(catalogFixtureStore()), "/v1/catalog/images/"+token)
	if response.Code != http.StatusNotFound || strings.Contains(response.Body.String(), "procedure-images") {
		t.Fatalf("missing stored image response = %d %s", response.Code, response.Body.String())
	}
}

func TestCatalogImageObjectReaderReadsFromConfiguredAutoDataStorage(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		if request.URL.Path != "/autodata-sources/procedure-images/abc123" {
			t.Fatalf("object storage path = %q", request.URL.Path)
		}
		response.Header().Set("Content-Type", "image/png")
		_, _ = response.Write([]byte("png-bytes"))
	}))
	t.Cleanup(server.Close)
	t.Setenv("AUTODATA_S3_URL", server.URL)
	t.Setenv("AUTODATA_SOURCE_BUCKET", "autodata-sources")
	t.Setenv("AUTODATA_S3_ACCESS_KEY", "")
	t.Setenv("AUTODATA_S3_SECRET_KEY", "")

	object, err := readCatalogImageObject(context.Background(), "procedure-images/abc123")
	if err != nil || string(object.Body) != "png-bytes" || object.ContentType != "image/png" {
		t.Fatalf("readCatalogImageObject() = %#v, %v", object, err)
	}
}

func TestCatalogImageReferencesFailClosedWithoutAStableSecret(t *testing.T) {
	t.Setenv("AUTODATA_IMAGE_URL_KEY", "")
	t.Setenv("AUTODATA_INGESTION_INTERNAL_TOKEN", "")
	server := catalogServer(catalogFixtureStore())
	articleResponse := catalogRequest(server, "/v1/catalog/vehicles/vehicle-1/articles/article-1")
	if articleResponse.Code != http.StatusOK || strings.Contains(articleResponse.Body.String(), "autoapitwo.vercel.app") || strings.Contains(articleResponse.Body.String(), "?src=") {
		t.Fatalf("missing key did not fail closed in the public article: %d %s", articleResponse.Code, articleResponse.Body.String())
	}
	imageResponse := catalogRequest(server, "/v1/catalog/images/random-token")
	if imageResponse.Code != http.StatusServiceUnavailable || strings.Contains(imageResponse.Body.String(), "autoapitwo") {
		t.Fatalf("missing key image response = %d %s", imageResponse.Code, imageResponse.Body.String())
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) { return f(request) }
