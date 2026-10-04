# Workshop interface

The consumer interface lives at `/workshop/` beside the administrative dashboard and Swagger. It is a plain HTML, CSS, and JavaScript client of the provider-neutral catalog API. It owns no ingestion or procedure rewriting.

The user selects year, make, model, and engine/trim, then searches the returned article index and opens an article. The browser uses returned identifiers and preserves procedure order and image associations. Catalog hydration is represented as a bounded waiting state; failed and empty reads offer recovery. Changing a parent selection invalidates dependent choices and outstanding reads.

The visual direction combines native selects, underlined article links, thin structural rules, locally served Instrument Sans, and a restrained mechanical masthead. The reader supports back navigation, reloadable article links, printing, keyboard use, reduced motion, and mobile screens. Stored body text is the fallback when a legacy record lacks usable structured steps; missing images are not invented.

Tracking: https://github.com/lucronn/autodata/issues/113 in https://github.com/users/lucronn/projects/8.
Plan: `docs/superpowers/plans/2026-09-25-workshop-interface.md`.

Todo: standalone layout/route; cancellable catalog and article workflow; focused regression tests and live browser verification.
