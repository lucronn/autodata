package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func externalReadRequest(handler http.Handler, method, path, requestedMethod string) *httptest.ResponseRecorder {
	request := httptest.NewRequest(method, path, nil)
	request.Header.Set("Origin", "http://localhost:5173")
	if requestedMethod != "" {
		request.Header.Set("Access-Control-Request-Method", requestedMethod)
		request.Header.Set("Access-Control-Request-Headers", "authorization,content-type,x-api-key")
	}
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	return response
}

func TestPublicWorkshopReadsHandleBrowserPreflights(t *testing.T) {
	server, _, _ := paidHTTPServer()
	handler := server.Handler()
	for _, path := range []string{
		"/v1/catalog/years?region=US",
		"/v1/catalog/years/2024/makes",
		"/v1/catalog/years/2024/makes/buick-truck/models",
		"/v1/catalog/years/2024/makes/buick-truck/models/envision-awd/configurations",
		"/v1/workshop/quote",
		"/openapi.json",
		"/openapi.yaml",
	} {
		t.Run(path, func(t *testing.T) {
			for _, method := range []string{http.MethodGet, http.MethodHead} {
				response := externalReadRequest(handler, http.MethodOptions, path, method)
				headers := response.Header()
				if response.Code != http.StatusNoContent || response.Body.Len() != 0 ||
					headers.Get("Access-Control-Allow-Origin") != "*" ||
					headers.Get("Access-Control-Allow-Methods") != "GET, HEAD" ||
					!strings.Contains(headers.Get("Access-Control-Allow-Headers"), "Authorization") ||
					headers.Get("Access-Control-Allow-Credentials") != "" {
					t.Fatalf("preflight for %s = %d, %v, %s", method, response.Code, headers, response.Body)
				}
			}
			rejected := externalReadRequest(handler, http.MethodOptions, path, http.MethodPost)
			if rejected.Code != http.StatusMethodNotAllowed || rejected.Header().Get("Access-Control-Allow-Origin") != "" {
				t.Fatalf("write preflight = %d, %v", rejected.Code, rejected.Header())
			}
		})
	}
}

func TestPublicReadCORSOnSuccessAndValidationErrors(t *testing.T) {
	server, _, _ := paidHTTPServer()
	handler := server.Handler()
	for _, test := range []struct {
		path string
		want int
	}{
		{"/openapi.json", http.StatusOK},
		{"/v1/catalog/years/invalid/makes", http.StatusUnprocessableEntity},
		{"/v1/workshop/quote", http.StatusBadRequest},
	} {
		response := externalReadRequest(handler, http.MethodGet, test.path, "")
		headers := response.Header()
		if response.Code != test.want || headers.Get("Access-Control-Allow-Origin") != "*" ||
			headers.Get("Access-Control-Allow-Credentials") != "" ||
			!strings.Contains(headers.Get("Access-Control-Expose-Headers"), "X-Request-ID") {
			t.Errorf("%s = %d, %v", test.path, response.Code, headers)
		}
	}
}

func TestPrivateWorkshopRoutesKeepTheirOriginBoundary(t *testing.T) {
	server, _, _ := paidHTTPServer()
	handler := server.Handler()
	for _, test := range []struct{ path, method string }{
		{"/auth/session", http.MethodGet},
		{"/auth/firebase/session", http.MethodPost},
		{"/v1/workshop/library", http.MethodGet},
		{"/v1/workshop/checkout-sessions", http.MethodPost},
		{"/v1/catalog/vehicles/vehicle/articles", http.MethodGet},
		{"/v1/catalog/images/example", http.MethodGet},
	} {
		for _, method := range []string{test.method, http.MethodOptions} {
			response := externalReadRequest(handler, method, test.path, test.method)
			if response.Header().Get("Access-Control-Allow-Origin") != "" ||
				response.Header().Get("Access-Control-Allow-Credentials") != "" {
				t.Errorf("%s %s advertises cross-origin access: %v", method, test.path, response.Header())
			}
		}
	}
	local := NewServerWithDependencies(nil, nil, nil).Handler()
	response := externalReadRequest(local, http.MethodOptions, "/v1/catalog/years", http.MethodGet)
	if response.Code != http.StatusMethodNotAllowed || response.Header().Get("Access-Control-Allow-Origin") != "" {
		t.Errorf("protected selector preflight = %d, %v", response.Code, response.Header())
	}
}
