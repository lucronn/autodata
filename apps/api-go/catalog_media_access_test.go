package main

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func paidMediaTestReference(now time.Time) paidCatalogImageReference {
	return paidCatalogImageReference{Version: 2, IssuedAt: now.Unix(), ExpiresAt: now.Unix() + 300,
		CustomerAccountID: "11111111-1111-4111-8111-111111111111", ConfigurationID: "22222222-2222-4222-8222-222222222222", Region: "US", CanonicalArticleID: "33333333-3333-4333-8333-333333333333", ProviderSlug: "bankone",
		SourceVehicleRefSHA256: strings.Repeat("a", 64), SourceArticleRefSHA256: strings.Repeat("b", 64), SelectedSourceRevisionID: "44444444-4444-4444-8444-444444444444", AnchorSourceRevisionID: "55555555-5555-4555-8555-555555555555", AnchorCanonicalRevisionID: stringPointer("66666666-6666-4666-8666-666666666666"), Projection: "article", AssetID: "asset-1", ObjectKey: "procedure-images/" + strings.Repeat("a", 64)}
}
func paidMediaSealRaw(t *testing.T, raw []byte, key []byte) string {
	t.Helper()
	block, err := aes.NewCipher(key)
	if err != nil {
		t.Fatal(err)
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		t.Fatal(err)
	}
	nonce := make([]byte, aead.NonceSize())
	if _, err = rand.Read(nonce); err != nil {
		t.Fatal(err)
	}
	return "v2." + base64.RawURLEncoding.EncodeToString(aead.Seal(nonce, nonce, raw, []byte("autodata:catalog-image:v2")))
}
func TestPaidCatalogMediaCodecAuthenticatedAndContextual(t *testing.T) {
	now := time.Unix(1800000000, 0)
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	ref := paidMediaTestReference(now)
	first, err := sealPaidCatalogImageReference(ref, key, now)
	if err != nil {
		t.Fatal(err)
	}
	second, err := sealPaidCatalogImageReference(ref, key, now)
	if err != nil {
		t.Fatal(err)
	}
	if first == second || !strings.HasPrefix(first, "v2.") || strings.Contains(first, "procedure-images") {
		t.Fatal("reference is not randomized opaque v2")
	}
	got, err := openPaidCatalogImageReference(first, key, now)
	if err != nil || got.ObjectKey != ref.ObjectKey || got.CustomerAccountID != ref.CustomerAccountID {
		t.Fatalf("decode: %#v %v", got, err)
	}
	corrupted := []byte(first)
	if corrupted[len(corrupted)-3] == 'a' {
		corrupted[len(corrupted)-3] = 'b'
	} else {
		corrupted[len(corrupted)-3] = 'a'
	}
	v1, err := sealCatalogImageReference(ref.ObjectKey, key)
	if err != nil {
		t.Fatal(err)
	}
	for _, token := range []string{string(corrupted), v1, "v2.", strings.Repeat("x", 6001)} {
		if _, err := openPaidCatalogImageReference(token, key, now); err == nil {
			t.Fatal("invalid token accepted")
		}
	}
	if _, err := openPaidCatalogImageReference(first, deriveCatalogImageReferenceKey(strings.Repeat("z", 32)), now); err == nil {
		t.Fatal("wrong key accepted")
	}
	if _, err := openCatalogImageReference(strings.TrimPrefix(first, "v2."), key); err == nil {
		t.Fatal("v2 ciphertext accepted with v1 AAD")
	}
	ref.AnchorCanonicalRevisionID = nil
	token, err := sealPaidCatalogImageReference(ref, key, now)
	if err != nil {
		t.Fatal(err)
	}
	got, err = openPaidCatalogImageReference(token, key, now)
	if err != nil || got.AnchorCanonicalRevisionID != nil {
		t.Fatal("source fallback null anchor lost")
	}
}
func TestPaidCatalogMediaCodecStrictPayloadAndTime(t *testing.T) {
	now := time.Unix(1800000000, 0)
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	ref := paidMediaTestReference(now)
	raw, err := json.Marshal(ref)
	if err != nil {
		t.Fatal(err)
	}
	var valid map[string]any
	if err = json.Unmarshal(raw, &valid); err != nil {
		t.Fatal(err)
	}
	cases := map[string]func(map[string]any){
		"unknown": func(m map[string]any) { m["extra"] = true }, "missing": func(m map[string]any) { delete(m, "anchor_canonical_revision_id") },
		"version": func(m map[string]any) { m["version"] = 1 }, "uuid": func(m map[string]any) { m["configuration_id"] = "vehicle-alias" }, "region": func(m map[string]any) { m["region"] = "us" },
		"digest": func(m map[string]any) { m["source_vehicle_ref_sha256"] = strings.Repeat("A", 64) }, "projection": func(m map[string]any) { m["projection"] = "any" }, "object": func(m map[string]any) { m["object_key"] = "../private" }, "asset": func(m map[string]any) { m["asset_id"] = "https://provider/image" },
		"expiry": func(m map[string]any) { m["expires_at"] = now.Unix() }, "lifetime": func(m map[string]any) { m["expires_at"] = now.Unix() + 301 }, "future": func(m map[string]any) { m["issued_at"] = now.Unix() + 31; m["expires_at"] = now.Unix() + 331 }, "oversize": func(m map[string]any) { m["asset_id"] = strings.Repeat("a", 4096) }, "null-account": func(m map[string]any) { m["customer_account_id"] = nil },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			m := map[string]any{}
			for k, v := range valid {
				m[k] = v
			}
			mutate(m)
			bad, _ := json.Marshal(m)
			if _, err := openPaidCatalogImageReference(paidMediaSealRaw(t, bad, key), key, now); err == nil {
				t.Fatal("invalid payload accepted")
			}
		})
	}
	for name, bad := range map[string][]byte{"duplicate": append([]byte(`{"version":2,`), raw[1:]...), "trailing": append(append([]byte(nil), raw...), []byte(` {}`)...), "array": []byte(`[]`)} {
		t.Run(name, func(t *testing.T) {
			if _, err := openPaidCatalogImageReference(paidMediaSealRaw(t, bad, key), key, now); err == nil {
				t.Fatal("invalid JSON accepted")
			}
		})
	}
	token, err := sealPaidCatalogImageReference(ref, key, now)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := openPaidCatalogImageReference(token, key, now.Add(300*time.Second)); err == nil {
		t.Fatal("expired reference accepted")
	}
	if _, err := sealPaidCatalogImageReference(ref, nil, now); err == nil {
		t.Fatal("weak key accepted")
	}
}

