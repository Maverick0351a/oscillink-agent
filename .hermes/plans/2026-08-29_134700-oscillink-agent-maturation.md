# Oscillink Agent Maturation Implementation Plan

> **For Hermes:** Execute this plan task-by-task with strict RED → GREEN → REFACTOR TDD, deterministic local self-review, and the checked-in verification gates. Do not use reviewer subagents or temporary review worktrees.

**Goal:** Mature Oscillink Agent from a strong governed-agent technical alpha into a reproducible private-pilot product with a browser-complete memory journey, one crash-safe governed tool trajectory, and measured continuity value.

**Architecture:** Preserve product-owned memory identities, immutable revisions, append-only execution events, content-addressed artifacts, provider-neutral adapters, and typed capability grants. Complete one vertical customer path before adding breadth: authenticated workspace → memory/source onboarding → governed review → cited provider response → persisted run/tool inspection → restart/export/restore. Persist external-call intent before dispatch and model multi-call runs as ordered causal trajectories rather than extending the current one-call assumptions.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLite WAL/FTS5, React 19, TypeScript, Vite, Vitest, pytest, Ruff, strict mypy, JSON Schema, `uv`, npm, Ollama/OpenAI-compatible providers.

**Target baseline:** `main` at `75664d847ba26f8493397e339754475258e1ed47`, package version `0.1.0`, 239 Python tests plus 25 frontend tests passing.

---

## Product constraints

1. Keep at most three active milestones.
2. Do not expose unrestricted host shell, arbitrary Python, broad network access, or reusable model credentials.
3. Do not let source presence, retrieval similarity, model output, or UI placement grant memory authority.
4. Do not add vectors, datasets, training, multi-agent orchestration, PostgreSQL/S3, Kubernetes, or PTY work until the three milestones below pass.
5. Every external call follows `persist intent → dispatch → persist outcome`.
6. Every browser-visible authority/readiness state comes from a typed backend contract.
7. Every milestone must pass the candidate gate before commit and the immutable-range gate after commit.
8. Use `PYTHONPATH=` and `.venv/Scripts/python.exe` for all project Python commands.

---

# Milestone 1 — Browser-complete governed memory journey

**Outcome:** A new private local user can initialize, populate, review, query, inspect, restart, and recover a workspace entirely through the browser without direct API calls.

**Finish line:** From an empty data directory, the user can authenticate to one local workspace, create native memory, explicitly synchronize an Obsidian source or import one configured-scope file, approve a revision, ask a question, inspect the exact cited context, restart the API/browser, and recover the same state.

**Explicit deferrals:** Removable-volume discovery, drag/drop host authority, vectors, datasets, appearance editing, terminal execution, public accounts, multi-tenancy.

## Task 1.1: Reconcile roadmap and release truth

**Objective:** Replace stale “next milestone” claims with a current executable-capability ledger and the three milestones in this plan.

**Files:**
- Modify: `README.md:16-30`
- Modify: `docs/build-plan.md:51-105`
- Modify: `docs/build-plan.md:225-300`
- Modify: `docs/build-plan.md:1056-1067`
- Modify: `.hermes/plans/2026-08-27_183950-oscillink-agent-local-to-cloud.md`
- Test: `tests/unit/test_verify_script.py`

**Steps:**
1. Add a failing verifier test requiring roadmap states to use `implemented`, `preview`, `contract-only`, `planned`, or `deferred`.
2. Run `PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/unit/test_verify_script.py -v`; expect failure.
3. Rewrite the current-state and immediate-order sections; preserve long-horizon design material but remove stale claims that approved-only retrieval and provider chat are future work.
4. Keep the mirrored `.hermes` plan byte-identical to `docs/build-plan.md` until the mirror invariant is intentionally redesigned.
5. Rerun the focused test; expect pass.
6. Run `PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD`.
7. Commit only this documentation/governance slice: `docs: reconcile Oscillink Agent maturity roadmap`.
8. Run `PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD^ --require-clean`.

## Task 1.2: Define authenticated local workspace contracts

**Objective:** Introduce one server-owned actor/workspace boundary before exposing additional browser mutations.

