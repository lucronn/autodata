package main

import (
	"os/exec"
	"strings"
	"testing"
)

// Exercise the actual Go producer and JS consumer together: neither side may
// substitute a hand-authored token or broaden the Firebase media policy.
func TestLocalCatalogImageTokenClientContract(t *testing.T) {
	node, err := exec.LookPath("node")
	if err != nil {
		t.Skip("Node is required for the Go/JS image token contract")
	}
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	objectKey := "procedure-images/" + strings.Repeat("a", 64)
	article := CatalogArticle{Images: []CatalogImage{{ID: "local-image", StorageKey: objectKey}}}
	rewriteCatalogImageURLs(&article, key)
	path := article.Images[0].URL
	token := strings.TrimPrefix(path, "/v1/catalog/images/")
	if decoded, err := openCatalogImageReference(token, key); err != nil || decoded != objectKey {
		t.Fatalf("actual local projection did not round trip: %v", err)
	}
	script := `import assert from 'node:assert/strict';
 import { localImageURL } from './workshop/catalog.mjs';
 const path=process.argv[1],origin='https://cars.example';
 assert.equal(localImageURL(path,origin,{authMode:'local'}),origin+path);
 assert.equal(localImageURL(path,origin),null);
 assert.equal(localImageURL(path,origin,{authMode:'firebase'}),null);
 assert.equal(localImageURL('https://external.example'+path,origin,{authMode:'local'}),null);`
	if output, err := exec.Command(node, "--input-type=module", "-e", script, path).CombinedOutput(); err != nil {
		t.Fatalf("Go-issued image URL rejected by local client contract: %v\n%s", err, output)
	}
}