type paidMediaCatalog struct {
	CatalogStore
	configuration                         CatalogConfiguration
	identity                              PaidArticleIdentity
	view                                  CatalogArticleView
	source                                CatalogSourceContent
	identityErr, viewErr, sourceErr       error
	identityCalls, viewCalls, sourceCalls atomic.Int32
	lastSource                            string
}

func (c *paidMediaCatalog) ConfigurationByVehicle(_ context.Context, _ Principal, id string) (CatalogConfiguration, error) {
	if id != c.configuration.ID {
		return CatalogConfiguration{}, ErrCatalogNotFound
	}
	return c.configuration, nil
}
func (c *paidMediaCatalog) PaidArticleIdentity(_ context.Context, config, article string) (PaidArticleIdentity, error) {
	c.identityCalls.Add(1)
	if config != c.configuration.ID || article != c.identity.CanonicalArticleID {
		return PaidArticleIdentity{}, ErrCatalogNotFound
	}
	return c.identity, c.identityErr
}
func (c *paidMediaCatalog) ArticleView(_ context.Context, _ Principal, config, article string) (CatalogArticleView, error) {
	c.viewCalls.Add(1)
	if config != c.configuration.ID || article != c.identity.CanonicalArticleID {
		return CatalogArticleView{}, ErrCatalogNotFound
	}
	return c.view, c.viewErr
}
func (c *paidMediaCatalog) ArticleSourceRevision(_ context.Context, _ Principal, config, article, revision string) (CatalogSourceContent, error) {
	c.sourceCalls.Add(1)
	c.lastSource = revision
	if config != c.configuration.ID || article != c.identity.CanonicalArticleID || revision != *c.source.SourceRevisionID {
		return CatalogSourceContent{}, ErrCatalogNotFound
	}
	return c.source, c.sourceErr
}

