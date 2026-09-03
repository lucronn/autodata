package main

import (
	"context"
	"encoding/hex"
	"net/http"
	"strings"
)

type requestContextKey string

const (
	requestIDContextKey   requestContextKey = "autodata.request_id"
	traceparentContextKey requestContextKey = "autodata.traceparent"
)

// withRequestObservability establishes the provider-neutral correlation
// boundary. A caller may supply an opaque request ID and a W3C traceparent;
// otherwise the API creates a request ID suitable for logs and error bodies.
// Downstream workers continue correlation through the event envelope's
// request_id and correlation_id fields rather than an HTTP-only context.
func withRequestObservability(next http.Handler) http.Handler {
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		requestID := request.Header.Get("X-Request-ID")
		if !validRequestID(requestID) {
			requestID = generatedObservabilityRequestID()
		}
		ctx := context.WithValue(request.Context(), requestIDContextKey, requestID)
		if traceparent := request.Header.Get("traceparent"); validTraceparent(traceparent) {
			ctx = context.WithValue(ctx, traceparentContextKey, traceparent)
			response.Header().Set("traceparent", traceparent)
		}
		request = request.WithContext(ctx)
		response.Header().Set("X-Request-ID", requestID)
		next.ServeHTTP(response, request)
	})
}

func requestIDFrom(request *http.Request) string {
	if request != nil {
		if requestID, ok := request.Context().Value(requestIDContextKey).(string); ok && requestID != "" {
			return requestID
		}
	}
	return "request-unassigned"
}

func generatedObservabilityRequestID() string {
	requestID, err := newRequestID()
	if err != nil {
		return "request-randomness-unavailable"
	}
	return requestID
}

func validRequestID(value string) bool {
	if value == "" || len(value) > 128 {
		return false
	}
	for _, character := range value {
		if (character < 'a' || character > 'z') &&
			(character < 'A' || character > 'Z') &&
			(character < '0' || character > '9') &&
			!strings.ContainsRune("._-", character) {
			return false
		}
	}
	return true
}

func validTraceparent(value string) bool {
	parts := strings.Split(value, "-")
	if len(parts) != 4 || len(parts[0]) != 2 || len(parts[1]) != 32 || len(parts[2]) != 16 || len(parts[3]) != 2 {
		return false
	}
	for index, part := range parts {
		if _, err := hex.DecodeString(part); err != nil || (index == 1 && strings.Trim(part, "0") == "") || (index == 2 && strings.Trim(part, "0") == "") {
			return false
		}
	}
	return parts[0] == "00"
}
