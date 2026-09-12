package main

import (
	"bufio"
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
)

const (
	maxChatEventFrameBytes  = 256 * 1024
	maxChatEventStreamBytes = 1 << 20
	maxChatEventFrames      = 1024
)

func (s *Server) streamChatEvents(response http.ResponseWriter, request *http.Request, principal Principal) {
	queryID, err := chatPathID(request)
	if err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	lastEventID := strings.TrimSpace(request.Header.Get("Last-Event-ID"))
	if len(lastEventID) > 256 {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "Last-Event-ID is too long", false)
		return
	}
	if s.chatClient == nil {
		writeAPIError(response, request, http.StatusServiceUnavailable, "INGESTION_UNAVAILABLE", "chat service is not configured", true)
		return
	}
	stream, err := s.chatClient.Events(
		request.Context(),
		chatInternalRequest(request, principal),
		queryID,
		lastEventID,
	)
	if err != nil {
		writeAPIError(response, request, http.StatusBadGateway, "INGESTION_UNAVAILABLE", "chat event stream is unavailable", true)
		return
	}
	defer stream.Close()
	if err := writeChatEventStream(response, request.Context(), stream); err != nil {
		// Headers may already be committed. Do not write a second JSON response
		// or leak the internal stream error into the event channel.
		return
	}
}

func writeChatEventStream(response http.ResponseWriter, ctx context.Context, stream io.Reader) error {
	flusher, ok := response.(http.Flusher)
	if !ok {
		return fmt.Errorf("streaming is not supported by the response writer")
	}
	response.Header().Set("Content-Type", "text/event-stream")
	response.Header().Set("Cache-Control", "no-cache")
	response.Header().Set("Connection", "keep-alive")
	response.Header().Set("X-Accel-Buffering", "no")
	response.WriteHeader(http.StatusOK)

	reader := bufio.NewReaderSize(stream, 4096)
	var frame bytes.Buffer
	var totalBytes int
	frameCount := 0
	writeFrame := func() error {
		if frame.Len() == 0 {
			return nil
		}
		if frame.Len() > maxChatEventFrameBytes || totalBytes+frame.Len() > maxChatEventStreamBytes || frameCount >= maxChatEventFrames {
			return fmt.Errorf("chat event stream exceeded configured bounds")
		}
		if _, err := response.Write(frame.Bytes()); err != nil {
			return err
		}
		totalBytes += frame.Len()
		frameCount++
		frame.Reset()
		flusher.Flush()
		return nil
	}

	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		part, err := reader.ReadSlice('\n')
		if len(part) > 0 {
			if frame.Len()+len(part) > maxChatEventFrameBytes {
				return fmt.Errorf("chat event frame exceeded configured limit")
			}
			_, _ = frame.Write(part)
			if bytes.HasSuffix(frame.Bytes(), []byte("\n\n")) || bytes.HasSuffix(frame.Bytes(), []byte("\r\n\r\n")) {
				if err := writeFrame(); err != nil {
					return err
				}
			}
		}
		if err == io.EOF {
			return writeFrame()
		}
		if err != nil && !errors.Is(err, bufio.ErrBufferFull) {
			return err
		}
	}
}
