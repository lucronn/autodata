package main

import (
	"strings"
	"unicode/utf8"
)

type CatalogFigureLayout struct {
	Width  float64              `json:"width"`
	Height float64              `json:"height"`
	Labels []CatalogFigureLabel `json:"labels"`
}

type CatalogFigureLabel struct {
	Left     float64  `json:"left"`
	Top      float64  `json:"top"`
	FontSize float64  `json:"font_size"`
	Lines    []string `json:"lines"`
}

type CatalogRasterDimensions struct {
	Width  int `json:"width"`
	Height int `json:"height"`
}

func parseCatalogRasterDimensions(value any) *CatalogRasterDimensions {
	dimensions, ok := value.(map[string]any)
	if !ok || len(dimensions) != 2 {
		return nil
	}
	width, widthOK := dimensions["width"].(float64)
	height, heightOK := dimensions["height"].(float64)
	if !widthOK || !heightOK || width < 1 || width > 10000 || height < 1 || height > 10000 ||
		width != float64(int(width)) || height != float64(int(height)) {
		return nil
	}
	return &CatalogRasterDimensions{Width: int(width), Height: int(height)}
}

// Project the numeric placement and authored lines without passing through CSS
// or permitting malformed placement data to make the rest of a source unreadable.
func parseCatalogFigureLayout(value any) *CatalogFigureLayout {
	layout, ok := value.(map[string]any)
	if !ok || len(layout) != 3 {
		return nil
	}
	number := func(value any, low, high float64) (float64, bool) {
		v, ok := value.(float64)
		return v, ok && low <= v && v <= high
	}
	width, widthOK := number(layout["width"], 1, 10000)
	height, heightOK := number(layout["height"], 1, 10000)
	items, ok := layout["labels"].([]any)
	if !widthOK || !heightOK || !ok || len(items) < 1 || len(items) > 32 {
		return nil
	}
	result := &CatalogFigureLayout{Width: width, Height: height, Labels: make([]CatalogFigureLabel, 0, len(items))}
	for _, item := range items {
		label, ok := item.(map[string]any)
		if !ok || len(label) != 4 {
			return nil
		}
		left, leftOK := number(label["left"], 0, width)
		top, topOK := number(label["top"], 0, height)
		font, fontOK := number(label["font_size"], 5, 72)
		lines, ok := label["lines"].([]any)
		if !leftOK || !topOK || !fontOK || !ok || len(lines) < 1 || len(lines) > 8 {
			return nil
		}
		placement := CatalogFigureLabel{Left: left, Top: top, FontSize: font, Lines: make([]string, 0, len(lines))}
		for _, line := range lines {
			text, ok := line.(string)
			if !ok || text == "" || utf8.RuneCountInString(text) > 160 || strings.Join(strings.Fields(text), " ") != text {
				return nil
			}
			placement.Lines = append(placement.Lines, text)
		}
		result.Labels = append(result.Labels, placement)
	}
	return result
}
