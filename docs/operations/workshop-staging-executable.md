# Executable Workshop staging release path

Status: synchronized planning checkpoint; no implementation or runtime apply on this planning turn.
Issue https://github.com/lucronn/autodata/issues/312, child of #186; Project https://github.com/users/lucronn/projects/8.
Canonical plan: `docs/superpowers/plans/2026-11-05-workshop-staging-executable.md`.

The delivery has two disjoint implementation lanes: real authenticated publication through the existing v3 validators and fixed staging orchestration through existing host helpers. It adds no simulated release authority. The concrete accepted-material source is the staging candidate/finalize workflow followed by a separate post-run verify-publication CLI process that re-fetches immutable artifacts and signature evidence. Independent owner acceptance binds that actual verification receipt and exact archive/manifest before host_install can consume them.

The registry verifier must accept actual production OCI layers above 4 MiB without loading unbounded blobs into memory. It streams and hashes original bytes under explicit limits and deadlines, checks each descriptor's digest and size, and retains the existing v3 publication acceptance contract. A supplied digest or inventory claim never substitutes for downloaded-byte verification.

Operator order is bootstrap → provision-check → provision → install → images → database → private → start → check. Each phase is a separate explicit invocation under the existing owner approval contract. The operator uses IAP/OS Login with accepted instance ID and SSH host key, finite commands and fixed destinations. Host helpers remain authoritative for disk/package/mount/guard, image identities, scoped roles/schema, secret installation and actual readiness. A disposable Debian12 VM must establish real package/systemd/device/reboot behavior before staging application. Local PG17 and fake command cases alone do not prove deployment.

Bootstrap creation is separately approved against its fixed project, instance name, resource nonce, cost and region. The numeric Compute instance ID cannot be known before creation, so the bootstrap receipt records it as unaccepted evidence. An independent owner acceptance must bind that returned ID into the operator config before any later host/IAP phase can acquire credentials or act.

The private step is invoked once per service in the fixed api, ingestion-http, article-worker, payment-reconciler, outbox-relay order. Each invocation consumes the next independently delivered service-specific approval and opaque stdin frames. The operator does not rotate or manufacture approvals; start is unavailable until all five actual private-material receipts pass.

Required runtime owner values: confirmed project (vehapi-torque is only a candidate), region/zone, monthly budget, distinct staging origin, numeric GitHub IDs/protected environment, WIF/principal/IAM, registry and immutable toolchain pins, independent trust/approver material, exact owner/device/offline-package approvals and secret-version inputs. Null/unresolved configuration fails before credentials or mutations. These omissions block runtime application, not implementation of the declared code scope. Production origins/config are denied.

Implementation acceptance includes real CLI/HTTP/process/cryptographic/ZIP tests, unchanged authenticated-v3 validators, full host/PG17 tests, independent exact-SHA review and the disposable-VM sequence. Deployment acceptance additionally requires real protected publication and actual same-source host start/check plus HTTPS healthz/readyz. Missing runtime evidence must remain explicitly blocked. Production cars.tk, $20 permanent vehicle access, DNS, live payments, provider acceptance and production promotion retain their separate existing gates.

## Concrete todo
- [ ] Implement the authenticated publisher CLI and real bounded build/sign/registry/GitHub/upload dependencies, preserving existing v3 validators.
- [ ] Install a reproducible pinned publisher toolchain and activate only the two protected staging workflow jobs.
- [ ] Implement the fixed staging operator and acceptance-material handoff using existing host helpers, with per-phase owner approvals and no arbitrary remote command.
- [ ] Prove real publication and disposable Debian12/PG17 host deployment through readyz; retain failures and independent exact-SHA review before staging application.
