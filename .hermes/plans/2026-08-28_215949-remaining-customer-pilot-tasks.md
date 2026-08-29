# Oscillink Agent Remaining Customer-Pilot Tasks

**Goal:** Deliver a private, customer-usable, provider-neutral agentic memory workspace that can create, govern, retrieve, cite, and act from durable product-owned memory with inspectable runs and deterministic recovery.

**Current baseline:** Product-owned `mem_…` identities, immutable revisions, approve/reject/supersede governance, optional Obsidian synchronization, artifact association, restart recovery, authority-aware Memory Lattice projections, and browser approve/reject controls are implemented and verified through commit `5a3b110`.

**Customer problems:** fragmented continuity, opaque or poisoned durable memory, irreproducible context and actions, provider/connector lock-in, overly broad execution authority, and incomplete recovery. The infrastructure response is governed memory, approved-only provenance-bearing retrieval, deterministic context manifests, provider-neutral adapters, bounded capabilities, inspectable runs and portable backup/restore.

**Execution discipline:** Keep no more than three active workstreams—Trustworthy Memory, Agent Workspace, and Provider/Runtime. Implement each milestone as a RED → GREEN → REFACTOR vertical slice, commit only after `scripts/verify.py --base HEAD`, and run immutable `--base HEAD^ --require-clean` verification after every milestone commit. Use deterministic local review; do not use reviewer subagents or temporary review worktrees.

---

## Recommended sequence

### 1. Native memory creation in the browser

**Outcome:** A customer can launch without Obsidian, create a candidate, receive a stable `mem_…` identity, inspect it immediately, approve or reject it, restart, and recover the same record and review history.

**Likely files:**
- `apps/web/src/memoryApi.ts`
- `apps/web/src/MemoryWorkspace.tsx`
- `apps/web/src/MemoryInspector.tsx`
- `apps/web/src/styles.css`
- `apps/web/src/MemoryWorkspace.test.tsx`
- `tests/integration/test_product_memory_api.py`

**Tasks:**
1. Add typed `createMemoryNode` client support.
2. Add a compact create-memory form with title, content, category, domains, and topics.
3. Validate required fields and preserve form data on API failure.
4. Refresh the product projection and focus the newly created stable ID after success.
5. Test successful creation, validation failure, API failure, double-submit prevention, and stale-response behavior.

**Finish line:** The complete no-Obsidian acceptance path works from the browser and survives restart.

### 2. Explicit source synchronization and import UX

**Outcome:** A customer can configure an optional source, explicitly synchronize it, see created/updated counts, and inspect source-backed product records without treating paths as canonical IDs.

**Likely files:**
- `src/oscillink_agent/api.py`
- `src/oscillink_agent/memory/repository.py`
- `src/oscillink_agent/memory/obsidian.py`
- `apps/web/src/memoryApi.ts`
- `apps/web/src/MemoryWorkspace.tsx`
- `tests/integration/test_product_memory_api.py`
- `tests/integration/test_artifact_import_api.py`

**Tasks:**
1. Expose source configuration/status without guessing a vault path.
2. Add an explicit synchronize action with typed event and idempotency identities.
3. Display sync results, conflicts, degraded notes, and unchanged-record outcomes.
4. Add explicit browser file selection/import using the existing governed artifact pipeline.
5. Show candidate associations to `mem_…` targets and route proposals into review rather than silently mutating approved memory.

**Finish line:** Connect or import → synchronize → inspect stable product IDs → rename/move source → synchronize → preserve identity.

### 3. Approved-only retrieval and evidence packets

**Outcome:** Agent retrieval excludes candidates, rejected records, superseded records, and unauthorized records by default while preserving provenance and contradiction visibility.

**Likely files:**
- `src/oscillink_agent/domain/memory.py`
- `src/oscillink_agent/memory/repository.py`
- `src/oscillink_agent/storage/interfaces.py`
- `src/oscillink_agent/memory/projection.py`
- `tests/unit/test_memory_domain.py`
- new retrieval unit/integration tests under `tests/`

