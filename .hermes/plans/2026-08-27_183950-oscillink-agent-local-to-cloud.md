# Oscillink Agent Local-to-Cloud Implementation Plan

> **For Hermes:** Execute this plan task-by-task with strict TDD and deterministic local self-review at phase gates; do not use reviewer subagents or temporary review worktrees.

**Goal:** Build Oscillink Agent as a customer-usable, model-neutral agentic memory development app that turns governed sources, conversations, files and agent runs into inspectable, provenance-linked memory without rewriting its core contracts as deployments scale.

**Architecture:** Keep the agent core model-agnostic and expose local or hosted inference through provider adapters. Use governed Markdown and future customer-managed sources for reviewed knowledge, an append-only event ledger for execution history, immutable artifact storage for imported evidence, FTS5 for initial retrieval, and explicit context manifests for every model call. Treat the web workspace, Memory Lattice, review queue and run inspector as product surfaces backed by typed contracts rather than decorative views.

**Tech Stack:** Python 3.11, `uv`, FastAPI, Pydantic v2, SQLite WAL/FTS5, Ollama, OpenAI-compatible HTTP, pytest, Ruff, mypy, JSON Schema, YAML, Docker, Obsidian Markdown, Git; later PostgreSQL, S3-compatible object storage, vLLM/NVIDIA NIM, OpenTelemetry, and a managed container/GPU platform.

**Project root:** `C:\Users\Maverick\Projects\oscillink-agent`

---

## 1. Product boundary

Oscillink Agent is the **memory control plane for long-running AI agents**: a governed, provider-neutral workspace for durable memory, deterministic context, bounded capabilities and inspectable runs. It should help customers preserve continuity without losing provenance, human control, portability, or the ability to explain and reverse what changed.

The product addresses six primary customer failures:

1. fragmented memory scattered across transcripts, prompts, files, vector stores and provider-specific systems;
2. opaque or poisoned memory whose authority, freshness, contradictions and origin cannot be inspected;
3. irreproducible answers and actions without exact retrieval, context, provider, tool and budget records;
4. provider, connector and filename lock-in that makes external systems accidental identity and authority layers;
5. overly broad credentials, filesystem, network and shell authority for narrow agent tasks;
6. incomplete export, deletion, rollback, restore and operational recovery.

The infrastructure answer is product-owned stable identity and immutable revisions, explicit human-governed authority, approved-only provenance-bearing retrieval, deterministic context manifests, interchangeable provider adapters, typed capability grants, replayable run history and portable recovery. See `docs/product-description.md`.

Version 0 does **not** attempt to:

- train a foundation model;
- claim AGI or consciousness;
- grant unrestricted host/network/credential authority;
- autonomously rewrite and deploy production code;
- make Obsidian the transactional runtime database;
- merge the agent's autobiographical memory with Oscillink's electromagnetic world-model state.

“Free model” means:

- open-weight checkpoint;
- locally controlled inference;
- no per-token API fee during local operation;
- user-controlled prompts and model routing;
- no dependency on a hosted moderation policy.

It does **not** mean zero cloud cost. Cloud GPU, storage, networking and operations will have real costs even when the model weights are freely licensed.

---

## 2. First customer-demo outcome

A new customer workspace, with no prior transcript in its prompt, must be able to:

1. create or open a governed workspace and connect an explicit memory source;
2. distinguish curated, candidate and approved records in the UI;
3. inspect every durable memory included in context through the Memory Lattice and citation panel;
4. converse through a configured model or agent provider without making one model the product identity;
5. propose, review, approve or reject durable memory changes without silent promotion;
6. import one explicitly selected file and inspect its immutable provenance and candidate associations;
7. execute one narrowly scoped tool through a typed capability grant;
8. inspect the complete run trajectory, context manifest, budgets and recovery state;
9. restart and recover the approved workspace state without replaying a raw transcript;
10. stop cleanly within configured turn, time and tool budgets.

Evaluation against transcript and summary baselines remains a release-quality gate, but it must not block the first coherent customer workflow.

### Product execution strategy

Oscillink Agent is an **agentic memory workspace**, not a Qwen application and not a generic autonomous-agent launcher. Its customer value is the ability to develop, inspect and govern an agent's durable memory over time.

Keep at most three active product workstreams:

1. **Project Memory and public launch** — one-command local continuity, stable records,
   corrections, provenance, deterministic context, and a clear open-source boundary.
2. **Coding-agent integration and evaluation** — exercise two real clients, survive
   compaction and switching, and measure total human effort under equal budgets.
3. **Physical-intelligence discovery** — validate read-only episode and dataset quality
   tooling before considering any actuator-connected integration.

The primary customer demo journey is:

```text
create workspace
  → connect or import governed sources
  → inspect the Memory Lattice
  → chat with a configured provider
  → inspect cited context and run events
  → review memory proposals
  → restart and recover approved state
```

Every visible UI state must correspond to a typed backend state. UI work proceeds alongside the backend vertical slice rather than waiting until all infrastructure is complete. Removable-volume discovery, datasets, training and public multi-tenant APIs remain deferred until the core customer journey works in a local/private pilot.

### Hermes inspiration and Oscillink differentiation

Adopt the useful customer primitives of Hermes—workspaces, chat sessions, project context, skills/tools, durable recall, approvals and inspectable run history—without copying Hermes internals or turning Oscillink Agent into a terminal wrapper. Oscillink Agent differentiates through its governed Memory Lattice: customers can see source provenance, review state, contradictions, context inclusion and memory change over time.

### Current executable capability ledger

