package main

import (
	"encoding/base64"
	"io"
	"net/http"
	"net/url"
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

func TestCatalogImageProjectionConvertsLegacySourceQueryToOpaquePath(t *testing.T) {
	article := CatalogArticle{Images: []CatalogImage{
		{ID: "image-1", URL: "/v1/catalog/images?src=https%3A%2F%2Fautoapitwo.vercel.app%2Ffig%2Fbrake.png"},
		{ID: "image-2", URL: "https://autoapitwo.vercel.app/fig/brake.png"},
	}}
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	rewriteCatalogImageURLs(&article, key)
	if len(article.Images) != 2 || !strings.HasPrefix(article.Images[0].URL, "/v1/catalog/images/") || !strings.HasPrefix(article.Images[1].URL, "/v1/catalog/images/") {
		t.Fatalf("images were not projected to opaque paths: %#v", article.Images)
	}
	if article.Images[0].URL == article.Images[1].URL {
		t.Fatal("each public image reference must be independently unique")
	}
	serialized := article.Images[0].URL + article.Images[1].URL
	if strings.Contains(serialized, "src=") || strings.Contains(serialized, "autoapitwo") || strings.Contains(serialized, "brake.png") {
		t.Fatalf("public image paths reveal source details: %s", serialized)
	}
	article.Images[0].URL = "/v1/catalog/images?src=https%3A%2F%2Fevil.example%2Fsecret.png"
	rewriteCatalogImageURLs(&article, key)
	if article.Images[0].URL != "" {
		t.Fatalf("non-allowlisted source should not produce a public image URL: %#v", article.Images[0])
	}
}

func TestArticleIndexDoesNotExposeSourceImagePaths(t *testing.T) {
	t.Setenv("AUTODATA_IMAGE_URL_KEY", testCatalogImageSecret)
	response := catalogRequest(catalogServer(catalogFixtureStore()), "/v1/catalog/vehicles/vehicle-1/articles")
	if response.Code != http.StatusOK {
		t.Fatalf("article index status = %d: %s", response.Code, response.Body.String())
	}
	if strings.Contains(response.Body.String(), "autoapitwo.vercel.app") || strings.Contains(response.Body.String(), "?src=") {
		t.Fatalf("article index exposed a source image URL: %s", response.Body.String())
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

	previousClient := catalogImageClient
	catalogImageClient = &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		if request.URL.String() != source {
			t.Fatalf("upstream URL = %q, want allowlisted URL", request.URL)
		}
		return &http.Response{StatusCode: http.StatusOK, Header: http.Header{"Content-Type": []string{"image/png"}}, Body: io.NopCloser(strings.NewReader("png-bytes")), Request: request}, nil
	})}
	t.Cleanup(func() { catalogImageClient = previousClient })

	response := catalogRequest(server, "/v1/catalog/images/"+token)
	if response.Code != http.StatusOK || response.Body.String() != "png-bytes" || response.Header().Get("Content-Type") != "image/png" {
		t.Fatalf("opaque image response = %d %q %#v", response.Code, response.Body.String(), response.Header())
	}
	if response.Header().Get("Referrer-Policy") != "no-referrer" {
		t.Fatalf("missing referrer policy: %#v", response.Header())
	}

	legacy := catalogRequest(server, "/v1/catalog/images?src="+url.QueryEscape(source))
	if legacy.Code == http.StatusOK || strings.Contains(legacy.Body.String(), source) {
		t.Fatalf("legacy source-bearing URL was accepted or echoed: %d %s", legacy.Code, legacy.Body.String())
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
