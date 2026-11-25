package main

import (
	"bytes"
	"context"
	"regexp"
	"slices"
)

const maxCatalogArticleLinkTargets = 128

var catalogArticleReferenceDigest = regexp.MustCompile("^[a-f0-9]{64}$")

type catalogArticleLinkResolver func([]string) map[string]string

func projectStoredCatalogDocument(document *CatalogDocument, raw []byte, resolve catalogArticleLinkResolver) *CatalogDocument {
	if resolve == nil || !bytes.Contains(raw, []byte(`"target_ref_sha256"`)) {
		return publicCatalogDocument(document)
	}
	return projectCatalogDocument(raw, resolve)
}

func addResolvedCatalogArticleLinks(slots map[string][]map[string]any, resolve catalogArticleLinkResolver) {
	hashes := make([]string, 0, len(slots))
	for hash := range slots {
		hashes = append(hashes, hash)
	}
	slices.Sort(hashes)
	for hash, id := range resolve(hashes) {
		if commerceUUID(id) {
			for _, link := range slots[hash] {
				link["target_article_id"] = id
			}
		}
	}
}

// Resolve only within the authorized origin's immutable provider identity.
// A withdrawn or ambiguous target stays readable as ordinary link text.
func (s *postgresCatalogStore) authoredArticleLinkResolver(ctx context.Context, identity PaidArticleIdentity) catalogArticleLinkResolver {
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
			GROUP BY ref_hash HAVING count(*)=1
			LIMIT $5`, identity.CanonicalArticleID, identity.ConfigurationID, identity.SourceVehicleRef, hashes, maxCatalogArticleLinkTargets)
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
