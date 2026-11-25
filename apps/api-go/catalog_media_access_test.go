package main

import (
	"bytes"
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
	"log"
	"net/http"
	"net/http/httptest"
	"reflect"
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
	ref.AnchorSourceRevisionID = ref.SelectedSourceRevisionID
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
	if view.Article.Images[0].URL != (*view.Article.Steps[0].Images)[0].URL {
		t.Fatal("identical figure in one authorized response got a second URL")
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

func TestPaidCatalogFigureURLReuseMatchesBothAssetAndObject(t *testing.T) {
	s, c, _, _, p, _ := paidMediaFixture()
	first := c.view.Article.Images[0]
	differentAsset := first
	differentAsset.ID, differentAsset.ImageID, differentAsset.AssetID = "other", "other", "other"
	differentObject := first
	differentObject.StorageKey = "procedure-images/" + strings.Repeat("b", 64)
	unavailable := first
	unavailable.Status = "unavailable"
	c.source.Images = append(c.source.Images, differentAsset, differentObject)
	seen := map[string]bool{}
	for range 2 {
		view := c.view
		view.Article.Images = []CatalogImage{first, differentAsset, differentObject, unavailable}
		if err := s.rewritePaidCatalogArticleImages(context.Background(), p, c.configuration, c.identity, &view); err != nil {
			t.Fatal(err)
		}
		for _, image := range view.Article.Images[:3] {
			ref, err := openPaidCatalogImageReference(strings.TrimPrefix(image.URL, "/v1/catalog/images/"), s.catalogImageKey, time.Now())
			if err != nil || ref.AssetID != paidCatalogImageAssetID(image) || ref.ObjectKey != image.StorageKey || seen[image.URL] {
				t.Fatal("reused a figure URL outside its asset, object or response", err)
			}
			seen[image.URL] = true
		}
		if view.Article.Images[3].URL != "" {
			t.Fatal("unavailable occurrence reused a URL")
		}
	}
}

func TestPaidCatalogOriginalFigureSurvivesFirstPublication(t *testing.T) {
	cases := []struct {
		name   string
		status int
		change func(*paidMediaCatalog, *paidMediaGrant, *Principal, *paidCatalogImageReference)
	}{
		{"original-same-source", http.StatusOK, nil},
		{"old-article-figure", http.StatusNotFound, func(_ *paidMediaCatalog, _ *paidMediaGrant, _ *Principal, r *paidCatalogImageReference) {
			r.Projection = "article"
		}},
		{"source-changed", http.StatusNotFound, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *Principal, _ *paidCatalogImageReference) {
			c.identity.CurrentSourceRevisionID = stringPointer("99999999-9999-4999-8999-999999999999")
		}},
		{"source-changed-after-identity-read", http.StatusNotFound, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *Principal, _ *paidCatalogImageReference) {
			c.view.Article.SourceRevisionID = stringPointer("99999999-9999-4999-8999-999999999999")
		}},
		{"historical-selected-source", http.StatusNotFound, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *Principal, r *paidCatalogImageReference) {
			r.SelectedSourceRevisionID = "99999999-9999-4999-8999-999999999999"
			c.source.SourceRevisionID = stringPointer(r.SelectedSourceRevisionID)
		}},
		{"canonical-replaced", http.StatusNotFound, func(_ *paidMediaCatalog, _ *paidMediaGrant, _ *Principal, r *paidCatalogImageReference) {
			r.AnchorCanonicalRevisionID = stringPointer("99999999-9999-4999-8999-999999999999")
		}},
		{"wrong-account", http.StatusNotFound, func(_ *paidMediaCatalog, _ *paidMediaGrant, p *Principal, _ *paidCatalogImageReference) {
			p.CustomerAccountID = "99999999-9999-4999-8999-999999999999"
		}},
		{"source-asset-removed", http.StatusNotFound, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *Principal, _ *paidCatalogImageReference) {
			c.source.Images = nil
		}},
		{"withdrawn", http.StatusGone, func(c *paidMediaCatalog, _ *paidMediaGrant, _ *Principal, _ *paidCatalogImageReference) {
			c.view.Withdrawn = true
		}},
		{"revoked-after-first-grant-check", http.StatusForbidden, func(_ *paidMediaCatalog, g *paidMediaGrant, _ *Principal, _ *paidCatalogImageReference) {
			g.errorAfterFirst = ErrVehicleGrantRevoked
		}},
	}
	for _, item := range cases {
		t.Run(item.name, func(t *testing.T) {
			s, catalog, grants, objects, principal, reference := paidMediaFixture()
			reference.AnchorCanonicalRevisionID = nil
			reference.Projection = "source"
			if item.change != nil {
				item.change(catalog, grants, &principal, &reference)
			}
			token, err := sealPaidCatalogImageReference(reference, s.catalogImageKey, time.Now())
			if err != nil {
				t.Fatal(err)
			}
			response := paidMediaRequest(s, principal, token)
			if response.Code != item.status {
				t.Fatalf("status=%d, want %d", response.Code, item.status)
			}
			if item.status == http.StatusOK {
				if !bytes.Equal(response.Body.Bytes(), objects.body) || grants.calls.Load() != 2 || objects.calls.Load() != 1 {
					t.Fatal("reply lost the retained bytes or required checks")
				}
			} else if objects.calls.Load() != 0 {
				t.Fatal("denial reached storage")
			}
		})
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
		{"selected-source", 404, func(_ *paidMediaCatalog, _ *paidMediaGrant, _ *paidMediaReader, _ *Principal, r *paidCatalogImageReference) {
			r.SelectedSourceRevisionID = "99999999-9999-4999-8999-999999999999"
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
	ref.AnchorSourceRevisionID = "99999999-9999-4999-8999-999999999999"
	c.identity.CurrentSourceRevisionID = &ref.AnchorSourceRevisionID
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

func TestPaidCatalogHistoricalImageRejectsChangedCurrentSource(t *testing.T) {
	s, c, _, reader, p, ref := paidMediaFixture()
	ref.Projection = "source"
	ref.AnchorCanonicalRevisionID = nil
	c.view.Article.CanonicalRevisionID = nil
	// The source changed between reading identity and reading the current view.
	c.view.Article.SourceRevisionID = stringPointer("99999999-9999-4999-8999-999999999999")
	token, err := sealPaidCatalogImageReference(ref, s.catalogImageKey, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if response := paidMediaRequest(s, p, token); response.Code != http.StatusNotFound || reader.calls.Load() != 0 {
		t.Fatalf("stale historical image status=%d, object reads=%d", response.Code, reader.calls.Load())
	}
}

func TestPaidCatalogSourceProjectsPinnedHTMLJSONWithoutMutation(t *testing.T) {
	const preference = "workshop-source-document"
	for _, tc := range []struct {
		name, accept, prefer string
		documentOnly         bool
	}{
		{name: "ordinary JSON", accept: "application/json"},
		{name: "document-only JSON", accept: "application/json", prefer: preference, documentOnly: true},
		{name: "inexact preference", accept: "application/json", prefer: preference + ", return=representation"},
		{name: "ordinary HTML", accept: "text/html"},
		{name: "HTML ignores preference", accept: "text/html", prefer: preference},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, c, _, _, p, ref := paidMediaFixture()
			c.view.Article.SourceRevisionID = c.identity.CurrentSourceRevisionID
			c.source.SnapshotID = "source-snapshot"
			c.source.Version = "provider-revision"
			c.source.ContentSHA256 = strings.Repeat("c", 64)
			c.source.ViewRevision = stringPointer("source-view")
			original := c.source.Images[0].URL
			path := catalogPinnedSourceURL(ref.ConfigurationID, ref.CanonicalArticleID, c.source.SourceRevisionID)
			read := func(accept, prefer string) *httptest.ResponseRecorder {
				t.Helper()
				request := httptest.NewRequest(http.MethodGet, path, nil)
				request.SetPathValue("vehicle_id", ref.ConfigurationID)
				request.SetPathValue("article_id", ref.CanonicalArticleID)
				request.Header.Set("Accept", accept)
				if prefer != "" {
					request.Header.Set("Prefer", prefer)
				}
				w := httptest.NewRecorder()
				s.serveCatalogSource(w, request, p)
				if w.Code != http.StatusOK || w.Header().Get("Cache-Control") != "private, no-store" {
					t.Fatalf("status=%d cache=%q", w.Code, w.Header().Get("Cache-Control"))
				}
				return w
			}
			w := read(tc.accept, tc.prefer)
			var applied string
			if tc.documentOnly {
				applied = preference
			}
			if got := w.Header().Get("Preference-Applied"); got != applied {
				t.Fatalf("Preference-Applied=%q, want %q", got, applied)
			}
			if c.source.Images[0].URL != original {
				t.Fatal("stored source images mutated")
			}
			var token string
			if tc.accept == "application/json" {
				var body CatalogSourceContentResponse
				if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
					t.Fatal(err)
				}
				wantSource := CatalogSourceReview{Available: true, SnapshotID: c.source.SnapshotID, Version: c.source.Version,
					ContentSHA256: c.source.ContentSHA256, Format: "html", URL: path}
				if body.Version != "v1" || body.Source != wantSource || !samePaidCatalogID(body.ViewRevision, c.source.ViewRevision) ||
					body.Document == nil || len(body.Document.Blocks) != 1 || len(body.Images) != 1 {
					t.Fatal("source JSON did not retain the pinned v1 document and metadata")
				}
				token = strings.TrimPrefix(body.Images[0].URL, "/v1/catalog/images/")
				if tc.documentOnly {
					var fields map[string]json.RawMessage
					if err := json.Unmarshal(w.Body.Bytes(), &fields); err != nil || string(fields["content"]) != `""` {
						t.Fatal("document-only JSON needs an explicit empty content string")
					}
					full := read("application/json", "")
					var recovered CatalogSourceContentResponse
					if err := json.Unmarshal(full.Body.Bytes(), &recovered); err != nil || len(recovered.Images) != 1 ||
						!strings.Contains(recovered.Content, "<img") {
						t.Fatal("ordinary JSON did not include rendered HTML")
					}
					saved := full.Body.Len() - w.Body.Len()
					if saved < len(recovered.Content) {
						t.Fatalf("document-only response saved %d bytes, smaller than omitted HTML", saved)
					}
					t.Logf("document-only JSON saved %d of %d response bytes", saved, full.Body.Len())
					// New capabilities are randomized for each response.
					body.Images[0].URL = ""
					recovered.Content, recovered.Images[0].URL = "", ""
					if !reflect.DeepEqual(body, recovered) {
						t.Fatal("document-only JSON changed fields other than the rendered content")
					}
				} else if !strings.Contains(body.Content, `<img src="`+body.Images[0].URL+`"`) {
					t.Fatal("ordinary JSON did not include the approved image in rendered HTML")
				}
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
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Prefer", "workshop-source-document")
	w := httptest.NewRecorder()
	s.serveCatalogSource(w, request, p)
	if w.Code != 403 || w.Header().Get("Preference-Applied") != "" || c.identityCalls.Load() != 0 || c.viewCalls.Load() != 0 || c.sourceCalls.Load() != 0 {
		t.Fatalf("denial=%d identity/view/source=%d/%d/%d", w.Code, c.identityCalls.Load(), c.viewCalls.Load(), c.sourceCalls.Load())
	}
	s, c, _, _, p, ref = paidMediaFixture()
	c.source.Document = nil
	c.source.Original = json.RawMessage(`{"_embedded":{"data":{"article":{"content":"<p>Body</p><img src=\"https://private-provider/image.png\"><img src=\"/v1/catalog/images/legacy\">"}}}}`)
	for _, accept := range []string{"text/html", "application/json"} {
		t.Run(accept, func(t *testing.T) {
			request := httptest.NewRequest(http.MethodGet, "/source?source_revision_id="+ref.SelectedSourceRevisionID, nil)
			request.SetPathValue("vehicle_id", ref.ConfigurationID)
			request.SetPathValue("article_id", ref.CanonicalArticleID)
			request.Header.Set("Accept", accept)
			request.Header.Set("Prefer", "workshop-source-document")
			w := httptest.NewRecorder()
			s.serveCatalogSource(w, request, p)
			content := w.Body.String()
			if accept == "application/json" {
				var body CatalogSourceContentResponse
				if json.Unmarshal(w.Body.Bytes(), &body) != nil || body.Document != nil {
					t.Fatal("unexpected structured document for raw source fallback")
				}
				content = body.Content
			}
			if w.Code != http.StatusOK || w.Header().Get("Preference-Applied") != "" || !strings.Contains(content, "<p>Body</p>") ||
				strings.Contains(content, "private-provider") || strings.Contains(content, "images/legacy") || strings.Contains(content, "<img") {
				t.Fatal("raw source fallback was lost or authorized an untrusted image", w.Code)
			}
		})
	}
}

func TestPaidCatalogSourcePreferenceRequiresNonemptyPinnedDocument(t *testing.T) {
	for _, tc := range []struct {
		name       string
		revision   string
		status     int
		sourceRead int32
	}{
		{name: "empty structured document", status: http.StatusOK, sourceRead: 1},
		{name: "unbound source revision", revision: "99999999-9999-4999-8999-999999999999", status: http.StatusNotFound, sourceRead: 1},
		{name: "malformed source revision", revision: "invalid-revision", status: http.StatusNotFound},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, c, _, _, p, ref := paidMediaFixture()
			c.source.Document.Blocks = nil
			revision := tc.revision
			if revision == "" {
				revision = ref.SelectedSourceRevisionID
			}
			request := httptest.NewRequest(http.MethodGet, catalogPinnedSourceURL(ref.ConfigurationID, ref.CanonicalArticleID, &revision), nil)
			request.SetPathValue("vehicle_id", ref.ConfigurationID)
			request.SetPathValue("article_id", ref.CanonicalArticleID)
			request.Header.Set("Accept", "application/json")
			request.Header.Set("Prefer", "workshop-source-document")
			w := httptest.NewRecorder()
			s.serveCatalogSource(w, request, p)
			if w.Code != tc.status || w.Header().Get("Preference-Applied") != "" || c.sourceCalls.Load() != tc.sourceRead {
				t.Fatalf("status=%d preference=%q source reads=%d", w.Code, w.Header().Get("Preference-Applied"), c.sourceCalls.Load())
			}
			if tc.sourceRead > 0 && c.lastSource != revision {
				t.Fatal("preference changed selected source revision")
			}
		})
	}
}

func TestPaidCatalogMediaRejectsMalformedBeforeProtectedReadsAndLogs(t *testing.T) {
	for _, kind := range []string{"v1", "expired", "forged", "weak-key", "missing-capability"} {
		t.Run(kind, func(t *testing.T) {
			s, c, _, r, p, ref := paidMediaFixture()
			token, err := sealPaidCatalogImageReference(ref, s.catalogImageKey, time.Now())
			if err != nil {
				t.Fatal(err)
			}
			want := 404
			switch kind {
			case "v1":
				token, err = sealCatalogImageReference(ref.ObjectKey, s.catalogImageKey)
			case "expired":
				ref.IssuedAt = time.Now().Unix() - 301
				ref.ExpiresAt = ref.IssuedAt + 300
				raw, _ := json.Marshal(ref)
				token = paidMediaSealRaw(t, raw, s.catalogImageKey)
			case "forged":
				token = "v2.forged-private-token"
			case "weak-key":
				s.catalogImageKey = nil
				want = 503
			case "missing-capability":
				s.catalog = &paidScopeCatalog{configuration: c.configuration}
				want = 503
			}
			var logs bytes.Buffer
			old := log.Writer()
			log.SetOutput(&logs)
			defer log.SetOutput(old)
			w := paidMediaRequest(s, p, token)
			if w.Code != want || r.calls.Load() != 0 {
				t.Fatalf("status=%d reads=%d", w.Code, r.calls.Load())
			}
			if kind != "missing-capability" && (c.identityCalls.Load() != 0 || c.viewCalls.Load() != 0 || c.sourceCalls.Load() != 0) {
				t.Fatal("invalid token accessed protected catalog")
			}
			if strings.Contains(logs.String(), token) || strings.Contains(logs.String(), ref.ObjectKey) || strings.Contains(logs.String(), "private-provider") {
				t.Fatal("private media context logged")
			}
		})
	}
}

func TestPaidCatalogMediaStoredByteValidationAndReaderFailures(t *testing.T) {
	for _, tc := range []struct {
		name   string
		body   []byte
		media  string
		err    error
		status int
	}{
		{"svg", []byte(`<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>`), "image/svg+xml", nil, 200},
		{"wrong-type", []byte(`<html>secret</html>`), "image/png", nil, 404},
		{"invalid-svg", []byte(`<!DOCTYPE svg><svg/>`), "image/svg+xml", nil, 404},
		{"empty", nil, "image/png", nil, 404},
		{"oversize", make([]byte, catalogImageMaxBytes+1), "image/png", nil, 404},
		{"missing", nil, "", ErrCatalogNotFound, 404},
		{"storage-outage", nil, "", errors.New("private storage details"), 503},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s, _, _, r, p, ref := paidMediaFixture()
			r.body, r.contentType, r.err = tc.body, tc.media, tc.err
			token, err := sealPaidCatalogImageReference(ref, s.catalogImageKey, time.Now())
			if err != nil {
				t.Fatal(err)
			}
			w := paidMediaRequest(s, p, token)
			if w.Code != tc.status || r.calls.Load() != 1 {
				t.Fatal(w.Code, r.calls.Load(), w.Body.String())
			}
			if tc.status != 200 && strings.Contains(w.Body.String(), "private storage") {
				t.Fatal("storage error leaked")
			}
			if tc.status == 200 && !strings.Contains(w.Header().Get("Content-Security-Policy"), "sandbox") {
				t.Fatal("SVG direct navigation lacks sandbox")
			}
		})
	}
}

func TestPaidCatalogMediaSourceFallbackAndStableViewRevision(t *testing.T) {
	s, c, _, _, p, _ := paidMediaFixture()
	c.view.Article.CanonicalRevisionID = nil
	c.view.Article.ContentOrigin = stringPointer("source")
	c.view.Article.Document = c.source.Document
	before := lifecycleArticle(c.view.Article)
	view := CatalogArticleView{Article: before}
	if err := s.rewritePaidCatalogArticleImages(context.Background(), p, c.configuration, c.identity, &view); err != nil {
		t.Fatal(err)
	}
	after := lifecycleArticle(view.Article)
	if !samePaidCatalogID(before.ViewRevision, after.ViewRevision) {
		t.Fatal("generated references changed stable view revision")
	}
	token := strings.TrimPrefix(view.Article.Images[0].URL, "/v1/catalog/images/")
	ref, err := openPaidCatalogImageReference(token, s.catalogImageKey, time.Now())
	if err != nil || ref.AnchorCanonicalRevisionID != nil {
		t.Fatal("source fallback anchor", ref, err)
	}
	if w := paidMediaRequest(s, p, token); w.Code != 200 {
		t.Fatal(w.Code, w.Body.String())
	}
}

func TestPaidCatalogSourceDoesNotExposeUnreviewedRawJSON(t *testing.T) {
	s, c, _, _, p, ref := paidMediaFixture()
	c.source.Document = nil
	c.source.Original = json.RawMessage(`{"private_provider_ref":"private-provider-article","image":"https://private-provider/image","storage_key":"procedure-images/secret"}`)
	request := httptest.NewRequest("GET", "/source?source_revision_id="+ref.SelectedSourceRevisionID, nil)
	request.SetPathValue("vehicle_id", ref.ConfigurationID)
	request.SetPathValue("article_id", ref.CanonicalArticleID)
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Prefer", "workshop-source-document")
	w := httptest.NewRecorder()
	s.serveCatalogSource(w, request, p)
	if w.Code != 503 || w.Header().Get("Preference-Applied") != "" || strings.Contains(w.Body.String(), "private-provider") || strings.Contains(w.Body.String(), "procedure-images/") {
		t.Fatal("paid source exposes unreviewed raw JSON; status", w.Code)
	}
}

func TestPaidCatalogMediaCodecRejectsNoncanonicalEncoding(t *testing.T) {
	now := time.Now()
	key := deriveCatalogImageReferenceKey(testCatalogImageSecret)
	token, err := sealPaidCatalogImageReference(paidMediaTestReference(now), key, now)
	if err != nil {
		t.Fatal(err)
	}
	noncanonical := token[:10] + "\n" + token[10:]
	if _, err := openPaidCatalogImageReference(noncanonical, key, now); err == nil {
		t.Fatal("noncanonical base64 encoding accepted")
	}
}

func TestPaidCatalogMediaNormalizesPublicAssetIdentifiers(t *testing.T) {
	s, c, _, _, p, _ := paidMediaFixture()
	privateID := "https://private-provider.example/asset?id=internal"
	c.source.Images[0].ID = privateID
	c.source.Images[0].ImageID = ""
	c.source.Images[0].AssetID = ""
	c.view.Article.Images[0] = c.source.Images[0]
	c.view.Article.Steps = nil
	view := c.view
	if err := s.rewritePaidCatalogArticleImages(context.Background(), p, c.configuration, c.identity, &view); err != nil {
		t.Fatal(err)
	}
	raw, err := json.Marshal(view.Article)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), "private-provider") || view.Article.Images[0].ID != publicCatalogAssetID(privateID) {
		t.Fatal("private locator leaked as public image identity")
	}
	token := strings.TrimPrefix(view.Article.Images[0].URL, "/v1/catalog/images/")
	if w := paidMediaRequest(s, p, token); w.Code != 200 {
		t.Fatal("normalized asset proof failed", w.Code)
	}
}
