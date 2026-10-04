package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

type catalogImageObject struct {
	Body        []byte
	ContentType string
}

var catalogImageObjectReader = readCatalogImageObject

var catalogImageStorageHTTPClient = &http.Client{
	Timeout: 20 * time.Second,
	CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
		return http.ErrUseLastResponse
	},
}

func readCatalogImageObject(ctx context.Context, storageKey string) (catalogImageObject, error) {
	if !validCatalogImageStorageKey(storageKey) {
		return catalogImageObject{}, os.ErrNotExist
	}
	endpoint, err := catalogObjectStorageEndpoint()
	if err != nil {
		return catalogImageObject{}, err
	}
	bucket := strings.TrimSpace(os.Getenv("AUTODATA_SOURCE_BUCKET"))
	if bucket == "" {
		bucket = "autodata-sources"
	}
	if !validCatalogImageStorageKey(bucket) {
		return catalogImageObject{}, errors.New("invalid object storage bucket")
	}
	endpoint.Path = strings.TrimRight(endpoint.Path, "/") + "/" + bucket + "/" + storageKey
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return catalogImageObject{}, err
	}
	request.Header.Set("Accept", "image/avif,image/webp,image/png,image/jpeg,image/gif;q=0.9,*/*;q=0.1")
	if err := signCatalogObjectStorageRequest(request); err != nil {
		return catalogImageObject{}, err
	}
	response, err := catalogImageStorageHTTPClient.Do(request)
	if err != nil {
		return catalogImageObject{}, err
	}
	defer response.Body.Close()
	if response.StatusCode == http.StatusNotFound {
		return catalogImageObject{}, os.ErrNotExist
	}
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		return catalogImageObject{}, fmt.Errorf("object storage returned status %d", response.StatusCode)
	}
	contentType := strings.ToLower(strings.TrimSpace(strings.Split(response.Header.Get("Content-Type"), ";")[0]))
	if !safeCatalogImageContentType(contentType) {
		return catalogImageObject{}, errors.New("stored catalog image has an invalid media type")
	}
	if response.ContentLength > catalogImageMaxBytes {
		return catalogImageObject{}, errors.New("stored catalog image is too large")
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, catalogImageMaxBytes+1))
	if err != nil {
		return catalogImageObject{}, err
	}
	if len(body) == 0 || len(body) > catalogImageMaxBytes {
		return catalogImageObject{}, errors.New("stored catalog image is empty or too large")
	}
	return catalogImageObject{Body: body, ContentType: contentType}, nil
}

func safeCatalogImageContentType(contentType string) bool {
	switch contentType {
	case "image/png", "image/jpeg", "image/gif", "image/webp", "image/avif", "image/bmp":
		return true
	default:
		return false
	}
}

func catalogObjectStorageEndpoint() (*url.URL, error) {
	raw := strings.TrimSpace(os.Getenv("AUTODATA_S3_URL"))
	if raw == "" {
		address := strings.TrimSpace(os.Getenv("AUTODATA_S3_ADDRESS"))
		if address == "" {
			address = "minio:9000"
		}
		scheme := "http"
		if strings.EqualFold(strings.TrimSpace(os.Getenv("AUTODATA_S3_SECURE")), "true") {
			scheme = "https"
		}
		raw = scheme + "://" + address
	}
	endpoint, err := url.Parse(raw)
	if err != nil || endpoint.Host == "" || endpoint.User != nil || (endpoint.Scheme != "http" && endpoint.Scheme != "https") {
		return nil, errors.New("invalid object storage endpoint")
	}
	return endpoint, nil
}

func signCatalogObjectStorageRequest(request *http.Request) error {
	accessKey := strings.TrimSpace(os.Getenv("AUTODATA_S3_ACCESS_KEY"))
	secretKey := strings.TrimSpace(os.Getenv("AUTODATA_S3_SECRET_KEY"))
	if accessKey == "" && secretKey == "" {
		return nil
	}
	if accessKey == "" || secretKey == "" {
		return errors.New("object storage credentials are incomplete")
	}
	region := strings.TrimSpace(os.Getenv("AUTODATA_S3_REGION"))
	if region == "" {
		region = "us-east-1"
	}
	now := time.Now().UTC()
	amzDate := now.Format("20060102T150405Z")
	date := now.Format("20060102")
	payloadHash := sha256.Sum256(nil)
	payloadHex := hex.EncodeToString(payloadHash[:])
	request.Header.Set("Host", request.Host)
	request.Header.Set("X-Amz-Date", amzDate)
	request.Header.Set("X-Amz-Content-Sha256", payloadHex)
	canonicalURI := request.URL.EscapedPath()
	if canonicalURI == "" {
		canonicalURI = "/"
	}
	canonicalHeaders := "host:" + request.Host + "\n" +
		"x-amz-content-sha256:" + payloadHex + "\n" +
		"x-amz-date:" + amzDate + "\n"
	signedHeaders := "host;x-amz-content-sha256;x-amz-date"
	canonicalRequest := strings.Join([]string{
		http.MethodGet,
		canonicalURI,
		request.URL.Query().Encode(),
		canonicalHeaders,
		signedHeaders,
		payloadHex,
	}, "\n")
	hash := sha256.Sum256([]byte(canonicalRequest))
	credentialScope := date + "/" + region + "/s3/aws4_request"
	stringToSign := strings.Join([]string{
		"AWS4-HMAC-SHA256", amzDate, credentialScope, hex.EncodeToString(hash[:]),
	}, "\n")
	dateKey := hmacSHA256([]byte("AWS4"+secretKey), date)
	regionKey := hmacSHA256(dateKey, region)
	serviceKey := hmacSHA256(regionKey, "s3")
	signingKey := hmacSHA256(serviceKey, "aws4_request")
	signature := hex.EncodeToString(hmacSHA256(signingKey, stringToSign))
	request.Header.Set("Authorization", "AWS4-HMAC-SHA256 Credential="+accessKey+"/"+credentialScope+", SignedHeaders="+signedHeaders+", Signature="+signature)
	return nil
}

func hmacSHA256(key []byte, value string) []byte {
	mac := hmac.New(sha256.New, key)
	_, _ = mac.Write([]byte(value))
	return mac.Sum(nil)
}
