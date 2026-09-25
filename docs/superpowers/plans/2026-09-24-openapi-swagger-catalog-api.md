# OpenAPI and Swagger documentation for the catalog API

Issue: https://github.com/lucronn/autodata/issues/113
Project: https://github.com/users/lucronn/projects/8

## Goal

Publish a comprehensive OpenAPI 3.0 contract for AutoData's provider-neutral
catalog API and serve an interactive Swagger UI with usable prefilled examples.
The contract must describe authentication, the complete vehicle selection
cascade, normalized article responses, source provenance behavior, and common
error responses without exposing immutable source originals.

## Todo

- Add the checked-in OpenAPI document with schemas, security, parameters,
  responses, and prefilled cascade/article examples.
- Serve the document and Swagger UI from the API's same-origin public surface.
- Add tests for the document route, UI route, and contract markers.
- Verify the live document parses and the documented examples match the live
  catalog endpoints.

## Boundaries

- Documentation routes are read-only and retain the existing API auth boundary
  for data endpoints.
- Swagger UI uses a pinned local distribution so the developer dashboard does
  not depend on a third-party CDN.
- The OpenAPI contract documents the public catalog surface; internal worker
  endpoints and disabled chatbot routes remain excluded.
