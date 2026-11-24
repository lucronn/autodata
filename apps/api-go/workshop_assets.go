package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io/fs"
	"net/http"
	"strings"
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
	const releasePrefix = prefix + "assets/"
	const bootstrapName = "bootstrap.mjs"
	bootstrap, err := fs.ReadFile(assets, bootstrapName)
	if err != nil {
		panic("embedded Workshop bootstrap unavailable: " + err.Error())
	}
	bootstrapVersion := fmt.Sprintf("v=%x", sha256.Sum256(bootstrap))
	var entryPage []byte
	tags := map[string]string{}
	release := sha256.New()
	err = fs.WalkDir(assets, ".", func(name string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil || entry.IsDir() {
			return walkErr
		}
		data, err := fs.ReadFile(assets, name)
		if err != nil {
			return err
		}
		if name == "index.html" {
			entryPage = data
			return nil
		}
		// A reverse proxy can serve the same asset with a different content coding.
		sum := sha256.Sum256(data)
		tags[prefix+name] = fmt.Sprintf(`W/"%x"`, sum)
		fmt.Fprintf(release, "%s\x00%x\n", name, sum)
		return nil
	})
	if err != nil {
		panic("embedded Workshop asset validation unavailable: " + err.Error())
	}
	if entryPage == nil {
		panic("embedded Workshop entry page unavailable")
	}
	version := hex.EncodeToString(release.Sum(nil))
	versionedPrefix := releasePrefix + version + "/"
	for _, asset := range []string{"bootstrap.mjs", "catalog.mjs", "styles.css", "fonts/InstrumentSans.woff2"} {
		unversioned := []byte(`"` + prefix + asset + `"`)
		if tags[prefix+asset] == "" || bytes.Count(entryPage, unversioned) != 1 {
			panic("Workshop entry page must reference " + asset + " once")
		}
		entryPage = bytes.Replace(entryPage, unversioned, []byte(`"`+versionedPrefix+asset+`"`), 1)
	}
	tags[prefix] = fmt.Sprintf(`W/"%x"`, sha256.Sum256(entryPage))
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
		if releasePath, versioned := strings.CutPrefix(path, releasePrefix); versioned {
			requestedVersion, asset, valid := strings.Cut(releasePath, "/")
			assetPath := prefix + asset
			if !valid || len(requestedVersion) != len(version) || assetPath == prefix || tags[assetPath] == "" {
				http.NotFound(w, r)
				return
			}
			if _, err := hex.DecodeString(requestedVersion); err != nil {
				http.NotFound(w, r)
				return
			}
			if requestedVersion != version {
				// An open tab can request a lazy module after another release.
				// Never cache different content under the old release's URL.
				w.Header().Set("Cache-Control", "no-store")
				http.Redirect(w, r, assetPath, http.StatusTemporaryRedirect)
				return
			}
			w.Header().Set("Cache-Control", "private, max-age=31536000, immutable")
			if r.URL.RawQuery == "" && r.Header.Get("Range") == "" {
				// The release digest identifies the exact embedded bytes. Keep
				// request-specific tracing values out of the shared response.
				w.Header().Set("Vercel-CDN-Cache-Control", "public, max-age=86400, immutable")
				w.Header().Del("X-Request-ID")
				w.Header().Del("Traceparent")
			}
			r = r.Clone(r.Context())
			r.URL.Path = assetPath
			r.URL.RawPath = ""
			path = assetPath
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
