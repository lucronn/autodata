package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"regexp"
	"slices"
	"strings"
	"unicode"
	"unicode/utf8"
)

const maxCatalogArticleLinkTargets = 128

var catalogArticleReferenceDigest = regexp.MustCompile("^[a-f0-9]{64}$")

type catalogArticleLinkResolver func([]string) map[string]string

type retainedCatalogLink struct {
	labelSHA256  string
	targetSHA256 string
}

type retainedCatalogInlineLink struct {
	label      string
	targetHash string
	itemIndex  int
}

type catalogArticleLinkProjection struct {
	resolve  catalogArticleLinkResolver
	retained map[string]retainedCatalogLink
	inline   map[string][]retainedCatalogInlineLink
}

func projectStoredCatalogDocument(document *CatalogDocument, raw []byte, links catalogArticleLinkProjection) *CatalogDocument {
	if links.resolve == nil || (len(links.retained) == 0 && len(links.inline) == 0 &&
		!bytes.Contains(raw, []byte(`"target_ref_sha256"`))) {
		return publicCatalogDocument(document)
	}
	return projectCatalogDocument(raw, links)
}

// Retained rows bind an immutable body and the currently effective published
// revision. An unavailable binding lookup leaves the original view readable.
func (s *postgresCatalogStore) retainedArticleLinkBindings(ctx context.Context, article string, source, canonical *string, bodySHA256 string) (map[string]retainedCatalogLink, map[string][]retainedCatalogInlineLink) {
	if source == nil || canonical == nil || !catalogArticleReferenceDigest.MatchString(bodySHA256) {
		return nil, nil
	}
	ctx, cancel := context.WithTimeout(ctx, catalogStatusReadTimeout)
	defer cancel()
	rows, err := s.pool.Query(ctx, `
		SELECT binding.block_id, binding.label_sha256, binding.target_ref_sha256, binding.item_index, binding.inline_label
		FROM canonical_articles a
		`+paidArticleCurrentJoinSQL+`
		JOIN LATERAL (
			SELECT block_id, label_sha256, target_ref_sha256, -1 AS item_index, '' AS inline_label
			FROM canonical_article_link_bindings
			WHERE canonical_article_revision_id=$3::uuid AND source_revision_id=$2::uuid
			  AND canonical_article_id=$1::uuid AND body_sha256=$4
			UNION ALL
			SELECT block_id, label_sha256, target_ref_sha256, item_index, label AS inline_label
			FROM canonical_article_inline_link_bindings
			WHERE canonical_article_revision_id=$3::uuid AND source_revision_id=$2::uuid
			  AND canonical_article_id=$1::uuid AND body_sha256=$4
		) binding ON true
		WHERE a.canonical_article_id=$1::uuid
		  AND a.provider_slug='bankone' AND a.membership_status='active'
		  AND c.canonical_revision_id=$3::uuid AND c.source_revision_id=$2::uuid AND c.takedown_status='active'
		  AND c.source_content_sha256::text=$4
		ORDER BY binding.block_id COLLATE "C", binding.item_index, binding.inline_label COLLATE "C"
		LIMIT $5`, article, *source, *canonical, bodySHA256, maxCatalogArticleLinkTargets+1)
	if err != nil {
		return nil, nil
	}
	defer rows.Close()
	links := make(map[string]retainedCatalogLink)
	inline := make(map[string][]retainedCatalogInlineLink)
	count := 0
	for rows.Next() {
		var blockID string
		var placement retainedCatalogInlineLink
		var link retainedCatalogLink
		if err := rows.Scan(&blockID, &link.labelSHA256, &link.targetSHA256, &placement.itemIndex, &placement.label); err != nil {
			return nil, nil
		}
		if blockID == "" || !catalogArticleReferenceDigest.MatchString(link.labelSHA256) ||
			!catalogArticleReferenceDigest.MatchString(link.targetSHA256) || count >= maxCatalogArticleLinkTargets {
			return nil, nil
		}
		count++
		if placement.label == "" {
			links[blockID] = link
		} else {
			placement.targetHash = link.targetSHA256
			inline[blockID] = append(inline[blockID], placement)
		}
	}
	if rows.Err() != nil {
		return nil, nil
	}
	return links, inline
}

func collectRetainedCatalogLink(retained map[string]retainedCatalogLink, matches map[string]map[string]any, node, out map[string]any) {
	blockID, _ := node["block_id"].(string)
	link, exists := retained[blockID]
	if !exists {
		return
	}
	_, duplicate := matches[blockID]
	matches[blockID] = nil
	label, hasLabel := node["text"].(string)
	_, hasAuthoredHash := node["target_ref_sha256"]
	if duplicate || node["type"] != "link" || !hasLabel || label == "" || hasAuthoredHash {
		return
	}
	digest := sha256.Sum256([]byte(label))
	if hex.EncodeToString(digest[:]) == link.labelSHA256 {
		matches[blockID] = out
	}
}

// Keep the in-document bindings and their original limit even if the combined
// lookup would exceed that limit. Retained bindings can only fill unused slots.
func addRetainedCatalogLinkSlots(slots map[string][]map[string]any, retained map[string]retainedCatalogLink, matches map[string]map[string]any) {
	extra := make(map[string]struct{})
	for blockID, block := range matches {
		hash := retained[blockID].targetSHA256
		if block != nil && len(slots[hash]) == 0 {
			extra[hash] = struct{}{}
		}
	}
	if len(slots)+len(extra) > maxCatalogArticleLinkTargets {
		return
	}
	for blockID, block := range matches {
		if block != nil {
			hash := retained[blockID].targetSHA256
			slots[hash] = append(slots[hash], block)
		}
	}
}

