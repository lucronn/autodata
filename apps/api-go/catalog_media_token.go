package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"os"
	"regexp"
	"strings"
)

const catalogImageTokenAAD = "autodata:catalog-image:v1"

var localCatalogImageKeyPattern = regexp.MustCompile(`^procedure-images/[a-f0-9]{64}$`)

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
