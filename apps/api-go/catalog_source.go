package main

import (
	"bytes"
	"context"
	"encoding/json"
	stdhtml "html"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"

	"golang.org/x/net/html"
)

type CatalogSourceContentResponse struct {
	Version      string              `json:"version"`
	Source       CatalogSourceReview `json:"source"`
	Content      string              `json:"content"`
	Document     *CatalogDocument    `json:"document,omitempty"`
	Images       []CatalogImage      `json:"images,omitempty"`
	ViewRevision *string             `json:"view_revision,omitempty"`
}

var unsafeCatalogSourceStyle = regexp.MustCompile(`(?i)(?:url\s*\([^)]*\)|expression\s*\(|behavior\s*:|-moz-binding\s*:)`)

func (s *Server) serveCatalogSource(response http.ResponseWriter, request *http.Request, principal Principal) {
	if s.paidCatalogEnabled() {
		s.servePaidCatalogSource(response, request, principal)
		return
	}
	vehicleID := request.PathValue("vehicle_id")
	articleID := request.PathValue("article_id")
	response.Header().Set("Cache-Control", "private, no-store")
	stored, err := s.catalog.ArticleSourceRevision(request.Context(), principal, vehicleID, articleID, request.URL.Query().Get("source_revision_id"))
	if err != nil {
		s.writeCatalogError(response, request, err)
		return
	}
	var format, content string
	if stored.Document != nil {
		article := CatalogArticle{Images: stored.Images}
		rewriteCatalogImageURLs(&article, s.catalogImageKey)
		stored.Images = article.Images
		format = "html"
		content = renderCatalogOrderedSource(stored.Document, stored.Images)
	} else {
		format, content, err = renderStoredCatalogSource(stored.Original, stored.SourceURI, s.catalogImageKey)
	}
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
		URL:           catalogPinnedSourceURL(vehicleID, articleID, stored.SourceRevisionID),
	}
	if acceptsJSON(request) {
		writeJSON(response, http.StatusOK, CatalogSourceContentResponse{Version: "v1", Source: review, Content: content, Document: stored.Document, Images: stored.Images, ViewRevision: stored.ViewRevision})
		return
	}
	writeCatalogSourceHTML(response, review, content, request.URL.Query().Get("evidence_id"), request.URL.Query().Get("source_locator"))
}