**Files:**
- Create: `src/oscillink_agent/workspaces/contracts.py`
- Create: `src/oscillink_agent/workspaces/service.py`
- Create: `src/oscillink_agent/workspaces/routes.py`
- Create: `src/oscillink_agent/api_auth.py`
- Modify: `src/oscillink_agent/api.py`
- Modify: `src/oscillink_agent/status/contracts.py`
- Modify: `src/oscillink_agent/status/routes.py`
- Create: `tests/adversarial/test_local_workspace_auth.py`
- Modify: `tests/integration/test_status_api.py`
- Modify: `schemas/event.schema.json` only if actor/workspace linkage requires a compatible schema revision

**Required contract:**
- one configured local workspace ID and opaque per-launch credential;
- server-derived human actor ID;
- constant-time credential comparison;
- mutation routes require the credential;
- read route policy is explicit, not accidental;
- strict allowed origins/hosts for the local frontend;
- no credential in logs, status, events, exceptions, frontend persistence, or `repr`;
- typed `unavailable | locked | ready` workspace/auth state;
- test injection can provide deterministic credentials without weakening production defaults.

**Steps:**
1. Write failing ASGI tests proving anonymous create/review/sync/import/chat mutations return 401 and create no storage.
2. Add tests proving a valid credential is bound to the configured workspace and actor.
3. Add tests for malformed, missing, wrong, and revoked/rotated credentials.
4. Add tests proving status contains readiness only, never credential material.
5. Implement the minimum dependency/middleware and workspace contracts.
6. Route actor identity into application services; do not leave `human_local_user` as a route-level assumption.
7. Run `PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/adversarial/test_local_workspace_auth.py tests/integration/test_status_api.py -v`.
8. Run Ruff and mypy on the touched Python boundaries.
9. Run the full candidate verifier.
10. Commit: `feat: add authenticated local workspace boundary`.
11. Run the immutable-range verifier.

## Task 1.3: Fix context-manifest transport parity

**Objective:** Make the backend context-manifest wire shape and frontend TypeScript contract exact so the persisted run inspector cannot render undefined metadata.

**Files:**
- Modify: `src/oscillink_agent/domain/context.py`
- Modify: `src/oscillink_agent/context/compiler.py`
- Modify: `schemas/context-manifest.schema.json`
- Modify: `apps/web/src/chatApi.ts`
- Modify: `apps/web/src/RunInspector.tsx`
- Modify: `tests/contract/test_schemas.py`
- Modify: `tests/integration/test_chat_runtime_api.py`
- Modify: `apps/web/src/App.test.tsx`

**Decision:** Prefer adding bounded display metadata (`title`, category, domains) to revision-bound `ContextItem` if the manifest is intended to remain independently inspectable. Otherwise remove those fields from TypeScript and render stable ID/hash only. Do not fetch mutable current-record metadata and present it as historical run truth.

**Steps:**
1. Add a failing integration test that validates the actual chat response against the frontend-required manifest projection.
2. Add a failing frontend test using the exact backend fixture, not a hand-expanded TypeScript-only fixture.
3. Implement the smallest contract-aligned shape on backend, schema, and frontend.
4. Add restart inspection regression coverage.
5. Run contract, chat API, and frontend focused tests.
6. Run the full candidate verifier.
7. Commit: `fix: align persisted context manifest transport`.
8. Run the immutable-range verifier.

## Task 1.4: Add browser-native memory creation

**Objective:** Let an authenticated user create a candidate memory revision with explicit category, domains, topics, and architecture associations.

**Files:**
- Create: `apps/web/src/MemoryCreatePanel.tsx`
- Modify: `apps/web/src/memoryApi.ts`
- Modify: `apps/web/src/MemoryWorkspace.tsx`
- Modify: `apps/web/src/styles.css`
- Create: `apps/web/src/MemoryCreatePanel.test.tsx`
- Modify: `apps/web/src/MemoryWorkspace.test.tsx`
- Modify: `src/oscillink_agent/memory/contracts.py` only if transport feedback fields are missing
- Modify: `tests/integration/test_product_memory_api.py`

**Required behavior:**
- create action is unavailable while workspace auth is locked;
- form starts with no implied approval;
- result is visibly `candidate`;
- successful mutation refreshes the lattice from the API;
- mutation success plus refresh failure are represented separately;
- stale async completion cannot replace a newly selected inspector;
- bounded fields and architecture associations match backend enums exactly.

