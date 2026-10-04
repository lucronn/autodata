package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"testing"
)

const testCatalogImageSecret = "0123456789abcdef0123456789abcdef-test"

func TestCatalogImageReferenceIsOpaqueUniqueAndAuthenticated(t *testing.T) {
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	source := "procedure-images/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	first, err := sealCatalogImageReference(source, key)
	if err != nil {
		t.Fatal(err)
	}
	second, err := sealCatalogImageReference(source, key)
	if err != nil {
		t.Fatal(err)
	}
	if first == second {
		t.Fatal("repeated references must use unique randomized paths")
	}
	for _, token := range []string{first, second} {
		if strings.Contains(token, "procedure-images") || strings.Contains(token, "0123456789") {
			t.Fatalf("opaque token reveals object key: %q", token)
		}
		decoded, err := openCatalogImageReference(token, key)
		if err != nil || decoded != source {
			t.Fatalf("openCatalogImageReference() = %q, %v", decoded, err)
		}
	}
	data, err := base64.RawURLEncoding.DecodeString(first)
	if err != nil {
		t.Fatal(err)
	}
	data[len(data)-1] ^= 1
	if _, err := openCatalogImageReference(base64.RawURLEncoding.EncodeToString(data), key); err == nil {
		t.Fatal("modified token must fail authentication")
	}
}

func TestCatalogImageProjectionConvertsLegacySourceQueryToOpaquePath(t *testing.T) {
	article := CatalogArticle{Images: []CatalogImage{
		{ID: "image-1", URL: "/v1/catalog/images?src=https%3A%2F%2Fautoapitwo.vercel.app%2Ffig%2Fbrake.png", StorageKey: "procedure-images/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
		{ID: "image-2", URL: "https://autoapitwo.vercel.app/fig/brake.png"},
	}}
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	rewriteCatalogImageURLs(&article, key)
	if len(article.Images) != 2 || !strings.HasPrefix(article.Images[0].URL, "/v1/catalog/images/") || article.Images[1].URL != "" {
		t.Fatalf("images were not projected to opaque paths: %#v", article.Images)
	}
	serialized := article.Images[0].URL + article.Images[1].URL
	if strings.Contains(serialized, "src=") || strings.Contains(serialized, "autoapitwo") || strings.Contains(serialized, "brake.png") {
		t.Fatalf("public image paths reveal source details: %s", serialized)
	}
	article.Images[0].StorageKey = "../secret"
	rewriteCatalogImageURLs(&article, key)
	if article.Images[0].URL != "" {
		t.Fatalf("non-allowlisted source should not produce a public image URL: %#v", article.Images[0])
	}
}

func TestCatalogImageStorageKeyLoadsPrivatelyAndNeverSerializes(t *testing.T) {
	const payload = `{"id":"img-1","url":"/legacy","storage_key":"procedure-images/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}`
	var image CatalogImage
	if err := json.Unmarshal([]byte(payload), &image); err != nil {
		t.Fatal(err)
	}
	if image.StorageKey == "" {
		t.Fatal("persisted object key was lost during decode")
	}
	encoded, err := json.Marshal(image)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(encoded), "storage_key") || strings.Contains(string(encoded), "procedure-images/") {
		t.Fatalf("internal object key leaked in public JSON: %s", encoded)
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

func TestOpaqueCatalogImageEndpointReadsLocalObjectAndRejectsLegacyURL(t *testing.T) {
	secret := testCatalogImageSecret
	t.Setenv("AUTODATA_IMAGE_URL_KEY", secret)
	server := catalogServer(catalogFixtureStore())
	objectKey := "procedure-images/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	key := deriveCatalogImageReferenceKey(secret)
	token, err := sealCatalogImageReference(objectKey, key)
	if err != nil {
		t.Fatal(err)
	}

	server.catalogImageReader = fakeCatalogImageReader{key: objectKey, body: []byte("png-bytes"), mediaType: "image/png"}

	response := catalogRequest(server, "/v1/catalog/images/"+token)
	if response.Code != http.StatusOK || response.Body.String() != "png-bytes" || response.Header().Get("Content-Type") != "image/png" {
		t.Fatalf("opaque image response = %d %q %#v", response.Code, response.Body.String(), response.Header())
	}
	if response.Header().Get("Referrer-Policy") != "no-referrer" {
		t.Fatalf("missing referrer policy: %#v", response.Header())
	}

	legacy := catalogRequest(server, "/v1/catalog/images?src=https%3A%2F%2Fautoapitwo.vercel.app%2Fdiagram.png")
	if legacy.Code == http.StatusOK || strings.Contains(legacy.Body.String(), "autoapitwo.vercel.app") {
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

type fakeCatalogImageReader struct {
	key       string
	body      []byte
	mediaType string
}

func (reader fakeCatalogImageReader) ReadImage(_ context.Context, key string) ([]byte, string, error) {
	if key != reader.key {
		return nil, "", errors.New("unexpected object key")
	}
	return reader.body, reader.mediaType, nil
}
