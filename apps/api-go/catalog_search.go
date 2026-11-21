package main

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// Match the local media route accepted by Workshop's localImageURL. Search
// also reads stored images before a short-lived media URL has been minted.
var catalogSearchImageURL = regexp.MustCompile(`^/v1/catalog/images/v2\.[a-zA-Z0-9_-]+$`)

// Search only text the Workshop can display. IDs, locators, image URLs, and
// source metadata are deliberately excluded from content search.
func filterCatalogArticleSearch(items []CatalogArticle, query string) []CatalogArticle {
	words := strings.Fields(strings.ToLower(query))
	if len(words) == 0 {
		return items
	}
	matches := make([]CatalogArticle, 0)
	for _, article := range items {
		if catalogSearchWordsMatch(catalogArticleSearchText(article), words) {
			matches = append(matches, article)
		}
	}
	return matches
}

func catalogSearchWordsMatch(text string, words []string) bool {
	text = strings.ToLower(text)
	for _, word := range words {
		if !strings.Contains(text, word) {
			return false
		}
	}
	return true
}

func catalogArticleSearchText(article CatalogArticle) string {
	parts := []string{article.Title, article.Component, article.Kind}
	images := append([]CatalogImage(nil), article.Images...)
	for _, step := range article.Steps {
		if step.Images != nil {
			images = append(images, (*step.Images)...)
		}
	}
	if article.Document != nil && len(article.Document.Blocks) > 0 {
		indexedImages := indexCatalogSearchImages(images)
		for _, block := range article.Document.Blocks {
			parts = append(parts, catalogBlockSearchText(block, indexedImages, nil))
		}
	} else {
		// Workshop renders retained introductions alongside usable legacy steps.
		// A partly empty sequence falls back to the body, matching articlePresentation.
		usable := len(article.Steps) > 0
		for _, step := range article.Steps {
			visible := strings.TrimSpace(step.Action) != "" || strings.TrimSpace(step.Heading) != ""
			for _, instruction := range step.Instructions {
				visible = visible || strings.TrimSpace(instruction) != ""
			}
			usable = usable && visible
		}
		if usable {
			parts = append(parts, catalogLegacyIntroductionSearchText(article.Body, article.Steps))
			for _, step := range article.Steps {
				if step.Action != "" {
					parts = append(parts, step.Action)
				} else {
					parts = append(parts, step.Heading)
				}
				parts = append(parts, step.Instructions...)
				if step.Images != nil {
					for _, image := range *step.Images {
						if catalogSearchableImage(image) {
							parts = append(parts, image.Alt)
						}
					}
				}
				for _, id := range step.ImageIDs {
					for _, image := range images {
						if catalogSearchImageDisplayID(image) == id {
							if catalogSearchableImage(image) {
								parts = append(parts, image.Alt)
							}
							break
						}
					}
				}
			}
		} else {
			parts = append(parts, article.Body)
		}
	}
	return strings.Join(parts, " ")
}

// These are the replay decisions made by articlePresentation, not a second
// layout renderer. Only exact replays disappear from the introduction; an
// unrelated body or numbered list remains visible and therefore searchable.
var catalogLegacyStepBoundary = regexp.MustCompile(`\b([0-9]{1,2})\.\s*([A-Z])`)
var catalogLegacyCallout = regexp.MustCompile(`(?i)(^| )(NOTE|HINT|CAUTION|WARNING|IMPORTANT) *: *`)

