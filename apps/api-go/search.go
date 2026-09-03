package main

import (
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"math"
	"strings"
)

const evidenceEmbeddingDimension = 1536

func deterministicQueryEmbedding(query string) ([]float64, error) {
	normalized := strings.TrimSpace(query)
	if normalized == "" {
		return nil, fmt.Errorf("search query cannot be empty")
	}
	seed := sha256.Sum256([]byte(normalized))
	vector := make([]float64, evidenceEmbeddingDimension)
	for index := range vector {
		var indexBytes [4]byte
		binary.BigEndian.PutUint32(indexBytes[:], uint32(index))
		digest := sha256.Sum256(append(seed[:], indexBytes[:]...))
		integer := binary.BigEndian.Uint64(digest[:8])
		vector[index] = math.Ldexp(float64(integer), -64)*2 - 1
	}
	return normalizeVector(vector), nil
}

func formatPGVector(vector []float64) (string, error) {
	if len(vector) != evidenceEmbeddingDimension {
		return "", fmt.Errorf("embedding dimension must be %d, got %d", evidenceEmbeddingDimension, len(vector))
	}
	values := make([]string, len(vector))
	for index, value := range vector {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return "", fmt.Errorf("embedding vector contains a non-finite value at index %d", index)
		}
		values[index] = fmt.Sprintf("%.8f", value)
	}
	return "[" + strings.Join(values, ",") + "]", nil
}

func cosineSimilarity(left, right []float64) float64 {
	if len(left) != len(right) || len(left) == 0 {
		return -1
	}
	var dot, leftNorm, rightNorm float64
	for index := range left {
		dot += left[index] * right[index]
		leftNorm += left[index] * left[index]
		rightNorm += right[index] * right[index]
	}
	if leftNorm == 0 || rightNorm == 0 {
		return -1
	}
	return dot / math.Sqrt(leftNorm*rightNorm)
}

func normalizeVector(vector []float64) []float64 {
	var norm float64
	for _, value := range vector {
		norm += value * value
	}
	norm = math.Sqrt(norm)
	for index := range vector {
		vector[index] /= norm
	}
	return vector
}
