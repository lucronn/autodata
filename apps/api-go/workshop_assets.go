package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io/fs"
	"net/http"
	"strings"
	"time"
)

const workshopEntryPath = "/workshop"
const workshopInitialYearsMarker = "<!-- Workshop initial years -->"
const workshopInitialYearsTimeout = 25 * time.Millisecond

var workshopAssetsHandler = buildWorkshopAssetsHandler()

type workshopEntryOptions struct {
	publicSelectors bool
	openDemo        bool
	publicDemo      bool
	initialYears    []byte
}

func (s *Server) workshopInitialYears(r *http.Request) []byte {
	if (r.URL.Path != workshopEntryPath && r.URL.Path != workshopEntryPath+"/") ||
		(r.Method != http.MethodGet && r.Method != http.MethodHead) {
		return nil
	}
	params := r.URL.Query()
	region := params.Get("region")
	if params.Get("sample") == "1" || params.Get("demo") == "1" || params.Get("view") == "library" ||
		params.Has("article") || params.Has("configuration") || params.Has("order") ||
		(region != "" && region != "US") {
		return nil
	}
	// The same anonymous snapshot backs the public year endpoint. Keep the page
	// available during database contention and leave discovery to the API.
	ctx, cancel := context.WithTimeout(r.Context(), workshopInitialYearsTimeout)
	defer cancel()
	years, err := s.readCatalogYears(ctx, Principal{})
	if err != nil || ctx.Err() != nil || !years.Complete || len(years.Items) == 0 {
		return nil
	}
	data, err := json.Marshal(years)
	if err != nil {
		return nil
	}
	return data
}

func buildWorkshopAssetsHandler() func(http.ResponseWriter, *http.Request, workshopEntryOptions) {
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
	if bytes.Count(entryPage, []byte(workshopInitialYearsMarker)) != 1 {
		panic("Workshop entry page must mark the initial year data location")
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
	const selectorMarker = `data-public-selectors="false"`
	if bytes.Count(entryPage, []byte(selectorMarker)) != 1 {
		panic("Workshop entry page must mark selector visibility")
	}
	publicEntry := bytes.Replace(entryPage, []byte(selectorMarker), []byte(`data-public-selectors="true"`), 1)
	publicEntryTag := fmt.Sprintf(`W/"%x"`, sha256.Sum256(publicEntry))
	const demoMarker = `data-workshop-open-demo="false"`
	if bytes.Count(entryPage, []byte(demoMarker)) != 1 {
		panic("Workshop entry page must mark public demo availability")
	}
	openDemoEntry := bytes.Replace(publicEntry, []byte(demoMarker), []byte(`data-workshop-open-demo="true"`), 1)
	openDemoEntryTag := fmt.Sprintf(`W/"%x"`, sha256.Sum256(openDemoEntry))
	// The public proxy can serve the entry with a different origin Host.
	browserOrigins := demoMarker + ` data-workshop-demo-origins="` + workshopPublicDemoOrigin + " https://" + workshopPublicDemoTunnelHost + `"`
	publicDemoEntry := bytes.Replace(publicEntry, []byte(demoMarker), []byte(browserOrigins), 1)
	publicDemoEntryTag := fmt.Sprintf(`W/"%x"`, sha256.Sum256(publicDemoEntry))
	files := http.StripPrefix(prefix, http.FileServer(http.FS(assets)))
	return func(w http.ResponseWriter, r *http.Request, entry workshopEntryOptions) {
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
			// Preserve the origin representation through the tunnel and shared cache.
			w.Header().Set("Cache-Control", "private, max-age=31536000, immutable, no-transform")
			w.Header().Add("Vary", "Accept-Encoding")
			if r.URL.RawQuery == "" && r.Header.Get("Range") == "" {
				// The release digest identifies the exact embedded bytes. Keep
				// request-specific tracing values out of the shared response.
				w.Header().Set("Vercel-CDN-Cache-Control", "public, max-age=86400, immutable, no-transform")
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
			// Every browser receives shared HTML with at most a public year snapshot.
			w.Header().Set("Cache-Control", "private, max-age=30, must-revalidate")
			document := entryPage
			if entry.publicDemo {
				document = publicDemoEntry
				w.Header().Set("ETag", publicDemoEntryTag)
			} else if entry.openDemo {
				document = openDemoEntry
				w.Header().Set("ETag", openDemoEntryTag)
			} else if entry.publicSelectors {
				document = publicEntry
				w.Header().Set("ETag", publicEntryTag)
			}
			if len(entry.initialYears) != 0 {
				data := fmt.Appendf(nil, `<script id="workshop-initial-years" type="application/json">%s</script>`, entry.initialYears)
				document = bytes.Replace(document, []byte(workshopInitialYearsMarker), data, 1)
				w.Header().Set("ETag", fmt.Sprintf(`W/"%x"`, sha256.Sum256(document)))
			}
			// Share the canonical picker only when it carries a complete anonymous
			// snapshot. Requests with selections keep the browser cache policy.
			if r.URL.Path == workshopEntryPath && r.URL.RawQuery == "" && !r.URL.ForceQuery &&
				entry.publicSelectors && len(entry.initialYears) != 0 &&
				r.Header.Get("Range") == "" && len(w.Header().Values("Set-Cookie")) == 0 {
				w.Header().Set("Vercel-CDN-Cache-Control", "public, max-age=15")
				w.Header().Del("X-Request-ID")
				w.Header().Del("Traceparent")
			}
			http.ServeContent(w, r, "index.html", time.Time{}, bytes.NewReader(document))
			return
		}
		files.ServeHTTP(w, r)
	}
}
