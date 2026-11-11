package main

import (
	"context"
	"encoding/json"
	"net/http"
	"time"
)

// A public presentation signal, never an access grant. Both processes must
// independently agree that the merchant is in test mode before showing it.
func workshopTestCheckoutMode(mode, environment string) bool {
	if mode != "stripe_test" {
		return false
	}
	switch environment {
	case "test", "development", "staging":
		return true
	default:
		return false
	}
}

func (s *Server) workshopDemoMode(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if r.URL.RawQuery != "" || r.URL.ForceQuery {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	enabled := false
	if s.workshopTestCheckout && s.commerceClient != nil {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		status, body, err := s.commerceClient.Do(ctx, "demo-mode", []byte(`{}`), "")
		if err == nil && status == http.StatusOK {
			var payload map[string]json.RawMessage
			if json.Unmarshal(body, &payload) == nil && len(payload) == 2 {
				var mode string
				var purchaseEnabled bool
				if json.Unmarshal(payload["mode"], &mode) == nil &&
					json.Unmarshal(payload["purchase_enabled"], &purchaseEnabled) == nil &&
					mode == "stripe_test" && purchaseEnabled {
					enabled = true
				}
			}
		}
	}
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_ = json.NewEncoder(w).Encode(struct {
			Enabled bool `json:"enabled"`
		}{Enabled: enabled})
	}
}
