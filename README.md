# Oscillink Agent

**Time Machine for AI Agents: preserve context, survive compaction, switch models, and
rewind mistakes.**

Oscillink Agent is an open-source, local-first continuity and control layer for
long-running AI agents. Its first product direction is **Oscillink Project Memory**:
one corrected, cited project history that compatible coding agents can share without
making a model provider, transcript, filename, or vector database the source of truth.

The existing alpha provides the governed foundation: immutable memory revisions,
approved-only deterministic context, provenance-bearing citations, bounded capabilities,
inspectable runs, reproducible evaluation, and versioned workspace recovery. A local
read-only MCP stdio server now implements `recall` and `explain` and is exercised with the
official Python MCP client. The `remember` and `correct` contracts exist but are not yet
advertised by the server.

> **Current status:** alpha research and private-pilot software. Do not use it to control
> robots, industrial equipment, or other safety-critical systems.

## What Project Memory is intended to solve

- **Fragmented continuity:** decisions and corrections are scattered across transcripts, prompts, files, vector stores and provider-specific memory.
- **Opaque or poisoned memory:** retrieved and generated text is often treated as trusted merely because it exists.
- **Irreproducible behavior:** teams cannot reconstruct which memory revisions, retrieval policy, model configuration, tools and budgets produced an answer.
- **Provider and connector lock-in:** paths, note applications and model vendors become accidental identity and authority systems.
- **Unsafe actions:** agents receive broad credentials, filesystem access or shell authority to perform narrow tasks.
- **Weak recovery:** export, deletion, rollback and restore are rarely complete product contracts.

Oscillink answers these problems with stable product-owned memory identities, immutable
revisions, explicit authority states, provenance-bearing retrieval, deterministic context
manifests, interchangeable providers, typed capability grants, and replayable run history.
Governance is intended to be **autonomous by default, governed by exception, and
reversible at all times**: routine low-risk maintenance should not require constant human
approval, while conflicts and consequential changes remain inspectable and recoverable.

The complete product description is in
[`docs/product-description.md`](docs/product-description.md).

## Current maturity

Oscillink Agent is a governed-agent `v0.2.0-alpha` research release candidate. The
browser-complete governed-memory journey, crash-safe provider/tool trajectory,
and versioned workspace recovery path are executable from an empty data root.
The deterministic longitudinal public evaluation harness is also implemented. The
active product milestone is to expose this foundation through a local Project Memory
sidecar and prove corrected continuity across two independently exercised agent clients.

The current foundation includes immutable domain contracts, an append-only SQLite ledger, content-addressed artifacts, governed file imports, product-owned `mem_` identities and immutable revisions, append-only approval/rejection/supersession decisions, native memory creation without Obsidian, restart recovery, and atomic idempotent Obsidian synchronization that preserves product identity across unambiguous source renames while marking disappeared sources as missing. The authenticated browser exposes that synchronization only as an explicit confirmed action and reports durable created/revised/unchanged/missing/issue accounting without revealing the configured source path. The typed Memory Lattice projects candidate, curated, approved, rejected and superseded records with visible source provenance and browser approve/reject controls. The unified web workspace places explicit memory associations inside named System Architecture containers, opens governed record details from each container, incorporates the agent face into Chat, and presents the execution-locked Workspace Terminal as a Chat drawer. Obsidian remains an optional connector rather than the canonical product database or review authority.

The authenticated browser enumerates only server-configured portable import targets, streams the selected bytes through bounded type/size and symlink/reparse checks, and reports sanitized content-addressed deduplication accounting. An exact `doc_` or product-owned `mem_` target creates a separate append-only `memory_proposal` candidate in `pending_review`; import never rewrites canonical memory or implies acceptance. The durable proposal queue reconstructs pending, approved and rejected relationship projections from ledger events, attributes one idempotent terminal decision to the authenticated human actor, and enforces one decision per proposal. Approved relationships remain explicit proposal projections rather than silently changing memory-content authority or entering model context. The vertical chat runtime ranks approved, non-missing product memory deterministically, records query and budget omissions without exposing unapproved content, compiles a content-addressed `ContextManifest`, and emits revision- and rank-bound citations. The fake provider and configured OpenAI-compatible/Ollama adapter share that authority boundary, while each three-event trajectory remains inspectable and replayable after restart. Candidate, missing, superseded and contradicted memory remains excluded.

`scripts/milestone_one_acceptance.py` exercises the complete authenticated journey in disposable state: native creation, explicit source sync, configured-target import, separate relationship and memory approval, approved-only chat context, immutable citation/run inspection, restart recovery, artifact verification, sanitization, and cleanup.