<!-- capability-ledger:start -->
| Capability | State | Evidence |
|---|---|---|
| Domain schemas and immutable event contracts | implemented | `src/oscillink_agent/domain/`, `schemas/` |
| Append-only ledger and content-addressed artifacts | implemented | `src/oscillink_agent/storage/` |
| Product-owned memory identities, revisions and review | implemented | `src/oscillink_agent/memory/` |
| Approved-only lexical retrieval and context manifests | implemented | `src/oscillink_agent/retrieval/`, `src/oscillink_agent/context/` |
| Fake and OpenAI-compatible provider chat | implemented | `src/oscillink_agent/providers/`, `src/oscillink_agent/chat/` |
| Persisted typed run reconstruction | implemented | Causal state projection recovers legacy and multi-call/tool trajectories across restart; tool execution remains unconnected |
| Crash-safe provider dispatch | implemented | Request, context and pending intent are durable before dispatch; success, bounded failure, timeout and interruption are inspectable, and ambiguous retries fail closed without redispatch |
| Truthful provider and actor provenance | implemented | Public non-secret execution identity drives provider kind, model, configuration hash, operation and model actor; authenticated human actor IDs remain server-derived |
| Governed file import | implemented | Browser enumerates only configured portable targets and imports them through the bounded content-addressed backend |
| Single-use `file.read` capability broker | implemented | Authenticated human decisions bind an exact pending request to one server-constructed grant; authorization precedes registration, consumption is atomic, and reuse fails after restart |
| Bounded provider tool-request contract | implemented | Fake and OpenAI-compatible providers return an exact final response or one portable `file.read` request; unknown, parallel, malformed, oversized and grant-bearing requests fail closed; execution requires the governed loop and a human grant |
| Governed one-tool agent loop | implemented | One approved `file.read` produces a portable external-untrusted observation before a no-tools follow-up provider dispatch; denied, expired, mismatched, reused and file-failure states remain inspectable without host-path exposure |
| Browser capability approval and complete run inspection | implemented | The authenticated workspace shows the exact portable authority envelope, distinct decision outcomes, refreshed semantic trajectories and separate exact trajectory JSON with stale-result guards |
| Versioned workspace export and atomic restore | implemented | Authenticated human routes select only server-managed export IDs; manifests hash canonical databases/artifacts, migrations are ordered with verified backups, and corrupt restores leave active state untouched |
| Bounded private-pilot launch and health | implemented | One Windows-first process serves the built UI and API with an out-of-data-root rotated credential, explicit bind/origin/host policy, non-mutating liveness, typed component readiness, bounded provider probing, and graceful shutdown |
| Human-clear next-action guidance | implemented | The agent workspace prioritizes unlock, trusted-memory setup, chat, and pending approval in plain language while preserving exact governed detail below |
| Browser memory creation, source sync and proposal review | implemented | `scripts/milestone_one_acceptance.py` proves the disposable, restart-recoverable, approved-only end-to-end journey |
| Authenticated local workspace boundary | implemented | Bearer-authenticated single-workspace scope, server-derived actor identity, strict local CORS/trusted-host allowlists and browser in-memory unlock are enforced |
| Workspace terminal execution | contract-only | The UI is intentionally execution-locked |
| Longitudinal public evaluation | implemented | Pinned public fixture, equal-budget baselines, deterministic report and offline smoke |
| Governed Project Memory MCP sidecar | implemented | Local stdio reads return deterministic approved context; idempotent `remember` and `correct` create provenance-bearing candidates requiring external promotion; the pinned independent-process demo and direct Hermes/OpenCode receipts are executable |
| Physical-intelligence dataset inspection | planned | Evidence-gated read-only discovery; no robot or equipment control |
| Semantic retrieval, training, multi-agent and cloud scale | deferred | Add only after measured product need |
<!-- capability-ledger:end -->

### Active maturity milestones

1. **Browser-complete governed memory journey — release candidate complete:** authenticate one local workspace; expose native create, explicit source sync, configured-scope import and proposal review; preserve exact context/run transport contracts.
2. **Crash-safe provider and governed tool trajectory — complete:** persist intent before dispatch, record truthful provider/actor provenance, reconstruct multi-call runs and connect one single-use `file.read`.
3. **Reproducible private pilot and measured value — implementation complete through public evaluation:** versioned recovery, bounded deployment, and deterministic longitudinal evaluation are executable; browser evidence summaries remain.
4. **Open Project Memory wedge — demo complete, external alpha active:** the public boundary, governed MCP/CLI sidecar, pinned independent-process continuity demo and direct Hermes/OpenCode receipts are executable; bounded external-user validation remains.

Each milestone must produce a coherent UI path backed by real typed API behavior, pass the deterministic candidate and immutable-range gates, and remain demoable without fabricated capability.

---

## 3. Architecture

```text
Optional sources                       Local or cloud model pool
Obsidian / files / connectors          Ollama → vLLM/NIM
              │                              │
              └──────────┐       ┌───────────┘
                         ▼       ▼
                    FastAPI control plane
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
       Memory repo  Context compiler  Capability broker
       IDs/revisions   manifests       typed grants
              │                     │
              ├──────────┐          ▼
              ▼          ▼    disposable runner
      SQLite events   derived FTS   local Docker first
      + reviews        projections
              │
              ▼
       Evaluation/promotion lab
       parent vs candidate
       equal budgets + rollback
```

### Authority by record class

| Record class | Local canonical store | Cloud evolution |
|---|---|---|
| Product memory identities, revisions and review decisions | Product-owned SQLite repository | PostgreSQL records, immutable revisions and review tables |
| Customer-authored source documents | Native records or optional Obsidian Markdown | Product editor plus connector/import APIs |
| Conversations, model calls, tool calls, outcomes | Append-only SQLite WAL | PostgreSQL append-only/event tables |
| Raw artifacts | Content-addressed local files | S3-compatible object storage |
| Imported-file provenance and dataset lineage | Append-only SQLite events + immutable artifact manifests | PostgreSQL events + S3 manifests |
| Lexical/structured retrieval | Rebuildable SQLite + FTS5 | PostgreSQL FTS and relational queries |
| Dense retrieval | Deferred local vector index | `pgvector` only after measured need |
| Task queue | In-process worker | PostgreSQL queue first; Redis/NATS only at measured scale |
| Model inference | Ollama | vLLM or NVIDIA NIM behind the same OpenAI-compatible adapter |
| Tool execution | Disposable local Docker containers | Isolated cloud jobs/containers with per-task identity |

### Core interfaces