**Steps:**
1. Write failing frontend tests for locked, pending, success, mutation-failure, and refresh-failure states.
2. Add an authenticated API integration fixture.
3. Implement `createMemoryNode()` in `memoryApi.ts` with typed request identity and idempotency metadata if added server-side.
4. Implement the form and refresh behavior.
5. Run focused backend and frontend tests.
6. Run full verification.
7. Commit: `feat: add browser-native memory creation`.
8. Run immutable verification.

## Task 1.5: Add explicit source synchronization controls

**Objective:** Expose configured Obsidian synchronization as an authenticated, explicit, inspectable browser action.

**Files:**
- Create: `apps/web/src/SourceSyncPanel.tsx`
- Modify: `apps/web/src/memoryApi.ts`
- Modify: `apps/web/src/MemoryWorkspace.tsx`
- Create: `apps/web/src/SourceSyncPanel.test.tsx`
- Modify: `tests/integration/test_product_memory_api.py`
- Modify: `src/oscillink_agent/memory/contracts.py`
- Modify: `src/oscillink_agent/memory/routes.py`

**Required behavior:**
- no automatic source scan or sync on page load;
- configured source shown by opaque kind/status, never absolute path;
- explicit confirmation before synchronization;
- result reports created, revised, unchanged, missing, and issue counts rather than only total records;
- idempotent retry does not duplicate revisions;
- source changes never inherit prior approval.

**Steps:**
1. Add failing API tests for typed synchronization accounting.
2. Add failing frontend tests for unavailable, confirmation, success, conflict, and refresh-failure states.
3. Extend the response contract and repository accounting minimally.
4. Implement the browser control.
5. Run focused tests and full verification.
6. Commit: `feat: add explicit browser source synchronization`.
7. Run immutable verification.

## Task 1.6: Add browser file import and proposal review

**Objective:** Complete one governed selected-file path from configured scope to immutable artifact to reviewable candidate association.

**Files:**
- Create: `apps/web/src/ArtifactImportPanel.tsx`
- Create: `apps/web/src/artifactApi.ts`
- Create: `apps/web/src/ProposalQueue.tsx`
- Modify: `apps/web/src/MemoryWorkspace.tsx`
- Modify: `apps/web/src/styles.css`
- Create: `apps/web/src/ArtifactImportPanel.test.tsx`
- Create: `apps/web/src/ProposalQueue.test.tsx`
- Create: `src/oscillink_agent/proposals/contracts.py`
- Create: `src/oscillink_agent/proposals/repository.py`
- Create: `src/oscillink_agent/proposals/routes.py`
- Modify: `src/oscillink_agent/api.py`
- Modify: `src/oscillink_agent/artifact_imports/service.py`
- Create: `tests/integration/test_memory_proposal_api.py`
- Modify: `tests/integration/test_artifact_import_api.py`

**Required behavior:**
- browser selects only among server-exposed opaque configured scopes/targets; no arbitrary absolute path field;
- import remains untrusted evidence;
- association remains `pending_review`;
- proposal queue resolves ledger-backed proposals and supports approve/reject with attributed human actor;
- approval creates a governed product-memory revision or governed relationship according to an explicit contract, not an event that no product projection can consume;
- idempotency covers target association and decision;
- restart recovers pending and resolved proposal states.

**Steps:**
1. Freeze the proposal state machine in failing contract/integration tests.
2. Add a read projection for pending/resolved proposals derived from durable events or a dedicated repository with explicit ledger lineage.
3. Add authenticated approve/reject routes.
4. Add browser import and proposal queue tests using deferred promises.
5. Implement the UI and API clients.
6. Run artifact, proposal, product-memory, and frontend focused suites.
7. Execute an empty-workspace live browser/API acceptance journey.
8. Run the full verifier.
9. Commit: `feat: complete governed browser import and proposal review`.
10. Run immutable verification.

## Milestone 1 acceptance gate

Run:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
```

Then execute a scripted/live acceptance journey from an empty temporary data root and record exact HTTP/UI outcomes. After committing the milestone:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD^ --require-clean
```

