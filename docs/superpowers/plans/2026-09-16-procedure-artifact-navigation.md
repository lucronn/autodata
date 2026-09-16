# Procedure artifact navigation and formatting

**Issue:** https://github.com/lucronn/autodata/issues/101

**Project:** https://github.com/users/lucronn/projects/8

## Goal

Make the complete procedure artifacts easy to read from the dashboard. A user
selecting the HTML or PDF procedure must get a formatted document in a new
browser tab/window, not an automatic file download or a replacement of the
chatbot page.

## Root cause

The dashboard anchors use the HTML `download` attribute, and both Go proxy
handlers return `Content-Disposition: attachment`. Those two signals force a
download even though the user needs to inspect the rendered procedure. The
HTML renderer already emits a standalone, self-contained document with the
source-authored procedure and embedded figures; this task changes delivery and
navigation semantics without changing its content.

## Scope and decisions

- Change the dashboard HTML and PDF actions to explicit “open complete guide”
  links with `target="_blank"` and `rel="noopener noreferrer"`.
- Remove the dashboard `download` attributes so the browser can render the
  document in the new tab/window.
- Return `Content-Disposition: inline` for authorized HTML and PDF guide
  responses while preserving the existing content types, authorization,
  immutable revision, and cache policy.
- Keep the dashboard’s compact procedure and quote output unchanged; the
  complete artifact remains the detailed view for source-authored formatting,
  figures, warnings, evidence, and all steps.
- Add regression tests for the markup and response headers, then exercise the
  exact action in the live dashboard and inspect the opened artifact.

## Concrete todo

- [x] Update the dashboard links and dynamic link binding for new-tab rendering.
- [x] Change guide response disposition from attachment to inline.
- [x] Add focused regression coverage for navigation and content disposition.
- [x] Rebuild the local API, run the relevant test suites, and verify the
      formatted procedure is rendered by the live dashboard with the new-tab
      actions present. The in-app browser security policy blocked the final
      cross-tab navigation click, so the authenticated inline artifact was
      additionally verified over HTTP.
- [ ] Synchronize the implementation SHA, Issue #101, Project #8, and CI
      evidence after the implementation commit is pushed.

## Verification note

The rebuilt local API passed its health and readiness checks. The live browser
dashboard rendered the selected 1997 Toyota RAV4 4-door 4WD 2L request with 99
source-authored steps, the unreviewed label, and HTML/PDF actions labeled to
open in a new window. The authenticated HTML artifact returned HTTP 200 with
`Content-Disposition: inline`, retained its formatted title and vehicle
content, and contained 80 embedded image payloads. The Codex in-app browser
blocked the final cross-tab navigation action by policy; this was recorded as
a harness limitation rather than treated as successful tab inspection.

## Acceptance criteria

- The dashboard visibly labels HTML and PDF actions as opening the complete
  guide in a new tab/window.
- Clicking either action leaves the chatbot page available and opens a
  rendered artifact with its title, vehicle applicability, ordered procedure,
  and source-authored content intact.
- HTML remains standalone with embedded images; PDF remains revision-matched.
- No download attribute or attachment disposition forces a file save.
- Existing authorization, review labels, source watermark, and unavailable
  artifact behavior remain unchanged.