**Tasks:**
1. Define a provider-neutral `MemoryQuery` and `EvidencePacket` contract.
2. Enforce authorization and authority eligibility before ranking.
3. Add deterministic lexical retrieval over approved/current revisions.
4. Preserve citations, content hashes, source bindings, contradiction state, and inclusion reasons.
5. Test that maximum relevance cannot admit an ineligible candidate and that mandatory policy/contradiction records are not suppressed.

**Finish line:** Given the same repository and query, retrieval returns the same approved evidence packet with inspectable reasons.

### 4. Deterministic context compiler and manifest

**Outcome:** Every model call receives a bounded context assembled from explicit inputs, and every inclusion or omission is replayable.

**Likely files:**
- `src/oscillink_agent/domain/context.py`
- `schemas/context-manifest.schema.json`
- `src/oscillink_agent/storage/sqlite.py`
- `src/oscillink_agent/api.py`
- new context compiler tests under `tests/unit/` and `tests/integration/`

**Tasks:**
1. Finalize context budget, manifest, citation, and omission contracts.
2. Compile approved evidence packets under deterministic token/record budgets.
3. Record exact memory revision hashes, retrieval policy version, provider configuration, and omission reasons.
4. Persist manifests append-only and expose them through typed APIs.
5. Verify deterministic replay after restart.

**Finish line:** A stored manifest reproduces the exact governed context supplied to a run.

### 5. Provider-neutral chat with citations

**Outcome:** A customer can configure an allowlisted provider, chat against approved memory, and inspect which memory supported each response.

**Likely files:**
- `src/oscillink_agent/providers/base.py`
- `src/oscillink_agent/providers/openai_compatible.py`
- `src/oscillink_agent/config.py`
- `src/oscillink_agent/api.py`
- new chat/provider components under `apps/web/src/`
- provider contract tests under `tests/`

**Tasks:**
1. Add deterministic fake-provider tests before real provider behavior.
2. Add an allowlisted provider registry and server-side credential boundary.
3. Support streaming responses and explicit failure/cancellation states.
4. Couple each response to a stored context manifest and citations.
5. Add customer-visible provider/model identity without making Qwen or any provider the product identity.

**Finish line:** Chat → cited answer → inspect exact approved context and provider configuration → restart → recover the session and manifest.

### 6. Run timeline and proposal-review workspace

**Outcome:** Customers can inspect the full trajectory of a run and govern model-generated durable-memory proposals.

**Likely files:**
- `src/oscillink_agent/domain/events.py`
- `src/oscillink_agent/storage/sqlite.py`
- `src/oscillink_agent/api.py`
- new run/proposal components under `apps/web/src/`
- run replay and proposal integration tests under `tests/integration/`

**Tasks:**
1. Persist session, model-call, retrieval, context, proposal, review, failure, and recovery events.
2. Add a chronological run inspector with event details and citations.
3. Add a proposal queue where generated memory remains a candidate until human promotion.
4. Preserve corrections, contradictions, retractions, supersession, and lineage.
5. Add restart/replay tests that compare recovered state with the original run.

**Finish line:** Every durable change and model response can be traced to its source evidence, run, proposal, and human decision.

### 7. One bounded read-only tool

**Outcome:** The agent can perform one useful action through typed, scoped, expiring grants without arbitrary host execution.

**Likely files:**
- `src/oscillink_agent/domain/capabilities.py`
- `schemas/capability-grant.schema.json`
- `src/oscillink_agent/api.py`
- capability and supervisor tests under `tests/`

**Tasks:**
1. Select one pilot-relevant read-only tool.
2. Validate typed arguments, resource scope, expiry, budgets, and actor identity.
3. Execute through an isolated adapter; do not add arbitrary shell or Python execution.
4. Record request, grant, observation, denial, timeout, and sanitized failure events.
5. Surface tool activity in the run inspector.

**Finish line:** The customer can see exactly what was requested, permitted, executed, returned, or denied.

### 8. Private-pilot packaging and operational hardening

**Outcome:** One customer/workspace can install, authenticate, back up, restore, and operate the product reproducibly.