// Paid source review loads current anchors separately from a pinned historical
// revision. A historical asset is never silently replaced by the newest source.
func (s *Server) servePaidCatalogSource(w http.ResponseWriter, r *http.Request, p Principal) {
	w.Header().Set("Cache-Control", "private, no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	r = r.WithContext(ctx)
	configuration, err := s.resolvePaidCatalogScope(ctx, p, r.PathValue("vehicle_id"), r.URL.Query().Get("region"))
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	articleID := r.PathValue("article_id")
	if !commerceUUID(articleID) {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	identity, err := s.paidMediaIdentity(ctx, configuration, articleID)
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	view, err := s.catalog.ArticleView(ctx, p, configuration.ID, articleID)
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	if view.Withdrawn {
		s.writePaidCatalogError(w, r, ErrCatalogWithdrawn)
		return
	}
	if !paidCatalogViewMatches(view, identity) {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	selected := r.URL.Query().Get("source_revision_id")
	if selected == "" {
		if view.Article.SourceRevisionID == nil {
			s.writePaidCatalogError(w, r, ErrVehicleGrantUnavailable)
			return
		}
		selected = *view.Article.SourceRevisionID
	}
	if !commerceUUID(selected) {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	stored, err := s.catalog.ArticleSourceRevision(ctx, p, configuration.ID, articleID, selected)
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	if stored.SourceRevisionID == nil || *stored.SourceRevisionID != selected {
		s.writePaidCatalogError(w, r, ErrCatalogNotFound)
		return
	}
	stored.Images = append([]CatalogImage{}, stored.Images...)
	stored.Document = publicCatalogDocument(stored.Document)
	now := time.Now()
	ref := paidCatalogProjectionReference(p, configuration, identity, view, selected, "source", now)
	s.rewritePaidCatalogImages(stored.Images, stored, ref, now)
	var format, content string
	if stored.Document != nil {
		format, content = "html", renderCatalogOrderedSource(stored.Document, stored.Images)
	} else {
		format, content, err = renderStoredCatalogSource(stored.Original, stored.SourceURI, s.catalogImageKey)
	}
	if err != nil {
		s.writePaidCatalogError(w, r, err)
		return
	}
	review := CatalogSourceReview{Available: true, SnapshotID: stored.SnapshotID, Version: stored.Version, ContentSHA256: stored.ContentSHA256, Format: format, URL: catalogPinnedSourceURL(configuration.ID, articleID, stored.SourceRevisionID)}
	if acceptsJSON(r) {
		writeJSON(w, http.StatusOK, CatalogSourceContentResponse{Version: "v1", Source: review, Content: content, Document: stored.Document, Images: stored.Images, ViewRevision: stored.ViewRevision})
		return
	}
	writeCatalogSourceHTML(w, review, content, r.URL.Query().Get("evidence_id"), r.URL.Query().Get("source_locator"))
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
		URL:           catalogPinnedSourceURL(vehicleID, articleID, article.SourceRevisionID),
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
				child.Type = html.TextNode
				child.Data = "Image unavailable"
				child.Attr = nil
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
	case "html", "head", "body", "div", "span", "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "em", "i", "u", "s", "sub", "sup", "pre", "code", "blockquote", "ul", "ol", "li", "dl", "dt", "dd", "table", "caption", "thead", "tbody", "tfoot", "tr", "th", "td", "img", "figure", "figcaption", "a":
		return false
	}
	return true
}

func sanitizeCatalogSourceAttributes(node *html.Node, sourceURI string, imageKey []byte) {
	attributes := make([]html.Attribute, 0, len(node.Attr))
	for _, attribute := range node.Attr {
		key := strings.ToLower(attribute.Key)
		switch key {
		case "src", "alt", "title", "colspan", "rowspan", "start", "value", "scope":
		default:
			continue
		}
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
	response.Header().Set("Cache-Control", "private, no-store")
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

func catalogPinnedSourceURL(vehicleID, articleID string, revision *string) string {
	result := catalogSourceURL(vehicleID, articleID)
	if revision != nil {
		result += "?source_revision_id=" + url.QueryEscape(*revision)
	}
	return result
}

// Ordered text is escaped at every leaf, including structured table cells.
func renderCatalogOrderedSource(document *CatalogDocument, images []CatalogImage) string {
	var output strings.Builder
	assets := map[string]CatalogImage{}
	for _, image := range images {
		assets[image.ID] = image
		assets[image.ImageID] = image
		if image.AssetID != "" {
			assets[image.AssetID] = image
		}
	}
	var cell func(any) string
	imageHTML := func(id, alt string) string {
		image, ok := assets[id]
		if !ok || image.URL == "" {
			return "<span>Image unavailable</span>"
		}
		return `<img src="` + stdhtml.EscapeString(image.URL) + `" alt="` + stdhtml.EscapeString(alt) + `">`
	}
	cell = func(value any) string {
		switch v := value.(type) {
		case string:
			return stdhtml.EscapeString(v)
		case map[string]any:
			result := ""
			if text, ok := v["text"].(string); ok {
				result = stdhtml.EscapeString(text)
			}
			if id, ok := v["asset_id"].(string); ok {
				result += imageHTML(id, "")
			}
			if nested, ok := v["images"].([]any); ok {
				for _, img := range nested {
					result += cell(img)
				}
			}
			if blocks, ok := v["blocks"].([]any); ok {
				for _, block := range blocks {
					result += cell(block)
				}
			}
			return result
		case []any:
			result := ""
			for _, item := range v {
				result += cell(item)
			}
			return result
		default:
			encoded, _ := json.Marshal(v)
			return stdhtml.EscapeString(string(encoded))
		}
	}
	for _, block := range document.Blocks {
		output.WriteString(`<section id="` + stdhtml.EscapeString(block.BlockID) + `">`)
		switch block.Type {
		case "step":
			number := block.Number
			if number < 1 {
				number = 1
			}
			output.WriteString(`<ol start="` + strconv.Itoa(number) + `"><li>` + stdhtml.EscapeString(block.Text) + `</li></ol>`)
		case "image":
			id := block.AssetID
			if id == "" {
				id = block.ImageID
			}
			output.WriteString(imageHTML(id, block.Alt))
		case "table":
			output.WriteString("<table>")
			if len(block.Columns) > 0 {
				output.WriteString("<thead><tr>")
				for _, column := range block.Columns {
					output.WriteString("<th>" + stdhtml.EscapeString(column) + "</th>")
				}
				output.WriteString("</tr></thead>")
			}
			output.WriteString("<tbody>")
			for _, row := range block.Rows {
				output.WriteString("<tr>")
				for _, value := range row {
					output.WriteString("<td>" + cell(value) + "</td>")
				}
				output.WriteString("</tr>")
			}
			output.WriteString("</tbody></table>")
		default:
			if block.Label != "" {
				output.WriteString("<strong>" + stdhtml.EscapeString(block.Label) + "</strong>")
			}
			output.WriteString("<p>" + stdhtml.EscapeString(block.Text) + "</p>")
			if len(block.Items) > 0 {
				output.WriteString("<ol>")
				for _, item := range block.Items {
					output.WriteString("<li>" + stdhtml.EscapeString(item) + "</li>")
				}
				output.WriteString("</ol>")
			}
		}
		for _, image := range block.Images {
			id := image.ID
			if id == "" {
				id = image.ImageID
			}
			if id == "" {
				id = image.AssetID
			}
			output.WriteString(imageHTML(id, image.Alt))
		}
		output.WriteString("</section>")
	}
	return output.String()
}
