# Bankone and Banktwo domain routing

## Intended ownership

AutoData is configured to call each bank at its own direct origin:

| Consumer setting | Local default | Intended service owner |
| --- | --- | --- |
| `BANKONE_BASE_URL` | `https://bankone.cars.tk` | Bankone project and [`lucronn/bankone`](https://github.com/lucronn/bankone) |
| `BANKTWO_BASE_URL` | `https://banktwo.cars.tk` | Banktwo project and [`lucronn/banktwo`](https://github.com/lucronn/banktwo) |

AutoData's defaults appear in `.env.example`, `infra/compose/compose.yaml`, and
`infra/k8s/base.yaml`. Each setting can be overridden separately, for example
to point local development at a service checkout. Each origin serves the
Source Connector v1 API below `/v1` and defines `/healthz` and `/readyz` in the
shared OpenAPI contract.

The current target has no `cars.tk/bankone` or `cars.tk/banktwo` path router,
no Banktwo-hosted Bankone rewrite, and no shared credential-forwarding proxy.
Older documents describing Banktwo as owner of the `cars.tk` apex or these
shared routes describe a superseded routing proposal. The desired ownership is
direct and independent; it does not itself prove that a domain is attached.

## Current deployment status

Only local configuration and repository state were inspected for this
architecture document. No live DNS lookup, Vercel project inspection, deploy,
TLS check, remote health probe, credential/auth check, release, or bank canary
was performed. Therefore the following are **pending**:

- Public DNS ownership and delegation for both subdomains.
- Vercel project attachment, including confirmation that neither bank depends
  on the `cars.tk` apex being owned by the other.
- Issued and valid TLS for each direct origin.
- Live `/healthz`, `/readyz`, and authenticated API behavior.
- Independent Bankone and Banktwo deployments, canaries, and releases.

Do not describe either configured hostname as a live service until those checks
are recorded against the deployed projects. Contract routes in
`packages/contracts/source-connector/v1/openapi.yaml` define the interface,
not the state of public DNS or deployments.

## Local references

- Runtime defaults and optional token names: `BANKONE_BASE_URL`,
  `BANKTWO_BASE_URL`, `BANKONE_API_TOKEN`, and `BANKTWO_API_TOKEN`.
- Contract: [`source-connector-api-compatibility.md`](source-connector-api-compatibility.md).
- Component ownership and persistence boundary:
  [`independent-bank-connectors.md`](independent-bank-connectors.md).
- Accepted design and deployment sequence:
  [`2026-10-08-independent-bank-connectors-design.md`](../superpowers/specs/2026-10-08-independent-bank-connectors-design.md)
  and [`2026-10-08-independent-bank-connectors.md`](../superpowers/plans/2026-10-08-independent-bank-connectors.md).
