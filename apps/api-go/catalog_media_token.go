package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"io"
	"os"
	"regexp"
	"strings"
	"time"
)

const catalogImageTokenAAD = "autodata:catalog-image:v1"

var localCatalogImageKeyPattern = regexp.MustCompile(`^(procedure-images/[a-f0-9]{64}|sources/[a-f0-9]{16}/[a-f0-9]{64})$`)

// configuredCatalogImageKey uses an explicit media key when available, or
// derives a domain-separated key from the API's existing internal token.
// Missing or weak secrets fail closed; public responses then omit image URLs.
func configuredCatalogImageKey() []byte {
	secret := strings.TrimSpace(os.Getenv("AUTODATA_IMAGE_URL_KEY"))
	if secret == "" {
		secret = strings.TrimSpace(os.Getenv("AUTODATA_INGESTION_INTERNAL_TOKEN"))
	}
	return deriveCatalogImageReferenceKey(secret)
}

func deriveCatalogImageReferenceKey(secret string) []byte {
	if len(secret) < 32 {
		return nil
	}
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte("autodata/catalog-image-reference-key/v1"))
	return mac.Sum(nil)
}

func sealCatalogImageReference(objectKey string, key []byte) (string, error) {
	if len(key) != 32 || !localCatalogImageKeyPattern.MatchString(objectKey) {
		return "", errors.New("invalid catalog image reference")
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, aead.NonceSize())
	if _, err := rand.Read(nonce); err != nil {
		return "", err
	}
	sealed := aead.Seal(nonce, nonce, []byte(objectKey), []byte(catalogImageTokenAAD))
	return base64.RawURLEncoding.EncodeToString(sealed), nil
}

func openCatalogImageReference(token string, key []byte) (string, error) {
	if len(key) != 32 || len(token) == 0 || len(token) > 6000 {
		return "", errors.New("invalid catalog image reference")
	}
	sealed, err := base64.RawURLEncoding.DecodeString(token)
	if err != nil {
		return "", errors.New("invalid catalog image reference")
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", errors.New("invalid catalog image reference")
	}
	aead, err := cipher.NewGCM(block)
	if err != nil || len(sealed) < aead.NonceSize()+aead.Overhead() {
		return "", errors.New("invalid catalog image reference")
	}
	nonce, ciphertext := sealed[:aead.NonceSize()], sealed[aead.NonceSize():]
	plaintext, err := aead.Open(nil, nonce, ciphertext, []byte(catalogImageTokenAAD))
	if err != nil {
		return "", errors.New("invalid catalog image reference")
	}
	if !localCatalogImageKeyPattern.Match(plaintext) {
		return "", errors.New("invalid catalog image reference")
	}
	return string(plaintext), nil
}

const paidCatalogImageTokenAAD = "autodata:catalog-image:v2"

// This encrypted context is a reference, never a substitute for current grant
// and source-rights checks. Provider-local identities are bound only by hashes.
type paidCatalogImageReference struct {
	Version                   int     `json:"version"`
	IssuedAt                  int64   `json:"issued_at"`
	ExpiresAt                 int64   `json:"expires_at"`
	CustomerAccountID         string  `json:"customer_account_id"`
	ConfigurationID           string  `json:"configuration_id"`
	Region                    string  `json:"region"`
	CanonicalArticleID        string  `json:"canonical_article_id"`
	ProviderSlug              string  `json:"provider_slug"`
	SourceVehicleRefSHA256    string  `json:"source_vehicle_ref_sha256"`
	SourceArticleRefSHA256    string  `json:"source_article_ref_sha256"`
	SelectedSourceRevisionID  string  `json:"selected_source_revision_id"`
	AnchorSourceRevisionID    string  `json:"anchor_source_revision_id"`
	AnchorCanonicalRevisionID *string `json:"anchor_canonical_revision_id"`
	Projection                string  `json:"projection"`
	AssetID                   string  `json:"asset_id"`
	ObjectKey                 string  `json:"object_key"`
}

