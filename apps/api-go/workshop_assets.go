package main

import (
	"crypto/sha256"
	"fmt"
	"io/fs"
	"net/http"
)

var workshopAssetsHandler = buildWorkshopAssetsHandler()

func buildWorkshopAssetsHandler() http.Handler {
	assets, err := fs.Sub(dashboardFiles, "workshop")
	if err != nil {
		panic("embedded Workshop assets unavailable: " + err.Error())
	}
	const prefix = "/workshop/"
	tags := map[string]string{}
	err = fs.WalkDir(assets, ".", func(name string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil || entry.IsDir() {
			return walkErr
		}
		data, err := fs.ReadFile(assets, name)
		if err != nil {
			return err
		}
		if name == "index.html" {
			name = ""
		}
		// A reverse proxy can serve the same asset with a different content coding.
		tags[prefix+name] = fmt.Sprintf(`W/"%x"`, sha256.Sum256(data))
		return nil
	})
	if err != nil {
		panic("embedded Workshop asset validation unavailable: " + err.Error())
	}
	files := http.StripPrefix(prefix, http.FileServer(http.FS(assets)))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD")
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Cache-Control", "no-cache")
		if tag := tags[r.URL.Path]; tag != "" {
			w.Header().Set("ETag", tag)
		}
		files.ServeHTTP(w, r)
	})
}
