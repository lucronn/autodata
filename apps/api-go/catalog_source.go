package main

import (
	"bytes"
	"encoding/json"
	stdhtml "html"
	"net/http"
	"net/url"
	"regexp"
	"strings"

	"golang.org/x/net/html"
)

type CatalogSourceContentResponse struct {
	Version string              `json:"version"`
	Source  CatalogSourceReview `json:"source"`
	Content string              `json:"content"`
}

var unsafeCatalogSourceStyle = regexp.MustCompile(`(?i)(?:url\s*\([^)]*\)|expression\s*\(|behavior\s*:|-moz-binding\s*:)`)
var catalogSourceExternalURL = regexp.MustCompile(`(?i)(?:https?://|//)[^\s"'<>]+`)
var catalogSourceSignedReference = regexp.MustCompile(`(?i)(?:^|[?&])(?:x-amz-[^=]+|awsaccesskeyid|signature|expires|sig|token)=`)
var catalogSourceBearerSecret = regexp.MustCompile(`(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}`)
var catalogSourceNamedSecret = regexp.MustCompile(`(?i)\b(?:authorization|access[_ -]?token|refresh[_ -]?token|id[_ -]?token|api[_ -]?key|secret|password|credential|token)\s*[:=]\s*["']?[A-Za-z0-9._~+/=-]{6,}`)

func (s *Server) serveCatalogSource(response http.ResponseWriter, request *http.Request, principal Principal) {
	vehicleID := request.PathValue("vehicle_id")
	articleID := request.PathValue("article_id")
	stored, err := s.catalog.ArticleSource(request.Context(), principal, vehicleID, articleID)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	format, content, err := renderStoredCatalogSource(stored.Original, stored.SourceURI, s.catalogImageKey)
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	review := CatalogSourceReview{
		Available:     true,
		SnapshotID:    stored.SnapshotID,
		Version:       stored.Version,
		ContentSHA256: stored.ContentSHA256,
		Format:        format,
		URL:           catalogSourceURL(vehicleID, articleID),
	}
	if acceptsJSON(request) {
		writeJSON(response, http.StatusOK, CatalogSourceContentResponse{Version: "v1", Source: review, Content: content})
		return
	}
	writeCatalogSourceHTML(response, review, content, request.URL.Query().Get("evidence_id"), request.URL.Query().Get("source_locator"))
}

func sourceReviewForArticle(article CatalogArticle, vehicleID, articleID string) *CatalogSourceReview {
	if !article.sourceAvailable {
		return nil
	}
	format := article.sourceFormat
	if format == "" {
		format = "html"
	}
	return &CatalogSourceReview{
		Available:     true,
		SnapshotID:    article.sourceSnapshotID,
		Version:       article.sourceVersion,
		ContentSHA256: article.sourceContentSHA256,
		Format:        format,
		URL:           catalogSourceURL(vehicleID, articleID),
	}
}

func catalogSourceFormat(raw json.RawMessage) string {
	var envelope any
	if err := json.Unmarshal(raw, &envelope); err == nil && strings.TrimSpace(nestedCatalogSourceString(envelope, "_embedded", "data", "article", "content")) != "" {
		return "html"
	}
	if len(bytes.TrimSpace(raw)) > 2 {
		return "json"
	}
	return ""
}

func acceptsJSON(request *http.Request) bool {
	accept := strings.ToLower(request.Header.Get("Accept"))
	return strings.Contains(accept, "application/json") && !strings.Contains(accept, "text/html")
}

func catalogSourceURL(vehicleID, articleID string) string {
	return "/v1/catalog/vehicles/" + url.PathEscape(vehicleID) + "/articles/" + url.PathEscape(articleID) + "/source"
}

func renderStoredCatalogSource(raw json.RawMessage, sourceURI string, imageKey []byte) (string, string, error) {
	var envelope any
	if err := json.Unmarshal(raw, &envelope); err != nil {
		return "", "", err
	}
	if content := nestedCatalogSourceString(envelope, "_embedded", "data", "article", "content"); strings.TrimSpace(content) != "" {
		rendered, err := sanitizeCatalogSourceHTML(content, sourceURI, imageKey)
		if err != nil {
			return "", "", err
		}
		return "html", rendered, nil
	}
	pretty, err := json.MarshalIndent(redactCatalogSourceJSON(envelope), "", "  ")
	if err != nil {
		return "", "", err
	}
	return "json", string(pretty), nil
}

func nestedCatalogSourceString(value any, path ...string) string {
	text, _ := nestedCatalogSourceValue(value, path...).(string)
	return text
}

