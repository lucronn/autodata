package main

import "slices"

const workshopLeadImagePreference = "workshop-preload-lead-image"

func workshopLeadImageURL(article CatalogArticle) string {
	if article.Document == nil {
		return ""
	}
	images := slices.Clone(article.Images)
	for _, step := range article.Steps {
		if step.Images != nil {
			images = append(images, (*step.Images)...)
		}
	}
	// The browser already treats the first image separately on image-heavy
	// documents. Those responses also have the most transfer to overlap.
	distinct := make(map[string]struct{})
	for _, image := range images {
		if image.Status != "unavailable" && isWorkshopSignedImagePath(image.URL) {
			distinct[image.URL] = struct{}{}
		}
	}
	if len(distinct) < 7 {
		return ""
	}
	return firstWorkshopBlockImage(article.Document.Blocks, indexCatalogSearchImages(images, false))
}

func isWorkshopSignedImagePath(path string) bool {
	return len(path) <= len("/v1/catalog/images/v2.")+6000 && catalogSearchImageURL.MatchString(path)
}

func workshopImageReferenceURL(ref CatalogImage, images catalogSearchImages) string {
	image := images.resolve(ref)
	if image != nil && isWorkshopSignedImagePath(image.URL) {
		return image.URL
	}
	return ""
}

func firstWorkshopInlineImage(values []any, images catalogSearchImages) string {
	for _, value := range values {
		fields, ok := value.(map[string]any)
		if !ok {
			continue
		}
		ref := workshopInlineImageReference(fields)
		if ref.AssetID != "" || ref.ImageID != "" {
			if path := workshopImageReferenceURL(ref, images); path != "" {
				return path
			}
		}
		if refs, ok := fields["images"].([]any); ok {
			for _, value := range refs {
				ref, _ := value.(map[string]any)
				if path := workshopImageReferenceURL(workshopInlineImageReference(ref), images); path != "" {
					return path
				}
			}
		}
		if path := firstWorkshopBlockImage(catalogNestedBlocks(fields["blocks"]), images); path != "" {
			return path
		}
	}
	return ""
}

func workshopInlineImageReference(fields map[string]any) CatalogImage {
	asset, _ := fields["asset_id"].(string)
	image, _ := fields["image_id"].(string)
	id, _ := fields["id"].(string)
	status, _ := fields["status"].(string)
	return CatalogImage{AssetID: asset, ImageID: image, ID: id, Status: status}
}

func firstWorkshopBlockImage(blocks []CatalogDocumentBlock, images catalogSearchImages) string {
	for _, block := range blocks {
		switch block.Type {
		case "image":
			ref := CatalogImage{AssetID: block.AssetID, ImageID: block.ImageID, Status: block.Status}
			if path := workshopImageReferenceURL(ref, images); path != "" {
				return path
			}
			continue
		case "ordered_list", "unordered_list":
			if path := firstWorkshopInlineImage(block.Items, images); path != "" {
				return path
			}
		case "table":
			if path := firstWorkshopInlineImage(block.Columns, images); path != "" {
				return path
			}
			for _, row := range block.Rows {
				if path := firstWorkshopInlineImage(row, images); path != "" {
					return path
				}
			}
		case "heading", "paragraph", "link", "callout", "step":
			// The renderer uses these blocks' image references directly.
		default:
			continue
		}
		for _, ref := range block.Images {
			if path := workshopImageReferenceURL(ref, images); path != "" {
				return path
			}
		}
	}
	return ""
}
