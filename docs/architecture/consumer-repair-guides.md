# Consumer repair-guide contract

Issue: https://github.com/lucronn/autodata/issues/89
Project: https://github.com/users/lucronn/projects/8
Plan: ../superpowers/plans/2026-09-14-consumer-repair-guides.md

AutoData returns an illustrated DIY guide in chat and a matching PDF when required content is complete. Both providers contribute vehicle-matched evidence. Retrieve supporting removal, installation, specifications, sealing, timing, fluids and checks rather than replacing them with generic instructions. Shared work is consolidated by mechanical prerequisites. Model-generated wording cannot create unsupported specifications or discard warnings. The consumer view omits sourcing/generation commentary; provenance and review status remain internal data and the existing review notice remains visible. Completeness does not imply technician approval.

The additive guide answer includes revision, applicability, preparation, ordered phases/steps, figure associations, torque references, completion state and actionable gaps. Existing procedure/quote consumers remain compatible. Previews cannot produce final PDF downloads. Authorized downloads represent exactly the displayed immutable revision, including its images. Provider or media failures remain visible gaps, not fabricated completions.

Delivery status: the bounded second-provider connector, dependency-aware guide
composition, revision-matched PDF renderer, and authenticated delivery path are
implemented. Live acceptance for the 1997 RAV4 oil-pump plus water-pump job
returned a complete 99-step guide with 80 associated figures; the PDF rendered
to 61 pages with 80 embedded image objects, and a warm replay returned the
identical PDF from the revision cache. Additional live chat and PDF acceptance
also passed for a 2005 Toyota Camry starter (14 steps, 4 figures, 5-page PDF),
a 2010 Subaru Forester 2.5L SOHC water pump (87 steps, 36 figures, 36-image
source coverage), and a 2002 Honda Civic LX front brake caliper (14 steps, 5
figures, 4-page PDF). The Forester test exercised the explicit engine-variant
selection flow. The consumer reviewer also exercised a valid RAV4 battery
request with no returned procedure article: it resolved the vehicle, withheld
the PDF, and recorded the expected fail-closed result without creating an
issue.

## Current implementation notes

The chat path uses AutoAPI Two vehicle search to resolve exact body and
drivetrain variants, then retrieves vehicle-scoped removal and installation
pages plus timing-belt prerequisites when required by the pump job. Ordered
HTML text and returned figures are converted into grouped consumer steps; the
installation instructions remain separate from removal and retain their
sealing, torque, timing, refill, and final-check details. A complete guide is
served as a revision-keyed PDF through the authenticated Go API proxy.
