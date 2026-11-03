package main

import (
	"context"
	"crypto/hmac"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"time"
)

func (s *customerAuthService) mountRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /auth/config", s.publicConfig)
	mux.HandleFunc("GET /auth/session", s.currentSession)
	mux.HandleFunc("POST /auth/firebase/session", s.exchangeSession)
	mux.HandleFunc("POST /auth/logout", s.logoutSession)
}
func (s *customerAuthService) publicConfig(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	result := map[string]any{"version": "v1", "mode": s.config.Mode, "login_available": false, "providers": []string{}}
	if s.config.Mode == "firebase" {
		result["login_available"] = true
		result["providers"] = []string{"google.com"}
		result["firebase"] = map[string]string{"apiKey": s.config.APIKey, "authDomain": s.config.AuthDomain, "projectId": s.config.ProjectID, "appId": s.config.AppID}
	}
	writeJSON(w, 200, result)
}
func (s *customerAuthService) writeError(w http.ResponseWriter, r *http.Request, err error) {
	w.Header().Set("Cache-Control", "no-store")
	status, code, message, retryable := 401, "UNAUTHENTICATED", "Authentication is required.", false
	switch {
	case errors.Is(err, ErrCustomerDependency):
		status, code, message, retryable = 503, "AUTHENTICATION_UNAVAILABLE", "Authentication is temporarily unavailable.", true
	case errors.Is(err, ErrCustomerBlocked):
		status, code, message = 403, "FORBIDDEN", "Access is denied."
	case errors.Is(err, ErrCustomerCSRF):
		status, code, message = 403, "FORBIDDEN", "Request origin or CSRF token is invalid."
	default:
		if s.config.Mode == "firebase" {
			http.SetCookie(w, customerSessionCookie("", time.Time{}, s.clock()))
		}
	}
	writeJSON(w, status, map[string]any{"error": map[string]any{"code": code, "message": message, "retryable": retryable, "request_id": requestIDFrom(r), "details": map[string]any{"login_available": s.config.Mode == "firebase"}}})
}
func (s *customerAuthService) currentSession(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	session, token, err := s.session(r, true)
	if err != nil {
		s.writeError(w, r, err)
		return
	}
	writeJSON(w, 200, map[string]any{"authenticated": true, "roles": []string{"dataset_viewer"}, "expires_at": session.ExpiresAt.UTC().Format(time.RFC3339), "csrf_token": customerCSRF(token)})
}
func (s *customerAuthService) exchangeSession(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	if s.config.Mode != "firebase" {
		writeJSON(w, 503, map[string]any{"error": map[string]any{"code": "AUTHENTICATION_UNAVAILABLE", "message": "Sign-in is unavailable.", "retryable": false, "request_id": requestIDFrom(r), "details": map[string]any{"login_available": false}}})
		return
	}
	if !s.validOrigin(r) || r.Header.Get("X-Autodata-Session-Exchange") != "1" {
		s.writeError(w, r, ErrCustomerCSRF)
		return
	}
	if len(r.Header.Values("Authorization")) != 0 {
		s.writeError(w, r, ErrUnauthenticated)
		return
	}
	contentType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || contentType != "application/json" {
		writeAPIError(w, r, 415, "INVALID_REQUEST", "JSON is required.", false)
		return
	}
	var input struct {
		IDToken string `json:"id_token"`
	}
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 32*1024))
	decoder.DisallowUnknownFields()
	err = decoder.Decode(&input)
	if err == nil {
		var trailing any
		if decoder.Decode(&trailing) != io.EOF {
			err = errors.New("trailing JSON")
		}
	}
	if err != nil || input.IDToken == "" {
		status := 400
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			status = 413
		}
		writeAPIError(w, r, status, "INVALID_REQUEST", "Invalid sign-in request.", false)
		return
	}
	if s.verifier == nil || s.store == nil {
		s.writeError(w, r, ErrCustomerDependency)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	identity, err := s.verifier.VerifyLogin(ctx, input.IDToken)
	if err != nil {
		s.writeError(w, r, err)
		return
	}
	now := s.clock()
	if identity.ProjectID != s.config.ProjectID || identity.UID == "" || identity.AuthTime <= 0 || identity.AuthTime < now.Unix()-300 || identity.AuthTime > now.Unix()+60 || identity.IssuedAt < now.Unix()-300 || identity.IssuedAt > now.Unix()+60 || identity.Expires <= now.Unix() {
		s.writeError(w, r, ErrUnauthenticated)
		return
	}
	token, hash, err := newCustomerSessionToken()
	if err != nil {
		s.writeError(w, r, ErrCustomerDependency)
		return
	}
	_, oldHash, _ := customerRequestToken(r)
	expires := now.Add(customerSessionLifetime)
	if _, err = s.store.Rotate(ctx, identity, hash, oldHash, now, expires); err != nil {
		s.writeError(w, r, err)
		return
	}
	http.SetCookie(w, customerSessionCookie(token, expires, now))
	w.WriteHeader(204)
}
func (s *customerAuthService) logoutSession(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	_, token, err := s.session(r, false)
	if err != nil {
		s.writeError(w, r, err)
		return
	}
	if !s.validOrigin(r) || !hmac.Equal([]byte(r.Header.Get("X-CSRF-Token")), []byte(customerCSRF(token))) {
		s.writeError(w, r, ErrCustomerCSRF)
		return
	}
	_, hash, err := customerRequestToken(r)
	if err != nil {
		s.writeError(w, r, err)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if err = s.store.Revoke(ctx, hash, s.clock()); err != nil {
		s.writeError(w, r, err)
		return
	}
	http.SetCookie(w, customerSessionCookie("", time.Time{}, s.clock()))
	w.WriteHeader(204)
}