type paidMediaGrant struct {
	calls                atomic.Int32
	err, errorAfterFirst error
}

func (g *paidMediaGrant) Do(context.Context, string, []byte, string) (int, []byte, error) {
	panic("unexpected commerce request")
}
func (g *paidMediaGrant) CheckVehicleGrant(_ context.Context, a, o, c, r string) (VehicleGrant, error) {
	n := g.calls.Add(1)
	if !commerceUUID(a) || !commerceUUID(o) {
		return VehicleGrant{}, ErrVehicleGrantUnavailable
	}
	if n > 1 && g.errorAfterFirst != nil {
		return VehicleGrant{}, g.errorAfterFirst
	}
	return VehicleGrant{ConfigurationID: c, Region: r}, g.err
}

type paidMediaReader struct {
	calls       atomic.Int32
	body        []byte
	contentType string
	err         error
	budget      time.Duration
	key         string
}

func (r *paidMediaReader) ReadImage(ctx context.Context, key string) ([]byte, string, error) {
	r.calls.Add(1)
	r.key = key
	if deadline, ok := ctx.Deadline(); ok {
		r.budget = time.Until(deadline)
	}
	return r.body, r.contentType, r.err
}

func paidMediaFixture() (*Server, *paidMediaCatalog, *paidMediaGrant, *paidMediaReader, Principal, paidCatalogImageReference) {
	ref := paidMediaTestReference(time.Now())
	p := Principal{CustomerAccountID: ref.CustomerAccountID, OrganizationID: "77777777-7777-4777-8777-777777777777"}
	image := CatalogImage{ID: ref.AssetID, AssetID: ref.AssetID, ImageID: ref.AssetID, StorageKey: ref.ObjectKey, URL: "https://private-provider.example/original"}
	nested := []CatalogImage{image}
	c := &paidMediaCatalog{configuration: CatalogConfiguration{ID: ref.ConfigurationID, VehicleID: "88888888-8888-4888-8888-888888888888", Region: ref.Region}, identity: PaidArticleIdentity{ConfigurationID: ref.ConfigurationID, CanonicalArticleID: ref.CanonicalArticleID, VehicleID: "88888888-8888-4888-8888-888888888888", ProviderSlug: ref.ProviderSlug, SourceVehicleRef: "private-provider-vehicle", SourceArticleRef: "private-provider-article", CurrentSourceRevisionID: stringPointer(ref.AnchorSourceRevisionID)}, view: CatalogArticleView{Article: CatalogArticle{ID: ref.CanonicalArticleID, CanonicalArticleID: stringPointer(ref.CanonicalArticleID), SourceRevisionID: stringPointer(ref.SelectedSourceRevisionID), CanonicalRevisionID: ref.AnchorCanonicalRevisionID, Availability: "available", Images: []CatalogImage{image}, Steps: []CatalogStep{{Action: "inspect", Instructions: []string{"Check."}, Images: &nested}}}}, source: CatalogSourceContent{SourceRevisionID: stringPointer(ref.SelectedSourceRevisionID), Images: []CatalogImage{image}, Document: &CatalogDocument{Blocks: []CatalogDocumentBlock{{Type: "image", AssetID: ref.AssetID}}}, Original: json.RawMessage(`{}`)}}
	ref.SourceVehicleRefSHA256 = fmt.Sprintf("%x", sha256.Sum256([]byte(c.identity.SourceVehicleRef)))
	ref.SourceArticleRefSHA256 = fmt.Sprintf("%x", sha256.Sum256([]byte(c.identity.SourceArticleRef)))
	g := &paidMediaGrant{}
	r := &paidMediaReader{body: []byte("\x89PNG\r\n\x1a\nfixture"), contentType: "image/png"}
	s := &Server{catalog: c, commerceClient: g, catalogImageKey: deriveCatalogImageReferenceKey(testCatalogImageSecret), catalogImageReader: r, customerAuth: &customerAuthService{config: customerAuthConfig{Mode: "firebase"}}}
	return s, c, g, r, p, ref
}
func paidMediaRequest(s *Server, p Principal, token string) *httptest.ResponseRecorder {
	request := httptest.NewRequest("GET", "/v1/catalog/images/"+token, nil)
	request.SetPathValue("token", token)
	response := httptest.NewRecorder()
	s.servePaidCatalogImage(response, request, p)
	return response
}

