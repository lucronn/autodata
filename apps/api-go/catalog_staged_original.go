package main

// A staged Original is a separately selectable source projection of the same
// retained body. The worker writes this binding only after it verifies every
// recovered legacy SVG and its authored position, before starting the rewrite.
// A later rewrite failure does not change the captured source or its binding.
// Recheck the binding and both captures' rights in each protected read. This
// selection never supplies canonical content or changes the current revision.
// Callers provide the canonical article (a) and its effective view (view_row).
const catalogStagedOriginalSQL = `
	SELECT candidate.source_revision_id, candidate.body_source_snapshot_id,
		body.content_sha256, observed.body_provider_revision
	FROM source_fetch_jobs j
	JOIN canonical_article_source_revisions candidate USING (canonical_article_id,source_revision_id)
	JOIN canonical_article_source_revisions prior ON prior.canonical_article_id=a.canonical_article_id
		AND prior.source_revision_id=a.current_source_revision_id
	JOIN source_snapshots body ON body.source_snapshot_id=candidate.body_source_snapshot_id
	JOIN canonical_article_source_observations observed ON observed.source_fetch_job_id=j.source_fetch_job_id
		AND observed.canonical_article_id=j.canonical_article_id AND observed.source_revision_id=j.source_revision_id
	LEFT JOIN LATERAL (
		SELECT resource_provenance, descriptor_source_snapshot_id, resolution_source_snapshot_id
		FROM canonical_article_source_observations o
		WHERE o.canonical_article_id=prior.canonical_article_id AND o.source_revision_id=prior.source_revision_id
		ORDER BY o.captured_at,o.source_observation_id LIMIT 1
	) old_observation ON true
	WHERE a.provider_slug='bankone' AND a.vehicle_configuration_id IS NOT NULL
	AND view_row.takedown_status='active' AND view_row.source_revision_id=a.current_source_revision_id
	AND view_row.canonical_revision_id=a.current_canonical_revision_id
	AND j.source_fetch_job_id=a.current_job_id AND j.request_generation=a.request_generation
	AND j.job_kind='article' AND j.canonical_article_id=a.canonical_article_id AND j.canonical_vehicle_id=a.vehicle_id
	AND j.provider_slug=a.provider_slug AND j.source_vehicle_ref=a.source_vehicle_ref AND j.source_article_ref=a.source_article_ref
	AND j.normalization_version=a.target_normalization_version AND j.rewrite_profile_version=a.target_rewrite_profile_version
	AND candidate.source_revision_id<>prior.source_revision_id
	AND candidate.body_source_snapshot_id=prior.body_source_snapshot_id
	AND j.checkpoint->'staged_media_refresh'=jsonb_build_object(
		'version',1,'source_revision_id',candidate.source_revision_id,
		'prior_source_revision_id',prior.source_revision_id,'prior_canonical_revision_id',view_row.canonical_revision_id)
	AND observed.request_generation<=j.request_generation AND observed.descriptor_source_snapshot_id=a.descriptor_source_snapshot_id
	AND candidate.projection_status='readable' AND jsonb_array_length(candidate.source_images)>0
	AND candidate.resource_manifest @> '[{"role":"asset_original","media_type":"image/svg+xml"}]'::jsonb
	AND jsonb_array_length(candidate.resource_manifest)=jsonb_array_length(observed.resource_provenance)
	AND jsonb_array_length(prior.resource_manifest)=jsonb_array_length(old_observation.resource_provenance)
	AND NOT EXISTS (
		SELECT 1 FROM (
			SELECT a.descriptor_source_snapshot_id AS snapshot_id,false AS resource
			UNION ALL SELECT observed.resolution_source_snapshot_id,false
			UNION ALL SELECT old_observation.descriptor_source_snapshot_id,false
			UNION ALL SELECT old_observation.resolution_source_snapshot_id,false
			UNION ALL SELECT candidate.body_source_snapshot_id,true
			UNION ALL
			SELECT asset.source_snapshot_id,true
			FROM (VALUES (candidate.resource_manifest,observed.resource_provenance),
				(prior.resource_manifest,old_observation.resource_provenance)) captured(manifest,provenance)
			CROSS JOIN LATERAL jsonb_array_elements(captured.manifest) WITH ORDINALITY entry(value,position)
			LEFT JOIN source_snapshots asset ON asset.content_sha256=(entry.value->>'sha256')::bpchar
				AND asset.content_sha256::text=entry.value->>'sha256'
				AND asset.content_sha256::text=captured.provenance->(entry.position-1)::int->>'sha256'
				AND asset.source_snapshot_id::text=captured.provenance->(entry.position-1)::int->>'source_snapshot_id'
			WHERE entry.value ? 'sha256'
		) retained
		LEFT JOIN source_snapshots snapshot ON snapshot.source_snapshot_id=retained.snapshot_id
		LEFT JOIN source_artifacts artifact ON retained.resource AND artifact.source_snapshot_id=retained.snapshot_id
		WHERE snapshot.source_snapshot_id IS NULL OR snapshot.takedown_status<>'active'
		OR artifact.extraction_status='quarantined' OR EXISTS (
			SELECT 1 FROM source_review_items quarantine
			WHERE quarantine.item_kind='quarantine' AND quarantine.status<>'approved'
			AND quarantine.source_snapshot_ids ? retained.snapshot_id::text
		)
	)`
