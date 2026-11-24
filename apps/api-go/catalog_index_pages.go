package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/url"
	"regexp"
	"strconv"
)

const catalogIndexPagesPreference = "workshop-index-pages"
const catalogIndexLivePagesPreference = "workshop-index-live-pages"
const catalogIndexPageSize = 100

var catalogIndexOffsetPattern = regexp.MustCompile(`^(0|[1-9][0-9]*00)$`)

type CatalogArticleIndexPage struct {
	Offset   int    `json:"offset"`
	Total    int    `json:"total"`
	Revision string `json:"revision"`
}

type catalogIndexPageRequest struct {
	offset string
	anchor string
}

func parseCatalogIndexPageRequest(filters url.Values) (catalogIndexPageRequest, bool) {
	offsets, anchors := filters["offset"], filters["anchor"]
	switch len(offsets) + len(anchors) {
	case 0:
		return catalogIndexPageRequest{}, true
	case 1:
		if filters.Has("q") || filters.Has("title") {
			return catalogIndexPageRequest{}, false
		}
		if len(anchors) == 1 {
			return catalogIndexPageRequest{anchor: anchors[0]}, commerceUUID(anchors[0])
		}
		return catalogIndexPageRequest{offset: offsets[0]}, catalogIndexOffsetPattern.MatchString(offsets[0])
	default:
		return catalogIndexPageRequest{}, false
	}
}

// Hash the current authorized index snapshot, in repository order. The projection
// uses only index metadata so retained body bytes and processing timers
// never affect a page revision.
func catalogIndexRevision(items []CatalogArticle) string {
	type descriptor struct {
		ID, Title, Kind, Component, Availability, ContentStatus string
		SourceRevisionID, CanonicalRevisionID, ViewRevision     *string
		ContentOrigin, Review                                   *string
		Complete                                                bool
	}
	sum := sha256.New()
	encoder := json.NewEncoder(sum)
	var projection descriptor
	for _, item := range items {
		projection = descriptor{
			ID: item.ID, Title: item.Title, Kind: item.Kind, Component: item.Component,
			Availability: item.Availability, ContentStatus: item.ContentStatus,
			SourceRevisionID: item.SourceRevisionID, CanonicalRevisionID: item.CanonicalRevisionID,
			ViewRevision: item.ViewRevision, ContentOrigin: item.ContentOrigin, Review: item.ReviewStatus,
			Complete: item.Complete,
		}
		_ = encoder.Encode(&projection)
	}
	return hex.EncodeToString(sum.Sum(nil))
}

func (requested catalogIndexPageRequest) selectPage(items []CatalogArticle) ([]CatalogArticle, *CatalogArticleIndexPage) {
	total := len(items)
	offset := 0
	if requested.offset != "" {
		requestedOffset, err := strconv.ParseUint(requested.offset, 10, 64)
		if err != nil || requestedOffset >= uint64(total) {
			offset = (total - 1) / catalogIndexPageSize * catalogIndexPageSize
		} else {
			offset = int(requestedOffset)
		}
	} else if requested.anchor != "" {
		for index, item := range items {
			if item.ID == requested.anchor {
				offset = index / catalogIndexPageSize * catalogIndexPageSize
				break
			}
		}
	}
	end := offset + min(catalogIndexPageSize, total-offset)
	return items[offset:end], &CatalogArticleIndexPage{
		Offset: offset, Total: total, Revision: catalogIndexRevision(items),
	}
}