func addResolvedCatalogArticleLinks(slots map[string][]map[string]any, resolve catalogArticleLinkResolver) map[string]string {
	hashes := make([]string, 0, len(slots))
	for hash := range slots {
		hashes = append(hashes, hash)
	}
	slices.Sort(hashes)
	resolved := resolve(hashes)
	for hash, id := range resolved {
		if commerceUUID(id) {
			for _, link := range slots[hash] {
				link["target_article_id"] = id
			}
		}
	}
	return resolved
}

// Project an exact authored title within a paragraph or numbered list item.
// The original stored document can still be rendered when a target is unavailable.
func applyRetainedInlineCatalogLinks(bindings map[string][]retainedCatalogInlineLink, matches map[string]map[string]any, resolved map[string]string) {
	for blockID, node := range matches {
		for _, binding := range bindings[blockID] {
			target := resolved[binding.targetHash]
			if !commerceUUID(target) || node == nil {
				continue
			}
			if binding.itemIndex == -1 && node["type"] == "paragraph" {
				appendInlineCatalogLink(node, binding.label, target)
			} else if node["type"] == "ordered_list" || node["type"] == "unordered_list" {
				items, _ := node["items"].([]any)
				if binding.itemIndex < 0 || binding.itemIndex >= len(items) {
					continue
				}
				switch item := items[binding.itemIndex].(type) {
				case string:
					expanded := map[string]any{"text": item}
					if appendInlineCatalogLink(expanded, binding.label, target) {
						items[binding.itemIndex] = expanded
					}
				case map[string]any:
					appendInlineCatalogLink(item, binding.label, target)
				}
			}
		}
	}
}

func appendInlineCatalogLink(node map[string]any, label, target string) bool {
	text, _ := node["text"].(string)
	if label == "" || strings.Count(text, label) != 1 {
		return false
	}
	start := strings.Index(text, label)
	end := start + len(label)
	before, _ := utf8.DecodeLastRuneInString(text[:start])
	after, _ := utf8.DecodeRuneInString(text[end:])
	if unicode.IsLetter(before) || unicode.IsDigit(before) || unicode.IsLetter(after) || unicode.IsDigit(after) {
		return false
	}
	links, _ := node["article_links"].([]CatalogArticleLink)
	node["article_links"] = append(links, CatalogArticleLink{Label: label, TargetArticleID: target})
	return true
}

// Resolve only within the authorized origin's immutable provider identity.
// A withdrawn or ambiguous target stays readable as ordinary link text.
func (s *postgresCatalogStore) authoredArticleLinkResolver(ctx context.Context, identity PaidArticleIdentity, readyOnly bool) catalogArticleLinkResolver {
	if identity.ProviderSlug != "bankone" || identity.SourceVehicleRef == "" ||
		!commerceUUID(identity.CanonicalArticleID) || !commerceUUID(identity.ConfigurationID) {
		return nil
	}
	return func(hashes []string) map[string]string {
		ctx, cancel := context.WithTimeout(ctx, catalogStatusReadTimeout)
		defer cancel()
		rows, err := s.pool.Query(ctx, `
			SELECT encode(sha256(convert_to(a.source_article_ref,'UTF8')),'hex') AS ref_hash,
			       min(a.canonical_article_id::text)
			FROM canonical_articles origin
			JOIN source_snapshots origin_descriptor ON origin_descriptor.source_snapshot_id=origin.descriptor_source_snapshot_id
			JOIN canonical_articles a ON a.provider_slug=origin.provider_slug
				AND a.scope_key=origin.scope_key AND a.vehicle_configuration_id=origin.vehicle_configuration_id
				AND a.vehicle_id=origin.vehicle_id AND a.source_vehicle_ref=origin.source_vehicle_ref
			JOIN source_snapshots descriptor ON descriptor.source_snapshot_id=a.descriptor_source_snapshot_id
			`+paidArticleCurrentJoinSQL+`
			WHERE origin.canonical_article_id=$1::uuid AND origin.vehicle_configuration_id=$2::uuid
			  AND origin.provider_slug='bankone' AND origin.source_vehicle_ref=$3
			  AND origin.membership_status='active' AND origin.takedown_status='active'
			  AND origin_descriptor.takedown_status='active'
			  AND a.takedown_status='active' AND descriptor.takedown_status='active' AND c.takedown_status='active'
			  AND encode(sha256(convert_to(a.source_article_ref,'UTF8')),'hex')=ANY($4::text[])
			  AND `+lifecycleEligibleSQL+`
			GROUP BY ref_hash HAVING count(*)=1 AND (NOT $6 OR bool_and(c.availability='available'))
			LIMIT $5`, identity.CanonicalArticleID, identity.ConfigurationID, identity.SourceVehicleRef, hashes, maxCatalogArticleLinkTargets, readyOnly)
		if err != nil {
			return nil
		}
		defer rows.Close()
		targets := make(map[string]string, len(hashes))
		for rows.Next() {
			var hash, id string
			if err := rows.Scan(&hash, &id); err != nil {
				return nil
			}
			targets[hash] = id
		}
		if rows.Err() != nil {
			return nil
		}
		return targets
	}
}