```python
class ModelProvider(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...

class EventStore(Protocol):
    def append(self, event: Event) -> str: ...
    def stream(self, session_id: str) -> Iterable[Event]: ...

class MemoryStore(Protocol):
    def query(self, request: MemoryQuery) -> EvidencePacket: ...

class ContextCompiler(Protocol):
    def compile(self, task: Task, budget: ContextBudget) -> ContextManifest: ...

class CapabilityBroker(Protocol):
    async def execute(self, grant: CapabilityGrant, action: ToolAction) -> Observation: ...

class Evaluator(Protocol):
    def evaluate(self, candidate: Candidate, suite: EvaluationSuite) -> ResultBundle: ...
```

All infrastructure migrations must preserve these contracts.

---

## 4. Provider strategy

### Product boundary

Oscillink Agent is provider-neutral. Customers configure an allowlisted local or hosted model/agent provider; the workspace, memory, provenance, review and capability contracts remain unchanged. Provider credentials stay server-side, and every run records exact provider/model/configuration identity.

### Local development option

The already available `qwen3:14b` through Ollama remains a zero-token-cost development and offline test option:

```text
base URL: http://localhost:11434/v1
model: qwen3:14b
license class: open-weight / locally served
initial context budget: 8K–16K tokens
parallel model calls: 1
idle unload: 5 minutes
```

Use `qwen2.5-coder:14b` only for deliberate coding-agent comparisons.

### Measured provider candidates

Benchmark any local or hosted candidate only after the provider contract, customer workflow and evaluation harness work end to end. For local `gpt-oss-20b`, its official MXFP4 checkpoint is close to the laptop's 16 GB memory boundary, so an optional acceptance test must measure:

- successful load;
- VRAM headroom;
- 8K and 16K context behavior;
- tool-call validity;
- tokens/second;
- latency to first token;
- quality on the same hidden tasks;
- model unload behavior.

Do not make any checkpoint the product identity or adopt an unverified derivative as a default. Use reviewed provider configurations with external capability controls.

### Cloud path

1. **First cloud deployment:** one GPU VM, Docker Compose, vLLM, FastAPI and managed PostgreSQL/object storage.
2. **Scale-up:** larger single GPU or tensor-parallel vLLM only when model size requires it.
3. **Scale-out:** multiple stateless API workers and an inference pool behind a gateway after measured concurrency.
4. **Enterprise/NVIDIA option:** NIM for packaged inference and observability if its operational benefits justify the licensing/runtime cost.
5. **Kubernetes:** defer until multiple replicas, rolling deployment, GPU scheduling or tenant isolation create a measured need.

The model alias—not application code—selects local versus cloud inference.

---

## 5. Repository layout

The executable repository currently separates domain contracts from adapters
and keeps planned infrastructure out of the runtime tree:

```text
oscillink-agent/
├── apps/web/                   React workspace, Memory Lattice and inspectors
├── docs/                       product, memory, frontend and terminal contracts
├── schemas/                    event, context, capability and benchmark schemas
├── scripts/verify.py           deterministic candidate/immutable-range gate
├── src/oscillink_agent/
│   ├── agent_runtime/          run orchestration and persisted reconstruction
│   ├── artifact_imports/       governed selected-file import boundary
│   ├── capabilities/           typed single-use file-read broker
│   ├── chat/                   transport contracts and routes
│   ├── context/                deterministic context compiler
│   ├── domain/                 infrastructure-independent contracts
│   ├── memory/                 product records, revisions and review
│   ├── providers/              fake and OpenAI-compatible adapters
│   ├── retrieval/              approved-only lexical retrieval
│   ├── status/                 truthful service readiness projection
│   └── storage/                SQLite ledger and immutable artifacts
└── tests/
    ├── adversarial/
    ├── contract/
    ├── integration/
    └── unit/
```

`evaluation/`, deployment, migration/export and broader tool-runtime modules
remain planned. Protected labels must stay outside agent-readable repository
paths during actual evaluation.

---

## 6. Implementation tasks

### Task 1: Bootstrap the repository and project records

**Objective:** Establish the new repository, project documentation and a single bounded outcome.

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `.gitignore`
- Create: `docs/build-plan.md`
- Create: `C:\Users\Maverick\Documents\Maverick HQ\20 Projects\Oscillink Agent.md`

**Steps:**

1. Initialize Git in `C:\Users\Maverick\Projects\oscillink-agent`.
2. Write the project outcome, next action and finish line into the Obsidian project note.
3. Link the project note to `docs/build-plan.md` and the repository.
4. Add Python, environment, database, index and secret exclusions to `.gitignore`.
5. Add repository rules to `AGENTS.md`: TDD, typed contracts, no secret files, no model-controlled promotion, no raw host execution.
6. Run a script that parses project-note frontmatter and confirms the active-project count remains no greater than three.
7. Commit: `chore: initialize Oscillink Agent project`.

**Verification:**

```bash
git status --short
python -c "from pathlib import Path; assert Path('README.md').exists(); assert Path('docs/build-plan.md').exists()"
```

Expected: clean status after commit and both assertions pass.

---

### Task 2: Create the Python package and quality gates

**Objective:** Produce an importable, tested Python 3.11 package with reproducible dependencies.

**Files:**
- Create: `pyproject.toml`
- Create: `src/oscillink_agent/__init__.py`
- Create: `tests/unit/test_package.py`
- Create: `.github/workflows/ci.yml`

**TDD steps:**