func nestedCatalogSourceValue(value any, path ...string) any {
	var current any = value
	for _, key := range path {
		object, ok := current.(map[string]any)
		if !ok {
			return nil
		}
		var found bool
		current, found = object[key]
		if !found {
			return nil
		}
	}
	return current
}

func redactCatalogSourceJSON(value any) any {
	projected, ok := projectCatalogSourceJSON(value)
	if !ok {
		return nil
	}
	return projected
}

func projectCatalogSourceJSON(value any) (any, bool) {
	switch typed := value.(type) {
	case map[string]any:
		result := make(map[string]any, len(typed))
		for key, child := range typed {
			if unsafeCatalogSourceJSONKey(key) {
				continue
			}
			projected, ok := projectCatalogSourceJSON(child)
			if ok {
				result[key] = projected
			}
		}
		return result, true
	case []any:
		result := make([]any, 0, len(typed))
		for _, child := range typed {
			projected, ok := projectCatalogSourceJSON(child)
			if ok {
				result = append(result, projected)
			}
		}
		return result, true
	case string:
		redacted := redactCatalogSourceText(typed)
		if strings.TrimSpace(redacted) == "" && strings.TrimSpace(typed) != "" {
			return nil, false
		}
		return redacted, true
	default:
		return value, true
	}
}

func unsafeCatalogSourceJSONKey(key string) bool {
	normalized := strings.ToLower(strings.TrimSpace(key))
	normalized = strings.NewReplacer("-", "_", " ", "_").Replace(normalized)
	if normalized == "_links" || normalized == "links" || normalized == "link" || normalized == "href" || normalized == "src" || normalized == "srcset" || normalized == "uri" || normalized == "url" || normalized == "request" || normalized == "response" || normalized == "navigation" || normalized == "object_key" || normalized == "source_uri" || normalized == "source_url" || normalized == "source_locator" || normalized == "provider_path" {
		return true
	}
	for _, fragment := range []string{"authorization", "authentication", "credential", "password", "secret", "cookie", "header", "signed", "signature", "access_token", "refresh_token", "id_token", "apikey", "session_token", "private_key", "expires", "expiry"} {
		if strings.Contains(normalized, fragment) {
			return true
		}
	}
	compact := strings.ReplaceAll(normalized, "_", "")
	if strings.Contains(compact, "token") || strings.Contains(compact, "apikey") {
		return true
	}
	return strings.Contains(normalized, "redirect") || strings.Contains(normalized, "callback") || strings.Contains(normalized, "provider_url") || strings.Contains(normalized, "provider_uri") || strings.HasSuffix(normalized, "_url") || strings.HasSuffix(normalized, "_uri") || strings.HasSuffix(normalized, "_href") || strings.HasSuffix(normalized, "_link") || normalized == "next" || normalized == "previous" || normalized == "prev" || normalized == "self" || normalized == "canonical"
}

func redactCatalogSourceText(value string) string {
	if catalogSourceSignedReference.MatchString(value) || catalogSourceBearerSecret.MatchString(value) || catalogSourceNamedSecret.MatchString(value) {
		return "[redacted]"
	}
	return catalogSourceExternalURL.ReplaceAllString(value, "[redacted-url]")
}

func sanitizeCatalogSourceHTML(raw, sourceURI string, imageKey []byte) (string, error) {
	document, err := html.Parse(strings.NewReader(raw))
	if err != nil {
		return "", err
	}
	sanitizeCatalogSourceNode(document, sourceURI, imageKey)
	var output bytes.Buffer
	if err := html.Render(&output, document); err != nil {
		return "", err
	}
	return output.String(), nil
}

func sanitizeCatalogSourceNode(node *html.Node, sourceURI string, imageKey []byte) {
	for child := node.FirstChild; child != nil; {
		next := child.NextSibling
		if child.Type == html.TextNode {
			child.Data = redactCatalogSourceText(child.Data)
		}
		if child.Type == html.ElementNode {
			tag := strings.ToLower(child.Data)
			if blockedCatalogSourceTag(tag) {
				node.RemoveChild(child)
				child = next
				continue
			}
			sanitizeCatalogSourceAttributes(child, sourceURI, imageKey)
			if tag == "img" && !catalogSourceImageHasSource(child) {
				node.RemoveChild(child)
				child = next
				continue
			}
		}
		sanitizeCatalogSourceNode(child, sourceURI, imageKey)
		child = next
	}
}

