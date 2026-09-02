# AutoData Autonomous Development System

## Purpose and authority

This system coordinates specialized agents to take a repository task from Issue to verified merge and ephemeral/dev deployment without a person approving intermediate steps. Its safety comes from deterministic checks, independent review agents, immutable evidence, and explicit failure states.

The initial authority boundary is:

- Agents may plan, implement, test, review, create pull requests, merge passing pull requests, update the GitHub Project, and deploy to ephemeral/dev environments.
- Agents may not deploy production, change production credentials, disable required checks, force-push protected branches, delete canonical data, or bypass a failed gate.
- A blocked task is a safe terminal state. Agents retry or use an alternate reviewer, but they do not force progress through contradictory evidence.

## Topology

```text
Issue / Project item / scheduled maintenance
                         |
                         v
                 autonomy-orchestrator
          plan, decompose, assign, correlate
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
    architect        builders          source/data
    contracts       isolated branch    provenance
        |                |                |
        +----------------+----------------+
                         |
                         v
                 independent verifiers
          tests / schema / quality / security
                         |
                         v
                  release controller
             PR / Project / merge / dev deploy
                         |
                         v
                   evidence bundle
```

The orchestrator owns state and evidence, not code correctness. Builders own implementation changes in isolated worktrees. Verifiers are read-only against the implementation branch except for test fixtures or reports in their own branches. The release controller is the only agent allowed to merge, and it can do so only when the machine gate expression in [data-integrity-gates.md](data-integrity-gates.md) evaluates to pass. The provider-neutral boundary for invoking these prompts is documented in [runner-interface.md](runner-interface.md).

## Agent roster

| Agent | Primary responsibility | Write scope | Gate role |
| --- | --- | --- | --- |
| `autodata-orchestrator` | Decompose tasks, coordinate runs, collect evidence | Run metadata and task state | Controls transitions |
| `autodata-architect` | Produce contracts, ADRs, acceptance criteria | Design/contract branch | Blocks ambiguous design |
| `autodata-go-builder` | Implement Go API/auth/projection behavior | Isolated implementation branch | None |
| `autodata-python-builder` | Implement ingestion/enrichment workers | Isolated implementation branch | None |
| `autodata-schema-agent` | Validate migrations and relational invariants | Schema branch/reports | Schema gate |
| `autodata-source-agent` | Validate source adapters and provenance | Source fixtures/reports | Source gate |
| `autodata-data-quality-agent` | Validate completeness, evidence, units, applicability | Quality fixtures/reports | Data-quality gate |
| `autodata-test-agent` | Add and execute deterministic test coverage | Test branch/reports | Test gate |
| `autodata-security-agent` | Check secrets, auth, webhooks, unsafe access | Reports only | Security gate |
| `autodata-reliability-agent` | Check idempotency, retries, replay, DLQs | Recovery tests/reports | Reliability gate |
| `autodata-review-agent` | Independently review the complete change | Reports only | Independent review gate |
| `autodata-release-agent` | Create/update PR, merge, Project, dev deployment | PR/Project/dev state | Executes only passed gates |

## Run lifecycle

1. The orchestrator claims an Issue or scheduled task using a unique `run_id`.
2. The architect emits a task contract with affected bounded contexts, interfaces, acceptance tests, and forbidden scope.
3. The orchestrator creates isolated implementation work and assigns one or more builders.
4. Builders implement only the task contract and record commands, changed paths, and outputs.
5. Schema, source, data-quality, test, security, reliability, and independent-review agents run in parallel when their inputs are available.
6. The orchestrator merges reports into one evidence bundle without changing their decisions.
7. The release agent evaluates deterministic policy and all independent decisions.
8. A passing run creates/updates the PR, updates the GitHub Project, merges with the exact head SHA, and deploys to ephemeral/dev.
9. A failed run retries within policy. Exhaustion creates a dead-letter record and leaves the task blocked; no merge occurs.

## No-human operating rule

No step waits for a person to click approve. Instead, every transition has a machine predicate and evidence requirement. The system may automatically retry with a different model or agent when disagreement is detected. Persistent disagreement, missing provenance, unsafe migration behavior, or insufficient test evidence is a blocked outcome, not permission to lower a threshold.

## Isolation and concurrency

- One builder owns a task branch/worktree at a time.
- Independent read-only verifiers may inspect the same candidate concurrently.
- Schema migrations are serialized per branch and tested from both clean and upgraded databases.
- A release decision is pinned to one exact implementation SHA; stale reports cannot be combined with a newer head.
- Agent prompts must not receive secrets, production data, or unrestricted GitHub tokens.
- The orchestrator must use least-privilege credentials and record the capability used for each external action.

## Required evidence

Each run produces a manifest, task contract, changed-path list, command output references, test results, quality report, security report, reliability report, independent review, and final decision. Evidence is content-addressed or tied to an exact commit SHA. The manifest format and decision vocabulary are defined in [agent-contracts.md](agent-contracts.md).
