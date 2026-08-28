# Oscillink Agent Local-to-Cloud Implementation Plan

> **For Hermes:** Execute this plan task-by-task with TDD and independent review at phase gates.

**Goal:** Build Oscillink Agent as a locally hosted, open-weight personal agent that develops durable, provenance-linked continuity with Maverick and can later move to scalable cloud infrastructure without rewriting its core contracts.

**Architecture:** Keep the agent core model-agnostic and expose inference through an OpenAI-compatible provider interface. Run Qwen 3 14B through Ollama locally, preserve `gpt-oss-20b` as a measured candidate, and move the same provider contract to vLLM or NVIDIA NIM on a cloud GPU later. Use Obsidian Markdown for human-governed knowledge, an append-only SQLite ledger for local execution events, FTS5 for retrieval, and explicit context manifests for every model call.

**Tech Stack:** Python 3.11, `uv`, FastAPI, Pydantic v2, SQLite WAL/FTS5, Ollama, OpenAI-compatible HTTP, pytest, Ruff, mypy, JSON Schema, YAML, Docker, Obsidian Markdown, Git; later PostgreSQL, S3-compatible object storage, vLLM/NVIDIA NIM, OpenTelemetry, and a managed container/GPU platform.

**Project root:** `C:\Users\Maverick\Projects\oscillink-agent`

---

## 1. Product boundary

Oscillink Agent is a governed longitudinal agent and successor-engineering platform. It should become more useful through verified external memory, reusable skills, better context compilation, tool integration and evaluated candidate improvements.

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

## 2. First 30-day outcome

A fresh local process, with no prior transcript in its prompt, must be able to:

1. recover an approved Oscillink Agent project state;
2. cite every durable memory included in context;
3. identify stale, superseded and contradictory records;
4. answer or abstain based on evidence;
5. execute one narrowly scoped local tool through a typed capability grant;
6. produce a complete event trajectory and context manifest;
7. outperform raw-transcript and hand-summary baselines on a preregistered hidden test bank;
8. stop cleanly within configured turn, time and tool budgets.

---

## 3. Architecture

```text
Obsidian / Git                         Local or cloud model pool
human governance + reviewed state     Ollama → vLLM/NIM
              │                              │
              └──────────┐       ┌───────────┘
                         ▼       ▼
                    FastAPI control plane
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       Context compiler       Capability broker
              │                     │
     evidence packets          typed tool grants
              │                     │
              ▼                     ▼
      SQLite event ledger      disposable runner
      + FTS5 projection        local Docker first
              │
              ▼
       Evaluation/promotion lab
       parent vs candidate
       equal budgets + rollback
```

### Authority by record class

| Record class | Local canonical store | Cloud evolution |
|---|---|---|
| Human governance, approved claims, procedures | Obsidian Markdown + Git | Git-backed repository or reviewed content service |
| Conversations, model calls, tool calls, approvals, outcomes | Append-only SQLite WAL | PostgreSQL append-only/event tables |
| Raw artifacts | Content-addressed local files | S3-compatible object storage |
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

## 4. Model strategy

### Local baseline

Use the already available `qwen3:14b` through Ollama for the first runnable system:

```text
base URL: http://localhost:11434/v1
model: qwen3:14b
license class: open-weight / locally served
initial context budget: 8K–16K tokens
parallel model calls: 1
idle unload: 5 minutes
```

Use `qwen2.5-coder:14b` only for deliberate coding-agent comparisons.

### Candidate model

Benchmark `gpt-oss-20b` only after the full local harness and evaluation bank work with Qwen 3 14B. Its official MXFP4 checkpoint is close to the laptop's 16 GB memory boundary, so the acceptance test must measure:

- successful load;
- VRAM headroom;
- 8K and 16K context behavior;
- tool-call validity;
- tokens/second;
- latency to first token;
- quality on the same hidden tasks;
- model unload behavior.

Do not adopt an unverified “abliterated” derivative as the baseline. Use official open-weight checkpoints with external capability controls.

### Cloud path

1. **First cloud deployment:** one GPU VM, Docker Compose, vLLM, FastAPI and managed PostgreSQL/object storage.
2. **Scale-up:** larger single GPU or tensor-parallel vLLM only when model size requires it.
3. **Scale-out:** multiple stateless API workers and an inference pool behind a gateway after measured concurrency.
4. **Enterprise/NVIDIA option:** NIM for packaged inference and observability if its operational benefits justify the licensing/runtime cost.
5. **Kubernetes:** defer until multiple replicas, rolling deployment, GPU scheduling or tenant isolation create a measured need.

The model alias—not application code—selects local versus cloud inference.

---

## 5. Repository layout

