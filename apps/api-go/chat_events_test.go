package main

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestChatEventsForwardLastEventIDAndStreamBoundedFrames(t *testing.T) {
	client := &fakeChatClient{eventsBody: io.NopCloser(strings.NewReader("id: event-2\nevent: chat.answer.updated\ndata: " + strings.Repeat("x", 8192) + "\n\n"))}
	server := newChatServer(client)
	request := httptest.NewRequest(http.MethodGet, "/chat/queries/q-1/events", nil)
	request.Header.Set("Last-Event-ID", "event-1")
	request.Header.Set("X-Request-ID", "request-2")
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusOK)
	}
	if !strings.HasPrefix(response.Header().Get("Content-Type"), "text/event-stream") {
		t.Fatalf("content type = %q, want text/event-stream", response.Header().Get("Content-Type"))
	}
	if !strings.Contains(response.Body.String(), "event: chat.answer.updated") {
		t.Fatalf("body = %q, want event frame", response.Body.String())
	}
	if !strings.Contains(response.Body.String(), strings.Repeat("x", 8192)) {
		t.Fatal("stream discarded a valid frame split across buffered reads")
	}
	if client.eventsID != "q-1" || client.eventsLastID != "event-1" {
		t.Fatalf("event forwarding = id %q last id %q", client.eventsID, client.eventsLastID)
	}
	if client.eventsReq.Header.Get("Last-Event-ID") != "event-1" || client.eventsReq.Header.Get("X-Request-ID") != "request-2" {
		t.Fatalf("event headers = last %q request %q", client.eventsReq.Header.Get("Last-Event-ID"), client.eventsReq.Header.Get("X-Request-ID"))
	}
}

func TestChatEventsStopWhenRequestIsCanceled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	client := &fakeChatClient{eventsBody: &contextReadCloser{ctx: ctx}}
	server := newChatServer(client)
	request := httptest.NewRequest(http.MethodGet, "/chat/queries/q-1/events", nil).WithContext(ctx)
	response := httptest.NewRecorder()
	cancel()

	server.Handler().ServeHTTP(response, request)

	if client.eventsCalls != 1 {
		t.Fatalf("event calls = %d, want 1", client.eventsCalls)
	}
	if response.Body.Len() > maxChatEventFrameBytes {
		t.Fatalf("canceled stream body length = %d, exceeds frame bound", response.Body.Len())
	}
}

func TestChatEventsRejectOversizedFrameWithoutBufferingIt(t *testing.T) {
	oversized := "data: " + strings.Repeat("x", maxChatEventFrameBytes+1) + "\n\n"
	client := &fakeChatClient{eventsBody: io.NopCloser(strings.NewReader(oversized))}
	server := newChatServer(client)
	request := httptest.NewRequest(http.MethodGet, "/chat/queries/q-1/events", nil)
	response := httptest.NewRecorder()

	server.Handler().ServeHTTP(response, request)

	if response.Body.Len() > maxChatEventFrameBytes {
		t.Fatalf("oversized frame was buffered or written: %d bytes", response.Body.Len())
	}
}

type contextReadCloser struct {
	ctx context.Context
}

func (r *contextReadCloser) Read(_ []byte) (int, error) {
	<-r.ctx.Done()
	return 0, r.ctx.Err()
}

func (r *contextReadCloser) Close() error { return nil }

