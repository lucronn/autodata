# Rename internal AutoAPI/AutoDB references to Bankone/Banktwo

**Goal:** Rename AutoData internal AutoAPI/AutoDB implementation names to Bankone/Banktwo while preserving persisted compatibility identifiers.

**Issue:** https://github.com/lucronn/autodata/issues/131  
**Project:** https://github.com/users/lucronn/projects/8  
**Architecture:** `docs/architecture/bank-internal-naming.md`

## Contract

- Rename active Python modules, symbols, scripts, and operator docs from AutoAPI/AutoDB naming to Bankone/Banktwo.
- Keep historical migrations, persisted provider IDs (`autoapi`/`autoapitwo`), SQL table names, and historical planning evidence unchanged.
- Prefer new `BANKONE`/`BANKTWO` environment names with legacy fallback where settings remain.
- Do not vendor banks into this repository.

## Concrete todo

- [x] Rename `bankone_batch` / `bankone_job_persistence` modules, symbols, tests, and `ingest_bankone_*` scripts to Bankone equivalents.
- [x] Update Dockerfile and README operator commands to the new script names.
- [x] Leave migration filenames and stored provider IDs unchanged.
- [x] Run focused Bankone batch/persistence tests and Compose/governance checks that reference the renamed paths.

## Validation

Focused ingestion tests for the renamed modules must pass. Remaining intentional `autoapi` spellings are limited to migrations, persisted IDs, and historical docs.
