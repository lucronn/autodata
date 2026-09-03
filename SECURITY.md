# Security policy

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/lucronn/autodata/security/advisories/new)
for vulnerabilities, exposed secrets, authentication or authorization bypasses,
privacy issues, and source-rights concerns. Public issues and pull requests are
not appropriate for sensitive reports.

Please include a concise impact description, affected commit or component,
safe reproduction context, and any suggested containment. Do not include credentials,
access tokens, private source payloads, personal data, or exploit details that
would enable abuse. If evidence is sensitive, refer to it by a safe identifier
and submit the details through the private channel.

## Response and disclosure

The maintainer will acknowledge a private report, reproduce it using the least
data necessary, assess severity, and coordinate remediation and disclosure
through the private advisory. Do not publish a fix or exploit before the
maintainer confirms that coordinated disclosure is safe.

## Development security requirements

- Secrets belong in environment or secret-manager interfaces and must never be
  committed to the repository, fixtures, logs, issue forms, or examples.
- Source ingestion preserves attribution, terms metadata, content hashes,
  retention rules, and takedown handling.
- Access-control, entitlement, webhook, and payment changes require explicit
  security and audit verification.
