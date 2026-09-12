package main

import (
	"bytes"
	"context"
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

const maxIngestionProxyBytes = 8 << 20

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
	outgoing, err := c.newInternalRequest(requestContext(nil, incoming), incoming, http.MethodPost, path, bytes.NewReader(body), idempotencyKey)
	if err != nil {
		return 0, nil, err
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

// Create, Select, Get, and Events implement ChatClient. The context is
// attached to every internal request so a disconnected public caller cancels
// work at the upstream boundary as well.
func (c *HTTPIngestionClient) Create(ctx context.Context, incoming *http.Request, body []byte, idempotencyKey string) (int, []byte, error) {
	return c.doChatJSON(ctx, incoming, http.MethodPost, "/v1/chat/queries", body, idempotencyKey)
}

func (c *HTTPIngestionClient) Select(ctx context.Context, incoming *http.Request, queryID string, body []byte, idempotencyKey string) (int, []byte, error) {
	path, err := chatInternalPath(queryID, "selections")
	if err != nil {
		return 0, nil, err
	}
	return c.doChatJSON(ctx, incoming, http.MethodPost, path, body, idempotencyKey)
}

func (c *HTTPIngestionClient) Get(ctx context.Context, incoming *http.Request, queryID string) (int, []byte, error) {
	path, err := chatInternalPath(queryID, "")
	if err != nil {
		return 0, nil, err
	}
	return c.doChatJSON(ctx, incoming, http.MethodGet, path, nil, "")
}

func (c *HTTPIngestionClient) Events(ctx context.Context, incoming *http.Request, queryID, lastEventID string) (io.ReadCloser, error) {
	if c == nil || c.client == nil {
		return nil, fmt.Errorf("ingestion client is not configured")
	}
	if len(lastEventID) > 256 {
		return nil, fmt.Errorf("Last-Event-ID is too long")
	}
	path, err := chatInternalPath(queryID, "events")
	if err != nil {
		return nil, err
	}
	outgoing, err := c.newInternalRequest(requestContext(ctx, incoming), incoming, http.MethodGet, path, nil, "")
	if err != nil {
		return nil, err
	}
	outgoing.Header.Set("Accept", "text/event-stream")
	if strings.TrimSpace(lastEventID) != "" {
		outgoing.Header.Set("Last-Event-ID", strings.TrimSpace(lastEventID))
	}
	result, err := c.client.Do(outgoing)
	if err != nil {
		return nil, err
	}
	if result.StatusCode < http.StatusOK || result.StatusCode >= http.StatusMultipleChoices {
		_ = result.Body.Close()
		return nil, fmt.Errorf("chat event stream returned status %d", result.StatusCode)
	}
	return result.Body, nil
}

func (c *HTTPIngestionClient) doChatJSON(ctx context.Context, incoming *http.Request, method, path string, body []byte, idempotencyKey string) (int, []byte, error) {
	if c == nil || c.client == nil {
		return 0, nil, fmt.Errorf("ingestion client is not configured")
	}
	var reader io.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	}
	outgoing, err := c.newInternalRequest(requestContext(ctx, incoming), incoming, method, path, reader, idempotencyKey)
	if err != nil {
		return 0, nil, err
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

func (c *HTTPIngestionClient) newInternalRequest(ctx context.Context, incoming *http.Request, method, path string, body io.Reader, idempotencyKey string) (*http.Request, error) {
	if c == nil || c.client == nil {
		return nil, fmt.Errorf("ingestion client is not configured")
	}
	outgoing, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, body)
	if err != nil {
		return nil, err
	}
	outgoing.Header.Set("Accept", "application/json")
	if body != nil {
		outgoing.Header.Set("Content-Type", "application/json")
	}
	if idempotencyKey != "" {
		outgoing.Header.Set("Idempotency-Key", idempotencyKey)
	}
	if c.token != "" {
		outgoing.Header.Set("X-Autodata-Internal-Token", c.token)
	}
	for _, header := range []string{
		"X-Request-ID",
		"traceparent",
		"X-Autodata-Owner-Id",
		"X-Autodata-Organization-Id",
	} {
		if incoming != nil {
			if value := strings.TrimSpace(incoming.Header.Get(header)); value != "" {
				outgoing.Header.Set(header, value)
			}
		}
	}
	return outgoing, nil
}

func requestContext(ctx context.Context, incoming *http.Request) context.Context {
	if ctx != nil {
		return ctx
	}
	if incoming != nil && incoming.Context() != nil {
		return incoming.Context()
	}
	return context.Background()
}

func chatInternalPath(queryID, suffix string) (string, error) {
	value := strings.TrimSpace(queryID)
	if value == "" || len(value) > 256 || strings.ContainsAny(value, "/?#") {
		return "", fmt.Errorf("chat query ID is invalid")
	}
	for _, character := range value {
		if character < 0x20 || character == 0x7f {
			return "", fmt.Errorf("chat query ID is invalid")
		}
	}
	return "/v1/chat/queries/" + url.PathEscape(value) + func() string {
		if suffix == "" {
			return ""
		}
		return "/" + suffix
	}(), nil
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