Acceptance assertions:
- anonymous mutation fails closed;
- authenticated empty-workspace journey completes in browser;
- candidate content never enters model context;
- approved revision is cited;
- restart preserves workspace, memory, proposals, and run;
- browser receives no absolute source path or credential;
- worktree is clean.

---

# Milestone 2 — Crash-safe provider and first governed tool loop

**Outcome:** One provider-neutral run can safely perform a single approved `file.read`, persist every intent/outcome, make a follow-up model call, and reconstruct the complete causal trajectory after restart.

**Finish line:** A deterministic provider requests one exact file; a human grants one use; the broker reads it as `external_untrusted`; a follow-up response is persisted; retry cannot repeat the call or reuse the grant; the browser inspector shows the complete ordered trajectory.

**Explicit deferrals:** Shell/PTY, write tools, network tools, parallel tools, autonomous grant issuance, broad tool registry, multi-agent execution.

## Task 2.1: Freeze a typed multi-step run state machine

**Objective:** Remove the one-model-call/one-response cardinality assumption before adding tools.

**Files:**
- Create: `src/oscillink_agent/agent_runtime/contracts.py`
- Modify: `src/oscillink_agent/agent_runtime/repository.py`
- Modify: `src/oscillink_agent/chat/contracts.py`
- Modify: `src/oscillink_agent/domain/events.py` only if a new explicit intent/failure type is required
- Modify: `schemas/event.schema.json`
- Create: `tests/unit/test_run_reconstruction.py`
- Modify: `tests/integration/test_chat_runtime_api.py`

**Required trajectory:**

```text
request_recorded
→ context_compiled
→ model_call_pending
→ model_call_succeeded | model_call_failed | model_call_interrupted
→ tool_requested | final_response
→ grant_approved | grant_denied
→ tool_call_claimed
→ observation | tool_failed
→ follow_up_model_call
→ final_response
```

**Steps:**
1. Add failing reconstruction tests with two model calls, one tool call, one observation, and a final response.
2. Add malformed-order, missing-parent, duplicate-final-response, and interrupted-run tests.
3. Implement causal ordered reconstruction without selecting the first event by type.
4. Preserve compatibility with existing three-event runs.
5. Run focused repository and API tests.
6. Run full verification.
7. Commit: `feat: reconstruct typed multi-step agent runs`.
8. Run immutable verification.

## Task 2.2: Persist provider intent before dispatch

**Objective:** Eliminate the crash window in which an external provider call occurs without durable intent.

**Files:**
- Modify: `src/oscillink_agent/agent_runtime/service.py`
- Modify: `src/oscillink_agent/agent_runtime/repository.py`
- Modify: `src/oscillink_agent/storage/sqlite.py`
- Modify: `tests/integration/test_chat_runtime_api.py`
- Modify: `tests/unit/test_provider_adapters.py`
- Create: `tests/adversarial/test_provider_dispatch_recovery.py`

**Required ordering:**
1. Validate idempotency before provider access.
2. Persist user request, context artifact, and pending provider-call event atomically enough to identify the intended dispatch.
3. Dispatch provider.
4. Persist success, bounded failure, timeout, or interruption.
5. On retry, resolve the durable state before deciding whether dispatch is safe.

**Steps:**
1. Write a provider test double that observes storage at `generate()` entry; require pending intent and context artifact to exist.
2. Add a crash-after-dispatch regression and define the conservative retry response.
3. Add durable failure and timeout inspection tests.
4. Refactor orchestration into prepare/dispatch/finalize phases.
5. Run focused adversarial and integration tests.
6. Run full verification.
7. Commit: `fix: persist provider intent before dispatch`.
8. Run immutable verification.

## Task 2.3: Correct configured provider and actor provenance

**Objective:** Ensure durable events truthfully identify the configured provider/model and server-derived human actor.

**Files:**
- Modify: `src/oscillink_agent/providers/base.py`
- Modify: `src/oscillink_agent/providers/config.py`
- Modify: `src/oscillink_agent/agent_runtime/service.py`
- Modify: `src/oscillink_agent/artifact_imports/service.py`
- Modify: `tests/unit/test_provider_adapters.py`
- Modify: `tests/integration/test_chat_runtime_api.py`
- Modify: `apps/web/src/RunInspector.tsx`
- Modify: `apps/web/src/App.test.tsx`

