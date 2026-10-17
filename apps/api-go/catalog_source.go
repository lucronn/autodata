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
	var envelope map[string]any
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
	var envelope map[string]any
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

func nestedCatalogSourceString(value map[string]any, path ...string) string {
	var current any = value
	for _, key := range path {
		object, ok := current.(map[string]any)
		if !ok {
			return ""
		}
		current = object[key]
	}
	text, _ := current.(string)
	return text
}

func redactCatalogSourceJSON(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		result := make(map[string]any, len(typed))
		for key, child := range typed {
			lower := strings.ToLower(key)
			if lower == "_links" || lower == "links" || lower == "href" || lower == "source_uri" || lower == "object_key" {
				continue
			}
			result[key] = redactCatalogSourceJSON(child)
		}
		return result
	case []any:
		result := make([]any, len(typed))
		for index, child := range typed {
			result[index] = redactCatalogSourceJSON(child)
		}
		return result
	default:
		return value
	}
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
		}
		attributes = append(attributes, attribute)
	}
	node.Attr = attributes
}

func catalogSourceAssetURL(sourceURI, raw string, imageKey []byte) (string, bool) {
	// Source snapshots currently do not retain an authoritative mapping from
	// each source URL to its localized object key. Never mint a token from the
	// source URL; omit it until that mapping is available.
	_, _, _ = sourceURI, raw, imageKey
	return "", false
}

func writeCatalogSourceHTML(response http.ResponseWriter, review CatalogSourceReview, content, evidenceID, sourceLocator string) {
	response.Header().Set("Content-Type", "text/html; charset=utf-8")
	response.Header().Set("Content-Security-Policy", "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; font-src 'none'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'")
	response.Header().Set("X-Content-Type-Options", "nosniff")
	response.Header().Set("Cache-Control", "private, max-age=60")
	metadata := []string{"Stored source copy", "Snapshot " + review.SnapshotID, "Version " + review.Version}
	if evidenceID != "" {
		metadata = append(metadata, "Evidence "+evidenceID)
	}
	if sourceLocator != "" {
		metadata = append(metadata, "Locator "+sourceLocator)
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