func TestPaidCatalogMediaProjectionClonesAndProvesSourceAssets(t *testing.T) {
	s, c, _, _, p, ref := paidMediaFixture()
	original := c.view.Article.Images[0].URL
	view := c.view
	view.Article.Images = append(view.Article.Images, CatalogImage{ID: "unmapped", StorageKey: ref.ObjectKey, URL: "https://secret/unmapped"})
	if err := s.rewritePaidCatalogArticleImages(context.Background(), p, c.configuration, c.identity, &view); err != nil {
		t.Fatal(err)
	}
	for _, image := range []CatalogImage{view.Article.Images[0], (*view.Article.Steps[0].Images)[0]} {
		token := strings.TrimPrefix(image.URL, "/v1/catalog/images/")
		got, err := openPaidCatalogImageReference(token, s.catalogImageKey, time.Now())
		if err != nil || got.Projection != "article" || got.AssetID != ref.AssetID || got.AnchorSourceRevisionID != ref.AnchorSourceRevisionID {
			t.Fatalf("projection=%+v err=%v", got, err)
		}
	}
	if view.Article.Images[1].URL != "" {
		t.Fatal("unmapped asset got URL")
	}
	if c.view.Article.Images[0].URL != original || (*c.view.Article.Steps[0].Images)[0].URL != original {
		t.Fatal("stored/hash image slices mutated")
	}
	c.source.Images[0].StorageKey = "procedure-images/" + strings.Repeat("b", 64)
	view = c.view
	if err := s.rewritePaidCatalogArticleImages(context.Background(), p, c.configuration, c.identity, &view); err != nil {
		t.Fatal(err)
	}
	if view.Article.Images[0].URL != "" || (*view.Article.Steps[0].Images)[0].URL != "" {
		t.Fatal("object-key association was not proved")
	}
	c.sourceErr = ErrCatalogWithdrawn
	view = c.view
	if err := s.rewritePaidCatalogArticleImages(context.Background(), p, c.configuration, c.identity, &view); !errors.Is(err, ErrCatalogWithdrawn) {
		t.Fatal("withdrawn source ignored", err)
	}
}

