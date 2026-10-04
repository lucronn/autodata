package main

import (
	"encoding/json"
	"os"
	"regexp"
	"strings"
	"testing"
)

var opaqueCatalogImageTokenExample = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

func TestCatalogOpenAPIContractDocumentsSafeSourceAndOpaqueMedia(t *testing.T) {
	jsonSpec, err := os.ReadFile("openapi.json")
	if err != nil {
		t.Fatal(err)
	}
	var document map[string]any
	if err := json.Unmarshal(jsonSpec, &document); err != nil {
		t.Fatalf("openapi.json is invalid: %v", err)
	}
	paths, ok := document["paths"].(map[string]any)
	if !ok {
		t.Fatal("openapi.json paths are missing")
	}
	for _, path := range []string{
		"/v1/catalog/vehicles/{vehicle_id}/compositions",
		"/v1/catalog/vehicles/{vehicle_id}/articles/{article_id}/source",
		"/v1/catalog/images/{token}",
		"/v1/catalog/images",
	} {
		if _, ok := paths[path]; !ok {
			t.Fatalf("OpenAPI is missing registered path %q", path)
		}
	}
	compositionPost, ok := paths["/v1/catalog/vehicles/{vehicle_id}/compositions"].(map[string]any)["post"].(map[string]any)
	if !ok || compositionPost["operationId"] != "composeVehicleProcedures" {
		t.Fatal("OpenAPI composition operation is missing or has an unexpected operationId")
	}

	sourceGet := paths["/v1/catalog/vehicles/{vehicle_id}/articles/{article_id}/source"].(map[string]any)["get"].(map[string]any)
	content := sourceGet["responses"].(map[string]any)["200"].(map[string]any)["content"].(map[string]any)
	for _, mediaType := range []string{"application/json", "text/html"} {
		if _, ok := content[mediaType]; !ok {
			t.Fatalf("source route is missing %s representation", mediaType)
		}
	}

	imageGet := paths["/v1/catalog/images/{token}"].(map[string]any)["get"].(map[string]any)
	parameters := imageGet["parameters"].([]any)
	var tokenExample string
	for _, rawParameter := range parameters {
		parameter := rawParameter.(map[string]any)
		if parameter["name"] == "token" {
			tokenExample, _ = parameter["schema"].(map[string]any)["example"].(string)
		}
	}
	if len(tokenExample) < 40 || len(tokenExample) > 6000 || !opaqueCatalogImageTokenExample.MatchString(tokenExample) {
		t.Fatalf("opaque image example is not a valid URL-safe token: %q", tokenExample)
	}

	serialized := string(jsonSpec)
	if strings.Contains(serialized, "storage_key") {
		t.Fatalf("public OpenAPI contains an internal storage key")
	}

	yamlSpec, err := os.ReadFile("openapi.yaml")
	if err != nil {
		t.Fatal(err)
	}
	yaml := string(yamlSpec)
	for _, required := range []string{
		"/v1/catalog/vehicles/{vehicle_id}/compositions:",
		"/v1/catalog/vehicles/{vehicle_id}/articles/{article_id}/source:",
		"/v1/catalog/images/{token}:",
		"/v1/catalog/images:",
		"application/json:",
		"text/html:",
		"example: IiIiIiIiIiIiIiIiHwuS-wx8k9Ql3htAjUd6PVg2n76mnd0I-cZlfDg9aebtUBIpKO8j5A",
	} {
		if !strings.Contains(yaml, required) {
			t.Fatalf("openapi.yaml is missing %q", required)
		}
	}
	if strings.Contains(yaml, "storage_key") {
		t.Fatal("public OpenAPI YAML contains an internal storage key")
	}
}
