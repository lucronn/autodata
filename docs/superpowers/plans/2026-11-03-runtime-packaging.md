# Disposable Codex runtime packaging remediation

Status: coordinator-reviewed and synchronized for a fresh committed-base preflight. Packaging and the retry begin only after that preflight. Scope is the explicitly authorized coordinator scratch Dockerfile/supervisor and disposable acceptance; no repository implementation change or production operation. Authentication bytes are never inspected or copied.

Issue: https://github.com/lucronn/autodata/issues/186  
Project: https://github.com/users/lucronn/projects/8  
Implementation integration: `f4d95680f721ce32f4d3cb2f8da0552ef1673750` (all eight reviewed candidate files unchanged;131 integrated tests pass).

## Concrete todo

- [ ] Preserve the actual missing-bubblewrap startup failure and synchronize this plan, Issue186, Project8 and canonical runtime evidence before a fresh committed-base preflight.
- [ ] Add only bubblewrap to the scratch Dockerfile package list, build a distinct image, and record its actual package/image/CLI versions offline without authentication.
- [ ] Preserve the nonroot read-only container, no added capabilities or privileges, exact Sol6.1 medium Fast profile, and strict rejection of every warning.
- [ ] Run one bounded success retry from the independently promoted adapter bytes in a fresh clone, retain actual protocol/decision evidence and independently replay at the original evidence root.
- [ ] Record pass or actual new blocking prerequisite without retry loops; unavailable-profile and interruption acceptance remain separate requirements.

## Evidence and scope

The reviewed adapter is f43508beedc4d5ccb1a29ed8e49912d5d6d55a49, independently verified with 131 passing autonomy tests. The first real trial is retained unchanged at `/tmp/autodata-appserver-success-6qkf9mga`. Its metadata records exit 20. The architect stdout at `payload/run/agents/architect/evidence/architect:stdout.bin` contains initialize response followed by `configWarning`: “Codex could not find bubblewrap on PATH. Install bubblewrap with your OS package manager. ... Codex will use the bundled bubblewrap in the meantime.” Matching stderr records the prerequisite error. There is no model/list, turn/start, inference, or builder execution in this attempt. Keep its failure status and all bytes.

`/tmp/autodata-runtime-container-v2/Dockerfile` uses node:22-bookworm-slim and installs python3, git and ca-certificates, then selects USER node. The actual current image is `autodata-runtime-fixture:codex-0.162.1-nonroot`, ID `sha256:5d664d80b32b8a2e4b40fea32dd1c6ae19c635d4eb0d18aac894e50b190459e4`. An offline, authentication-free run under `--network none --read-only --cap-drop ALL --security-opt no-new-privileges` confirms uid1000/node, no bwrap PATH entry, and `dpkg-query: no packages found matching bubblewrap`.

Official source pin remains rust-v0.162.1 / 092d3acd6bec3e3a14bdc7e7a2810ab628ab759d. The cached app-server source exposes ConfigWarningNotification/config_warnings propagation in `codex-rs/app-server/src/message_processor.rs`; the partial cache does not contain the sandboxing prerequisite implementation. Do not invent a source-line claim for the missing package test. The installed native 0.162.1 binary contains the exact observed warning text and recommends the OS package manager. Its strings also identify user-namespace prerequisites. This independently supports an environment prerequisite diagnosis, with the observed wire warning as primary evidence.

## Smallest correction

