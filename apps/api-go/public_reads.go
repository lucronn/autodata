package main

import "net/http"

// Public read routes support browser clients without cross-origin credentials.
func mountPublicRead(mux *http.ServeMux, path string, read http.HandlerFunc) {
	mux.HandleFunc("GET "+path, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Expose-Headers", "X-Request-ID, Retry-After")
		read(w, r)
	})
	mux.HandleFunc("OPTIONS "+path, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Allow", "GET, HEAD, OPTIONS")
		switch r.Header.Get("Access-Control-Request-Method") {
		case http.MethodGet, http.MethodHead:
			w.Header().Set("Access-Control-Allow-Origin", "*")
			w.Header().Set("Access-Control-Allow-Methods", "GET, HEAD")
			// Fetch requires Authorization to be listed even for public requests.
			w.Header().Set("Access-Control-Allow-Headers", "*, Authorization")
			w.Header().Set("Access-Control-Max-Age", "600")
		case "":
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
}
