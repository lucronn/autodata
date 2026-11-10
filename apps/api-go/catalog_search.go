package main

import (
	"fmt"
	"strings"
)

// Search only text the Workshop can display. IDs, locators, image URLs, and
// source metadata are deliberately excluded from content search.
func filterCatalogArticleSearch(items []CatalogArticle, query string) []CatalogArticle {
	words := strings.Fields(strings.ToLower(query))
	if len(words) == 0 {
		return items
	}
	matches := make([]CatalogArticle, 0)
	for _, article := range items {
		text := strings.ToLower(catalogArticleSearchText(article))
		all := true
		for _, word := range words {
			if !strings.Contains(text, word) {
				all = false
				break
			}
		}
		if all {
			matches = append(matches, article)
		}
	}
	return matches
}

func catalogArticleSearchText(article CatalogArticle) string {
	parts := []string{article.Title, article.Component, article.Kind}
	if article.Document != nil && len(article.Document.Blocks) > 0 {
		for _, block := range article.Document.Blocks {
			parts = append(parts, catalogBlockSearchText(block))
		}
	} else {
		parts = append(parts, article.Body)
		for _, step := range article.Steps {
			parts = append(parts, step.Text, step.Action, step.Heading)
			parts = append(parts, step.Instructions...)
		}
	}
	return strings.Join(parts, " ")
}

func catalogBlockSearchText(block CatalogDocumentBlock) string {
	parts := []string{}
	switch block.Type {
	case "heading", "paragraph", "link":
		parts = append(parts, block.Text)
	case "callout":
		parts = append(parts, block.Label, block.Text)
	case "image":
		if block.Alt != "" {
			parts = append(parts, block.Alt)
		} else {
			parts = append(parts, block.Caption)
		}
	case "step":
		parts = append(parts, block.Text)
	case "ordered_list", "unordered_list":
		parts = append(parts, block.Items...)
	case "table":
		if block.Label != "" {
			parts = append(parts, block.Label)
		} else {
			parts = append(parts, block.Caption)
		}
		parts = append(parts, block.Columns...)
		for _, row := range block.Rows {
			for _, cell := range row {
				parts = append(parts, catalogTableCellSearchText(cell))
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
	if block.Type == "callout" || block.Type == "step" || block.Type == "ordered_list" || block.Type == "unordered_list" {
		for _, image := range block.Images {
			parts = append(parts, image.Alt)
		}
	}
	return strings.Join(parts, " ")
}

func catalogTableCellSearchText(cell any) string {
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
		if images, ok := value["images"].([]any); ok {
			for _, image := range images {
				if fields, ok := image.(map[string]any); ok {
					if alt, ok := fields["alt"].(string); ok {
						parts = append(parts, alt)
					}
				}
			}
		}
		return strings.Join(parts, " ")
	default:
		return ""
	}
}