func TestHTTPIngestionClientChatMethodsUseBoundedSafeRequests(t *testing.T) {
	var mu sync.Mutex
	var paths []string
	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		mu.Lock()
		paths = append(paths, request.Method+" "+request.URL.Path)
		mu.Unlock()
		if request.Header.Get("Authorization") != "" {
			t.Errorf("authorization header was forwarded")
		}
		if request.Header.Get("X-Autodata-Internal-Token") != "internal-secret" {
			t.Errorf("internal token was not set")
		}
		if request.Header.Get("X-Request-ID") != "request-3" || request.Header.Get("X-Autodata-Owner-Id") != "owner-3" || request.Header.Get("X-Autodata-Organization-Id") != "org-3" {
			t.Errorf("safe correlation headers = request %q owner %q organization %q", request.Header.Get("X-Request-ID"), request.Header.Get("X-Autodata-Owner-Id"), request.Header.Get("X-Autodata-Organization-Id"))
		}
		switch request.URL.Path {
		case "/v1/chat/queries":
			if request.Method != http.MethodPost || request.Header.Get("Idempotency-Key") != "create-3" {
				t.Errorf("create method/key = %s/%q", request.Method, request.Header.Get("Idempotency-Key"))
			}
			response.Header().Set("X-Internal-Secret", "must-not-cross")
			response.Header().Set("Content-Type", "application/json")
			_, _ = response.Write([]byte(`{"query_id":"q-3"}`))
		case "/v1/chat/queries/q-3/selections":
			if request.Method != http.MethodPost || request.Header.Get("Idempotency-Key") != "select-3" {
				t.Errorf("select method/key = %s/%q", request.Method, request.Header.Get("Idempotency-Key"))
			}
			_, _ = response.Write([]byte(`{"query_id":"q-3","status":"processing"}`))
		case "/v1/chat/queries/q-3":
			if request.Method != http.MethodGet {
				t.Errorf("get method = %s", request.Method)
			}
			_, _ = response.Write([]byte(`{"query_id":"q-3"}`))
		case "/v1/chat/queries/q-3/events":
			if request.Method != http.MethodGet || request.Header.Get("Accept") != "text/event-stream" || request.Header.Get("Last-Event-ID") != "event-2" {
				t.Errorf("events method/accept/last-id = %s/%q/%q", request.Method, request.Header.Get("Accept"), request.Header.Get("Last-Event-ID"))
			}
			_, _ = response.Write([]byte("id: event-3\ndata: {}\n\n"))
		default:
			response.WriteHeader(http.StatusNotFound)
		}
	}))
	defer server.Close()

	client, err := NewHTTPIngestionClient(server.URL, "internal-secret", 2*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	incoming := httptest.NewRequest(http.MethodPost, "/chat/queries", strings.NewReader("{}"))
	incoming.Header.Set("Authorization", "Bearer public-secret")
	incoming.Header.Set("X-Request-ID", "request-3")
	incoming.Header.Set("X-Autodata-Owner-Id", "owner-3")
	incoming.Header.Set("X-Autodata-Organization-Id", "org-3")

	if status, body, err := client.Create(context.Background(), incoming, []byte(`{"message":"brakes"}`), "create-3"); err != nil || status != http.StatusOK || !strings.Contains(string(body), "q-3") {
		t.Fatalf("create = %d/%s/%v", status, body, err)
	}
	if status, _, err := client.Select(context.Background(), incoming, "q-3", []byte(`{"option_number":1}`), "select-3"); err != nil || status != http.StatusOK {
		t.Fatalf("select = %d/%v", status, err)
	}
	if status, _, err := client.Get(context.Background(), incoming, "q-3"); err != nil || status != http.StatusOK {
		t.Fatalf("get = %d/%v", status, err)
	}
	stream, err := client.Events(context.Background(), incoming, "q-3", "event-2")
	if err != nil {
		t.Fatal(err)
	}
	streamBody, err := io.ReadAll(stream)
	_ = stream.Close()
	if err != nil || !strings.Contains(string(streamBody), "event-3") {
		t.Fatalf("events = %s/%v", streamBody, err)
	}

	mu.Lock()
	defer mu.Unlock()
	want := []string{"POST /v1/chat/queries", "POST /v1/chat/queries/q-3/selections", "GET /v1/chat/queries/q-3", "GET /v1/chat/queries/q-3/events"}
	if strings.Join(paths, ",") != strings.Join(want, ",") {
		t.Fatalf("paths = %v, want %v", paths, want)
	}
}
