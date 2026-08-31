# Oscillink Project Memory

**Install once. Preserve corrected, cited project history across compatible AI coding
agents. Survive compaction, switch clients, and inspect why context was selected.**

Oscillink is an open-source, local-first continuity and control layer for long-running AI
agents. Project Memory is its first product: one governed project history that does not make
a model provider, transcript, filename, or vector database the source of truth.

> **Status:** `v0.2.0-alpha` research and private-pilot software. External-user validation is
> still required. Do not use it to control robots, industrial equipment, or other
> safety-critical systems.

## See corrected continuity in under five minutes

After cloning this repository, run one command:

```bash
PYTHONPATH= uv run --locked python scripts/run_project_memory_demo.py \
  --data-root .oscillink-demo
```

The pinned demo starts Agent A in one MCP client process, ends it, applies an externally
governed correction, and starts Agent B in a fresh process with no transcript replay. Its JSON
report shows:

- current corrected project decisions and a recorded failed approach;
- exact revision/content-hash citations and correction lineage;
- deterministic token cost, omissions, and authority exclusions;
- distinct Agent A, governance, and Agent B process identities; and
- elapsed time below five minutes.

It runs locally over stdio, opens no network port, and needs no account or model credential.
Read the full [Project Memory quickstart](docs/project-memory-quickstart.md) and
[pinned demo contract](examples/project-memory-demo/README.md).

## What Project Memory changes

| Common failure | Project Memory boundary |
| --- | --- |
| Decisions disappear after compaction | Approved revisions persist outside the transcript |
| A correction competes with stale memory | Exact replacement lineage supersedes the old revision |
| Retrieved text is treated as trusted | Memory content remains untrusted and cannot grant authority |
| Each client owns a separate history | Compatible clients use one model-neutral MCP sidecar |
| Context cost and provenance are opaque | Every recall returns a deterministic cited context manifest |
| Agent writes silently become truth | Writes create candidates; external governance controls approval |

The operating principle is **autonomous by default, governed by exception, and reversible at
all times**. Routine low-risk maintenance should not require constant review; corrections,
conflicts, consequential changes, and permissions remain inspectable and recoverable.

## Run the real MCP sidecar

Choose one persistent data root for a real project:

```bash
PYTHONPATH= uv run --locked oscillink-project-memory \
  --data-root /absolute/path/to/project/.oscillink-memory
```

Configure a compatible MCP client to launch that command over stdio. The server exposes
exactly four tools:

- `recall` — deterministic approved-only context with citations, budget, omissions, and
  exclusion counts;
- `explain` — exact revision inclusion/exclusion and correction lineage;
- `remember` — idempotent provenance-bearing **candidate** creation; and
- `correct` — exact-revision replacement **candidate** creation.

Clients cannot approve, reject, promote, or supersede memory. The server-bound data root and
actor identity cannot be changed by a tool request. See the strict
[Project Memory MCP contract](docs/project-memory-contract.md).

## Verified compatibility—not a broad claim

The following paths have been exercised directly with synthetic public data:

- official Python MCP client over real stdio subprocesses;
- Hermes native MCP discovery of all four tools;
- OpenCode 1.18.25 recall and current-revision explain; and
- a separately delegated Hermes Agent B continuing from MCP evidence alone.

Codex, Claude Code, Cline, Cursor, and other clients remain unclaimed until each path is
tested directly. The deterministic independent-process harness is the timed artifact;
exploratory model runs are not counted toward the five-minute claim.

## Current foundation

The implemented alpha includes:

- product-owned memory identities and immutable revisions;
- append-only approve/reject/supersede decisions and restart reconstruction;
- approved-only deterministic retrieval and persisted `ContextManifest` evidence;
- provider-neutral chat with revision-bound citations and inspectable run trajectories;
- typed, scoped, expiring capability grants for one bounded `file.read` path;
- content-addressed artifacts and governed imports/proposals;
- versioned workspace export, integrity verification, atomic restore, and rollback;
- equal-budget longitudinal public evaluation; and
- an authenticated browser Evidence workspace for evaluation and recovery manifests.

Obsidian is an optional connector, not canonical authority. Browser terminal execution,
semantic/vector retrieval, cloud synchronization, broad multi-agent orchestration, training,
and physical control remain deferred behind evidence and safety gates.

## Evidence and validation

- [Browser evaluation and recovery evidence](docs/browser-evidence.md)
- [Community/external-user validation protocol](docs/community-validation.md)
- [Open-source and commercial boundary](docs/open-source-boundary.md)
- [Workspace recovery contract](docs/workspace-recovery.md)
- [Advanced private-pilot runbook](docs/private-pilot-runbook.md)
- [Product description](docs/product-description.md)
- [Implementation plan](docs/build-plan.md)

Current promotion requires at least five external users on their own projects, with measured
setup, supervision, correction, cleanup, and recovery time. Demonstrations, stars, funding
announcements, and model self-report are not treated as product evidence.

## Development

Prerequisites are Python 3.11, `uv`, Node.js, and npm. Install locked dependencies:

```bash
uv sync --locked --dev
npm --prefix apps/web ci
```

Run the complete deterministic candidate gate:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
```

The verifier runs pytest, Ruff, strict mypy, frontend tests/typecheck/build, npm audit, schema
validation, LF checks, a deterministic diff review, and security scans. See
[CONTRIBUTING.md](CONTRIBUTING.md) before changing contracts, fixtures, schemas, or
compatibility claims.

## Safety, community, and license

- Retrieved content and model output cannot create or expand permissions.
- No unrestricted browser shell, arbitrary host execution, self-promotion, or robot control.
- Report vulnerabilities through the private-first process in [SECURITY.md](SECURITY.md).
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md) in project spaces.

Oscillink Agent is licensed under the [Apache License 2.0](LICENSE). The local continuity,
provenance, correction, evaluation, and adapter foundation is intended to remain useful
without a mandatory account. Expected commercial layers are encrypted synchronization,
hosted reliability, team coordination, managed connectors, enterprise deployment, audit,
policy administration, and support—not marked-up model inference.