var paidCatalogDigestPattern = regexp.MustCompile(`^[a-f0-9]{64}$`)
var paidCatalogAssetPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$`)

func validPaidCatalogImageReference(ref paidCatalogImageReference, now time.Time) bool {
	if ref.Version != 2 || ref.IssuedAt <= 0 || ref.IssuedAt > now.Unix()+30 || ref.ExpiresAt <= now.Unix() || ref.ExpiresAt-ref.IssuedAt != 300 {
		return false
	}
	for _, id := range []string{ref.CustomerAccountID, ref.ConfigurationID, ref.CanonicalArticleID, ref.SelectedSourceRevisionID, ref.AnchorSourceRevisionID} {
		if !commerceUUID(id) {
			return false
		}
	}
	if ref.AnchorCanonicalRevisionID != nil && !commerceUUID(*ref.AnchorCanonicalRevisionID) {
		return false
	}
	return commerceRegion(ref.Region) && (ref.ProviderSlug == "bankone" || ref.ProviderSlug == "banktwo") && paidCatalogDigestPattern.MatchString(ref.SourceVehicleRefSHA256) && paidCatalogDigestPattern.MatchString(ref.SourceArticleRefSHA256) && (ref.Projection == "article" || ref.Projection == "source") && paidCatalogAssetPattern.MatchString(ref.AssetID) && localCatalogImageKeyPattern.MatchString(ref.ObjectKey)
}

func sealPaidCatalogImageReference(ref paidCatalogImageReference, key []byte, now time.Time) (string, error) {
	if len(key) != 32 || !validPaidCatalogImageReference(ref, now) {
		return "", errors.New("invalid paid catalog image reference")
	}
	raw, err := json.Marshal(ref)
	if err != nil || len(raw) > 4096 {
		return "", errors.New("invalid paid catalog image reference")
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", err
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, aead.NonceSize())
	if _, err = rand.Read(nonce); err != nil {
		return "", err
	}
	return "v2." + base64.RawURLEncoding.EncodeToString(aead.Seal(nonce, nonce, raw, []byte(paidCatalogImageTokenAAD))), nil
}

func openPaidCatalogImageReference(token string, key []byte, now time.Time) (paidCatalogImageReference, error) {
	var ref paidCatalogImageReference
	invalid := errors.New("invalid paid catalog image reference")
	if len(key) != 32 || len(token) > 6000 || !strings.HasPrefix(token, "v2.") {
		return ref, invalid
	}
	sealed, err := base64.RawURLEncoding.Strict().DecodeString(strings.TrimPrefix(token, "v2."))
	if err != nil {
		return ref, invalid
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return ref, invalid
	}
	aead, err := cipher.NewGCM(block)
	if err != nil || len(sealed) < aead.NonceSize()+aead.Overhead() || len(sealed)-aead.NonceSize()-aead.Overhead() > 4096 {
		return ref, invalid
	}
	raw, err := aead.Open(nil, sealed[:aead.NonceSize()], sealed[aead.NonceSize():], []byte(paidCatalogImageTokenAAD))
	if err != nil {
		return ref, invalid
	}
	// Parse the object once to reject duplicate keys, including duplicate null
	// anchors. The typed second pass rejects every unknown or mistyped field.
	decoder := json.NewDecoder(bytes.NewReader(raw))
	start, err := decoder.Token()
	if err != nil || start != json.Delim('{') {
		return ref, invalid
	}
	fields := map[string]bool{}
	for decoder.More() {
		name, err := decoder.Token()
		if err != nil {
			return ref, invalid
		}
		field, ok := name.(string)
		if !ok || fields[field] {
			return ref, invalid
		}
		fields[field] = true
		var value json.RawMessage
		if decoder.Decode(&value) != nil {
			return ref, invalid
		}
	}
	if _, err = decoder.Token(); err != nil {
		return ref, invalid
	}
	var trailing any
	if decoder.Decode(&trailing) != io.EOF {
		return ref, invalid
	}
	if len(fields) != 16 {
		return ref, invalid
	}
	for _, field := range []string{"version", "issued_at", "expires_at", "customer_account_id", "configuration_id", "region", "canonical_article_id", "provider_slug", "source_vehicle_ref_sha256", "source_article_ref_sha256", "selected_source_revision_id", "anchor_source_revision_id", "anchor_canonical_revision_id", "projection", "asset_id", "object_key"} {
		if !fields[field] {
			return ref, invalid
		}
	}
	decoder = json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&ref) != nil || !validPaidCatalogImageReference(ref, now) {
		return paidCatalogImageReference{}, invalid
	}
	return ref, nil
}