**Steps:**
1. Add a failing configured-provider test asserting no event actor/operation claims `deterministic_fake` or `fake_provider_chat`.
2. Add tests for server-derived human actor identity on chat/import/review events.
3. Add a public provider execution identity contract containing only non-secret kind/model/actor metadata.
4. Generate operation and actor values from that contract.
5. Add run-inspector coverage for provider/model display.
6. Run focused tests and full verification.
7. Commit: `fix: record truthful provider and actor provenance`.
8. Run immutable verification.

## Task 2.4: Add typed tool-request/provider contracts

**Objective:** Allow the deterministic provider and OpenAI-compatible adapter to return either a final answer or one bounded `file.read` request.

**Files:**
- Modify: `src/oscillink_agent/providers/base.py`
- Modify: `src/oscillink_agent/providers/fake.py`
- Modify: `src/oscillink_agent/providers/openai_compatible.py`
- Create: `src/oscillink_agent/agent_runtime/tools.py`
- Modify: `tests/unit/test_provider_adapters.py`
- Create: `tests/contract/test_tool_request_contract.py`

**Required behavior:**
- discriminated result: `final_response | tool_request`;
- only exact registered `file.read` operation;
- portable scope/target request, never host path;
- malformed, repeated, undeclared, or oversized requests fail closed;
- provider text cannot fabricate an approved grant;
- no parallel calls in this milestone.

**Steps:**
1. Freeze valid and invalid tool-request fixtures.
2. Add fake-provider deterministic tool-request behavior.
3. Parse OpenAI-compatible tool calls into the same strict contract.
4. Reject unknown operations and extra fields.
5. Run contract and provider tests.
6. Run full verification.
7. Commit: `feat: add bounded provider tool-request contract`.
8. Run immutable verification.

## Task 2.5: Expose human grant approval and broker invocation through the runtime

**Objective:** Connect ledger-backed human approval, the existing capability broker, and one run trajectory without exposing a generic execution endpoint.

**Files:**
- Create: `src/oscillink_agent/capabilities/routes.py`
- Create: `src/oscillink_agent/capabilities/service.py`
- Modify: `src/oscillink_agent/capabilities/broker.py`
- Modify: `src/oscillink_agent/api.py`
- Modify: `src/oscillink_agent/agent_runtime/service.py`
- Create: `tests/integration/test_agent_file_read_loop.py`
- Modify: `tests/adversarial/test_capability_broker.py`

**Required behavior:**
- authenticated human approves one exact pending request;
- authorization event is persisted before grant registration;
- caller cannot submit an arbitrary pre-approved grant object;
- grant subject matches configured model actor and run;
- consumption remains atomic and restart-safe;
- observation is marked `external_untrusted` and recorded before follow-up provider dispatch;
- no physical host path enters response, event, artifact metadata, or browser state;
- denial/failure/expiry/reuse are inspectable terminal states.

**Steps:**
1. Add failing end-to-end integration tests for approved, denied, expired, mismatched, reused, restart, and file-failure trajectories.
2. Add authenticated grant decision route bound to the pending request/run.
3. Call the existing broker from runtime service after durable approval resolution.
4. Append `TOOL_CALL` and `OBSERVATION` events with exact causal parents.
5. Dispatch one follow-up provider call using approved memory plus untrusted observation under an explicit prompt boundary.
6. Run capability and runtime focused suites.
7. Run full verification.
8. Commit: `feat: connect one governed file-read agent loop`.
9. Run immutable verification.

## Task 2.6: Extend the browser run inspector and approval surface

**Objective:** Let the user inspect and approve the pending tool request and then view the complete persisted trajectory.

**Files:**
- Create: `apps/web/src/CapabilityApprovalPanel.tsx`
- Modify: `apps/web/src/chatApi.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/RunInspector.tsx`
- Modify: `apps/web/src/runInspector.css`
- Create: `apps/web/src/CapabilityApprovalPanel.test.tsx`
- Modify: `apps/web/src/App.test.tsx`

**Required behavior:**
- approval shows exact logical scope, target, actor, expiry, byte limit, extensions, and network denial;
- no host path or credential appears;
- approve/reject is target-scoped and authenticated;
- pending, denied, consumed, failed, and succeeded states are distinct;
- inspector reloads persisted trajectory after mutation;
- stale async results cannot replace another run’s inspector.

