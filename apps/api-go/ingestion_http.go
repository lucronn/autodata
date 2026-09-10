package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const maxIngestionProxyBytes = 1 << 20

type IngestionClient interface {
	Do(*http.Request, string, []byte, string) (int, []byte, error)
}

type HTTPIngestionClient struct {
	baseURL string
	token   string
	client  *http.Client
}

func NewHTTPIngestionClient(baseURL, token string, timeout time.Duration) (*HTTPIngestionClient, error) {
	parsed, err := url.Parse(strings.TrimRight(strings.TrimSpace(baseURL), "/"))
	if err != nil || parsed.Scheme != "http" && parsed.Scheme != "https" || parsed.Host == "" {
		return nil, fmt.Errorf("ingestion URL must be an HTTP(S) URL")
	}
	if timeout <= 0 {
		return nil, fmt.Errorf("ingestion timeout must be positive")
	}
	return &HTTPIngestionClient{
		baseURL: strings.TrimRight(parsed.String(), "/"),
		token:   token,
		client:  &http.Client{Timeout: timeout},
	}, nil
}

func (c *HTTPIngestionClient) Do(incoming *http.Request, path string, body []byte, idempotencyKey string) (int, []byte, error) {
	if c == nil || c.client == nil {
		return 0, nil, fmt.Errorf("ingestion client is not configured")
	}
	outgoing, err := http.NewRequestWithContext(
		incoming.Context(),
		http.MethodPost,
		c.baseURL+path,
		bytes.NewReader(body),
	)
	if err != nil {
		return 0, nil, err
	}
	outgoing.Header.Set("Accept", "application/json")
	outgoing.Header.Set("Content-Type", "application/json")
	outgoing.Header.Set("Idempotency-Key", idempotencyKey)
	if c.token != "" {
		outgoing.Header.Set("X-Autodata-Internal-Token", c.token)
	}
	result, err := c.client.Do(outgoing)
	if err != nil {
		return 0, nil, err
	}
	defer result.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(result.Body, maxIngestionProxyBytes+1))
	if err != nil {
		return 0, nil, err
	}
	if len(responseBody) > maxIngestionProxyBytes {
		return 0, nil, fmt.Errorf("ingestion response exceeds the configured limit")
	}
	return result.StatusCode, responseBody, nil
}

func (s *Server) createArticleIntake(response http.ResponseWriter, request *http.Request, _ Principal) {
	s.proxyIngestionRequest(response, request, "/v1/article-intakes")
}

func (s *Server) createKnowledgeQuery(response http.ResponseWriter, request *http.Request, _ Principal) {
	s.proxyIngestionRequest(response, request, "/v1/knowledge-queries")
}

func (s *Server) createJobPlan(response http.ResponseWriter, request *http.Request, _ Principal) {
	s.proxyIngestionRequest(response, request, "/v1/job-plans")
}

func (s *Server) proxyIngestionRequest(response http.ResponseWriter, request *http.Request, path string) {
	if strings.TrimSpace(request.Header.Get("Idempotency-Key")) == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "Idempotency-Key is required", false)
		return
	}
	body, err := io.ReadAll(io.LimitReader(request.Body, maxIngestionProxyBytes+1))
	if err != nil || len(body) > maxIngestionProxyBytes {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "ingestion request body is invalid or too large", false)
		return
	}
	if !jsonObject(body) {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "ingestion request body must be a JSON object", false)
		return
	}
	if s.ingestionClient == nil {
		writeAPIError(response, request, http.StatusServiceUnavailable, "INGESTION_UNAVAILABLE", "ingestion service is not configured", true)
		return
	}
	status, responseBody, err := s.ingestionClient.Do(request, path, body, request.Header.Get("Idempotency-Key"))
	if err != nil {
		writeAPIError(response, request, http.StatusBadGateway, "INGESTION_UNAVAILABLE", "ingestion service request failed", true)
		return
	}
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_, _ = response.Write(responseBody)
}

func jsonObject(body []byte) bool {
	var value map[string]any
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&value) != nil || value == nil {
		return false
	}
	var trailing any
	return decoder.Decode(&trailing) == io.EOF
}

func envDurationSeconds(name string, fallback int) time.Duration {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return time.Duration(fallback) * time.Second
	}
	seconds, err := strconv.Atoi(value)
	if err != nil || seconds <= 0 {
		return time.Duration(fallback) * time.Second
	}
	return time.Duration(seconds) * time.Second
}
