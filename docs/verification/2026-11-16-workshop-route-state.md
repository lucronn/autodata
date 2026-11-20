# Workshop route state verification

Issue: https://github.com/lucronn/autodata/issues/446
Parent: https://github.com/lucronn/autodata/issues/398
Related search: https://github.com/lucronn/autodata/issues/393
Project: https://github.com/users/lucronn/projects/8

## Gate and implementation

Planning checkpoint `2c90eff82a95b6ee58e68f42b0100d62c3dee45d` was committed and pushed before application edits. Machine preflight at that checkpoint returned `status: synchronized`, `errors: []`. Issue #446 and its Project #8 item contain the plan, canonical architecture link and concrete todo; the item was In Progress before implementation.

The change resets selector rows/options, query and vehicle/quote context at route restoration before its direct configuration, library, order or hierarchical branch. Explicit URL q is restored for direct article and hierarchical links. Hierarchical routes repopulate their saved choices. My vehicles activation clears the previous search and selector options before creating the new exact configuration/region URL.

## Regressions and checks

Before implementation, six focused actual-production-function regressions failed: direct article URL without q retained an old query; explicit direct URL q was ignored; library and order routes retained old vehicle context; partial hierarchy routes left stale enabled descendants; My vehicles activation retained an old search. The saved full hierarchy control passed before and after.

After implementation, the complete client/demo suites pass **314 tests, zero failures/skips**. The harness executes the production populate, restoreRoute and library activation functions and existing payment lifecycle tests execute production selector resets. JS syntax checks and git diff --check pass. An optional full `go test ./...` was interrupted at coordinator request when physical home free space fell; it did not pass and is not claimed as validation.

Existing anonymous desktop1440/mobile390 screenshots and their README were inspected. They cover the initial responsive shell with synthetic empty years and do not exercise these account/article/library paths. This change has no visual layout edits. No new live browser, identity, entitlement, article, payment or runtime acceptance is claimed. No deployment or authenticated/provider/Stripe call was performed.

## Modern Web Guidance

I searched asynchronous-request guidance and checked the accessibility guide; neither specified a new browser pattern for this route-state correction, so no guide-specific code change was applied. Existing native selects, labels and navigation-generation behavior are retained.