**Steps:**
1. Write deferred-promise frontend tests for approve/reject, mutation failure, refresh failure, and changed selection.
2. Implement typed API clients and approval panel.
3. Extend event timeline rendering for provider intent, tool request, approval, tool call, observation, follow-up call, and final response.
4. Add exact JSON trajectory view separate from the manifest view.
5. Run focused frontend tests and production build.
6. Run a live fake-provider browser/API tool journey.
7. Run full verification.
8. Commit: `feat: inspect and approve governed tool runs`.
9. Run immutable verification.

## Milestone 2 acceptance gate

Acceptance assertions:
- provider intent is durable before dispatch;
- real provider events never claim fake identity;
- one run reconstructs two model calls and one tool observation;
- grant reuse fails after restart;
- crash/failure states are inspectable;
- no untrusted observation grants authority or enters approved memory automatically;
- browser terminal remains execution-locked;
- full candidate and immutable-range verifiers pass.

---

# Milestone 3 — Reproducible private pilot and measured value

**Outcome:** One design partner can install, operate, recover, export, and evaluate Oscillink with evidence about whether governed memory improves a real longitudinal workflow.

**Finish line:** A clean-machine private deployment completes the core journey, restores from backup, switches between fake/local/hosted provider configurations without migrating canonical memory, and produces a versioned evaluation report against simpler baselines.

**Explicit deferrals:** Public SaaS, multi-tenant billing, Kubernetes, PostgreSQL/S3, training, datasets, terminal/PTY, generalized tool marketplace.

## Task 3.1: Define migration and workspace export contracts

**Objective:** Make all durable stores versioned, inspectable, and portable before declaring pilot readiness.

**Files:**
- Create: `src/oscillink_agent/storage/migrations.py`
- Create: `src/oscillink_agent/workspaces/export.py`
- Create: `src/oscillink_agent/workspaces/contracts.py` or extend the Milestone 1 file
- Modify: `src/oscillink_agent/memory/repository.py`
- Modify: `src/oscillink_agent/capabilities/broker.py`
- Modify: `src/oscillink_agent/storage/sqlite.py`
- Create: `tests/integration/test_workspace_export_restore.py`
- Create: `tests/adversarial/test_migration_recovery.py`

**Required behavior:**
- explicit schema version for event, memory, capability, and proposal stores;
- ordered, restart-safe migrations with backup/failure behavior;
- export manifest hashes every included database/artifact;
- export excludes credentials, launch tokens, caches, indexes, and absolute host paths;
- restore verifies hashes, rejects traversal/corruption, and rebuilds derived projections;
- failed restore never partially replaces the active workspace;
- deletion and rollback semantics are documented even if administrative deletion remains a later operation.

**Steps:**
1. Write failing migration-from-v1 and interrupted-migration tests.
2. Write failing export/restore round-trip and corrupt-manifest tests.
3. Implement a minimal version registry and atomic restore staging.
4. Add workspace export/restore API or CLI only through authenticated human authority.
5. Run focused recovery suites.
6. Run full verification.
7. Commit: `feat: add versioned workspace export and restore`.
8. Run immutable verification.

## Task 3.2: Package a reproducible local/private deployment

**Objective:** Provide one documented startup path with health, shutdown, bounded configuration, and no accidental public exposure.

**Files:**
- Create: `docker-compose.local.yml` or a Windows-first launcher if Docker adds no immediate value
- Create: `scripts/launch_private_pilot.py`
- Create: `src/oscillink_agent/health/contracts.py`
- Create: `src/oscillink_agent/health/routes.py`
- Modify: `src/oscillink_agent/api.py`
- Modify: `README.md`
- Create: `docs/private-pilot-runbook.md`
- Create: `tests/integration/test_local_deployment.py`

**Required behavior:**
- explicit bind address and origin policy;
- generated per-launch credential delivered outside logs;
- readiness distinguishes API, stores, provider reachability, and broker state;
- liveness does not mutate storage;
- bounded graceful shutdown;
- no orphan server/process;
- documented backup, restore, rotation, logs, and failure recovery;
- provider outage does not corrupt runs.