func TestPaidCatalogMediaRevalidatesBeforeObjectRead(t *testing.T) {
	cases := []struct {
		name   string
		status int
		change func(*paidMediaCatalog, *paidMediaGrant, *paidMediaReader, *Principal, *paidCatalogImageReference)
	}{
		{"ok", 200, func(*paidMediaCatalog, *paidMediaGrant, *paidMediaReader, *Principal, *paidCatalogImageReference) {}},
		{"owner", 404, func(_ *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, p *Principal, _ *paidCatalogImageReference) {
			p.CustomerAccountID = "99999999-9999-4999-8999-999999999999"
		}},
		{"configuration", 404, func(_ *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, r *paidCatalogImageReference) {
			r.ConfigurationID = "99999999-9999-4999-8999-999999999999"
		}},
		{"region", 404, func(_ *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, r *paidCatalogImageReference) {
			r.Region = "CA"
		}},
		{"provider", 404, func(_ *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, r *paidCatalogImageReference) {
			r.ProviderSlug = "banktwo"
		}},
		{"vehicle-ref", 404, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.identity.SourceVehicleRef = "changed"
		}},
		{"article-ref", 404, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.identity.SourceArticleRef = "changed"
		}},
		{"source-anchor", 404, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.identity.CurrentSourceRevisionID = stringPointer("99999999-9999-4999-8999-999999999999")
		}},
		{"canonical-anchor", 404, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.view.Article.CanonicalRevisionID = nil
		}},
		{"selected-source", 404, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.view.Article.SourceRevisionID = c.identity.CurrentSourceRevisionID
		}},
		{"asset", 404, func(_ *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, r *paidCatalogImageReference) {
			r.AssetID = "other"
		}},
		{"source-asset-removed", 404, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.source.Images = nil
		}},
		{"article-asset-removed", 404, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.view.Article.Images = nil
			c.view.Article.Steps = nil
		}},
		{"withdrawn", 410, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.view.Withdrawn = true
		}},
		{"source-withdrawn", 410, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.sourceErr = ErrCatalogWithdrawn
		}},
		{"required", 403, func(_ *paidMediaCatalog, g *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			g.err = ErrVehicleGrantRequired
		}},
		{"revoked", 403, func(_ *paidMediaCatalog, g *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			g.err = ErrVehicleGrantRevoked
		}},
		{"final-revocation", 403, func(_ *paidMediaCatalog, g *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			g.errorAfterFirst = ErrVehicleGrantRevoked
		}},
		{"grant-outage", 503, func(_ *paidMediaCatalog, g *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			g.err = ErrVehicleGrantUnavailable
		}},
		{"identity-outage", 503, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.identityErr = errors.New("private identity query")
		}},
		{"view-outage", 503, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.viewErr = errors.New("private source query")
		}},
		{"source-outage", 503, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, _ *paidCatalogImageReference) {
			c.sourceErr = errors.New("private source query")
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			s, c, g, r, p, ref := paidMediaFixture()
			tc.change(c, g, r, &p, &ref)
			token, err := sealPaidCatalogImageReference(ref, s.catalogImageKey, time.Now())
			if err != nil {
				t.Fatal(err)
			}
			w := paidMediaRequest(s, p, token)
			if w.Code != tc.status {
				t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
			}
			if w.Header().Get("Cache-Control") != "private, no-store" {
				t.Fatal("missing private cache header")
			}
			if tc.status != 200 && r.calls.Load() != 0 {
				t.Fatal("denied request read object")
			}
			if tc.status == 200 && (r.calls.Load() != 1 || g.calls.Load() != 2 || r.budget <= 0 || r.budget > 4*time.Second) {
				t.Fatalf("reader=%d grants=%d budget=%s", r.calls.Load(), g.calls.Load(), r.budget)
			}
			if tc.status != 200 && (strings.Contains(w.Body.String(), token) || strings.Contains(w.Body.String(), "private") || strings.Contains(w.Body.String(), ref.ObjectKey)) {
				t.Fatal("error leaked private context")
			}
			if (tc.name == "required" || tc.name == "revoked" || tc.name == "grant-outage") && (c.identityCalls.Load() != 0 || c.viewCalls.Load() != 0 || c.sourceCalls.Load() != 0) {
				t.Fatal("unpaid request read protected metadata")
			}
		})
	}
}

