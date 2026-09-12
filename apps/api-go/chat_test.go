package main

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type fakeChatClient struct {
	createCalls  int
	createBody   []byte
	createKey    string
	createReq    *http.Request
	createStatus int
	createReply  []byte
	createErr    error

	selectCalls  int
	selectID     string
	selectBody   []byte
	selectKey    string
	selectReq    *http.Request
	selectStatus int
	selectReply  []byte
	selectErr    error

	getCalls  int
	getID     string
	getReq    *http.Request
	getStatus int
	getReply  []byte
	getErr    error

	eventsCalls  int
	eventsID     string
	eventsLastID string
	eventsReq    *http.Request
	eventsBody   io.ReadCloser
	eventsErr    error
}

func (f *fakeChatClient) Do(_ *http.Request, _ string, _ []byte, _ string) (int, []byte, error) {
	return http.StatusNotImplemented, nil, nil
}

func (f *fakeChatClient) Create(_ context.Context, request *http.Request, body []byte, idempotencyKey string) (int, []byte, error) {
	f.createCalls++
	f.createReq = request.Clone(request.Context())
	f.createBody = append([]byte(nil), body...)
	f.createKey = idempotencyKey
	return f.createStatus, f.createReply, f.createErr
}

func (f *fakeChatClient) Select(_ context.Context, request *http.Request, queryID string, body []byte, idempotencyKey string) (int, []byte, error) {
	f.selectCalls++
	f.selectReq = request.Clone(request.Context())
	f.selectID = queryID
	f.selectBody = append([]byte(nil), body...)
	f.selectKey = idempotencyKey
	return f.selectStatus, f.selectReply, f.selectErr
}

func (f *fakeChatClient) Get(_ context.Context, request *http.Request, queryID string) (int, []byte, error) {
	f.getCalls++
	f.getReq = request.Clone(request.Context())
	f.getID = queryID
	return f.getStatus, f.getReply, f.getErr
}

func (f *fakeChatClient) Events(_ context.Context, request *http.Request, queryID, lastEventID string) (io.ReadCloser, error) {
	f.eventsCalls++
	f.eventsReq = request.Clone(request.Context())
	f.eventsID = queryID
	f.eventsLastID = lastEventID
	return f.eventsBody, f.eventsErr
}

func newChatServer(client *fakeChatClient) *Server {
	return NewServerWithIngestionClient(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
		client,
	)
}

func TestChatCreateRequiresAuthentication(t *testing.T) {
	client := &fakeChatClient{createStatus: http.StatusAccepted, createReply: []byte(`{"query_id":"q-1"}`)}
	server := NewServerWithDependencies(
		staticReadiness{},
		&fakeAuthenticator{err: ErrUnauthenticated},
		newMemoryRequestStore(),
	)
	server.ingestionClient = client

	request := httptest.NewRequest(http.MethodPost, "/chat/queries", strings.NewReader(`{"message":"97 Toyota RAV4 brake procedure"}`))
	request.Header.Set("Idempotency-Key", "chat-1")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnauthorized)
	}
	assertErrorCode(t, response, "UNAUTHENTICATED")
	if client.createCalls != 0 {
		t.Fatalf("create calls = %d, want 0", client.createCalls)
	}
}

func TestChatCreateForwardsBodyIdempotencyAndPrincipalCorrelation(t *testing.T) {
	body := []byte(`{"conversation_id":"c-1","message":"97 Toyota RAV4 brake procedure and quote"}`)
	client := &fakeChatClient{createStatus: http.StatusAccepted, createReply: []byte(`{"query_id":"q-1","status":"processing"}`)}
	server := newChatServer(client)
	request := httptest.NewRequest(http.MethodPost, "/chat/queries", strings.NewReader(string(body)))
	request.Header.Set("Idempotency-Key", "chat-1")
	request.Header.Set("X-Request-ID", "request-1")
	request.Header.Set("traceparent", "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusAccepted)
	}
	if string(client.createBody) != string(body) {
		t.Fatalf("body = %q, want %q", client.createBody, body)
	}
	if client.createKey != "chat-1" {
		t.Fatalf("idempotency key = %q, want chat-1", client.createKey)
	}
	if client.createReq.Header.Get("X-Autodata-Owner-Id") != "org-1" || client.createReq.Header.Get("X-Autodata-Organization-Id") != "org-1" {
		t.Fatalf("principal headers = owner %q organization %q", client.createReq.Header.Get("X-Autodata-Owner-Id"), client.createReq.Header.Get("X-Autodata-Organization-Id"))
	}
	if client.createReq.Header.Get("X-Request-ID") != "request-1" || client.createReq.Header.Get("traceparent") == "" {
		t.Fatalf("correlation headers were not preserved: request=%q traceparent=%q", client.createReq.Header.Get("X-Request-ID"), client.createReq.Header.Get("traceparent"))
	}
	if strings.Contains(string(response.Body.Bytes()), "Authorization") {
		t.Fatal("response unexpectedly contains authorization material")
	}
}

