# AutoData

AutoData turns heterogeneous automotive source resources into evidence-backed,
vehicle-specific dataset projections. A fast lane publishes the minimum useful
view quickly; a deep lane enriches it with procedures, diagnostics, images,
diagrams, search, embeddings, and quality review.

## Start here

- [Architecture](Architecture)
- [Getting Started](Getting-Started)
- [Contributing](Contributing)
- [Repository README](https://github.com/lucronn/autodata#readme)
- [Canonical documentation](https://github.com/lucronn/autodata/tree/master/docs)

## Illustrated repair guides

Describe the exact vehicle and repair in chat. AutoData can combine its
existing catalog with the read-only [AutoAPI Two repair-content API](https://autoapitwo.vercel.app/docs)
to produce a vehicle-matched DIY guide with access, removal, reassembly,
installation, torque values, timing, fluids, final checks, and step-specific
figures. A complete guide can be downloaded as the same immutable PDF revision
shown in chat. Missing required content remains a preview and does not produce
a final PDF.

## Current boundary

The deterministic local path uses PostgreSQL with pgvector, NATS JetStream,
MinIO, fake source data, and a fake payment provider. It is the supported
credential-free development path. A generated procedure or source-derived
result is `UNREVIEWED` until authorized human review changes its status.

The current development slice and remaining source-evidence follow-ups are
tracked in [Issue #85](https://github.com/lucronn/autodata/issues/85), while
illustrated repair guides are tracked in
[Issue #89](https://github.com/lucronn/autodata/issues/89).

## Source of truth

This Wiki is a public-facing navigation layer. Normative architecture,
lifecycle, contract, infrastructure, governance, and agent-policy content lives
in the repository's [`docs/`](https://github.com/lucronn/autodata/tree/master/docs)
tree at the exact verified commit. When a Wiki summary differs from the
repository documentation, the repository documentation wins.
