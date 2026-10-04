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
	"strings"
)

const catalogImageTokenAAD = "autodata:catalog-image:v1"
const catalogImageStorageTokenAAD = "autodata:catalog-image-storage:v1"

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

func sealCatalogImageURL(source string, key []byte) (string, error) {
	if len(key) != 32 || len(source) == 0 || len(source) > 4096 {
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
	sealed := aead.Seal(nonce, nonce, []byte(source), []byte(catalogImageTokenAAD))
	return base64.RawURLEncoding.EncodeToString(sealed), nil
}

func openCatalogImageURL(token string, key []byte) (string, error) {
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
	return string(plaintext), nil
}

func sealCatalogImageStorageKey(storageKey string, key []byte) (string, error) {
	if !validCatalogImageStorageKey(storageKey) {
		return "", errors.New("invalid catalog image storage reference")
	}
	return sealCatalogImageReference(storageKey, key, catalogImageStorageTokenAAD)
}

func openCatalogImageStorageKey(token string, key []byte) (string, error) {
	storageKey, err := openCatalogImageReference(token, key, catalogImageStorageTokenAAD)
	if err != nil || !validCatalogImageStorageKey(storageKey) {
		return "", errors.New("invalid catalog image storage reference")
	}
	return storageKey, nil
}

func sealCatalogImageReference(value string, key []byte, aad string) (string, error) {
	if len(key) != 32 || value == "" || len(value) > 4096 {
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
	sealed := aead.Seal(nonce, nonce, []byte(value), []byte(aad))
	return base64.RawURLEncoding.EncodeToString(sealed), nil
}

func openCatalogImageReference(token string, key []byte, aad string) (string, error) {
	if len(key) != 32 || token == "" || len(token) > 6000 {
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
	plaintext, err := aead.Open(nil, nonce, ciphertext, []byte(aad))
	if err != nil {
		return "", errors.New("invalid catalog image reference")
	}
	return string(plaintext), nil
}

func validCatalogImageStorageKey(storageKey string) bool {
	if storageKey == "" || len(storageKey) > 1024 || strings.HasPrefix(storageKey, "/") || strings.Contains(storageKey, "\\") {
		return false
	}
	for _, part := range strings.Split(storageKey, "/") {
		if part == "" || part == "." || part == ".." || strings.ContainsAny(part, "\x00\r\n") {
			return false
		}
	}
	return true
}
