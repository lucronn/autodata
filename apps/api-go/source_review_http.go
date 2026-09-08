package main

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strconv"
	"strings"
)

func (s *Server) listSourceReviewItems(response http.ResponseWriter, request *http.Request, principal Principal) {
	status := strings.TrimSpace(strings.ToLower(request.URL.Query().Get("status")))
	if status == "" {
		status = "pending"
	}
	if status != "pending" && status != "approved" && status != "rejected" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "status must be pending, approved, or rejected", false)
		return
	}
	limit := 50
	if raw := strings.TrimSpace(request.URL.Query().Get("limit")); raw != "" {
		parsed, err := strconv.Atoi(raw)
		if err != nil || parsed < 1 || parsed > 200 {
			writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "limit must be between 1 and 200", false)
			return
		}
		limit = parsed
	}
	queue, err := s.sourceReviews.List(principal, status, limit)
	if err != nil {
		writeSourceReviewError(response, request, err)
		return
	}
	writeJSON(response, http.StatusOK, queue)
}

func (s *Server) reviewSourceItem(response http.ResponseWriter, request *http.Request, principal Principal) {
	id := strings.TrimSpace(request.PathValue("id"))
	if id == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "source review item ID is required", false)
		return
	}
	var input SourceReviewReviewInput
	decoder := json.NewDecoder(io.LimitReader(request.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "source review body is invalid", false)
		return
	}
	input = normalizedSourceReviewDecision(input)
	item, err := s.sourceReviews.Review(id, input, principal)
	if err != nil {
		writeSourceReviewError(response, request, err)
		return
	}
	writeJSON(response, http.StatusOK, item)
}

func writeSourceReviewError(response http.ResponseWriter, request *http.Request, err error) {
	switch {
	case errors.Is(err, ErrSourceReviewNotFound):
		writeAPIError(response, request, http.StatusNotFound, "SOURCE_REVIEW_NOT_FOUND", err.Error(), false)
	case errors.Is(err, ErrSourceReviewConflict):
		writeAPIError(response, request, http.StatusConflict, "SOURCE_REVIEW_CONFLICT", err.Error(), false)
	case errors.Is(err, ErrInvalidSourceReview):
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
	default:
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "source review item could not be read", true)
	}
}
