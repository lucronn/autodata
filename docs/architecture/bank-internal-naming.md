# Internal Bankone and Banktwo naming

## Goal
Rename AutoData internal AutoAPI/AutoDB references to Bankone/Banktwo.

## Plan and contract
- Plan: docs/superpowers/plans/2026-10-08-bank-internal-rename.md
- Contract: docs/architecture/bank-internal-naming.md
- Project: https://github.com/users/lucronn/projects/8

## Concrete todo
- Rename Python modules, symbols, scripts, active documentation and service directory.
- Rename configuration to BANKONE/BANKTWO with legacy environment fallback; distinguish Banktwo upstream settings from connector settings.
- Preserve database schema, persisted provider IDs, stable key namespaces, historical migration files, upstream hostnames and historical planning evidence.
- Verify Python, Go, service and Compose contracts and inspect remaining legacy references.

Issue: https://github.com/lucronn/autodata/issues/131

## Implementation decisions
AutoAPI and AutoDBone symbols become Bankone; AutoAPItwo and AutoDBtwo become Banktwo. Python modules and scripts are renamed with all in-repository imports/callers. AUTODATA_AUTOAPITWO_BASE_URL becomes AUTODATA_BANKTWO_UPSTREAM_BASE_URL, while AUTODATA_AUTODBTWO_BASE_URL becomes AUTODATA_BANKTWO_BASE_URL. Other AUTOAPITWO settings become BANKTWO settings. New environment names take precedence with legacy fallback. services/autodbtwo becomes services/banktwo; preserve submodule Git storage and dirty work. No deployment, database rewrite or historical evidence rewrite. Keep persisted provider identifiers, source versions, ID namespaces, SQL table names and payload keys stable. Keep upstream URLs, existing image artifacts and Kubernetes secret keys valid. Existing local modifications must survive the rename.

## Validation
Run the ingestion worker suite, Go API suite, Banktwo tests/typecheck, developer migration/Compose checks and parse Compose configuration without printing secrets. Add direct new/legacy environment precedence tests and test the renamed modules. Report pre-existing failures separately.

Legacy wire/storage identifiers are compatibility contracts, not implementation names. Their remaining spellings are intentional until a separately planned data migration.