```text
oscillink-agent/
├── .hermes/plans/
├── .github/workflows/ci.yml
├── docs/
│   ├── architecture.md
│   ├── build-plan.md
│   ├── model-strategy.md
│   ├── memory-contract.md
│   ├── threat-model.md
│   └── adr/
│       ├── 0001-openai-compatible-model-boundary.md
│       ├── 0002-authority-by-record-class.md
│       └── 0003-local-first-cloud-portable.md
├── schemas/
│   ├── event.schema.json
│   ├── context-manifest.schema.json
│   ├── capability-grant.schema.json
│   ├── benchmark-manifest.schema.json
│   └── memory-claim.schema.json
├── src/oscillink_agent/
│   ├── __init__.py
│   ├── api.py
│   ├── config.py
│   ├── domain/
│   │   ├── events.py
│   │   ├── memory.py
│   │   ├── context.py
│   │   ├── capabilities.py
│   │   └── benchmarks.py
│   ├── providers/
│   │   ├── base.py
│   │   └── openai_compatible.py
│   ├── storage/
│   │   ├── sqlite.py
│   │   ├── artifacts.py
│   │   └── migrations/
│   ├── memory/
│   │   ├── indexer.py
│   │   ├── retriever.py
│   │   ├── compiler.py
│   │   └── obsidian.py
│   ├── runtime/
│   │   ├── loop.py
│   │   ├── broker.py
│   │   └── supervisor.py
│   └── evaluation/
│       ├── runner.py
│       ├── metrics.py
│       └── baselines.py
├── tests/
│   ├── contract/
│   ├── unit/
│   ├── integration/
│   └── adversarial/
├── evaluations/
│   ├── public/
│   └── manifests/
├── scripts/
│   ├── verify_local_model.py
│   ├── rebuild_index.py
│   └── run_hidden_suite.py
├── .env.example
├── .gitignore
├── AGENTS.md
├── README.md
├── docker-compose.local.yml
├── pyproject.toml
└── uv.lock
```

Protected hidden labels must live outside agent-readable repository paths during actual evaluation.

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

**Objective:** Define the event, context, capability and benchmark schemas before implementing their behavior.

**Files:**
- Create: `schemas/event.schema.json`
- Create: `schemas/context-manifest.schema.json`
- Create: `schemas/capability-grant.schema.json`
- Create: `schemas/benchmark-manifest.schema.json`
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

**Objective:** Create typed Pydantic models that correspond exactly to the schemas.

**Files:**
- Create: `src/oscillink_agent/domain/events.py`
- Create: `src/oscillink_agent/domain/context.py`
- Create: `src/oscillink_agent/domain/capabilities.py`
- Create: `src/oscillink_agent/domain/memory.py`
- Test: `tests/unit/test_domain_models.py`

**TDD steps:**

1. Write tests for round-trip JSON/schema validation.
2. Add tests for valid time versus record time.
3. Add tests preventing mutation of frozen records.
4. Implement the minimum Pydantic models.
5. Run unit and contract suites.
6. Commit: `feat: add typed domain contracts`.

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

### Task 7: Index reviewed Obsidian records into SQLite/FTS5

**Objective:** Deterministically project approved Markdown records into a rebuildable lexical/structured index.

**Files:**
- Create: `docs/memory-contract.md`
- Create: `src/oscillink_agent/memory/obsidian.py`
- Create: `src/oscillink_agent/memory/indexer.py`
- Create: `scripts/rebuild_index.py`
- Test: `tests/integration/test_obsidian_index.py`

**Required record semantics:**

- stable opaque ID;
- record type;
- epistemic class;
- review status;
- valid-time interval;
- record-time interval;
- source IDs and hashes;
- supersedes/contradicts relations;
- sensitivity and project scope.

**TDD steps:**

1. Create a temporary test vault with accepted, candidate, superseded and contradictory records.
2. Confirm the indexer excludes unapproved records from default retrieval.
3. Confirm full index deletion and rebuild produces the same record IDs and hashes.
4. Implement parser, validator and FTS5 projection.
5. Commit: `feat: index reviewed Obsidian memory`.

**Gate:** 100% recovery of canonical IDs and hashes after deleting all derived indexes.

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

**TDD steps:**

1. Test manifest hashing and label isolation.
2. Test candidate and parent receive equal budgets.
3. Test unsupported self-reported completion cannot pass a deterministic evaluator.
4. Implement baseline runner and report bundle.
5. Run public smoke suite, then the protected Oscillink Agent hidden bank.
6. Commit: `test: add longitudinal evaluation harness`.

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
| `v0.1` | Contracts, append-only ledger, deterministic tests | Local |
| `v0.2` | Obsidian indexing and cited retrieval | Local |
| `v0.3` | Qwen-powered bounded agent with one safe tool | Local |
| `v0.4` | Hidden longitudinal evaluation and poisoning tests | Local |
| `v0.5` | Reproducible local Docker deployment | Local |
| `v0.6` | PostgreSQL/S3/model-provider parity | Local cloud-smoke |
| `v0.7` | Private single-GPU cloud deployment | Cloud |
| `v1.0` | Measured continuity improvement, rollback and operational runbook | Hybrid |

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

---

## 10. Immediate execution order

Execute Tasks 1–4 first. Do not write the agent loop until schemas and hidden evaluation structure exist.

The first implementation checkpoint is:

```text
repository initialized
+ project note created
+ quality gates passing
+ four schemas valid
+ immutable domain objects tested
```

Only then proceed to event storage and memory retrieval.
