# Workshop SVG localization

Issue: https://github.com/lucronn/autodata/issues/419
Project: https://github.com/users/lucronn/projects/8
Plan: [bounded SVG localization](../superpowers/plans/2026-11-14-workshop-svg-localization.md)

Provider SVG illustrations currently fail capture as unsupported media. The planned consumer preserves exact private source bytes and derives bounded PNG images in an isolated subprocess. It rejects external references before rendering, blocks runtime resource fetches, limits CPU/memory/time/dimensions, and leaves unsupported images honestly unavailable. Both original and derivative remain linked in immutable provenance; only the PNG enters displayable image projection.

Concrete todo: add the pinned isolated rasterizer; retain original/derivative lineage and failure reasons; verify on synthetic input and strict required CI. No production capture, grants, supplier rights, customer access or external-tester display is authorized by this design. Existing customer/configuration grant and source-rights authority remains required. See [retained-reader evidence](https://github.com/lucronn/autodata/pull/418).

Upstream primary references checked 2026-11-14: [CairoSVG releases](https://github.com/Kozea/CairoSVG/releases/tag/2.9.1), [documentation](https://cairosvg.org/documentation/), and [security advisories](https://github.com/Kozea/CairoSVG/security/advisories). Version 2.9.1 is the inspected release; upstream safety defaults complement, but do not replace, application prevalidation and process bounds.

The initial conservative dry-run recovered 0/14 assets. The amendment permits validated embedded PNG/JPEG data through an exact per-render memory allowlist, and removes only tightly recognized standard W3C SVG external PUBLIC DOCTYPE declarations before defused parsing and serialization. Internal subsets/entities, external resource fetches and nested SVG data remain denied. See the plan for limits and repeat-acceptance requirements.

Runtime activation requires a separate ingestion image build and reviewed deployment containing CairoSVG 2.9.1, libcairo2 and fonts. The existing private ingestion image has none of the new renderer dependencies; a read-only source bind or the separate mount-only rollout cannot install them. Source merge alone is not runtime acceptance. Image deployment, authorized recapture and authenticated retained article/media browser acceptance remain blocked on their own release and supplier-rights gates.

The parent performs only bounded byte/timeout checks before process creation. All XML/CSS parsing and embedded image decoding occurs after child resource limits, and the child returns only PNG or an allowlisted fixed failure code. Verification receipts are recorded in [SVG localization evidence](../verification/2026-11-14-workshop-svg-localization.md).

## Protected-base integration checkpoint

Coordinator-authorized protected master: `92d81a1afbcf9e025d017b9b30f6dd4bb54f3e8a`, tree `0e4038a6bd506fd1349caa0bfa320813106ce5ad`, after protected merge of #417. Create this documentation-only checkpoint directly on that exact master, synchronize Issue #419/Project #8 and run the pinned machine preflight before integrating it into the reviewed SVG feature branch. Existing reviewed SVG implementation is `a021fcc50ed29b7ca61772f383f7c221ad2d08c5`; preserve its implementation files byte-for-byte while bringing in the current protected base.

Integration todo:
- Integrate exact protected master through this synchronized checkpoint while preserving reviewed SVG implementation.
- Run focused synthetic actual-image and fresh PostgreSQL/S3 lifecycle persistence checks after integration; run appropriate current-base suites.
- Push the integrated exact head and pass strict required CI; keep PR #422 draft for coordinator review and runtime image decision.

Hold all merges, serving changes, licensed/provider recapture and additional cleanup without concrete space need. Prior private 14/14 conversion evidence remains historical compatibility evidence; do not repeat provider reads as part of current-base verification. Source merge remains separate from image deployment, rights, grants and real authenticated browser acceptance.

## Protected #421 integration checkpoint

Protected master `5b3e19d3b34208773a77b4b9cfccd3085726cabe`, tree `92da3c0238725728e43a2bbd4df7a0ec29d02de6`, contains merged #421 after #417. This docs-only checkpoint is created directly on that exact base; synchronize Issue #419/Project #8 and pass pinned preflight before feature integration. Preserve reviewed SVG implementation from `a021fcc50ed29b7ca61772f383f7c221ad2d08c5`.

Current integration todo:
- Integrate this exact protected #421 base through the synchronized checkpoint; report conflicts and branch checkpoint.
- Run focused actual-image synthetic SVG and enabled isolated PostgreSQL/S3 lifecycle checks without provider calls or serving writes.
- Hold final review-head push and strict CI until coordinator supplies #415 protected merge; then synchronize the final current-base gate and verify once. Keep #422 draft and hold all merges/runtime activation/licensed recapture.
