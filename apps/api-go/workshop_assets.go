package main

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"io/fs"
	"net/http"
	"time"
)

const workshopEntryPath = "/workshop"

var workshopAssetsHandler = buildWorkshopAssetsHandler()

func buildWorkshopAssetsHandler() http.Handler {
	assets, err := fs.Sub(dashboardFiles, "workshop")
	if err != nil {
		panic("embedded Workshop assets unavailable: " + err.Error())
	}
	const prefix = workshopEntryPath + "/"
	const bootstrapName = "bootstrap.mjs"
	bootstrap, err := fs.ReadFile(assets, bootstrapName)
	if err != nil {
		panic("embedded Workshop bootstrap unavailable: " + err.Error())
	}
	bootstrapVersion := fmt.Sprintf("v=%x", sha256.Sum256(bootstrap))
	bootstrapSrc := []byte(`src="` + prefix + bootstrapName + `"`)
	versionedSrc := []byte(`src="` + prefix + bootstrapName + "?" + bootstrapVersion + `"`)
	var entryPage []byte
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
			if bytes.Count(data, bootstrapSrc) != 1 {
				return fmt.Errorf("Workshop entry page must reference %s once", bootstrapName)
			}
			entryPage = bytes.Replace(data, bootstrapSrc, versionedSrc, 1)
			data = entryPage
			name = ""
		}
		// A reverse proxy can serve the same asset with a different content coding.
		tags[prefix+name] = fmt.Sprintf(`W/"%x"`, sha256.Sum256(data))
		return nil
	})
	if err != nil {
		panic("embedded Workshop asset validation unavailable: " + err.Error())
	}
	if entryPage == nil {
		panic("embedded Workshop entry page unavailable")
	}
	files := http.StripPrefix(prefix, http.FileServer(http.FS(assets)))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD")
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Cache-Control", "no-cache")
		path := r.URL.Path
		if path == workshopEntryPath {
			path = prefix
		}
		if path == prefix+bootstrapName && r.URL.RawQuery == bootstrapVersion {
			w.Header().Set("Cache-Control", "private, max-age=31536000, immutable")
		}
		if tag := tags[path]; tag != "" {
			w.Header().Set("ETag", tag)
		}
		if path == prefix {
			http.ServeContent(w, r, "index.html", time.Time{}, bytes.NewReader(entryPage))
			return
		}
		files.ServeHTTP(w, r)
	})
}