The current critical path is:

1. make the repository safe and understandable for public contributors;
2. extend the read-only MCP sidecar with governed candidate writes;
3. prove a five-minute compaction, correction, and client-switch demonstration;
4. validate the workflow with external coding-agent users.

## Read-only Project Memory MCP

From a source checkout, start the account-free local stdio server with one command:

```bash
uv run oscillink-project-memory --data-root /path/to/oscillink-workspace
```

The human selects the data root in client configuration; tool requests cannot select
another workspace or actor identity. The process opens no network port and advertises only
`recall` and `explain`, with read-only, non-destructive, idempotent, closed-world MCP hints.
Returned memory text remains untrusted input. Its manifest identifies the exact approved
revisions, token budget, omissions, and exclusion counts.

This path has been exercised with the official Python MCP client. Compatibility with
Claude, Codex, Hermes, OpenCode, or Cline is not claimed until each client is tested.

A read-only physical-intelligence dataset experiment may run as a separate discovery
track. Robot control, semantic retrieval, terminal execution, training, generalized
multi-agent orchestration, and cloud scale remain deferred until their evidence gates
pass.

## Provider strategy

- Product boundary: model and agent providers are configurable adapters, not the product identity.
- Local/offline option: `qwen3:14b` through Ollama at `http://localhost:11434/v1`.
- Hosted/cloud option: reviewed OpenAI-compatible or higher-level agent adapters behind the same memory, provenance and capability contracts.
- Scale path: provider/runtime configuration can target vLLM or NVIDIA NIM without changing workspace semantics.

Open weights can remove per-token provider fees locally; hosted inference, cloud GPU and storage still have operating costs.

## License and commercial boundary

The repository is licensed under the
[Apache License 2.0](LICENSE). The local continuity, provenance, correction, context,
evaluation, and adapter foundation is intended to remain useful without a mandatory
account. Expected commercial layers are operational services around that foundation:
encrypted synchronization, hosted reliability, team coordination, managed connectors,
enterprise deployment, audit, policy administration, and support—not marked-up model
inference.

See [`docs/open-source-boundary.md`](docs/open-source-boundary.md) for the explicit
code, data, model, connector, and physical-intelligence boundaries.

## Architecture

```text
Native memory + optional connectors
                 ↓
 product-owned IDs/revisions/reviews
                 ↓
      cited context compiler
                 ↓
    local/cloud model provider
                 ↓
       typed capability broker
                 ↓
    isolated tools + verification
                 ↓
  evaluation, promotion, rollback
```

## Development

The project uses Python 3.11, `uv`, pytest, Ruff, mypy, Pydantic v2, SQLite/FTS5, FastAPI, React, TypeScript, Vite, Vitest, and an application-owned projected-3D Canvas renderer.

### Launch a bounded private pilot

Build the browser application and run the single-process launcher:

```bash
npm --prefix apps/web ci
npm --prefix apps/web run build
PYTHONPATH= .venv/Scripts/python.exe scripts/launch_private_pilot.py \
  --host 127.0.0.1 \
  --port 8765 \
  --data-dir "$HOME/AppData/Local/oscillink-agent-private/workspace" \
  --credential-file "$HOME/AppData/Local/oscillink-agent-private-runtime/workspace.credential" \
  --frontend-dist apps/web/dist
```

See [`docs/private-pilot-runbook.md`](docs/private-pilot-runbook.md) for health
checks, provider setup, private-network binding, shutdown, credential rotation,
backup, restore, and failure recovery.

### Launch the Phase 1 interface

Install locked dependencies:

```bash
uv sync --locked --dev
npm --prefix apps/web ci
```

Start the API from the repository root:

```bash
export OSCILLINK_AGENT_VAULT_DIR="$HOME/Documents/Maverick HQ"
export OSCILLINK_AGENT_WORKSPACE_CREDENTIAL="$(.venv/Scripts/python.exe -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf 'Local workspace credential: %s\n' "$OSCILLINK_AGENT_WORKSPACE_CREDENTIAL"
PYTHONPATH= .venv/Scripts/python.exe -m uvicorn oscillink_agent.api:app --host 127.0.0.1 --port 8765
```