After the fresh gate passes, add only `bubblewrap` to the existing Debian apt package list in the scratch Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends python3 git ca-certificates bubblewrap && rm -rf /var/lib/apt/lists/*
```

Keep every other Dockerfile line unchanged. Build a distinct retained image tag; preserve the old image/build logs. Change only the scratch supervisor's IMAGE constant to the new tag. No repository adapter, reducer, allowlist, schema, task execution profile or application code changes are required by this missing-PATH finding. Package installation happens at image build time as the existing root build step; workload execution stays non-root.

Suggested coordinator commands after synchronization:

```sh
docker build --pull=false --progress plain \
  -t autodata-runtime-fixture:codex-0.162.1-nonroot-bwrap \
  /tmp/autodata-runtime-container-v2 \
  > /tmp/autodata-runtime-container-v2/build-bwrap.log 2>&1

docker image inspect autodata-runtime-fixture:codex-0.162.1-nonroot-bwrap \
  --format '{{.Id}} {{.Config.User}} {{.Config.WorkingDir}}'

docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  autodata-runtime-fixture:codex-0.162.1-nonroot-bwrap \
  sh -c 'test "$(id -u)" = 1000 && command -v bwrap && dpkg-query -W bubblewrap && bwrap --version'
```

Retain the actual Debian package version, new image ID, complete build log, effective nonsecret launch specification and offline command exits. Do not assume a package version from the host, which runs a different distribution. Verify the unchanged mounted Codex package with the existing offline `codex --version` procedure; require exactly codex-cli 0.162.1. This command must not initialize an app-server or mount authentication during offline checks. Syntax-check the scratch supervisor after changing IMAGE.

## Privileges and unresolved prerequisite behavior

No capability, privilege, seccomp, host-kernel or repository code change is justified or authorized by the current finding. Preserve USER node/uid1000, read-only root filesystem, `--cap-drop ALL`, `no-new-privileges`, resource limits, isolated writable evidence/tmp/home, read-only installed Codex, read-only root-owned boundary proof, no host sockets/published ports, truthful standard Docker bridge/unrestricted outbound network metadata, and only the already authorized read-only Codex authentication mount for the eventual trial. Do not inspect or copy authentication bytes.

A separate offline probe using the bundled bwrap (with no authentication mount and no Codex process) under these same security flags returned:

```text
bubblewrap built for Codex
bwrap: No permissions to create a new namespace, likely because the kernel does not allow non-privileged user namespaces.
```

The probe used `bwrap --unshare-user --unshare-net --ro-bind / / /bin/true` and exited 1. It establishes that this restricted container currently cannot create that nested namespace. It does not establish a requirement to grant privileges to this danger-full-access fixture, whose execution isolation is the outer disposable container. It also prevents claiming that installing the package guarantees app-server startup: the missing-PATH warning might expose a further namespace prerequisite warning. The exact follow-on startup check is unverified in the partial offline source cache.

Do not enable SYS_ADMIN, privileged mode, unconfined seccomp, additional capabilities, setuid privilege acquisition, host sysctl changes or a sandbox fallback. If the unchanged adapter reports a new prerequisite warning/error, preserve it and stop this remediation. Any alternative boundary requires its own reviewed design/checkpoint rather than being slipped into package installation.

## One bounded retry and acceptance

The coordinator first records this separate remediation goal/todo/evidence in the canonical plan/tracking checkpoint and passes the repository gate. Pin the exact retry SHA, confirm the reviewed f43508b adapter/runner/replay bytes are unchanged if the checkpoint adds only planning documents, and use the newly identified image. Make no in-place edits to the original failure evidence or its run metadata.

Run exactly one fresh success-case trial in a newly owned disposable clone/evidence directory through the existing trusted supervisor, with the newly selected image. Keep the exact gpt-6.1-sol / medium / Fast(priority), features.fast_mode=true and allow_fallback=false contract. Keep the 120-second provider bound and 400-second outer trial bound; one case attempt, no automatic retries, no extra trial batch. The existing supervisor watchdog/cleanup remains in force. Before writing proof, inspect the actual new container launch and namespaces exactly as before.

The adapter must continue rejecting every configWarning, including this one. No warning allowlist, notification suppression, profile substitution or invented metadata is permitted. Success requires genuine supported catalog data, resolved exact profile, matching clean completed turn(s), retained complete evidence and independent replay under the existing acceptance contract. Package presence or successful initialize alone is not certification. Report configured request tier separately from the unobserved upstream served/billed tier.

If startup remains blocked, report the actual new warning/error and inference count, retain all evidence and stop after this one attempt. If only some downstream calls complete before the outer bound, preserve the partial result without promoting it to full-chain success. Genuine-unavailable and interrupted-provider certification remain separate existing requirements; this packaging attempt does not silently count them as exercised.

## Synchronized coordinator record

```json
{
  "goal": "Correct the disposable Codex runtime missing-bubblewrap prerequisite without changing its reviewed adapter, requested profile or container isolation, then run one bounded success retry.",
  "plan_ref": "docs/superpowers/plans/2026-11-03-runtime-packaging.md",
  "issue_ref": "https://github.com/lucronn/autodata/issues/186",
  "project_ref": "https://github.com/users/lucronn/projects/8",
  "repository_doc_refs": [
    "docs/agents/runner-interface.md",
    "docs/verification/2026-11-03-agent-evidence-hardening.md",
    "docs/superpowers/plans/2026-11-03-production-release-orchestration.md"
  ],
  "todo": [
    "Preserve the actual missing-bubblewrap startup failure and synchronize this plan, Issue186, Project8 and canonical runtime evidence before a fresh committed-base preflight.",
    "Add only bubblewrap to the scratch Dockerfile package list, build a distinct image, and record its actual package/image/CLI versions offline without authentication.",
    "Preserve the nonroot read-only container, no added capabilities or privileges, exact Sol6.1 medium Fast profile, and strict rejection of every warning.",
    "Run one bounded success retry from the independently promoted adapter bytes in a fresh clone, retain actual protocol/decision evidence and independently replay at the original evidence root.",
    "Record pass or actual new blocking prerequisite without retry loops; unavailable-profile and interruption acceptance remain separate requirements."
  ],
  "status": "synchronized",
  "updated_at": "2026-11-03T11:08:22.298096+00:00"
}
```
