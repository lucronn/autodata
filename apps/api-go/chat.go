package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"strconv"
	"strings"
)

const (
	maxChatRequestBytes  = 1 << 20
	maxChatResponseBytes = 8 << 20
)

// ChatClient is the public API's provider-neutral boundary to the internal
// chat service. Implementations must honor the supplied context and never
// expose internal authentication or upstream response headers to callers.
type ChatClient interface {
	Create(context.Context, *http.Request, []byte, string) (int, []byte, error)
	Select(context.Context, *http.Request, string, []byte, string) (int, []byte, error)
	Get(context.Context, *http.Request, string) (int, []byte, error)
	Events(context.Context, *http.Request, string, string) (io.ReadCloser, error)
}

func (s *Server) createChatQuery(response http.ResponseWriter, request *http.Request, principal Principal) {
	idempotencyKey, ok := chatIdempotencyKey(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "Idempotency-Key is required", false)
		return
	}
	body, err := readChatJSONBody(request.Body)
	if err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	if s.chatClient == nil {
		writeAPIError(response, request, http.StatusServiceUnavailable, "INGESTION_UNAVAILABLE", "chat service is not configured", true)
		return
	}
	status, upstreamBody, err := s.chatClient.Create(
		request.Context(),
		chatInternalRequest(request, principal),
		body,
		idempotencyKey,
	)
	s.writeChatJSONResponse(response, request, status, upstreamBody, err)
}

func (s *Server) getChatQuery(response http.ResponseWriter, request *http.Request, principal Principal) {
	queryID, err := chatPathID(request)
	if err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	if s.chatClient == nil {
		writeAPIError(response, request, http.StatusServiceUnavailable, "INGESTION_UNAVAILABLE", "chat service is not configured", true)
		return
	}
	status, upstreamBody, err := s.chatClient.Get(
		request.Context(),
		chatInternalRequest(request, principal),
		queryID,
	)
	s.writeChatJSONResponse(response, request, status, upstreamBody, err)
}

func (s *Server) selectChatVehicle(response http.ResponseWriter, request *http.Request, principal Principal) {
	queryID, err := chatPathID(request)
	if err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	idempotencyKey, ok := chatIdempotencyKey(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "Idempotency-Key is required", false)
		return
	}
	body, err := readChatJSONBody(request.Body)
	if err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	if !chatSelectionHasOption(body) {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "a vehicle selection option is required", false)
		return
	}
	if s.chatClient == nil {
		writeAPIError(response, request, http.StatusServiceUnavailable, "INGESTION_UNAVAILABLE", "chat service is not configured", true)
		return
	}
	status, upstreamBody, err := s.chatClient.Select(
		request.Context(),
		chatInternalRequest(request, principal),
		queryID,
		body,
		idempotencyKey,
	)
	s.writeChatJSONResponse(response, request, status, upstreamBody, err)
}

func (s *Server) writeChatJSONResponse(response http.ResponseWriter, request *http.Request, status int, body []byte, err error) {
	// Internal errors and 5xx responses are deliberately collapsed to a stable
	// public error. This prevents worker headers, bodies, and credentials from
	// crossing the authenticated API boundary.
	if err != nil || status < http.StatusOK || status >= http.StatusInternalServerError {
		writeAPIError(response, request, http.StatusBadGateway, "INGESTION_UNAVAILABLE", "chat service request failed", true)
		return
	}
	if len(body) > maxChatResponseBytes || (status != http.StatusNoContent && !validJSONDocument(body)) {
		writeAPIError(response, request, http.StatusBadGateway, "INGESTION_UNAVAILABLE", "chat service returned an invalid response", true)
		return
	}
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	if len(body) > 0 {
		_, _ = response.Write(body)
	}
}

func readChatJSONBody(reader io.Reader) ([]byte, error) {
	if reader == nil {
		return nil, fmt.Errorf("chat request body is required")
	}
	body, err := io.ReadAll(io.LimitReader(reader, maxChatRequestBytes+1))
	if err != nil {
		return nil, fmt.Errorf("chat request body is invalid or too large")
	}
	if len(body) > maxChatRequestBytes {
		return nil, fmt.Errorf("chat request body is invalid or too large")
	}
	if !jsonObject(body) {
		return nil, fmt.Errorf("chat request body must be a JSON object")
	}
	return body, nil
}

func validJSONDocument(body []byte) bool {
	decoder := json.NewDecoder(bytes.NewReader(body))
	var value any
	if decoder.Decode(&value) != nil {
		return false
	}
	var trailing any
	return decoder.Decode(&trailing) == io.EOF
}

func chatIdempotencyKey(request *http.Request) (string, bool) {
	value := strings.TrimSpace(request.Header.Get("Idempotency-Key"))
	return value, value != ""
}

func chatPathID(request *http.Request) (string, error) {
	value := strings.TrimSpace(request.PathValue("id"))
	if value == "" {
		return "", fmt.Errorf("chat query ID is required")
	}
	if len(value) > 256 || strings.ContainsAny(value, "/?#") {
		return "", fmt.Errorf("chat query ID is invalid")
	}
	for _, character := range value {
		if character < 0x20 || character == 0x7f {
			return "", fmt.Errorf("chat query ID is invalid")
		}
	}
	return value, nil
}

func chatSelectionHasOption(body []byte) bool {
	var selection map[string]any
	if err := json.Unmarshal(body, &selection); err != nil {
		return false
	}
	for _, key := range []string{"option_number", "vehicle_id", "candidate_key"} {
		if value, ok := selection[key]; ok && validChatSelectionValue(key, value) {
			return true
		}
	}
	if nested, ok := selection["selection"]; ok {
		switch value := nested.(type) {
		case string:
			return strings.TrimSpace(value) != ""
		case float64:
			return value > 0
		case map[string]any:
			encoded, err := json.Marshal(value)
			return err == nil && chatSelectionHasOption(encoded)
		}
	}
	return false
}

func validChatSelectionValue(key string, value any) bool {
	if value == nil {
		return false
	}
	if key != "option_number" {
		text, ok := value.(string)
		return ok && strings.TrimSpace(text) != ""
	}
	switch typed := value.(type) {
	case float64:
		return typed >= 1 && typed == math.Trunc(typed)
	case string:
		parsed, err := strconv.Atoi(strings.TrimSpace(typed))
		return err == nil && parsed > 0
	default:
		return false
	}
}

func chatInternalRequest(request *http.Request, principal Principal) *http.Request {
	forwarded := request.Clone(request.Context())
	forwarded.Header = request.Header.Clone()
	forwarded.Header.Del("X-Autodata-Owner-Id")
	forwarded.Header.Del("X-Autodata-Organization-Id")
	if organization := strings.TrimSpace(principal.OrganizationID); organization != "" {
		// The initial access model is organization-scoped. Until an identity
		// adapter supplies a subject ID, the organization is the stable owner
		// partition used by the internal chat service.
		forwarded.Header.Set("X-Autodata-Owner-Id", organization)
		forwarded.Header.Set("X-Autodata-Organization-Id", organization)
	}
	return forwarded
}
