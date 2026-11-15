# Workshop SVG localization

Issue: https://github.com/lucronn/autodata/issues/419
Project: https://github.com/users/lucronn/projects/8
Plan: [bounded SVG localization](../superpowers/plans/2026-11-14-workshop-svg-localization.md)

Provider SVG illustrations currently fail capture as unsupported media. The planned consumer preserves exact private source bytes and derives bounded PNG images in an isolated subprocess. It rejects external references before rendering, blocks runtime resource fetches, limits CPU/memory/time/dimensions, and leaves unsupported images honestly unavailable. Both original and derivative remain linked in immutable provenance; only the PNG enters displayable image projection.

Concrete todo: add the pinned isolated rasterizer; retain original/derivative lineage and failure reasons; verify on synthetic input and strict required CI. No production capture, grants, supplier rights, customer access or external-tester display is authorized by this design. Existing customer/configuration grant and source-rights authority remains required. See [retained-reader evidence](../verification/2026-11-14-workshop-retained-reader-acceptance.md) when available on the integrated branch.

Upstream primary references checked 2026-11-14: [CairoSVG releases](https://github.com/Kozea/CairoSVG/releases/tag/2.9.1), [documentation](https://cairosvg.org/documentation/), and [security advisories](https://github.com/Kozea/CairoSVG/security/advisories). Version 2.9.1 is the inspected release; upstream safety defaults complement, but do not replace, application prevalidation and process bounds.

The initial conservative dry-run recovered 0/14 assets. The amendment permits validated embedded PNG/JPEG data through an exact per-render memory allowlist, and removes only tightly recognized standard W3C SVG external PUBLIC DOCTYPE declarations before defused parsing and serialization. Internal subsets/entities, external resource fetches and nested SVG data remain denied. See the plan for limits and repeat-acceptance requirements.
