# Frontend Architecture

## Product boundary

Oscillink Agent uses a dedicated first-party web interface. The product-owned memory repository is canonical for stable IDs, immutable revisions, authority transitions and review decisions. Obsidian remains an optional customer-authored source and portability adapter; it is not required for onboarding, identity, review authority, the transactional ledger, artifact storage, or the browser application.

```text
Native records + optional sources ┐
Product memory + SQLite events ───┼─> projection/context services ─> typed HTTP API ─> web UI
SHA-256 artifacts ────────────────┘
```

The browser never opens vault paths, SQLite databases, or artifact paths directly. Every record displayed by the browser arrives through a typed API response.

## Phase 1 implementation

`apps/web` is a React and TypeScript Vite application. It contains:

- an accessible Chat and Memory Lattice application shell;
- live `/api/v1/status` telemetry;
- a disabled chat composer while the model runtime is unavailable;
- a local SVG foundation avatar identified as an interface preview;
- a projected-3D reviewed-memory lattice with stable-record focus, search, category/domain filters and an exact-provenance inspector;
- browser approve/reject controls for candidate and curated product records, with pending, failure and refresh states;
- the neural architecture scaffold retained as a separate System Architecture view clearly marked as non-memory data;
- reduced-motion and responsive layout support.

The Python API exposes read-only status inspection and a typed reviewed-memory projection. It does not create runtime directories during a health or memory request. Existing ledgers are inspected through a read-only SQLite connection, artifact counts include only valid content-addressed object paths, and memory responses expose only vault-relative source paths.

## State and authority

| State | Authority | Browser behavior |
|---|---|---|
| Product memory and governance | Product-owned records, immutable revisions and append-only reviews | Display provenance, authority and governed actions |
| Optional source documents | Customer-authored source plus product source binding | Display sanitized locator and synchronization state |
| Execution events | Append-only SQLite ledger | Display trajectory and runtime status |
| Raw evidence | Content-addressed artifact store | Request by validated digest only |
| Search and graph layout | Rebuildable projections | Filter, navigate, and discard safely |
| Draft text, active tab, viewport | Browser session | Never promote automatically |
| Candidate durable changes | Candidate event/record | Require review and promotion |

Graph nodes cannot grant permissions. Retrieved content, citations, provenance, and agent output are data—not authority.

## API direction

Implemented endpoints:

- `GET /api/v1/status`;
- `GET /api/v1/memory/index` for projection health, legends and issues;
- `GET /api/v1/memory/nodes` with controlled category and domain filters;
- `GET /api/v1/memory/nodes/{node_id}` for focused inspector metadata.
- `POST /api/v1/memory/nodes` for native candidate creation;
- `POST /api/v1/memory/nodes/{node_id}/reviews` for governed review decisions;
- `POST /api/v1/memory/sources/obsidian/sync` for explicit configured-source synchronization.

Planned endpoints are versioned under `/api/v1`:

- `POST /chat/sessions`;
- `POST /chat/sessions/{session_id}/messages`;
- `GET /chat/sessions/{session_id}/stream` using Server-Sent Events;
- `GET /memory/graph` with temporal and review filters;
- artifact retrieval by digest, never by host path;
- appearance candidate, preview, approval, and rollback operations.
- governed command-runner and terminal-session endpoints only after capability, authentication and process-supervision prerequisites are complete.

## Memory Lattice contract

“Lattice” is the product term. The underlying model is a typed, temporal provenance graph. Planned node classes include evidence, observations, claims, decisions, procedures, contradictions, retractions, events, artifacts, and reviews. Planned edge classes include support, contradiction, supersession, retraction, derivation, citation, and causality.

The UI must expose:

- node and edge type;
- review status;
- record and valid time;
- current, stale, retracted, and superseded state;
- canonical source citation and digest;
- lineage and contradiction details;
- the exact nodes used by a chat response.

The projection is disposable. Rebuilding it from canonical records must reproduce stable logical node identities.

The implemented reviewed-memory workspace loads projection health and sanitized node summaries from the typed API, then requests focused detail by stable node ID. Category is always represented by label, symbol and color; domains remain independent labels. The inspector exposes relative source path, SHA-256 digest, source status, classification basis, topics and exact wikilinks. Search and category/domain filtering operate over the sanitized browser snapshot. When filtering hides the focused record, focus moves to the first visible stable record or clears when no records remain.

The browser does not synthesize category, proximity or similarity edges. In the current projection, an edge appears only when an exact wikilink in the focused detail resolves to another visible reviewed record. Structural, reviewed, inferred and retrieval-session edges will remain visually and semantically distinct as those typed APIs are added.

The shared renderer uses deterministic XYZ coordinates projected onto an application-owned Canvas 2D surface. Reviewed records use stable ID-derived positions; foundation components retain their authored coordinates. Spherical nodes are depth-sorted, and curved synapses carry bounded visual signal pulses. Pointer drag and arrow keys orbit the field; wheel and plus/minus inputs adjust focus. A keyboard-accessible record roster provides deterministic node selection. Below 520 CSS pixels, reviewed-memory coordinates use a compact density and the roster/inspector become the labeling surface so Canvas text cannot collide or clip; architecture labels retain their authored behavior. `prefers-reduced-motion` disables autonomous rotation and pulse animation while preserving the complete static graph. The renderer is a disposable view and cannot alter graph records, review state, or authority.

## Transport and deployment

Development runs FastAPI on `127.0.0.1:8765` and Vite on `127.0.0.1:5173`; Vite proxies `/api` to FastAPI. Production should serve the built frontend and API under one origin. A later desktop wrapper may use Tauri without changing the browser/API contracts.

Loopback is not authentication. Before enabling chat or mutation endpoints, add a per-launch local credential, strict origin checks, sanitized Markdown rendering, explicit capability approvals, and bounded request sizes.

## Governed terminal direction

The browser may eventually expose a Workspace Terminal, but never a direct or unrestricted host shell. The first terminal-adjacent surface should be a structured command runner tied to an authenticated workspace, actor, typed grant, bounded process, sanitized output and append-only run record. A persistent human-interactive PTY follows only after process-tree cancellation, reconnect/orphan handling, secret redaction, terminal-escape sanitization and sandbox policy are verified. Agent-proposed commands are inert until authorized, and agent-invoked commands require narrower grants than human-interactive use. See [`workspace-terminal.md`](workspace-terminal.md).

## Verification

The repository review gate runs:

- locked Python dependency sync;
- Python tests, Ruff, and strict mypy;
- locked npm install;
- frontend component tests;
- TypeScript checking;
- production frontend build;
- repository invariants and security scanning.
