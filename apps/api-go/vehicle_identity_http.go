package main

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
)

func (s *Server) resolveVehicleIdentity(response http.ResponseWriter, request *http.Request, principal Principal) {
	idempotencyKey := request.Header.Get("Idempotency-Key")
	if idempotencyKey == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "Idempotency-Key is required", false)
		return
	}
	var input VehicleIdentityResolveInput
	decoder := json.NewDecoder(io.LimitReader(request.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "vehicle list is invalid", false)
		return
	}
	record, duplicate, err := s.vehicleIdentity.Resolve(principal, input, idempotencyKey)
	if errors.Is(err, ErrVehicleIdentityInvalid) {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	if errors.Is(err, ErrVehicleIdentityConflict) {
		writeAPIError(response, request, http.StatusConflict, "DUPLICATE_REQUEST", err.Error(), false)
		return
	}
	if err != nil {
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "vehicle identity could not be resolved", true)
		return
	}
	status := http.StatusCreated
	if duplicate {
		status = http.StatusOK
	}
	writeJSON(response, status, record)
}

func (s *Server) listVehicleIdentitySelectors(response http.ResponseWriter, request *http.Request, principal Principal) {
	selectors, err := s.vehicleIdentity.Selectors(principal)
	if err != nil {
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "vehicle selectors could not be read", true)
		return
	}
	writeJSON(response, http.StatusOK, selectors)
}