func catalogSourceImageHasSource(node *html.Node) bool {
	for _, attribute := range node.Attr {
		if strings.EqualFold(attribute.Key, "src") && strings.TrimSpace(attribute.Val) != "" {
			return true
		}
	}
	return false
}

func blockedCatalogSourceTag(tag string) bool {
	switch tag {
	case "base", "button", "embed", "form", "iframe", "input", "link", "meta", "object", "script", "select", "textarea":
		return true
	default:
		return false
	}
}

func sanitizeCatalogSourceAttributes(node *html.Node, sourceURI string, imageKey []byte) {
	attributes := make([]html.Attribute, 0, len(node.Attr))
	for _, attribute := range node.Attr {
		key := strings.ToLower(attribute.Key)
		if strings.HasPrefix(key, "on") || key == "srcdoc" || key == "srcset" {
			continue
		}
		switch key {
		case "src":
			if node.Data == "img" {
				if resolved, ok := catalogSourceAssetURL(sourceURI, attribute.Val, imageKey); ok {
					attribute.Val = resolved
				} else {
					continue
				}
			} else {
				continue
			}
		case "href":
			// Source navigation stays as visible text. Rewriting arbitrary
			// article links as image URLs would create broken links and could
			// make the review page navigate outside the stored snapshot.
			continue
		case "style":
			if unsafeCatalogSourceStyle.MatchString(attribute.Val) {
				continue
			}
		default:
			attribute.Val = redactCatalogSourceText(attribute.Val)
		}
		attributes = append(attributes, attribute)
	}
	node.Attr = attributes
}

func catalogSourceAssetURL(_ string, raw string, imageKey []byte) (string, bool) {
	raw = strings.TrimSpace(raw)
	// Source review may only retain a reference that the localized media worker
	// already minted for an AutoData storage object. Never turn a provider URL
	// or source-relative path into a token: the media route resolves storage
	// tokens through object storage and cannot serve provider-URL tokens.
	parsed, err := url.Parse(raw)
	if err != nil || parsed.IsAbs() || parsed.Host != "" || parsed.RawQuery != "" || parsed.Fragment != "" || !strings.HasPrefix(parsed.Path, "/v1/catalog/images/") {
		return "", false
	}
	token := strings.TrimPrefix(parsed.Path, "/v1/catalog/images/")
	if token == "" || strings.Contains(token, "/") {
		return "", false
	}
	if _, err := openCatalogImageStorageKey(token, imageKey); err != nil {
		return "", false
	}
	return "/v1/catalog/images/" + token, true
}

func writeCatalogSourceHTML(response http.ResponseWriter, review CatalogSourceReview, content, evidenceID, sourceLocator string) {
	response.Header().Set("Content-Type", "text/html; charset=utf-8")
	response.Header().Set("Content-Security-Policy", "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; font-src 'none'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'")
	response.Header().Set("X-Content-Type-Options", "nosniff")
	response.Header().Set("Cache-Control", "private, max-age=60")
	metadata := []string{"Stored source copy", "Snapshot " + redactCatalogSourceText(review.SnapshotID), "Version " + redactCatalogSourceText(review.Version)}
	if evidenceID != "" {
		metadata = append(metadata, "Evidence "+redactCatalogSourceText(evidenceID))
	}
	if sourceLocator != "" {
		metadata = append(metadata, "Locator "+redactCatalogSourceText(sourceLocator))
	}
	body := content
	if review.Format == "json" {
		body = "<pre>" + stdhtml.EscapeString(content) + "</pre>"
	}
	// The source document has already been parsed and sanitized. Metadata is
	// escaped separately because it is assembled from request/database values.
	_, _ = response.Write([]byte("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Stored source copy</title><style>body{margin:0;background:#f5f6f2;color:#20262d;font:16px/1.6 system-ui,sans-serif}header{position:sticky;top:0;padding:14px 22px;border-bottom:1px solid #cfd4cd;background:#f5f6f2}header strong{display:block;color:#234bd8;font-size:14px}header span{display:block;color:#65706a;font-size:12px}main{max-width:920px;margin:24px auto;padding:0 22px}.source-document{background:#fff;padding:24px;box-shadow:0 1px 8px #1d2b3414}.source-document img{max-width:100%;height:auto}</style></head><body><header><strong>"))
	_, _ = response.Write([]byte(stdhtml.EscapeString(metadata[0])))
	_, _ = response.Write([]byte("</strong><span>" + stdhtml.EscapeString(strings.Join(metadata[1:], " · ")) + "</span></header><main><article class=\"source-document\">"))
	_, _ = response.Write([]byte(body))
	_, _ = response.Write([]byte("</article></main></body></html>"))
}