1. Write `test_package.py` asserting a semantic `__version__` exists.
2. Run `uv run pytest tests/unit/test_package.py -v`; expect import failure.
3. Create package metadata and minimal `__init__.py`.
4. Configure pytest, Ruff and mypy in `pyproject.toml`.
5. Run:

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run mypy src
```

6. Add CI with the same commands.
7. Commit: `build: add Python package and quality gates`.

**Gate:** all commands exit 0 from a clean clone.

---

### Task 3: Freeze machine-readable contracts before runtime code

**Objective:** Define the event, context, capability, benchmark and memory-claim schemas before implementing their behavior.

**Files:**
- Create: `schemas/event.schema.json`
- Create: `schemas/context-manifest.schema.json`
- Create: `schemas/capability-grant.schema.json`
- Create: `schemas/benchmark-manifest.schema.json`
- Create: `schemas/memory-claim.schema.json`
- Create: `tests/contract/test_schemas.py`

**Required event fields:**

- stable event ID;
- schema version;
- session/run/task IDs;
- actor and actor type;
- event type;
- observed time and recorded time;
- payload hash and artifact references;
- causal parent IDs;
- model/provider/configuration identity where applicable;
- trust and sensitivity classes.

**TDD steps:**

1. Write valid and invalid fixtures in the test module.
2. Confirm tests fail because schemas do not exist.
3. Implement JSON Schemas with `additionalProperties: false` at trust boundaries.
4. Validate fixtures with `jsonschema`.
5. Commit: `feat: define core agent contracts`.

**Gate:** schemas reject missing provenance, malformed IDs, unauthorized capability fields and unknown trust classes.

---

### Task 4: Implement immutable domain objects

**Objective:** Create typed Pydantic models whose wire shapes and primitive acceptance
rules correspond to the schemas, with explicitly documented runtime-only semantic
invariants that standard Draft 2020-12 cannot express.

JSON Schema is the structural ingress layer. Pydantic validators additionally enforce
cross-field chronology, canonical-content hashes, causal self-reference, token sums and
review relationships. The future ledger/store must revalidate those invariants and
resolve referenced records transactionally; schema acceptance alone never proves them.

`frozen=True` records are immutable through supported application APIs. Public instance
dictionaries are read-only, nested JSON containers have attribute-free immutable
storage, and copy/update reconstructs through validation. These Python objects are not
a security boundary against arbitrary trusted in-process reflection; canonical bytes,
process isolation and store/broker revalidation provide that boundary.

**Files:**
- Create: `src/oscillink_agent/domain/events.py`
- Create: `src/oscillink_agent/domain/context.py`
- Create: `src/oscillink_agent/domain/capabilities.py`
- Create: `src/oscillink_agent/domain/benchmarks.py`
- Create: `src/oscillink_agent/domain/memory.py`
- Test: `tests/unit/test_domain_models.py`
- Test: `tests/unit/test_benchmark_models.py`

**TDD steps:**

1. Write tests for round-trip JSON/schema validation.
2. Add tests for valid time versus record time.
3. Add tests preventing mutation of frozen records.
4. Add bilateral primitive and structural schema/model parity tests.
5. Add runtime-only tests for semantic invariants that JSON Schema cannot express.
6. Implement the minimum Pydantic models.
7. Run unit and contract suites.
8. Commit: `feat: add typed domain contracts`.

---

### Task 5: Build the append-only SQLite event ledger

**Objective:** Persist and replay agent events without silent update/delete operations.

**Files:**
- Create: `src/oscillink_agent/storage/sqlite.py`
- Create: `src/oscillink_agent/storage/migrations/001_events.sql`
- Test: `tests/integration/test_event_store.py`

**Required behavior:**

- SQLite WAL mode;
- append-only application API;
- unique event IDs and idempotency keys;
- transaction boundaries;
- ordered session replay;
- payload hashes;
- explicit correction/retraction events rather than updates;
- privacy purge as a separate administrator-controlled operation.

**TDD steps:**

1. Test append and replay order.
2. Test duplicate idempotency behavior.
3. Test that normal API exposes no update/delete method.
4. Test process restart and replay.
5. Implement minimal SQL and repository.
6. Commit: `feat: add append-only event ledger`.

**Gate:** kill/restart test preserves all committed events and no partially committed event appears.

---

### Task 6: Add content-addressed artifact storage

**Objective:** Store raw source material and tool outputs by cryptographic digest.

**Files:**
- Create: `src/oscillink_agent/storage/artifacts.py`
- Test: `tests/unit/test_artifacts.py`

**TDD steps:**

1. Test identical bytes produce one artifact ID.
2. Test corruption is detected on read.
3. Test path traversal is rejected.
4. Implement local filesystem backend.
5. Define a backend protocol compatible with future S3 storage.
6. Commit: `feat: add content-addressed artifact store`.

---

### Task 6A: Establish the visible product shell

**Objective:** Make the governed foundation launchable and inspectable without fabricating memory or agent capability.

**Files:**
- Create: `docs/frontend-architecture.md`
- Create: `docs/appearance-contract.md`
- Create: `src/oscillink_agent/api.py`
- Create: `apps/web/`
- Test: `tests/integration/test_status_api.py`
- Test: `apps/web/src/*.test.ts*`

**TDD steps:**

1. Require a read-only status API that reports actual ledger and artifact state without creating runtime directories.
2. Require an accessible Chat and Memory Lattice shell connected to that API.
3. Keep chat disabled and labeled until the governed model runtime exists.
4. Render a projected-3D neural architecture scaffold that is explicitly not memory data.
5. Render a local foundation avatar labeled as an ungoverned interface preview.
6. Add responsive, reduced-motion and keyboard-visible cyberpunk presentation.
7. Add locked npm install, component tests, typecheck and production build to the deterministic gate.

**Gate:** live browser verification shows both views, the neural renderer creates a real canvas with orbit controls, the composer remains unavailable while chat is planned, and a 390-pixel viewport has no horizontal overflow.

---

### Task 7: Build the reviewed Obsidian index and typed memory projection

**Objective:** Deterministically index curated Markdown without modifying the vault, then expose approved records through a rebuildable typed projection and lexical index.

**Files:**
- Create: `docs/memory-contract.md`
- Create: `src/oscillink_agent/memory/obsidian.py`
- Create: `src/oscillink_agent/memory/indexer.py`
- Create: `scripts/rebuild_index.py`
- Test: `tests/unit/test_obsidian_index.py`
- Test: `tests/integration/test_obsidian_index.py`

**Required record semantics:**

- stable opaque ID;
- record type;
- epistemic class;
- review status;
- valid-time interval;
- record-time interval;
- source IDs and hashes;
- primary category, accessible legend and subject domains;
- classification basis distinguishing reviewed labels from automatic projection;
- supersedes/contradicts relations;
- sensitivity and project scope.

**TDD steps:**

1. Create a temporary vault with curated notes, inbox captures, templates, malformed records and unsupported labels.
2. Implement the deterministic read-only source index with stable path-derived IDs, SHA-256 source digests, wikilinks and explicit issue records.
3. Add the controlled category/color and multi-domain taxonomy, allowing reviewed frontmatter overrides while recording automatic classification basis.
4. Add typed projection API contracts without exposing absolute vault paths or direct browser filesystem access.
5. Add approved/candidate/superseded/contradictory fixtures and exclude unapproved records from default retrieval.
6. Implement the SQLite/FTS5 projection and confirm full deletion and rebuild reproduces record IDs and hashes.
7. Commit: `feat: index reviewed Obsidian memory`.

**Gate:** the source vault remains byte-identical after indexing, malformed sources are visible as issues, and deleting all derived indexes yields 100% recovery of canonical IDs and hashes.

---

### Task 7A: Connect real memory nodes, inspector and focused navigation

**Objective:** Replace the primary foundation-only lattice with typed reviewed-memory nodes while retaining the seven-node architecture scaffold as a separate System Architecture view.

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/MemoryGraph.tsx`
- Modify: `apps/web/src/styles.css`
- Create: `apps/web/src/memoryApi.ts`
- Create: `apps/web/src/memoryGraphLayout.ts`
- Create: `apps/web/src/MemoryInspector.tsx`
- Create: `apps/web/src/MemoryWorkspace.tsx`
- Test: `apps/web/src/App.test.tsx`
- Test: `apps/web/src/MemoryGraph.test.tsx`
- Test: `apps/web/src/MemoryInspector.test.tsx`
- Test: `apps/web/src/MemoryWorkspace.test.tsx`
- Test: `apps/web/src/memoryApi.test.ts`

**TDD steps:**

1. Render only records returned by the typed projection API; never read vault files from the browser.
2. Show category label, symbol and color plus independent domain badges.
3. Add category/domain filters, text search and stable-ID focused navigation.
4. Show exact source digest, relative source path, classification basis, status and wikilinks in the inspector.
5. Draw only exact focused-record wikilinks that resolve to visible stable records; do not synthesize category, proximity or similarity edges. Keep future structural, reviewed, inferred and retrieval-session links typed and visually distinct.
6. Preserve reduced-motion, keyboard navigation and non-color semantics.

**Gate:** every visible memory node resolves to an inspectable stable record, and the architecture scaffold remains truthfully separated from memory data.

---

### Task 7B: Add governed file and removable-storage ingestion

**Objective:** Import explicitly selected local or removable-media files into immutable artifact storage and propose associations to stable memory records without granting the browser raw filesystem authority.

**Files:**
- Create: `src/oscillink_agent/domain/imports.py`
- Create: `src/oscillink_agent/storage/imports.py`
- Create: `src/oscillink_agent/devices/base.py`
- Create: `src/oscillink_agent/devices/windows.py`
- Modify: `src/oscillink_agent/storage/artifacts.py`
- Modify: `src/oscillink_agent/storage/interfaces.py`
- Modify: `src/oscillink_agent/api.py`
- Test: `tests/adversarial/test_artifact_imports.py`
- Test: `tests/integration/test_artifact_import_api.py`
- Test: `tests/integration/test_removable_storage_api.py`

**Required behavior:**

- trusted local backend detects connected/disconnected volumes and returns sanitized opaque descriptors;
- no silent device scan or automatic ingestion;
- user explicitly selects each file or bounded selection;
- streaming SHA-256 import avoids loading datasets wholly into memory;
- path traversal, symlink/reparse escapes, unsupported types and size-limit violations fail closed;
- disconnects and partial reads publish no artifact and leave an inspectable failure event;
- identical bytes deduplicate physically while retaining separate provenance events;
- dropping onto a node creates a candidate association to a stable record ID;
- dropping onto a derived cluster requires choosing or creating a stable target record;
- imported content is never executed merely because it was selected or dropped.

**Implementation slices:**

1. Backend import foundation: strict selection/policy/result contracts, scoped source validation, streaming staged SHA-256 publication, size/extension limits, symlink/reparse rejection, deduplication accounting and canonical success/failure event construction.
2. Typed local API and candidate stable-record association; browser requests never contain arbitrary absolute host paths.
3. Trusted removable-volume discovery and disconnect handling through sanitized opaque descriptors.
4. Browser selection/drop workflow with explicit target confirmation and review.

**Status (2026-08-28):** Slices 1 and 2 are implemented. The typed local API rejects arbitrary absolute/traversal targets, validates exact stable reviewed-memory IDs before importing, preserves separate import and candidate-association provenance, uses server-populated recording time, returns idempotent canonical replays, rejects association-changing retries, detects changed-request key reuse with a sanitized scoped-selection digest, and distinguishes logical imported bytes from unique physical bytes. Slice 4's explicit browser import/review experience is now part of the customer-workspace vertical slice and follows truthful curated/candidate/approved memory states. Slice 3 removable-volume discovery is deferred until after that customer journey works; no removable device is scanned and no browser drag/drop authority exists yet.

**Gate:** removing a device during import cannot publish partial bytes, expose an absolute device path to the browser or mutate source media.

---

### Task 7C: Build the dataset catalog and lineage tab

**Objective:** Let users register training data as governed immutable versions and inspect raw, validated, processed, split and training-ready states with truthful storage accounting.

**Files:**
- Create: `src/oscillink_agent/domain/datasets.py`
- Create: `src/oscillink_agent/datasets/catalog.py`
- Create: `apps/web/src/Datasets.tsx`
- Test: `tests/unit/test_dataset_contracts.py`
- Test: `tests/integration/test_dataset_api.py`
- Test: `apps/web/src/Datasets.test.tsx`

**Required metadata:**

- dataset ID and immutable version;
- raw and derived artifact digests;
- import provenance, license, permitted use and sensitivity/PII class;
- media type, logical bytes, deduplicated physical bytes and processed bytes;
- deterministic sample/record counts when supported;
- validation status and bounded errors;
- processing pipeline identity, parameters, code digest and parent version;
- train/validation/test split manifest and leakage-group keys;
- consuming evaluation/training run IDs.

**Initial formats:** bounded CSV, JSONL, Parquet, plain text and separately validated media. Reject arbitrary pickle/joblib deserialization and executable formats.

**Gate:** raw versions are immutable, every processed version has complete parent/pipeline lineage, and uploading data never authorizes processing or training automatically.

---

### Task 8: Implement evidence-packet retrieval

**Objective:** Return cited evidence records rather than free-floating generated summaries.

**Files:**
- Create: `src/oscillink_agent/memory/retriever.py`
- Test: `tests/unit/test_retriever.py`

**Route order:**

1. permission, sensitivity and project scope;
2. stable-ID/structured lookup;
3. valid-time and record-time filtering;
4. FTS5 lexical retrieval;
5. contradiction/supersession expansion;
6. token-capped packet construction.

**Packet fields:** record ID, source hash, exact excerpt, epistemic class, validity, status, contradiction IDs, retrieval route/score and index version.

**TDD steps:**

1. Test exact ID/name retrieval.
2. Test as-of temporal retrieval.
3. Test superseded records are excluded from current view but available historically.
4. Test contradictions are included alongside the selected claim.
5. Test prompt-like text remains untrusted data.
6. Implement lexical retrieval only; do not add vectors.
7. Commit: `feat: return provenance-linked evidence packets`.

---

### Task 9: Add the OpenAI-compatible model provider

**Objective:** Call Ollama locally through a provider contract that can later target vLLM or NIM.

**Files:**
- Create: `src/oscillink_agent/providers/base.py`
- Create: `src/oscillink_agent/providers/openai_compatible.py`
- Create: `src/oscillink_agent/config.py`
- Create: `.env.example`
- Create: `scripts/verify_local_model.py`
- Test: `tests/unit/test_model_provider.py`
- Test: `tests/integration/test_ollama_provider.py`

**Configuration:**

```text
OSCILLINK_MODEL_BASE_URL=http://localhost:11434/v1
OSCILLINK_MODEL_NAME=qwen3:14b
OSCILLINK_MODEL_API_KEY=ollama
OSCILLINK_MODEL_CONTEXT_BUDGET=8192
```

**TDD steps:**

1. Mock a valid tool-capable OpenAI response.
2. Test timeout, malformed tool calls, retry cap and server error behavior.
3. Ensure secrets never enter event payloads or logs.
4. Implement async HTTP adapter.
5. Run the integration test against live Ollama.
6. Record exact model identity and generation parameters in each model event.
7. Commit: `feat: add portable model provider`.

**Gate:** the same integration test can pass by changing only environment variables to a compatible remote endpoint.

---

### Task 9A: Add the provider-first agent adapter registry

**Objective:** Connect configured local or hosted agents through allowlisted adapters before exposing Oscillink agents to external clients.

**Files:**
- Create: `src/oscillink_agent/providers/agents.py`
- Create: `src/oscillink_agent/providers/registry.py`
- Test: `tests/contract/test_agent_provider.py`

**Contract:** configured agent identity, run creation, event streaming, cancellation, declared capabilities, usage, bounded errors and provider provenance. Keep this separate from the lower-level `ModelProvider.generate()` contract.

**TDD steps:**

1. Test local and remote adapters against the same contract fixture.
2. Test timeout, cancellation, malformed events and provider outage behavior.
3. Keep credentials server-side and out of browser state, events and logs.
4. Reject arbitrary unreviewed endpoint registration and undeclared capabilities.
5. Record provider/model/agent identity and configuration digest per run.

**Gate:** adding an allowlisted provider requires an adapter/configuration change, not changes to memory, runtime or UI authority rules.

---

### Task 10: Build the context compiler

**Objective:** Assemble a minimal, cited context manifest instead of loading the entire vault.

**Files:**
- Create: `src/oscillink_agent/memory/compiler.py`
- Test: `tests/unit/test_context_compiler.py`

**Context order:**

1. human-owned governance;
2. task and exact authorization;
3. approved project state;
4. cited evidence excerpts;
5. conflicts and stale records;
6. relevant procedures;
7. current budget and stop conditions.

**TDD steps:**

1. Test deterministic output for fixed inputs.
2. Test token-budget truncation preserves governance and citations.
3. Test candidate/untrusted memory is excluded by default.
4. Test every included item has an inclusion reason and source hash.
5. Implement the compiler.
6. Commit: `feat: compile cited task contexts`.

---

### Task 11: Implement the capability broker and supervisor

**Objective:** Ensure model freedom does not become unrestricted execution authority.

**Files:**
- Create: `src/oscillink_agent/runtime/broker.py`
- Create: `src/oscillink_agent/runtime/supervisor.py`
- Create: `docs/threat-model.md`
- Test: `tests/adversarial/test_capability_broker.py`

**Initial capability:** read a file from an allowlisted project root. No shell or arbitrary Python execution.

**TDD steps:**

1. Test exact grant scope, destination, expiration and single-use semantics.
2. Test path traversal, symlink escape and expired grant rejection.
3. Test turn, tool, wall-clock and output limits.
4. Test cancellation terminates the full child process tree.
5. Implement broker and supervisor.
6. Commit: `feat: enforce typed capability grants`.

**Gate:** no model text or retrieved document can create or expand a grant.

---

### Task 11A: Evaluate and prototype a governed workspace terminal

**Objective:** Let customers build and inspect AI infrastructure through reproducible workspace operations without exposing an unrestricted browser-accessible host shell.

**Prerequisites:** authenticated workspace/actor identity, capability broker, process supervisor, full process-tree cancellation, run inspector, secret-redaction policy and one verified bounded read-only tool.

**Files:**
- Create: `src/oscillink_agent/runtime/commands.py`
- Modify: `src/oscillink_agent/runtime/broker.py`
- Modify: `src/oscillink_agent/runtime/supervisor.py`
- Create: `apps/web/src/WorkspaceRunner.tsx`
- Create: `tests/adversarial/test_workspace_commands.py`
- Reference: `docs/workspace-terminal.md`

**Delivery order:**

1. Start with a non-interactive structured command runner declaring executable, arguments, relative working directory, environment allowlist, timeout, output limit, network policy and expected artifacts.
2. Bind every request to actor, workspace, run, policy/grant version and append-only command events.
3. Execute inside a disposable sandbox with read-only workspace access by default, bounded writable outputs, no host home/credential mounts, no Docker socket and network disabled by default.
4. Test path/symlink/reparse escape, cross-workspace access, secret redaction, output/runtime limits, cancellation, process-tree cleanup, grant mismatch/reuse and terminal-control-sequence sanitization.
5. Add a human-interactive PTY only after reconnect, orphan, clipboard, escape-sequence and session-isolation behavior is verified.
6. Permit agent invocation only through narrower typed grants; destructive, privileged, networked, deployment, credential and governance operations remain denied or explicitly confirmation-gated.

**Gate:** human terminal use never grants reusable agent authority, and agent/retrieved text cannot trigger a command or widen its grant. Host execution is a separate high-risk capability and never a silent fallback from sandbox failure.

---

### Task 12: Build the bounded agent loop and API

**Objective:** Produce the first usable local agent interaction with complete event logging.

**Files:**
- Create: `src/oscillink_agent/runtime/loop.py`
- Create: `src/oscillink_agent/api.py`
- Test: `tests/integration/test_agent_loop.py`
- Test: `tests/integration/test_api.py`

**Loop:**

```text
orient → retrieve → plan → request capability → act
       → observe → verify → propose memory → stop/continue
```

**TDD steps:**

1. Test a no-tool answer with cited memory.
2. Test one granted file-read tool call.
3. Test malformed/repeated tool calls terminate safely.
4. Test model memory proposals remain candidate records.
5. Implement loop and `/health`, `/sessions`, `/runs` endpoints.
6. Run the app locally and exercise it with the live Qwen model.
7. Commit: `feat: add bounded local agent loop`.

**Gate:** a fresh process reproduces the correct state and complete event trajectory.

---

### Task 12A: Add authenticated external client access and context-grounding health

**Objective:** Let authorized clients invoke configured Oscillink agents while exposing calibrated context and grounding risk signals for each run.

**Files:**
- Create: `src/oscillink_agent/runtime/health.py`
- Create: `src/oscillink_agent/api_auth.py`
- Modify: `src/oscillink_agent/api.py`
- Create: `apps/web/src/AgentHealth.tsx`
- Test: `tests/adversarial/test_agent_api_auth.py`
- Test: `tests/unit/test_context_health.py`

**External client boundary:**

- authenticated agent/profile IDs and project scopes;
- narrowly scoped credentials, rate/spend limits and revocation;
- idempotent run creation, event streaming and cancellation;
- capability allowlists and complete event provenance;
- no unrestricted public tool-execution endpoint;
- local/private access first; public or multi-tenant exposure requires explicit deployment approval.

**Health signals:** context utilization and remaining budget, evidence/citation coverage, stale evidence, unresolved contradictions, compression depth, retrieval sufficiency, tool failures and post-generation unsupported-claim checks.

The UI label is **Context & Grounding Health**, not a hallucination detector. A composite status must expose its component measurements, threshold version and recommended recovery action. Color is never the only signal.

**Gate:** low health cannot silently expand context or permissions; it triggers abstention, cited carryover, a fresh context or human escalation according to tested policy.

---

### Task 12B: Add bounded dataset processing jobs

**Objective:** Convert registered raw datasets into validated and processed versions through supervised, reproducible workers.

**Files:**
- Create: `src/oscillink_agent/datasets/processor.py`
- Create: `src/oscillink_agent/runtime/jobs.py`
- Test: `tests/adversarial/test_dataset_processing.py`

**Gate:** processing runs in a bounded worker, publishes outputs atomically, records exact code/configuration lineage, preserves raw artifacts and cannot execute dataset-supplied code.

---

### Task 13: Create the longitudinal evaluation harness

**Objective:** Measure whether memory actually improves outcomes.

**Files:**
- Create: `src/oscillink_agent/evaluation/runner.py`
- Create: `src/oscillink_agent/evaluation/metrics.py`
- Create: `src/oscillink_agent/evaluation/baselines.py`
- Create: `evaluations/manifests/public-smoke.yaml`
- Create: `scripts/run_hidden_suite.py`
- Test: `tests/unit/test_evaluation.py`

**Conditions:**

1. no memory;
2. raw transcript;
3. hand-maintained Markdown;
4. generated summary;
5. FTS5 evidence packets;
6. provenance/contradiction-aware packets.

**Metrics:** correctness, citation precision, evidence recall, current/as-of accuracy, obsolete-memory reuse, contradiction detection, abstention, unsafe instruction following, latency, tokens and correction burden.

Also calibrate Context & Grounding Health against observed unsupported-claim, citation and abstention outcomes. Report component metrics as well as any composite status.

**TDD steps:**

1. Test manifest hashing and label isolation.
2. Test candidate and parent receive equal budgets.
3. Test unsupported self-reported completion cannot pass a deterministic evaluator.
4. Implement baseline runner and report bundle.
5. Run public smoke suite, then the protected Oscillink Agent hidden bank.
6. Commit: `test: add longitudinal evaluation harness`.

---

### Task 13A: Add governed training runs

**Objective:** Allow an explicitly approved, training-ready dataset version to start a reproducible candidate-training run only after the evaluation harness exists.

**Required behavior:**

- explicit human approval, budget, base model, dataset/split versions and training configuration;
- pinned code/environment identity and complete output artifact lineage;
- protected holdouts unavailable to the training process;
- parent/candidate evaluation under equal budgets;
- no automatic promotion or production deployment;
- cancellation, resource limits and rollback.

**Gate:** a training run cannot begin from raw/unvalidated data or promote its own result; only independently evaluated candidates can enter governed review.

---

### Task 14: Package the complete local deployment

**Objective:** Make the local system reproducible with one documented startup path.

**Files:**
- Create: `docker-compose.local.yml`
- Modify: `README.md`
- Create: `tests/integration/test_local_deployment.py`

**Steps:**

1. Package API and storage dependencies; keep Ollama as the Windows host service initially.
2. Mount only explicit vault and project paths read-only where possible.
3. Add health/readiness checks.
4. Start the deployment.
5. Run API, restart-recovery and local-model integration tests.
6. Stop it and confirm no orphan processes remain.
7. Commit: `ops: package verified local deployment`.

**Gate:** clean-machine instructions reproduce the same health and evaluation smoke results.

---

### Task 15: Prove cloud portability without deploying production

**Objective:** Validate that storage and model boundaries can move to cloud services without changing domain/runtime code.

**Files:**
- Create: `src/oscillink_agent/storage/postgres.py`
- Create: `src/oscillink_agent/storage/s3.py`
- Create: `docker-compose.cloud-smoke.yml`
- Test: `tests/contract/test_backend_parity.py`

**Steps:**

1. Run local PostgreSQL and S3-compatible MinIO in Docker.
2. Execute the same event-store contract tests against SQLite and PostgreSQL.
3. Execute artifact tests against filesystem and S3 adapters.
4. Run a vLLM-compatible mock server through the existing model adapter.
5. Verify domain/runtime modules contain no backend-specific imports.
6. Commit: `feat: prove cloud backend parity`.

**Gate:** changing environment variables—not agent logic—switches all three backends.

---

### Task 16: First cloud deployment

**Objective:** Deploy a private, observable single-GPU version before considering horizontal scale.

**Prerequisites:** explicit provider/budget selection, secret store, network policy and deletion/backup policy.

**Infrastructure:**

- one GPU VM or approved GPU service;
- vLLM or NIM model server;
- private FastAPI service;
- managed PostgreSQL;
- private S3 bucket;
- TLS and authenticated access;
- OpenTelemetry traces/metrics;
- encrypted backups;
- no public tool-execution endpoint.

**Verification:**

1. Run backend parity tests.
2. Run the public and protected evaluation suites.
3. Compare local versus cloud answer quality, latency, cost and event parity.
4. Exercise restore from backup.
5. Exercise full shutdown and credential revocation.

**Gate:** cloud results preserve provenance and authorization contracts; scaling does not precede functional parity.

---

### Task 17: Scale only from measured demand

**Objective:** Add infrastructure only when telemetry shows a bottleneck.

**Decision gates:**

- add API replicas when concurrent sessions saturate the API, not the GPU;
- add inference replicas when queue wait dominates latency;
- add batching when throughput improves without breaking interaction latency;
- add Redis/NATS only when PostgreSQL/in-process coordination is insufficient;
- add Kubernetes only when replica management, GPU scheduling or tenant isolation justify it;
- add `pgvector` only when lexical/structured retrieval loses on held-out tasks;
- add a graph service only when relational edge queries fail measured workloads.

Every scaling change must pass contract parity, hidden evaluations, security tests and rollback.

---

## 7. Phase gates and release plan

| Release | Finish line | Local/cloud |
|---|---|---|
| `v0.1` | Governed memory kernel, approved retrieval, provider chat and three-event run inspection | Local technical alpha |
| `v0.2.0-alpha` | Authenticated browser-complete governed memory journey | Local/private technical alpha |
| `v0.3` | Crash-safe multi-call run with one governed `file.read` | Local/private |
| `v0.4-private-pilot` | Versioned export/restore, deployment runbook and public evaluation | Private pilot |
| `v0.4` | Completed pilot rehearsal with measured outcomes and no critical recovery/auth defects | Private |
| `v1.0` | Repeated measured continuity improvement, rollback and operational evidence | Hybrid only if demanded |

---

## 8. Tests required before `v1.0`

### Correctness

- restart recovery;
- exact event replay;
- schema round trips;
- idempotent ingestion;
- as-of temporal queries;
- contradictions and supersession;
- evidence citation completeness;
- model-provider parity;
- storage-backend parity.

### Security

- path traversal and symlink escape;
- prompt injection in retrieved notes;
- memory poisoning and delayed influence;
- secret redaction;
- cross-project and cross-user isolation;
- expired/single-use capability grants;
- process-tree termination;
- no unapproved network egress;
- deleted-text remnants in FTS/vector indexes.
- removable-media disconnects, path/reparse escapes and partial-import cleanup;
- archive/format bombs and prohibited dataset deserialization;
- dataset license/sensitivity enforcement and split leakage;
- external client authentication, scope, rate-limit and revocation enforcement.

### Evaluation integrity

- hidden labels unavailable to candidate;
- parent/candidate equal budgets;
- deterministic verification where possible;
- judge calibration against human checks;
- contamination and leakage log;
- worst-case regressions reported;
- failed candidates preserved.

### Operations

- backup and restore;
- local-to-cloud backend switch;
- model-server outage and retry cap;
- clean shutdown;
- observability without prompt/secret leakage;
- rollback to prior model, schema and release.

---

## 9. Primary risks and mitigations

| Risk | Mitigation |
|---|---|
| Fluent but false durable memory | Candidate state, source excerpts, explicit review, contradiction checks |
| “Free model” misunderstood as free infrastructure | Track GPU/electricity/cloud cost separately from model licensing |
| Local model too weak for reliable tool use | Keep provider interface replaceable; use frontier cloud evaluation without making it canonical |
| `gpt-oss-20b` exhausts 16 GB VRAM | Keep Qwen 3 14B baseline; measure constrained context before adoption |
| Obsidian concurrency/schema drift | Validate Markdown, use stable IDs, keep machine events in transactional ledger |
| SQLite becomes a scaling bottleneck | Preserve event-store contract and migrate to PostgreSQL after parity tests |
| Memory poisoning | Quarantine proposals, trust classes, source provenance, adversarial tests |
| Candidate overfits hidden benchmark | Freeze protocols, limit feedback, refresh holdouts, preserve leakage budget |
| Cloud complexity arrives too early | Single GPU VM first; defer queues/Kubernetes until telemetry |
| AGI narrative outruns evidence | Require reproducible longitudinal improvements and publish failures |
| Removable media or imported datasets cross trust boundaries | Explicit selection, streaming validation, quarantine, immutable artifacts and provenance |
| A context-health bar is mistaken for a hallucination detector | Expose calibrated components, uncertainty and recovery policy; never claim certainty |
| Broad provider/client APIs expand authority | Allowlisted adapters, server-side credentials, scoped auth, quotas and broker-enforced capabilities |

---

## 10. Immediate execution order

The repository bootstrap, schemas, ledger, memory authority, approved retrieval,
provider chat and initial workspace already exist. Execute the three active
maturity milestones in dependency order:

```text
authenticated browser-complete memory journey
→ crash-safe multi-call provider/tool trajectory
→ export, restore, deployment and longitudinal pilot evidence
```

Do not add terminal execution, semantic retrieval, datasets, training,
multi-agent orchestration or cloud scale while these finish lines remain open.
