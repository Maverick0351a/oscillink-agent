# Oscillink Agent

Oscillink Agent is a customer-facing, model-neutral agentic memory workspace. It helps people connect governed sources, inspect how an agent's memory develops, review durable proposals, trace cited context and run history, and move from local/private use to scalable deployment without changing the core provenance and authority contracts.

## Current milestone

The first milestone is a governed continuity kernel:

- append-only execution events;
- product-owned memory identities, revisions and human review decisions;
- provenance-linked retrieval;
- context manifests for model calls;
- typed capability grants;
- parent-versus-candidate evaluation.

The current foundation includes immutable domain contracts, an append-only SQLite ledger, content-addressed artifacts, governed file imports, product-owned `mem_` identities and immutable revisions, append-only approval/rejection/supersession decisions, native memory creation without Obsidian, restart recovery, and explicit idempotent Obsidian synchronization that preserves product identity across unambiguous source renames. The typed Memory Lattice projects candidate, curated, approved, rejected and superseded records with visible source provenance. Obsidian remains an optional connector rather than the canonical product database or review authority.

`POST /api/v1/artifact-imports` accepts only configured opaque source scopes and portable relative targets, streams selected files through bounded type/size and symlink/reparse checks, returns sanitized logical/physical deduplication accounting, and supports canonical idempotent retries that reject association-changing reuse. An optional exact `doc_` or product-owned `mem_` target creates a separate append-only `memory_proposal` candidate in `pending_review`; import never rewrites canonical memory or implies acceptance. The next customer slice exposes create, synchronization and review controls in the browser, then connects approved-memory retrieval, provider-neutral chat, citations and run inspection. Removable-volume discovery remains deferred.

## Provider strategy

- Product boundary: model and agent providers are configurable adapters, not the product identity.
- Local/offline option: `qwen3:14b` through Ollama at `http://localhost:11434/v1`.
- Hosted/cloud option: reviewed OpenAI-compatible or higher-level agent adapters behind the same memory, provenance and capability contracts.
- Scale path: provider/runtime configuration can target vLLM or NVIDIA NIM without changing workspace semantics.

Open weights can remove per-token provider fees locally; hosted inference, cloud GPU and storage still have operating costs.

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

### Launch the Phase 1 interface

Install locked dependencies:

```bash
uv sync --locked --dev
npm --prefix apps/web ci
```

Start the API from the repository root:

```bash
export OSCILLINK_AGENT_VAULT_DIR="$HOME/Documents/Maverick HQ"
PYTHONPATH= .venv/Scripts/python.exe -m uvicorn oscillink_agent.api:app --host 127.0.0.1 --port 8765
```

If `OSCILLINK_AGENT_VAULT_DIR` is omitted, native memory still works. Empty read endpoints return a typed `unavailable` state until a native record exists; the application never guesses or creates a vault path.

Start the frontend in a second terminal:

```bash
npm --prefix apps/web run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the local FastAPI process. Set `OSCILLINK_AGENT_DATA_DIR` before launching the API to inspect a non-default runtime directory.

Run the complete deterministic gate with:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
```

The implementation plan is in [`docs/build-plan.md`](docs/build-plan.md).
Frontend and appearance boundaries are in [`docs/frontend-architecture.md`](docs/frontend-architecture.md) and [`docs/appearance-contract.md`](docs/appearance-contract.md).
Reviewed indexing, category colors and subject-domain labels are specified in [`docs/memory-contract.md`](docs/memory-contract.md).

## Safety boundary

An open or unrestricted model may reason and propose freely, but it does not receive unrestricted credentials, filesystem/network access, memory-promotion authority, governance mutation, self-deployment or shutdown control.
