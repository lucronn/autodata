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
	"slices"
	"strings"
	"time"
)

const workshopEntryPath = "/workshop"
const workshopInitialYearsMarker = "<!-- Workshop initial years -->"
const workshopInitialYearsTimeout = 25 * time.Millisecond
const workshopInitialMakeFallbackYearCount = 6
const workshopInitialMakesMaxBytes = 24 << 10

var workshopAssetsHandler = buildWorkshopAssetsHandler()

type workshopEntryOptions struct {
	publicSelectors bool
	openDemo        bool
	publicDemo      bool
	initialYears    []byte
	initialMakes    []byte
}

type workshopEntryMakes struct {
	Options []CatalogMake `json:"options"`
	Years   map[int][]int `json:"years"`
}

func encodeWorkshopEntryMakes(years []int, lists map[int][]CatalogMake) ([]byte, error) {
	packed := workshopEntryMakes{Years: make(map[int][]int, len(lists))}
	positions := make(map[CatalogMake]int)
	for _, year := range years {
		makes := lists[year]
		if len(makes) == 0 {
			continue
		}
		indexes := make([]int, 0, len(makes))
		for _, makeChoice := range makes {
			index, found := positions[makeChoice]
			if !found {
				index = len(packed.Options)
				packed.Options = append(packed.Options, makeChoice)
				positions[makeChoice] = index
			}
			indexes = append(indexes, index)
		}
		packed.Years[year] = indexes
	}
	if len(packed.Years) == 0 {
		return nil, nil
	}
	return json.Marshal(packed)
}

func (s *Server) workshopInitialSelectors(r *http.Request) (yearData, makeData []byte) {
	if (r.URL.Path != workshopEntryPath && r.URL.Path != workshopEntryPath+"/") ||
		(r.Method != http.MethodGet && r.Method != http.MethodHead) {
		return nil, nil
	}
	params := r.URL.Query()
	region := params.Get("region")
	if params.Get("sample") == "1" || params.Get("demo") == "1" || params.Get("view") == "library" ||
		params.Has("article") || params.Has("configuration") || params.Has("order") ||
		(region != "" && region != "US") {
		return nil, nil
	}
	// The same anonymous snapshot backs the public year endpoint. Keep the page
	// available during database contention and leave discovery to the API.
	ctx, cancel := context.WithTimeout(r.Context(), workshopInitialYearsTimeout)
	defer cancel()
	years, err := s.readCatalogYears(ctx, Principal{})
	if err != nil || ctx.Err() != nil || !years.Complete || len(years.Items) == 0 {
		return nil, nil
	}
	yearData, err = json.Marshal(years)
	if err != nil {
		return nil, nil
	}
	// The initial make lists share the existing entry read deadline.
	if store, ok := s.catalog.(interface {
		catalogMakeLists(context.Context, []int, string, bool) (map[int][]CatalogMake, error)
	}); ok {
		modelYears := make([]int, 0, len(years.Items))
		for _, item := range years.Items {
			modelYears = append(modelYears, item.Year)
		}
		slices.Sort(modelYears)
		modelYears = slices.Compact(modelYears)
		lists, err := store.catalogMakeLists(ctx, modelYears, "US", true)
		if err == nil && ctx.Err() == nil && len(lists) > 0 {
			encoded, err := encodeWorkshopEntryMakes(modelYears, lists)
			if err == nil && len(encoded) > workshopInitialMakesMaxBytes {
				recent := modelYears[max(0, len(modelYears)-workshopInitialMakeFallbackYearCount):]
				encoded, err = encodeWorkshopEntryMakes(recent, lists)
			}
			if err == nil && ctx.Err() == nil && len(encoded) <= workshopInitialMakesMaxBytes {
				makeData = encoded
			}
		}
	}
	return yearData, makeData
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
			// The shared entry carries only anonymous selector data.
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
				if len(entry.initialMakes) != 0 {
					data = fmt.Appendf(data, `<script id="workshop-initial-makes" type="application/json">%s</script>`, entry.initialMakes)
				}
				document = bytes.Replace(document, []byte(workshopInitialYearsMarker), data, 1)
				w.Header().Set("ETag", fmt.Sprintf(`W/"%x"`, sha256.Sum256(document)))
			}
			http.ServeContent(w, r, "index.html", time.Time{}, bytes.NewReader(document))
			return
		}
		files.ServeHTTP(w, r)
	}
}
