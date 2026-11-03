package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func paidMediaTestReference(now time.Time) paidCatalogImageReference {
	return paidCatalogImageReference{Version: 2, IssuedAt: now.Unix(), ExpiresAt: now.Unix() + 300,
		CustomerAccountID: "11111111-1111-4111-8111-111111111111", ConfigurationID: "22222222-2222-4222-8222-222222222222", Region: "US", CanonicalArticleID: "33333333-3333-4333-8333-333333333333", ProviderSlug: "bankone",
		SourceVehicleRefSHA256: strings.Repeat("a", 64), SourceArticleRefSHA256: strings.Repeat("b", 64), SelectedSourceRevisionID: "44444444-4444-4444-8444-444444444444", AnchorSourceRevisionID: "55555555-5555-4555-8555-555555555555", AnchorCanonicalRevisionID: stringPointer("66666666-6666-4666-8666-666666666666"), Projection: "article", AssetID: "asset-1", ObjectKey: "procedure-images/" + strings.Repeat("a", 64)}
}
func paidMediaSealRaw(t *testing.T, raw []byte, key []byte) string {
	t.Helper()
	block, err := aes.NewCipher(key)
	if err != nil {
		t.Fatal(err)
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		t.Fatal(err)
	}
	nonce := make([]byte, aead.NonceSize())
	if _, err = rand.Read(nonce); err != nil {
		t.Fatal(err)
	}
	return "v2." + base64.RawURLEncoding.EncodeToString(aead.Seal(nonce, nonce, raw, []byte("autodata:catalog-image:v2")))
}
func TestPaidCatalogMediaCodecAuthenticatedAndContextual(t *testing.T) {
	now := time.Unix(1800000000, 0)
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	ref := paidMediaTestReference(now)
	first, err := sealPaidCatalogImageReference(ref, key, now)
	if err != nil {
		t.Fatal(err)
	}
	second, err := sealPaidCatalogImageReference(ref, key, now)
	if err != nil {
		t.Fatal(err)
	}
	if first == second || !strings.HasPrefix(first, "v2.") || strings.Contains(first, "procedure-images") {
		t.Fatal("reference is not randomized opaque v2")
	}
	got, err := openPaidCatalogImageReference(first, key, now)
	if err != nil || got.ObjectKey != ref.ObjectKey || got.CustomerAccountID != ref.CustomerAccountID {
		t.Fatalf("decode: %#v %v", got, err)
	}
	corrupted := []byte(first)
	if corrupted[len(corrupted)-3] == 'a' {
		corrupted[len(corrupted)-3] = 'b'
	} else {
		corrupted[len(corrupted)-3] = 'a'
	}
	v1, err := sealCatalogImageReference(ref.ObjectKey, key)
	if err != nil {
		t.Fatal(err)
	}
	for _, token := range []string{string(corrupted), v1, "v2.", strings.Repeat("x", 6001)} {
		if _, err := openPaidCatalogImageReference(token, key, now); err == nil {
			t.Fatal("invalid token accepted")
		}
	}
	if _, err := openPaidCatalogImageReference(first, deriveCatalogImageReferenceKey(strings.Repeat("z", 32)), now); err == nil {
		t.Fatal("wrong key accepted")
	}
	if _, err := openCatalogImageReference(strings.TrimPrefix(first, "v2."), key); err == nil {
		t.Fatal("v2 ciphertext accepted with v1 AAD")
	}
	ref.AnchorCanonicalRevisionID = nil
	token, err := sealPaidCatalogImageReference(ref, key, now)
	if err != nil {
		t.Fatal(err)
	}
	got, err = openPaidCatalogImageReference(token, key, now)
	if err != nil || got.AnchorCanonicalRevisionID != nil {
		t.Fatal("source fallback null anchor lost")
	}
}
func TestPaidCatalogMediaCodecStrictPayloadAndTime(t *testing.T) {
	now := time.Unix(1800000000, 0)
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	ref := paidMediaTestReference(now)
	raw, err := json.Marshal(ref)
	if err != nil {
		t.Fatal(err)
	}
	var valid map[string]any
	if err = json.Unmarshal(raw, &valid); err != nil {
		t.Fatal(err)
	}
	cases := map[string]func(map[string]any){
		"unknown": func(m map[string]any) { m["extra"] = true }, "missing": func(m map[string]any) { delete(m, "anchor_canonical_revision_id") },
		"version": func(m map[string]any) { m["version"] = 1 }, "uuid": func(m map[string]any) { m["configuration_id"] = "vehicle-alias" }, "region": func(m map[string]any) { m["region"] = "us" },
		"digest": func(m map[string]any) { m["source_vehicle_ref_sha256"] = strings.Repeat("A", 64) }, "projection": func(m map[string]any) { m["projection"] = "any" }, "object": func(m map[string]any) { m["object_key"] = "../private" }, "asset": func(m map[string]any) { m["asset_id"] = "https://provider/image" },
		"expiry": func(m map[string]any) { m["expires_at"] = now.Unix() }, "lifetime": func(m map[string]any) { m["expires_at"] = now.Unix() + 301 }, "future": func(m map[string]any) { m["issued_at"] = now.Unix() + 31; m["expires_at"] = now.Unix() + 331 }, "oversize": func(m map[string]any) { m["asset_id"] = strings.Repeat("a", 4096) }, "null-account": func(m map[string]any) { m["customer_account_id"] = nil },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			m := map[string]any{}
			for k, v := range valid {
				m[k] = v
			}
			mutate(m)
			bad, _ := json.Marshal(m)
			if _, err := openPaidCatalogImageReference(paidMediaSealRaw(t, bad, key), key, now); err == nil {
				t.Fatal("invalid payload accepted")
			}
		})
	}
	for name, bad := range map[string][]byte{"duplicate": append([]byte(`{"version":2,`), raw[1:]...), "trailing": append(append([]byte(nil), raw...), []byte(` {}`)...), "array": []byte(`[]`)} {
		t.Run(name, func(t *testing.T) {
			if _, err := openPaidCatalogImageReference(paidMediaSealRaw(t, bad, key), key, now); err == nil {
				t.Fatal("invalid JSON accepted")
			}
		})
	}
	token, err := sealPaidCatalogImageReference(ref, key, now)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := openPaidCatalogImageReference(token, key, now.Add(300*time.Second)); err == nil {
		t.Fatal("expired reference accepted")
	}
	if _, err := sealPaidCatalogImageReference(ref, nil, now); err == nil {
		t.Fatal("weak key accepted")
	}
}