**Steps:**
1. Write failing black-box deployment and health tests.
2. Implement the smallest launcher and health projection.
3. Exercise fake provider, live Ollama when available, and a local OpenAI-compatible mock.
4. Stop and restart; verify state and no orphan process.
5. Follow the runbook from a clean disposable copy.
6. Run full verification.
7. Commit: `ops: package reproducible private pilot`.
8. Run immutable verification.

## Task 3.3: Build the minimum longitudinal evaluation runner

**Objective:** Measure the product’s core claim before adding retrieval or infrastructure complexity.

**Files:**
- Create: `src/oscillink_agent/evaluation/contracts.py`
- Create: `src/oscillink_agent/evaluation/runner.py`
- Create: `src/oscillink_agent/evaluation/metrics.py`
- Create: `src/oscillink_agent/evaluation/baselines.py`
- Create: `evaluations/manifests/public-smoke.yaml`
- Create: `scripts/run_public_evaluation.py`
- Create: `tests/unit/test_evaluation_runner.py`
- Create: `tests/integration/test_public_evaluation.py`
- Modify: `.gitignore`

**Initial conditions:**
1. no durable memory;
2. raw transcript excerpt;
3. generated summary;
4. approved Oscillink lexical context.

**Initial metrics:**
- answer correctness against public deterministic labels;
- citation precision;
- evidence recall;
- obsolete-memory reuse;
- contradiction handling where fixtures support it;
- abstention when approved evidence is insufficient;
- prompt-injection following from retrieved content;
- latency;
- context units/provider usage where available;
- human correction burden captured as a pilot field, not fabricated automatically.

**Required integrity:**
- exact manifest and fixture hashes;
- equal budgets across conditions;
- no protected labels inside agent-readable runtime context;
- deterministic fake-provider smoke separate from model-quality runs;
- failed candidates/results preserved;
- results labeled by provider/model/configuration and code revision.

**Steps:**
1. Freeze public fixture and manifest schema in failing tests.
2. Implement deterministic baseline runners and equal-budget enforcement.
3. Implement metric bundle and machine-readable report.
4. Run the public fake-provider smoke.
5. Run a live local/provider comparison only when the provider is reachable; report unavailable rather than substituting mock quality.
6. Run full verification.
7. Commit: `test: add longitudinal public evaluation`.
8. Run immutable verification.

## Task 3.4: Add browser pilot operations and evaluation summaries

**Objective:** Make recovery state and measured outcomes visible without turning metrics into unsupported confidence claims.

**Files:**
- Create: `apps/web/src/WorkspaceOperations.tsx`
- Create: `apps/web/src/EvaluationSummary.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`
- Create: `apps/web/src/WorkspaceOperations.test.tsx`
- Create: `apps/web/src/EvaluationSummary.test.tsx`
- Add authenticated API routes for export and evaluation-report retrieval

**Required behavior:**
- export is explicit human action;
- restore requires confirmation and uses an uploaded governed artifact/manifest path, never arbitrary host path;
- evaluation displays condition, provider, revision, budget, metric definitions, and failures;
- no composite “truth” or “hallucination” score;
- unavailable or stale evaluation is visibly labeled;
- UI cannot trigger training or promotion.

**Steps:**
1. Add frontend tests for unavailable, stale, success, failure, and confirmation states.
2. Implement operations and read-only evaluation summary surfaces.
3. Run focused tests and production build.
4. Run full verification.
5. Commit: `feat: expose pilot recovery and evaluation evidence`.
6. Run immutable verification.

## Task 3.5: Conduct one design-partner pilot rehearsal

**Objective:** Convert technical readiness into evidence about customer value and operational friction.

**Artifacts:**
- Create: `docs/pilot-protocol.md`
- Create: `docs/pilot-readiness-checklist.md`
- Store actual customer/private results outside the public repository unless explicitly sanitized and approved.

**Protocol:**
1. Choose one bounded longitudinal workflow with repeated corrections and source changes.
2. Record the baseline process and success criteria before using Oscillink.
3. Complete onboarding without developer API intervention.
4. Run at least three sessions separated by restart.
5. Introduce one source revision, one rejected proposal, and one contradiction fixture.
6. Export and restore the workspace.
7. Switch provider configuration without migrating memory.
8. Score correctness, citation precision, stale-memory use, abstention, correction burden, setup time, and recovery time.
9. Record failures and user confusion without rewriting the protocol after seeing outcomes.
10. Decide whether the next release should improve workflow, retrieval, operations, or commercial packaging based on measured evidence.