func catalogLegacyIntroductionSearchText(body string, steps []CatalogStep) string {
	body = strings.Join(strings.Fields(body), " ")
	boundaries := catalogLegacyStepBoundary.FindAllStringSubmatchIndex(body, -1)
	if len(boundaries) > 0 {
		replay := len(boundaries) == len(steps)
		if replay {
			for index, boundary := range boundaries {
				ordinal, _ := strconv.Atoi(body[boundary[2]:boundary[3]])
				number := steps[index].Number
				if number <= 0 {
					number = index + 1
				} // Public orderedCatalogSteps normalizes missing ordinals.
				end := len(body)
				if index+1 < len(boundaries) {
					end = boundaries[index+1][0]
				}
				text := body[boundary[4]:end] // Keep the uppercase letter consumed by RE2.
				text = catalogLegacyCallout.ReplaceAllStringFunc(text, func(marker string) string {
					prefix := ""
					if strings.HasPrefix(marker, " ") {
						prefix = " "
					}
					label := strings.TrimSpace(strings.SplitN(marker, ":", 2)[0])
					return prefix + strings.ToUpper(label) + ": "
				})
				text = strings.Join(strings.Fields(text), " ")
				matched := false
				for _, parts := range catalogLegacyReplayVariants(steps[index : index+1]) {
					candidate := strings.Join(strings.Fields(strings.Join(parts, " ")), " ")
					matched = matched || candidate != "" && candidate == text
				}
				if ordinal != number || !matched {
					replay = false
					break
				}
			}
		}
		if replay {
			return strings.TrimSpace(body[:boundaries[0][0]])
		}
		return body
	}
	words := strings.Fields(body)
	// The full step projection has at least as many words as instructions alone,
	// matching the renderer's longest-exact-suffix-first decision.
	for _, parts := range catalogLegacyReplayVariants(steps) {
		suffix := strings.Fields(strings.Join(parts, " "))
		if len(suffix) == 0 || len(suffix) > len(words) {
			continue
		}
		start := len(words) - len(suffix)
		matched := true
		for index, word := range suffix {
			if words[start+index] != word {
				matched = false
				break
			}
		}
		if matched {
			return strings.Join(words[:start], " ")
		}
	}
	return body
}

func catalogLegacyReplayVariants(steps []CatalogStep) [][]string {
	full, instructions := []string{}, []string{}
	for _, step := range steps {
		heading := step.Action
		if heading == "" {
			heading = step.Heading
		}
		full = append(full, heading)
		full = append(full, step.Instructions...)
		instructions = append(instructions, step.Instructions...)
	}
	return [][]string{full, instructions}
}

func catalogBlockSearchText(block CatalogDocumentBlock, images catalogSearchImages, placed map[string]bool) string {
	parts := []string{}
	switch block.Type {
	case "heading", "paragraph", "link":
		parts = append(parts, block.Text)
	case "callout":
		parts = append(parts, block.Label, block.Text)
	case "image":
		ref := CatalogImage{AssetID: block.AssetID, ImageID: block.ImageID, Status: block.Status, Alt: block.Alt, Caption: block.Caption}
		return catalogImageSearchText(ref, images.resolve(ref), placed)
	case "step":
		parts = append(parts, block.Text)
	case "ordered_list", "unordered_list":
		for _, item := range block.Items {
			parts = append(parts, catalogInlineSearchText(item, images, placed))
		}
	case "table":
		if block.Label != "" {
			parts = append(parts, block.Label)
		} else {
			parts = append(parts, block.Caption)
		}
		cellImageIDs := map[string]bool{}
		for _, column := range block.Columns {
			parts = append(parts, catalogInlineSearchText(column, images, cellImageIDs))
		}
		for _, row := range block.Rows {
			for _, cell := range row {
				parts = append(parts, catalogInlineSearchText(cell, images, cellImageIDs))
			}
		}
		for _, ref := range block.Images {
			if image := images.resolve(ref); image != nil && !cellImageIDs[catalogSearchImageDisplayID(*image)] {
				parts = append(parts, catalogImageSearchText(ref, image, placed))
			}
		}
		if placed != nil {
			for id := range cellImageIDs {
				placed[id] = true
			}
		}
	case "break":
		return ""
	default:
		if block.Text != "" {
			parts = append(parts, block.Text)
		} else {
			parts = append(parts, block.UnavailableReason)
		}
	}
	switch block.Type {
	case "heading", "paragraph", "link", "callout", "step", "ordered_list", "unordered_list":
		for _, ref := range block.Images {
			parts = append(parts, catalogImageSearchText(ref, images.resolve(ref), placed))
		}
	}
	return strings.Join(parts, " ")
}