func TestPaidCatalogMediaHTTPAndHistoricalSourceProjection(t *testing.T) {
	s, c, g, r, p, ref := paidMediaFixture()
	ref.Projection = "source"
	c.view.Article.SourceRevisionID = c.identity.CurrentSourceRevisionID
	c.view.Article.Images = nil
	c.view.Article.Steps = nil
	token, err := sealPaidCatalogImageReference(ref, s.catalogImageKey, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /v1/catalog/images/{token}", func(w http.ResponseWriter, r *http.Request) { s.servePaidCatalogImage(w, r, p) })
	server := httptest.NewServer(mux)
	defer server.Close()
	response, err := server.Client().Get(server.URL + "/v1/catalog/images/" + token)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(response.Body)
	if response.StatusCode != 200 || string(body) != string(r.body) || r.calls.Load() != 1 || g.calls.Load() != 2 {
		t.Fatal(response.StatusCode, string(body))
	}
	for _, header := range []string{"Content-Security-Policy", "Cross-Origin-Resource-Policy", "Referrer-Policy", "X-Content-Type-Options"} {
		if response.Header.Get(header) == "" {
			t.Fatal("missing header", header)
		}
	}
}

func TestPaidCatalogSourceProjectsPinnedHTMLJSONWithoutMutation(t *testing.T) {
	for _, accept := range []string{"application/json", "text/html"} {
		t.Run(accept, func(t *testing.T) {
			s, c, _, _, p, ref := paidMediaFixture()
			c.view.Article.SourceRevisionID = c.identity.CurrentSourceRevisionID
			original := c.source.Images[0].URL
			request := httptest.NewRequest("GET", "/v1/catalog/vehicles/"+ref.ConfigurationID+"/articles/"+ref.CanonicalArticleID+"/source?source_revision_id="+ref.SelectedSourceRevisionID, nil)
			request.SetPathValue("vehicle_id", ref.ConfigurationID)
			request.SetPathValue("article_id", ref.CanonicalArticleID)
			request.Header.Set("Accept", accept)
			w := httptest.NewRecorder()
			s.serveCatalogSource(w, request, p)
			if w.Code != 200 {
				t.Fatalf("status=%d %s", w.Code, w.Body.String())
			}
			if c.source.Images[0].URL != original {
				t.Fatal("stored source images mutated")
			}
			var token string
			if accept == "application/json" {
				var body CatalogSourceContentResponse
				if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
					t.Fatal(err)
				}
				if len(body.Images) != 1 || !strings.Contains(body.Content, "/v1/catalog/images/v2.") {
					t.Fatal("source JSON did not project image", w.Body.String())
				}
				token = strings.TrimPrefix(body.Images[0].URL, "/v1/catalog/images/")
			} else {
				prefix := `src="/v1/catalog/images/`
				_, after, found := strings.Cut(w.Body.String(), prefix)
				if !found {
					t.Fatal("source HTML missing image", w.Body.String())
				}
				token, _, _ = strings.Cut(after, `"`)
			}
			got, err := openPaidCatalogImageReference(token, s.catalogImageKey, time.Now())
			if err != nil || got.Projection != "source" || got.SelectedSourceRevisionID != ref.SelectedSourceRevisionID || got.AnchorSourceRevisionID != ref.AnchorSourceRevisionID {
				t.Fatalf("source reference=%+v err=%v", got, err)
			}
			if c.lastSource != ref.SelectedSourceRevisionID {
				t.Fatal("historical source replaced with current")
			}
			response := paidMediaRequest(s, p, token)
			if response.Code != 200 {
				t.Fatal("fresh historical source image denied", response.Code, response.Body.String())
			}
			if strings.Contains(w.Body.String(), "private-provider") || strings.Contains(w.Body.String(), ref.ObjectKey) {
				t.Fatal("source response leaks private identity")
			}
		})
	}
}

func TestPaidCatalogSourceDeniedBeforeReadAndRawSanitizerOmission(t *testing.T) {
	s, c, g, _, p, ref := paidMediaFixture()
	g.err = ErrVehicleGrantRequired
	request := httptest.NewRequest("GET", "/source", nil)
	request.SetPathValue("vehicle_id", ref.ConfigurationID)
	request.SetPathValue("article_id", ref.CanonicalArticleID)
	w := httptest.NewRecorder()
	s.serveCatalogSource(w, request, p)
	if w.Code != 403 || c.identityCalls.Load() != 0 || c.viewCalls.Load() != 0 || c.sourceCalls.Load() != 0 {
		t.Fatalf("denial=%d identity/view/source=%d/%d/%d", w.Code, c.identityCalls.Load(), c.viewCalls.Load(), c.sourceCalls.Load())
	}
	s, c, _, _, p, ref = paidMediaFixture()
	c.source.Document = nil
	c.source.Original = json.RawMessage(`{"_embedded":{"data":{"article":{"content":"<p>Body</p><img src=\"https://private-provider/image.png\"><img src=\"/v1/catalog/images/legacy\">"}}}}`)
	request = httptest.NewRequest("GET", "/source?source_revision_id="+ref.SelectedSourceRevisionID, nil)
	request.SetPathValue("vehicle_id", ref.ConfigurationID)
	request.SetPathValue("article_id", ref.CanonicalArticleID)
	w = httptest.NewRecorder()
	s.serveCatalogSource(w, request, p)
	if w.Code != 200 || strings.Contains(w.Body.String(), "private-provider") || strings.Contains(w.Body.String(), "images/legacy") || strings.Contains(w.Body.String(), "<img") {
		t.Fatal("raw source image authorized from untrusted URL", w.Code, w.Body.String())
	}
}