func TestChatDuplicateIdempotencyReturnsTheSameUpstreamQuery(t *testing.T) {
	client := &fakeChatClient{createStatus: http.StatusAccepted, createReply: []byte(`{"query_id":"q-stable","status":"processing"}`)}
	server := newChatServer(client)
	first := httptest.NewRecorder()
	second := httptest.NewRecorder()
	for _, response := range []*httptest.ResponseRecorder{first, second} {
		request := httptest.NewRequest(http.MethodPost, "/chat/queries", strings.NewReader(`{"message":"replace brake line"}`))
		request.Header.Set("Idempotency-Key", "same-key")
		server.Handler().ServeHTTP(response, request)
	}
	if string(first.Body.Bytes()) != string(second.Body.Bytes()) {
		t.Fatalf("duplicate response changed: first=%s second=%s", first.Body.Bytes(), second.Body.Bytes())
	}
	if client.createCalls != 2 || client.createKey != "same-key" {
		t.Fatalf("proxy calls/key = %d/%q, want two calls with same key", client.createCalls, client.createKey)
	}
}

func TestChatGetAndSelectionForwardQueryIDsAndBodies(t *testing.T) {
	client := &fakeChatClient{
		getStatus:    http.StatusOK,
		getReply:     []byte(`{"query_id":"q-1","status":"awaiting_vehicle"}`),
		selectStatus: http.StatusOK,
		selectReply:  []byte(`{"query_id":"q-1","status":"processing"}`),
	}
	server := newChatServer(client)

	getResponse := httptest.NewRecorder()
	getRequest := httptest.NewRequest(http.MethodGet, "/chat/queries/q-1", nil)
	server.Handler().ServeHTTP(getResponse, getRequest)
	if getResponse.Code != http.StatusOK || client.getID != "q-1" {
		t.Fatalf("get status/id = %d/%q", getResponse.Code, client.getID)
	}

	selectBody := `{"selection_type":"vehicle","option_number":2}`
	selectResponse := httptest.NewRecorder()
	selectRequest := httptest.NewRequest(http.MethodPost, "/chat/queries/q-1/selections", strings.NewReader(selectBody))
	selectRequest.Header.Set("Idempotency-Key", "selection-1")
	server.Handler().ServeHTTP(selectResponse, selectRequest)
	if selectResponse.Code != http.StatusOK {
		t.Fatalf("selection status = %d, want %d", selectResponse.Code, http.StatusOK)
	}
	if client.selectID != "q-1" || string(client.selectBody) != selectBody || client.selectKey != "selection-1" {
		t.Fatalf("selection forwarding = id %q body %q key %q", client.selectID, client.selectBody, client.selectKey)
	}
}

func TestChatSelectionRequiresAnOption(t *testing.T) {
	client := &fakeChatClient{selectStatus: http.StatusOK, selectReply: []byte(`{"status":"processing"}`)}
	server := newChatServer(client)
	request := httptest.NewRequest(http.MethodPost, "/chat/queries/q-1/selections", strings.NewReader(`{"selection_type":"vehicle"}`))
	request.Header.Set("Idempotency-Key", "selection-1")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusUnprocessableEntity)
	}
	assertErrorCode(t, response, "INVALID_REQUEST")
	if client.selectCalls != 0 {
		t.Fatalf("selection calls = %d, want 0", client.selectCalls)
	}
}

func TestChatSelectionRejectsEmptyNumericOptions(t *testing.T) {
	client := &fakeChatClient{selectStatus: http.StatusOK, selectReply: []byte(`{"status":"processing"}`)}
	server := newChatServer(client)
	for _, body := range []string{`{"option_number":null}`, `{"option_number":0}`, `{"option_number":"0"}`} {
		request := httptest.NewRequest(http.MethodPost, "/chat/queries/q-1/selections", strings.NewReader(body))
		request.Header.Set("Idempotency-Key", "selection-invalid-"+strings.Trim(body, `{}`))
		response := httptest.NewRecorder()

		server.Handler().ServeHTTP(response, request)

		if response.Code != http.StatusUnprocessableEntity {
			t.Fatalf("body %s status = %d, want %d", body, response.Code, http.StatusUnprocessableEntity)
		}
	}
	if client.selectCalls != 0 {
		t.Fatalf("selection calls = %d, want 0", client.selectCalls)
	}
}

func TestChatUpstreamFailureDoesNotExposeInternalBody(t *testing.T) {
	secretBody := []byte(`{"error":"internal upstream secret","authorization":"Bearer should-not-leak"}`)
	client := &fakeChatClient{createStatus: http.StatusBadGateway, createReply: secretBody}
	server := newChatServer(client)
	request := httptest.NewRequest(http.MethodPost, "/chat/queries", strings.NewReader(`{"message":"replace alternator"}`))
	request.Header.Set("Idempotency-Key", "chat-error-1")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusBadGateway)
	}
	assertErrorCode(t, response, "INGESTION_UNAVAILABLE")
	if strings.Contains(response.Body.String(), "internal upstream secret") || strings.Contains(response.Body.String(), "should-not-leak") {
		t.Fatalf("response leaked upstream body: %s", response.Body.String())
	}
}

func TestChatUnavailableClientReturnsRetryableError(t *testing.T) {
	server := NewServerWithDependencies(
		staticReadiness{},
		&fakeAuthenticator{principal: Principal{OrganizationID: "org-1", Roles: []string{"dataset_viewer"}}},
		newMemoryRequestStore(),
	)
	request := httptest.NewRequest(http.MethodPost, "/chat/queries", strings.NewReader(`{"message":"replace alternator"}`))
	request.Header.Set("Idempotency-Key", "chat-unavailable-1")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusServiceUnavailable)
	}
	assertErrorCode(t, response, "INGESTION_UNAVAILABLE")
}