The credential is generated for this launch, kept out of application logs and
entered into the browser's **Local workspace credential** field. The browser
keeps it only in memory; refreshing the page locks mutation controls again.
Without `OSCILLINK_AGENT_WORKSPACE_CREDENTIAL`, status reports authentication as
`unavailable` and every mutating route fails closed. CORS defaults to the two
local Vite origins and trusted hosts default to `localhost`, `127.0.0.1`, and
`testserver`; deployments must set `OSCILLINK_AGENT_ALLOWED_ORIGINS` and
`OSCILLINK_AGENT_TRUSTED_HOSTS` explicitly as comma-separated allowlists.

The deterministic fake provider remains the default. To use local Ollama without changing memory authority or retrieval policy:

```bash
export OSCILLINK_CHAT_PROVIDER=ollama
export OSCILLINK_CHAT_BASE_URL=http://127.0.0.1:11434/v1
export OSCILLINK_CHAT_MODEL=qwen3:14b
PYTHONPATH= .venv/Scripts/python.exe -m uvicorn oscillink_agent.api:app --host 127.0.0.1 --port 8765
```

For another OpenAI-compatible endpoint, use `OSCILLINK_CHAT_PROVIDER=openai_compatible` and set both `OSCILLINK_CHAT_BASE_URL` and `OSCILLINK_CHAT_MODEL`. `OSCILLINK_CHAT_API_KEY` is optional and is never included in provider projections, events, artifacts or citations.

If `OSCILLINK_AGENT_VAULT_DIR` is omitted, native memory still works. Empty read endpoints return a typed `unavailable` state until a native record exists; the application never guesses or creates a vault path.

Start the frontend in a second terminal:

```bash
npm --prefix apps/web run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the local FastAPI process. Set `OSCILLINK_AGENT_DATA_DIR` before launching the API to inspect a non-default runtime directory.

Candidate and curated records expose explicit **Approve memory** and **Reject memory** actions in the inspector. Decisions are sent with typed event identities and idempotency keys, and the lattice refreshes from product-owned state after a successful review.

The **Workspace Terminal** navigation surface is now available as an execution-locked preview. It exposes the intended workspace, sandbox, network, budget and audit envelope while creating no process, exposing no host path and accepting no command.

The first capability-broker slice is implemented behind that locked surface: a human-approval event from the append-only ledger can authorize one exact `file.read` grant for one model actor, one portable target, one configured opaque scope, one extension set, one byte limit and at most 300 seconds. The broker atomically consumes the grant, survives restart, denies actor mismatch, expiry, reuse, scope escape, disallowed extensions, oversized or non-UTF-8 content, and returns file text explicitly marked `external_untrusted` without exposing the physical host path or enabling network access. This broker is reported as **preview** because provider-driven tool requests and tool-event integration are not connected yet; the browser terminal still executes nothing.

Run the complete deterministic gate with:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
```

The implementation plan is in [`docs/build-plan.md`](docs/build-plan.md).
Frontend and appearance boundaries are in [`docs/frontend-architecture.md`](docs/frontend-architecture.md) and [`docs/appearance-contract.md`](docs/appearance-contract.md).
Reviewed indexing, category colors and subject-domain labels are specified in [`docs/memory-contract.md`](docs/memory-contract.md).
Versioned canonical export, atomic restore, rollback and deletion semantics are documented in [`docs/workspace-recovery.md`](docs/workspace-recovery.md).
Private-pilot startup, health, shutdown and recovery are documented in [`docs/private-pilot-runbook.md`](docs/private-pilot-runbook.md).

## Governed workspace terminal

A terminal is technically feasible, but Oscillink will not expose an unrestricted browser-accessible host shell. The **governed workspace terminal** must remain subordinate to authenticated workspace scope, typed capability policy and append-only run history. Human-interactive and agent-invoked modes require distinct authorization; execution must be bounded, cancellable, secret-redacted, process-tree supervised and isolated where feasible.

The recommended sequence is a structured command runner after the capability broker and run inspector, followed later by a human-interactive PTY and narrowly granted agent invocation. The terminal design and acceptance criteria are in [`docs/workspace-terminal.md`](docs/workspace-terminal.md).

## Safety boundary

An open or unrestricted model may reason and propose freely, but it does not receive unrestricted credentials, filesystem/network access, memory-promotion authority, governance mutation, self-deployment or shutdown control.

## Community and security

- Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing code, fixtures, schemas, or
  compatibility claims.
- Follow the [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) in project spaces.
- Report vulnerabilities through the private-first process in
  [`SECURITY.md`](SECURITY.md); do not publish exploit details or real credentials.
- Community and design-partner claims follow the evidence gates in
  [`docs/community-validation.md`](docs/community-validation.md).

Oscillink Agent is distributed under the [Apache License 2.0](LICENSE).
