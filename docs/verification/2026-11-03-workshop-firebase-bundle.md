# Firebase browser SDK packaging verification

The ten-path packaging milestone is independently verified at `2a226577efd70dab4924d38a8ab5745feb874b98`
and integrated as `2577383aa2ee3d149232f27f2b8deca019a715a5`. This delivers build assets;
Google popup behavior, application login/storage flow and live configuration
remain required in the separately gated customer UI/release work.

## Scope and evidence

The base is `3e9d06253bf747d69b21e4a8371daa742b0391f4`, with a synchronized
Issue186/Project8 record and passing exact-base preflight. Exactly the ten paths
in `docs/agents/tasks/2026-11-03-production-release/workshop-firebase-bundle.json`
changed; root independently compared every integrated file to candidate bytes.
Three builder commits are preserved: `503f0b7`, `e24f737`, `2a226577`.

- Official Firebase12.19.0 and esbuild0.28.2 are pinned in the complete lock.
  Public Firebase/auth archive SHA512 values were independently recomputed from
  retained public package-cache bytes and match the reviewed pins.
- The self-hosted ESM has exactly ten intended exports, no external module
  imports and no application initialization. SDK bytes are unchanged by the
  license repair:112641 bytes, SHA256
  `bd2f3d36daaecdb5556e601603bea4e80cd202fc515faa931b2b0c5d0f7344f1`.
- Build/check use owned external temporary directories; check mode preserves
  checkout inputs. Nineteen packaging checks cover clean install/check,
  repeated deterministic output, stale/changed/missing inputs and artifacts,
  embedded-license integrity, exports and missing native build tooling.
- Actual Go HTTP asset tests verify served MIME, bytes and provenance. Three
  adversarial HTTP cases prove matching altered provenance cannot hide missing
  or truncated full license terms. Existing14 Node helper tests also passed.
- Root independently ran `go test -count=1 ./...` at candidate (1.208s) and
  integrated source (1.156s). Builder full/focused Go tests also passed.
  Root build `--check`, exact scope, every provenance input/output size/hash and
  `git diff --check` passed. Ordinary Go tests do not execute required PG/browser
  acceptance absent their dedicated fixtures; those remain separately tracked.

## Independent review and repair

First review at `e24f737` found missing full Apache2.0 terms: extracted headers
and a license URL were present, but included Firebase packages had no top-level
license file for the original collector to append. The successor embeds the
complete official Apache text from https://www.apache.org/licenses/LICENSE-2.0.txt
(11358 bytes, SHA256
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`)
and records its source/integrity in provenance. Existing notices and the actual
idb ISC license are preserved byte-for-byte around the inserted Apache block.
An earlier review description called idb's license MIT; archive inspection
corrected it to ISC.

Independent successor review approved `2a226577efd70dab4924d38a8ab5745feb874b98` with no remaining
findings. Root initially assumed the complete previous legal asset was a prefix;
that check failed because the insertion precedes the unchanged ISC section.
The corrected check removes exactly the inserted block and reconstructs every
previous byte. The diagnostic and corrected receipt remain retained.

Retained local receipts (private machine paths, not durable CI artifacts):
`/tmp/autodata-firebase-bundle-verification.json`,
`/tmp/autodata-firebase-apache-http-verification.json`,
`/tmp/autodata-firebase-bundle-root-verification.json`,
`/tmp/autodata-firebase-bundle-independent-review.md` and
`/tmp/autodata-firebase-bundle-successor-review.md`.
Successor review SHA256:
`9190190b0960da8f7f8d12af2a8a9d67b93b735a1db280921b878bad833bccb3`.

## Remaining release evidence

Integrated GitHub CI [41700061868](https://github.com/lucronn/autodata/actions/runs/41700061868)
passed at `3114366d409f3fde98bdd921a8cc1ef6c4377d17`, including the actual live
Compose fast-lane smoke and Go/Python/contracts/development suites. Final UI work
must execute the actual bundled SDK popup/storage behavior,120 DTO/browser and21
actual API/browser cases, plus production image asset proof. No live Firebase,
Stripe, cloud resource, customer data or DNS operation occurred in this milestone.