**Likely files:**
- `src/oscillink_agent/config.py`
- `src/oscillink_agent/api.py`
- deployment/configuration files at repository root
- `README.md`
- `docs/threat-model.md`
- new backup/restore and authentication tests

**Tasks:**
1. Add private single-workspace authentication and secure server-side provider configuration.
2. Add workspace export, backup, restore, deletion, and rollback contracts.
3. Package a reproducible local/private deployment with health checks and bounded shutdown.
4. Add observability for repository health, provider health, budgets, and failed jobs without logging secrets or private prompts.
5. Run the complete customer acceptance journey and document recovery procedures.

**Finish line:** A clean machine can deploy the pilot, complete the customer workflow, restart, restore from backup, and pass deterministic verification.

### 9. Governed workspace terminal evaluation

**Outcome:** Customers can run reproducible development and inspection commands without turning Oscillink into a terminal wrapper or granting agents unrestricted host access.

**Prerequisites:** Milestones 6–8 must provide authenticated actor/workspace identity, capability grants, process supervision, run inspection, secret redaction, cancellation and recovery.

**Tasks:**
1. Begin with a structured non-interactive command runner, not a persistent shell.
2. Record executable, arguments, relative working directory, policy, actor, bounds, output, exit status and artifacts.
3. Execute in a disposable sandbox with read-only workspace mounts and network disabled by default.
4. Test path escape, cross-workspace access, secret leakage, terminal escape sequences, limits, cancellation and process-tree cleanup.
5. Add a human-interactive PTY only after reconnect/orphan and browser transport risks are verified.
6. Keep agent-proposed commands inert until approved and agent invocation narrower than human-interactive authority.

**Finish line:** Workspace commands are bounded, attributable, cancellable, secret-redacted and inspectable; sandbox failure never silently falls back to host execution. See `docs/workspace-terminal.md`.

### 10. Memory Focus after retrieval governance is proven

**Outcome:** Customers can emphasize eligible memory without changing truth, approval, authorization, relevance, freshness, confidence, or contradiction handling.

**Prerequisite:** Milestones 3 and 4 must be complete so Focus can be applied after eligibility and recorded in context manifests.

**Tasks:**
1. Define versioned `FocusProfile` persistence with bounded levels `-2 … +2`.
2. Support profile, workspace, domain/category, and record scopes with deterministic precedence.
3. Apply Focus only as a bounded reranking adjustment among eligible records.
4. Add impact preview, reset, and “why included” explanations.
5. Record effective focus policy/version in every affected `ContextManifest`.
6. Keep “Pin to context” separate and budget-declared.

**Finish line:** Focus changes ranking within eligible memory, cannot promote a candidate, cannot hide contradictions or mandatory policy, and replays deterministically.

---

## Deferred until the pilot loop is proven

- Public multi-tenancy and broad external APIs.
- Removable-volume discovery and drag/drop breadth.
- Dataset/training workflows beyond what a validated customer wedge requires.
- Dense/vector retrieval until lexical/structured retrieval has measured deficiencies.
- Redis, NATS, Kubernetes, multi-GPU serving, and other scale infrastructure without measured need.
- Agent-authored Focus changes without explicit human review.
- Claims of consciousness, identity transfer, AGI, or autonomous self-improvement.

## Verification required for every milestone

```bash
PYTHONPATH= .venv/Scripts/python.exe -m pytest -q
PYTHONPATH= .venv/Scripts/python.exe -m ruff check . --no-cache
PYTHONPATH= .venv/Scripts/python.exe -m mypy src --cache-dir .mypy_cache
npm --prefix apps/web test -- --run
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
```

After each milestone commit:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD^ --require-clean
```

## Pilot completion definition

```text
launch without Obsidian
→ create native candidate in browser
→ receive stable mem_… identity
→ review and approve
→ retrieve only eligible approved memory
→ compile and persist exact context manifest
→ chat through a configured provider with citations
→ inspect run, tools and proposals
→ restart and recover identical governed state
→ export, restore and verify the workspace
```