func catalogImageRefID(image CatalogImage) string {
	if image.AssetID != "" {
		return image.AssetID
	}
	return image.ImageID
}

type catalogSearchImages map[string]*CatalogImage

func indexCatalogSearchImages(images []CatalogImage) catalogSearchImages {
	if len(images) == 0 {
		return nil
	}
	indexed := make(catalogSearchImages, len(images))
	for i := range images {
		image := &images[i]
		if image.Status == "unavailable" {
			continue
		}
		var renderable *CatalogImage
		if catalogSearchableImage(*image) {
			renderable = image
		}
		for _, id := range []string{image.ID, image.ImageID, image.AssetID} {
			// A first matching asset without a usable address still owns its alias.
			if _, exists := indexed[id]; id != "" && !exists {
				indexed[id] = renderable
			}
		}
	}
	return indexed
}

func (images catalogSearchImages) resolve(ref CatalogImage) *CatalogImage {
	if ref.Status == "unavailable" {
		return nil
	}
	id := catalogImageRefID(ref)
	if id == "" {
		id = ref.ID
	}
	return images[id]
}

func catalogSearchImageDisplayID(image CatalogImage) string {
	if image.ID != "" {
		return image.ID
	}
	if image.ImageID != "" {
		return image.ImageID
	}
	return image.AssetID
}

func catalogImageSearchText(ref CatalogImage, image *CatalogImage, placed map[string]bool) string {
	if image == nil {
		return ""
	}
	if placed != nil {
		placed[catalogSearchImageDisplayID(*image)] = true
	}
	alt := ref.Alt
	if alt == "" && ref.Caption == "" {
		alt = image.Alt
	}
	if ref.Caption == "" {
		return alt
	}
	if alt == "" || alt == ref.Caption {
		return ref.Caption
	}
	return ref.Caption + " " + alt
}

func catalogSearchableImage(image CatalogImage) bool {
	return image.Status != "unavailable" &&
		(image.ID != "" || catalogImageRefID(image) != "") &&
		(localCatalogImageKeyPattern.MatchString(image.StorageKey) ||
			len(image.URL) <= len("/v1/catalog/images/v2.")+6000 && catalogSearchImageURL.MatchString(image.URL))
}

func catalogInlineImageSearchText(fields map[string]any, images catalogSearchImages, placed map[string]bool) string {
	var ref CatalogImage
	ref.AssetID, _ = fields["asset_id"].(string)
	ref.ImageID, _ = fields["image_id"].(string)
	ref.ID, _ = fields["id"].(string)
	ref.Status, _ = fields["status"].(string)
	ref.Caption, _ = fields["caption"].(string)
	ref.Alt, _ = fields["alt"].(string)
	image := images.resolve(ref)
	// An omitted alt defaults to the reference caption. Inline JSON can carry
	// an explicit empty alt, which lets the reader fall back to the asset alt.
	if _, explicitAlt := fields["alt"]; image != nil && explicitAlt && ref.Alt == "" {
		ref.Alt = image.Alt
	}
	return catalogImageSearchText(ref, image, placed)
}

func catalogInlineSearchText(cell any, images catalogSearchImages, placed map[string]bool) string {
	switch value := cell.(type) {
	case string:
		return value
	case bool, int, int64, float64:
		return fmt.Sprint(value)
	case map[string]any:
		parts := []string{}
		if text, ok := value["text"].(string); ok {
			parts = append(parts, text)
		}
		assetID, _ := value["asset_id"].(string)
		imageID, _ := value["image_id"].(string)
		if assetID != "" || imageID != "" {
			parts = append(parts, catalogInlineImageSearchText(value, images, placed))
		}
		if cellImages, ok := value["images"].([]any); ok {
			for _, image := range cellImages {
				if fields, ok := image.(map[string]any); ok {
					parts = append(parts, catalogInlineImageSearchText(fields, images, placed))
				}
			}
		}
		for _, nested := range catalogNestedBlocks(value["blocks"]) {
			parts = append(parts, catalogBlockSearchText(nested, images, placed))
		}
		return strings.Join(parts, " ")
	default:
		return ""
	}
}
