# Bankone CLI timeout compatibility Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans after exact-base preflight and coordinator dispatch.

**Goal:** Restore Bankone ingestion CLI construction by passing --timeout-seconds to the existing SourceConnectorClient timeout parameter.

**Architecture:** Preserve `--timeout-seconds` as the public CLI flag and pass its parsed float to the existing `SourceConnectorClient(..., timeout=...)` interface. The client remains the authority for timeout validation; avoid adding aliases or touching shared client code.

**Tech Stack:** Python, unittest/mock, existing Bankone ingestion CLI and batch tests.

**Spec:** docs/architecture/source-connector-api-compatibility.md, Bankone CLI timeout compatibility.

Parent: https://github.com/lucronn/autodata/issues/186
Project: https://github.com/users/lucronn/projects/8
Source baseline: `27b959bf3845bb6bc3f20c3b40db5a582c61573e`.
Branch: `codex/bankone-cli-timeout-gate`.
Separate from Issue317 HAL adaptation; no dependency on that branch.

## Concrete todo

- [ ] Add a focused offline CLI regression using the real SourceConnectorClient constructor and mocked traversal/persistence.
- [ ] Change only the CLI constructor keyword from timeout_seconds to timeout, retaining the flag, default, credentials and persist behavior.
- [ ] Run red/green focused checks, Bankone batch regressions and diff checks; commit/push the validated two-file fix for independent exact-SHA review.

## Exact scope

Implementation allowlist:
- `scripts/dev/ingest_bankone_service.py`
- `scripts/dev/test_ingest_bankone_service.py` (new)

Observed failure: `ingest_bankone_service.py --year 2012 --make Toyota --limit 10 --persist` raises `TypeError` before traversal because line156 uses `timeout_seconds=args.timeout_seconds`, while the shared client constructor accepts `timeout`. The smallest fix changes that one keyword. No provider calls, persistence operations, deployment, schema, shared client, catalog traversal, credential handling or output format changes are authorized for implementation verification.

## One bounded task

Interface: existing `main(argv: list[str] | None = None) -> None`. Preserve `--timeout-seconds` default30.0 and custom floating-point values; preserve `--persist`, year/make/limit selection and source metadata.

- [ ] Create the test file with `unittest.TestCase`, loading the adjacent CLI via `importlib.util.spec_from_file_location` to avoid package assumptions. Keep its real `SourceConnectorClient` class; patch `source_connector_token` to return None, `fetch_bankone_batches` to return `([object()], [], {"traversal_error_count":0})`, and `execute_bank_batch` to return `{"status":"ok"}`. Redirect stdout with `contextlib.redirect_stdout(io.StringIO())`; no network/database calls are possible through mocked boundaries.
- [ ] Exercise `main(["--base-url","http://127.0.0.1:9999","--year","2012","--make","Toyota","--limit","10","--persist"])` and the same command plus `--timeout-seconds 7.5`. Assert the connector passed to mocked traversal has timeout30.0/7.5, provider bankone and the exact base URL. Assert traversal receives target_year2012, target_makeToyota and limit10; assert batch execution receives persistTrue and adapter_namebankone; assert emitted JSON statusok. Add `--timeout-seconds 0` asserting existing constructor ValueError before traversal or persistence. Use a Mock wrapping the real constructor only if needed; do not mock away constructor keyword validation.
- [ ] Run `PYTHONPATH=workers/ingestion-python/src python3 -m unittest discover -s scripts/dev -p test_ingest_bankone_service.py -v`; retain failing TypeError as red evidence.
- [ ] Replace exactly `timeout_seconds=args.timeout_seconds` with `timeout=args.timeout_seconds` in the existing CLI constructor. Add no shared client compatibility alias or unrelated cleanup.
- [ ] Re-run the focused unittest; then run `PYTHONPATH=workers/ingestion-python/src python3 -m pytest workers/ingestion-python/tests/test_bankone_batch.py -q` and `git diff --check`. Verify `--help` still lists `--timeout-seconds`. No authenticated provider or database calls are required or allowed in these tests.
- [ ] Commit/push the validated two-file implementation. Independent exact-SHA review checks that constructor validation is genuinely exercised and timeout/selector/persist/output contracts remain intact. Coordinator records evidence in this plan, canonical doc, Issue and Project before integration. No merge, live ingestion or deploy follows automatically.

## Gate handoff

Record: docs/agents/records/2026-11-05-bankone-cli-timeout-compatibility.json. Commit/push this docs-only checkpoint, pin the actual SHA externally, and require:

```sh
python3 scripts/autonomy/pre_implementation.py --record docs/agents/records/2026-11-05-bankone-cli-timeout-compatibility.json --base-sha <committed-checkpoint-sha>
```

Expected `{"status":"synchronized","errors":[]}`. Issue and Project source/status readback hashes are in the synchronized record. Coordinator owns exact-SHA implementation dispatch.

Issue: https://github.com/lucronn/autodata/issues/318
Project item: PVTI_lAHOCSJ8cc4BiQ2BzhGS3rE
Tracking readback: Issue body and Project Source/status Ready matched literally before checkpoint.

## Implementation and review evidence

The implementation milestone is `f15ce05bd29d0f5a0cceb9ab8f3642c6f73b268c`, after the synchronized gate at `1a3a33ccf707d2e7820f3abc72b12f86e5a06871`. Three focused tests first failed with the observed `timeout_seconds` constructor `TypeError`; after the one-keyword correction, all three passed. Ten Bankone batch regressions passed, `--help` retained the public flag, and `git diff --check` passed. Coordinator review of the exact two-file diff found no P1/P2 issue. The live bounded ingestion rerun and GitHub CI remain pending; this milestone does not claim production activation.
