# Oscillink Agent

Oscillink Agent is a customer-facing, model-neutral agentic memory workspace. It helps people connect governed sources, inspect how an agent's memory develops, review durable proposals, trace cited context and run history, and move from local/private use to scalable deployment without changing the core provenance and authority contracts.

## Current milestone

The first milestone is a governed continuity kernel:

- append-only execution events;
- reviewed Obsidian knowledge;
- provenance-linked retrieval;
- context manifests for model calls;
- typed capability grants;
- parent-versus-candidate evaluation.

The current foundation includes immutable domain contracts, an append-only SQLite ledger, content-addressed artifacts, governed file imports, a deterministic read-only Obsidian metadata index, typed memory/import APIs, and a launchable cyberpunk web workspace. `POST /api/v1/artifact-imports` accepts only configured opaque source scopes and portable relative targets, streams selected files through bounded type/size and symlink/reparse checks, returns sanitized logical/physical deduplication accounting, and supports canonical idempotent retries that reject association-changing reuse. An optional exact stable `doc_` record target creates a separate append-only `memory_proposal` candidate in `pending_review`; import never rewrites canonical reviewed Markdown or implies acceptance. The next customer vertical slice will make curated, candidate and approved memory states truthful in the UI, add explicit browser import/review flow, and connect provider-neutral chat, citations and run inspection. Removable-volume discovery is deferred until that workflow works. The shell reports live backend/storage status, renders real source records with search, category/domain filters and an exact-provenance inspector, keeps the architecture scaffold as a separate non-memory view, and keeps chat disabled until the governed runtime exists.

## Provider strategy

- Product boundary: model and agent providers are configurable adapters, not the product identity.
- Local/offline option: `qwen3:14b` through Ollama at `http://localhost:11434/v1`.
- Hosted/cloud option: reviewed OpenAI-compatible or higher-level agent adapters behind the same memory, provenance and capability contracts.
- Scale path: provider/runtime configuration can target vLLM or NVIDIA NIM without changing workspace semantics.

Open weights can remove per-token provider fees locally; hosted inference, cloud GPU and storage still have operating costs.

## Architecture

```text
Obsidian/Git + append-only events
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

If `OSCILLINK_AGENT_VAULT_DIR` is omitted, the memory endpoints return a typed `unavailable` state and never guess or create a vault path.

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
