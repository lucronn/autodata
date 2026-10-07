package main

import (
	"context"
	"errors"
	"io"
	"os"
	"strings"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

const catalogImageBucketDefault = "autodata-sources"

type catalogImageObjectReader interface {
	ReadImage(context.Context, string) ([]byte, string, error)
}

type minioCatalogImageReader struct {
	client *minio.Client
	bucket string
}

func configuredCatalogImageReader() catalogImageObjectReader {
	endpoint := strings.TrimSpace(os.Getenv("AUTODATA_S3_ENDPOINT"))
	if endpoint == "" {
		return nil
	}
	accessKey := strings.TrimSpace(os.Getenv("AUTODATA_S3_ACCESS_KEY"))
	secretKey := strings.TrimSpace(os.Getenv("AUTODATA_S3_SECRET_KEY"))
	if accessKey == "" || secretKey == "" {
		return nil
	}
	client, err := minio.New(endpoint, &minio.Options{
		Creds:        credentials.NewStaticV4(accessKey, secretKey, ""),
		Secure:       strings.EqualFold(os.Getenv("AUTODATA_S3_SECURE"), "true"),
		BucketLookup: minio.BucketLookupPath,
	})
	if err != nil {
		return nil
	}
	bucket := strings.TrimSpace(os.Getenv("AUTODATA_SOURCE_BUCKET"))
	if bucket == "" {
		bucket = catalogImageBucketDefault
	}
	return &minioCatalogImageReader{client: client, bucket: bucket}
}

func (reader *minioCatalogImageReader) ReadImage(ctx context.Context, key string) ([]byte, string, error) {
	if reader == nil || reader.client == nil || !localCatalogImageKeyPattern.MatchString(key) {
		return nil, "", errors.New("invalid catalog image reference")
	}
	object, err := reader.client.GetObject(ctx, reader.bucket, key, minio.GetObjectOptions{})
	if err != nil {
		return nil, "", err
	}
	defer object.Close()
	info, err := object.Stat()
	if err != nil {
		return nil, "", err
	}
	if info.Size <= 0 || info.Size > catalogImageMaxBytes {
		return nil, "", errors.New("catalog image size is invalid")
	}
	payload, err := io.ReadAll(io.LimitReader(object, catalogImageMaxBytes+1))
	if err != nil || len(payload) == 0 || len(payload) > catalogImageMaxBytes {
		return nil, "", errors.New("catalog image could not be read")
	}
	mediaType := strings.ToLower(strings.TrimSpace(strings.Split(info.ContentType, ";")[0]))
	if !strings.HasPrefix(mediaType, "image/") {
		return nil, "", errors.New("catalog image media type is invalid")
	}
	return payload, mediaType, nil
}