**Finish line:** A signed-off pilot report identifies one customer outcome, one next action, one finish line, and no more than three remaining active risks.

## Milestone 3 acceptance gate

Run the full candidate verifier and immutable post-commit verifier. Additionally require:
- clean-machine launch succeeds;
- authenticated browser journey succeeds;
- provider outage and restart are truthful;
- export/restore reproduces canonical IDs, revisions, reviews, events, and artifact hashes;
- public evaluation report is reproducible from its manifest;
- no release claim depends on fake-provider answer quality;
- no credentials or private pilot data enter Git;
- release tag remains blocked until all required pilot checks pass.

---

# Release progression

| Release | Required finish line |
|---|---|
| `v0.2.0` | Milestone 1: authenticated browser-complete governed memory journey |
| `v0.3.0` | Milestone 2: crash-safe provider/tool trajectory with one `file.read` |
| `v0.4.0-private-pilot` | Milestone 3 tasks 3.1–3.4: deployment, recovery, evaluation package |
| `v0.4.0` | One completed pilot rehearsal with documented blockers and no critical recovery/auth defects |

Do not tag a release merely because the test suite is green. Tag only after the corresponding executable finish line passes from a clean committed revision.

---

# Verification commands

## Focused Python

```bash
PYTHONPATH= .venv/Scripts/python.exe -m pytest <focused-test-paths> -v
PYTHONPATH= .venv/Scripts/python.exe -m ruff check <touched-paths> --no-cache
PYTHONPATH= .venv/Scripts/python.exe -m mypy src --cache-dir .mypy_cache
```

## Focused frontend

```bash
npm --prefix apps/web test -- <focused-test-file>
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

## Candidate gate before every milestone commit

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
```

## Immutable range after commit

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD^ --require-clean
```

## Required review evidence

For each task/milestone record:
- exact revision and worktree status;
- focused RED command and expected failure;
- focused GREEN command and exact pass count;
- full verifier output and reviewed diff hash;
- post-commit immutable-range verifier output;
- live acceptance result where required;
- explicit skipped tests and reasons;
- unresolved blockers after no more than two remediation cycles.

---

# Principal risks and mitigations

| Risk | Mitigation |
|---|---|
| Authentication work becomes a full account platform | Implement one private local workspace and per-launch credential only |
| Browser workflow hides backend authority | Keep all visible status and actions bound to typed server responses |
| Provider retry duplicates paid/external calls | Persist pending intent before dispatch and define interrupted recovery states |
| Tool loop weakens memory trust | Keep observations `external_untrusted`; never promote automatically |
| Run repository remains one-call-shaped | Complete typed multi-step reconstruction before wiring broker |
| Frontend fixtures drift from transport | Validate exact backend fixtures/shared generated types across boundary |
| Export leaks secrets or host paths | Hash/allowlist export contents and adversarially inspect the archive |
| Evaluation becomes self-congratulatory | Freeze baselines, equal budgets, public labels, and preserve negative results |
| Pilot scope expands into terminal/MLOps/cloud | Enforce explicit milestone deferrals and one customer journey |
| Windows symlink checks remain skipped locally | Require corresponding Ubuntu CI coverage and add Windows reparse-specific tests where feasible |

---

# Definition of mature enough for private pilot

Oscillink Agent is private-pilot ready only when all are true:

- one authenticated browser workflow works from empty workspace through restart;
- memory creation, sync/import, review, retrieval, citation, and proposal resolution are UI-complete;
- provider intent and outcomes are durable across failure;
- provider/actor provenance is truthful;
- one bounded `file.read` trajectory is inspectable and single-use after restart;
- export and restore reproduce canonical state;
- local deployment has health, shutdown, and a runbook;
- at least one public evaluation compares governed memory with simpler baselines;
- no critical auth, cross-scope, path, secret, or recovery defect remains;
- the exact committed release candidate passes both local and hosted gates;
- the project can state measured wins and losses without AGI, consciousness, or autonomy claims.
