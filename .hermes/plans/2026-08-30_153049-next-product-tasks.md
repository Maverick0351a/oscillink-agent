# Oscillink Next Product Tasks

> **For Hermes:** Execute production behavior with strict vertical RED → GREEN → REFACTOR TDD. Use deterministic local self-review; do not use reviewer subagents or temporary review worktrees. Buildbox verifies an immutable exact commit only after local candidate and immutable-range verification.

**Goal:** Establish Oscillink Project Memory as a useful open-source coding-agent continuity product while testing, without actuator control, whether Oscillink's provenance and evaluation substrate is valuable for human-supervised physical-intelligence data.

**Architecture:** Keep one event-sourced, provider-neutral core for durable memory, corrections, provenance, capability grants, and evaluation. Expose it first through a local MCP/CLI sidecar for coding agents. Explore physical intelligence through a separate LeRobot-compatible dataset inspection adapter that reads recorded episodes but cannot command hardware.

**Tech Stack:** Python 3.11, Pydantic v2, SQLite, FastAPI, MCP over local stdio, pytest, Ruff, mypy, React/Vitest, Hugging Face LeRobotDataset v3 inspection, pinned public fixtures.

---

## Current state and priority decision

- Repository: `main` at `a1a47ea`, clean, one commit ahead of `origin/main`.
- Deterministic longitudinal public evaluation exists and has been verified locally and on Buildbox.
- The current roadmap names browser pilot Task 3.4 next, but the repository does not yet expose the one-command coding-agent sidecar required by the selected community wedge.
- Public-launch basics are missing: `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md`.
- No physical-intelligence connector, dataset fixture, episode contract, user study, or safety analysis exists.

### Priority order

1. **Make the repository safely publishable and the promise understandable.**
2. **Build one complete Project Memory MCP continuity slice.**
3. **Prove the five-minute multi-agent continuity demonstration.**
4. **Complete only the thin browser evidence/recovery surface needed to support that demonstration.**
5. **Run external coding-agent validation.**
6. **In parallel, validate a non-actuating LeRobot Data Doctor experiment.**
7. **Expand either lane only after its validation gate passes.**

At most three workstreams may be active:

1. Project Memory/public launch.
2. Coding-agent integration and evaluation.
3. Physical-intelligence discovery experiment.

---

# Workstream A — Immediate repository and public-launch work

## Task A1: Freeze the public product boundary and license

**Objective:** Make the open-source/community promise and commercial boundary explicit before accepting public adoption.

**Files:**
- Create: `LICENSE`
- Create: `docs/open-source-boundary.md`
- Modify: `README.md`
- Modify: `pyproject.toml`

**Steps:**
1. Decide between Apache-2.0, MPL-2.0, and AGPL-3.0 before adding a license. Recommended default: Apache-2.0 for low-friction robotics/agent adoption, with paid hosted operations rather than source-code exclusivity as the moat.
2. State that local memory, provenance, correction, context compilation, evaluation, and adapters are open.
3. State that hosted encrypted synchronization, team coordination, enterprise connectors, managed deployment, audit, and support are expected paid layers.
4. Replace broad product language with the first outcome: install once, preserve corrected project history across compatible coding agents, survive compaction, and inspect why context was selected.
5. Preserve the physical-intelligence direction as an experimental adjacency, not a shipping robot-control claim.
6. Verify package metadata and README claims against executable behavior.

**Finish line:** A new visitor can identify the target user, first five-minute outcome, local/no-account path, current limitations, and license without reading internal architecture documents.

## Task A2: Add community and security files

**Objective:** Make public contribution and vulnerability handling credible before promotion.

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `SECURITY.md`
- Create: `docs/community-validation.md`

**Required behavior:**
- Document Python 3.11, `uv`, frontend commands, LF line endings, strict TDD, and `PYTHONPATH=` verification.
- Prohibit secrets, runtime databases, private prompts, hidden labels, and unsafe actuator/shell additions.
- Document responsible disclosure without inventing an unavailable email or security program.
- Define evidence-bearing issues: reproduction, exact version, expected/observed behavior, sanitized artifacts.

**Verification:** Run documentation link checks available in the repository and the full candidate verifier.

## Task A3: Rewrite onboarding around one outcome

**Objective:** Reduce the current private-pilot-heavy README to a five-minute community path while retaining advanced runbooks.

**Files:**
- Modify: `README.md`
- Create: `docs/project-memory-quickstart.md`
- Modify: `docs/product-description.md`
- Modify: `docs/build-plan.md`

**Finish line:** The main README leads with Project Memory, gives one local command, shows one multi-agent continuity demo, and moves private-pilot infrastructure detail into linked documentation.

---

# Workstream B — Coding-agent wedge implementation

## Task B1: Freeze the Project Memory sidecar contract

**Objective:** Define the smallest MCP/CLI behavior that demonstrates corrected, cited continuity without creating a second memory system.

**Files:**
- Create: `docs/project-memory-contract.md`
- Create: `src/oscillink_agent/integrations/mcp/contracts.py`
- Create: `tests/contract/test_project_memory_mcp_contract.py`
- Modify: `pyproject.toml` only if an entry point or reviewed dependency is required.

**Initial tools:**
- `remember`: create a candidate project-memory revision with source provenance.
- `recall`: return deterministic, budgeted approved memory and citations.
- `correct`: create a correction/supersession candidate; never silently overwrite history.
- `explain`: show why a record was selected, excluded, stale, contradicted, or unapproved.

**Deferred from the first slice:** generalized conversation rewind, workspace Git rollback, cloud sync, semantic vectors, broad tool execution, and automatic high-risk promotion.

**Contract constraints:**
- Local stdio transport first.
- No account or external credential.
- No raw host paths in public responses.
- Retrieved content remains untrusted.
- Low-risk observations may be auto-curated only under an explicit policy; corrections and conflicts remain inspectable.
- Deterministic context budgets and truncation.
- Typed unavailable/failure states without raw exception leakage.

## Task B2: Implement a read-only MCP continuity slice

**Status:** Completed in `3e462f6`; final paths use
`src/oscillink_agent/integrations/mcp/cli.py` and
`tests/integration/test_project_memory_mcp.py`.

**Objective:** Let one compatible agent call `recall` and `explain` against the existing approved memory/context compiler.

**Likely files:**
- Create: `src/oscillink_agent/integrations/__init__.py`
- Create: `src/oscillink_agent/integrations/mcp/__init__.py`
- Create: `src/oscillink_agent/integrations/mcp/server.py`
- Create: `src/oscillink_agent/cli.py`
- Create: `tests/unit/test_mcp_recall.py`
- Create: `tests/integration/test_mcp_stdio.py`
- Modify: `pyproject.toml`

**TDD slices:**
1. Server initialization and capability listing.
2. Empty workspace returns typed unavailable state.
3. Approved memory is returned with exact revision citations.
4. Candidate/rejected/missing/superseded memory is excluded.
5. Budget pressure truncates deterministically and reports omissions.
6. Malformed and oversized requests fail closed.
7. Subprocess stdio test proves the installed entry point works without network credentials.

**Finish line:** One local command starts a read-only MCP server and a real subprocess client retrieves approved, cited project context.

## Task B3: Add governed `remember` and `correct`

**Status:** Implemented and candidate-verified locally; pending immutable-range verification.

**Objective:** Complete the cross-agent learning loop without silent canonical mutation.

**Likely files:**
- Modify: `src/oscillink_agent/integrations/mcp/server.py`
- Reuse: `src/oscillink_agent/memory/service.py`
- Reuse: `src/oscillink_agent/proposals/service.py`
- Create: `tests/integration/test_mcp_memory_lifecycle.py`
- Create: `tests/adversarial/test_mcp_memory_boundary.py`

**Required tests:**
- Candidate creation preserves actor/source provenance.
- Correction references the exact prior memory and revision.
- Contradictory updates are surfaced instead of merged into invented truth.
- Repeated idempotency keys cannot duplicate changes.
- Retrieved text cannot authorize promotion or tool access.
- Sensitive-looking values are rejected or redacted according to the existing boundary.
- Restart reconstructs the exact lifecycle.

**Finish line:** Agent A records a decision, a governed correction supersedes it, and Agent B retrieves only the approved current revision while `explain` preserves the old decision and correction lineage.

## Task B4: Build the five-minute continuity demonstration

**Objective:** Prove the public promise with two real compatible clients before advertising five integrations.

**Artifacts:**
- Create: `examples/project-memory-demo/README.md`
- Create: `examples/project-memory-demo/project-fixture/`
- Create: `scripts/run_project_memory_demo.py`
- Create: `tests/acceptance/test_project_memory_demo.py`
- Add a pinned public evaluation case without agent-readable labels.

**Scenario:**
1. Agent A learns three project decisions and one failed approach.
2. Simulate compaction/restart with no transcript replay.
3. Correct one decision with provenance.
4. Agent B continues the task using the corrected history.
5. Verify it does not repeat the failed approach or reuse the superseded decision.
6. Display exact context cost, omissions, citations, and revision lineage.

**Integration order:**
1. Hermes plus one independently testable MCP coding client.
2. Add Claude Code, OpenCode, Cline, Cursor, or Codex only after each compatibility path is exercised directly.

**Finish line:** Clean-machine setup to useful cited recall takes under five minutes, requires no account, and the acceptance test reproduces the same manifest under the same inputs.

## Task B5: Narrow roadmap Task 3.4 to evidence needed by the demo

**Objective:** Preserve the useful browser control-center work without letting a broad UI milestone delay the sidecar.

**Files from the existing roadmap:**
- Create: `apps/web/src/EvaluationSummary.tsx`
- Create: `apps/web/src/EvaluationSummary.test.tsx`
- Create or narrow: `apps/web/src/WorkspaceOperations.tsx`
- Create or narrow: `apps/web/src/WorkspaceOperations.test.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`
- Add authenticated read-only evaluation and server-managed export routes only where absent.

**Required behavior:**
- Show condition, provider, code revision, dataset/fixture revision, budget, metric definitions, failures, and stale/unavailable state.
- Restore may select only a governed server-managed export manifest and requires confirmation.
- No browser-triggered training, memory promotion, arbitrary host path, composite truth score, or robot control.

**Finish line:** The browser can inspect the same evidence emitted by the CLI demo; it is not required for first use.

---

# Workstream C — Physical-intelligence discovery experiment

## Task C1: Complete focused problem validation

**Objective:** Determine whether the first valuable physical artifact is episode quality/correction tooling rather than assuming funding equals product demand.

**Research targets:**
- Five robotics hobbyists using LeRobot/SO-101 or similar hardware.
- Five embodied-AI researchers or lab engineers.
- Five teleoperators, data-collection leads, or robot deployment engineers where reachable.
- Firsthand GitHub issues/discussions from LeRobot, Isaac Lab, robomimic, ROS/MCAP, and open teleoperation projects.

**Questions:**
- How are episodes rejected, retried, corrected, and versioned today?
- Which failures are discovered only after training?
- How much operator and reviewer time is spent per accepted hour/trajectory?
- How are calibration, sensor, controller, environment, task, and operator revisions tracked?
- How are interventions and recovery trajectories represented?
- What would they safely run on existing data this week?
- Who owns the budget for collection operations, data quality, and evaluation?

**Deliverable:** `docs/research/physical-skillops-discovery.md` with direct sources, dates, caveats, current workarounds, strongest counterargument, and a build/monitor/reject decision.

**Gate:** Do not add a robot-control adapter unless interviews and workflow evidence identify a bounded need that cannot be solved read-only.

## Task C2: Freeze a read-only episode receipt contract

**Objective:** Map existing Oscillink provenance primitives onto recorded robot episodes without inventing a universal robotics ontology.

**Files:**
- Create: `docs/physical-intelligence-safety-boundary.md`
- Create: `src/oscillink_agent/physical/episode_contracts.py`
- Create: `tests/contract/test_episode_receipt.py`
- Create: `evaluations/fixtures/lerobot-smoke/` using reproducible, licensed, SHA-256-pinned public bytes.

**Minimum receipt:**
- Episode/task identity and revision.
- Robot/embodiment, controller, sensor, calibration, operator, and environment provenance.
- Original timestamps and synchronization facts.
- Success, failure, intervention, and correction annotations as separate evidence-bearing fields.
- Dataset membership revision and supersession/deletion state.
- Explicit distinction between reversible digital state and irreversible physical action.

**Non-goals:** No actuator command, live intervention, safety score, certification claim, policy training, or policy promotion.

## Task C3: Build the LeRobot Data Doctor vertical slice

**Objective:** Inspect an existing local LeRobotDataset and emit an actionable, reproducible episode-quality report.

**Likely files:**
- Create: `src/oscillink_agent/physical/lerobot_adapter.py`
- Create: `src/oscillink_agent/physical/doctor.py`
- Create: `scripts/run_lerobot_data_doctor.py`
- Create: `tests/unit/test_lerobot_adapter.py`
- Create: `tests/integration/test_lerobot_data_doctor.py`

**First checks:**
- Dataset finalization/completeness.
- Missing or inconsistent robot/calibration/task identifiers.
- Timestamp monotonicity and cross-stream gaps.
- Missing frames or incomplete episodes where deterministically observable.
- Excessive idle segments.
- Duplicated episodes using transparent deterministic signals.
- Missing success/failure/intervention labels.
- Train/evaluation split leakage by exact content identity.

**Output:** Machine-readable report plus human-readable retake/curation recommendations. Do not claim that a heuristic proves policy quality.

**Finish line:** The tool finds seeded defects in a pinned fixture, reports a clean fixture honestly, runs without robot hardware, and never imports an actuator or teleoperation command path.

## Task C4: Optional Hermes read-only operator-copilot demo

**Prerequisite:** C1 validates the problem and C3 is useful to at least three external users on their own datasets.

**Allowed MCP operations:**
- `inspect_dataset`
- `explain_episode_issue`
- `compare_dataset_revisions`
- `propose_retake_queue`
- `summarize_evaluation`

**Forbidden:** Direct joint commands, robot enable/disable, safety PLC changes, emergency-stop control, unrestricted ROS topic publication, training promotion, or deployment.

---

# Deferred work

Do not begin until a preceding gate creates evidence:

- General desktop-agent replacement.
- Ambient screen recording.
- Universal semantic/vector memory.
- Cloud multi-tenancy and broad enterprise workflows.
- More than two coding-agent integrations before the demo works.
- Teleoperator labor marketplace.
- Robot foundation-model training.
- Generic data-labeling platform.
- Live actuator control or unrestricted ROS 2 publishing.
- Household humanoid application platform.
- Physical-action “rewind” claims.
- Automatic policy promotion or browser-triggered training.
- Custom robot hardware.

---

# Measurable validation gates

## Gate 1 — Public readiness

Pass only if:
- License and open/commercial boundary are explicit.
- Security and contribution documents exist.
- No secrets, private fixtures, hidden labels, or runtime databases are present.
- Clean local installation succeeds from documented commands.
- Full verifier passes and claims match executable behavior.

## Gate 2 — Coding-agent technical efficacy

Pass only if:
- Setup to first useful recall is under five minutes on a clean environment.
- Two independently exercised clients use the same corrected project memory.
- Compaction/restart requires no raw transcript replay.
- Superseded memory is not reused.
- Failed approaches remain available as history but are not recommended as current truth.
- Context manifests and citations are deterministic under equal inputs and budgets.
- Offline fake-provider execution requires no credentials.

## Gate 3 — Coding-agent product evidence

Run a bounded alpha with at least five external users. Continue only if:
- At least three use it across three separated sessions.
- At least two independently report avoiding re-explanation, repeated mistakes, or stale context.
- Users provide their own project data rather than only watching the demo.
- At least one requests a concrete integration or hosted/team capability.
- Human review and cleanup time do not erase the measured benefit.

If the gate fails, improve onboarding or narrow the use case before adding features.

## Gate 4 — Physical-intelligence problem evidence

Pass only if:
- At least ten firsthand workflow records across hobbyist, research, and operator contexts identify repeated episode-quality, correction, lineage, or evaluation burden.
- At least three users run Data Doctor on their own datasets.
- The tool finds at least one actionable issue for at least two users.
- One user requests a specific integration, recurring workflow, or paid/private pilot.
- The value is not already solved adequately by a trivial existing LeRobot command.

If the gate fails, keep the episode contract as a reusable component and do not expand into robotics operations.

## Gate 5 — Physical deployment consideration

Even after Gate 4, any actuator-connected work requires a separate safety plan covering simulation-first testing, bounded action spaces, deterministic low-level control, hardware emergency stop, operator responsibility, authentication, network isolation, incident logging, insurance/liability, and the fact that physical actions cannot be rolled back.

---

# Immediate execution sequence

1. **A1:** Decide license/open-core boundary and update positioning.
2. **A2:** Add public community/security documents.
3. **B1:** Freeze the four-tool Project Memory MCP contract.
4. **B2:** Implement read-only `recall`/`explain` over stdio.
5. **B3:** Implement governed `remember`/`correct`.
6. **B4:** Prove the two-client, five-minute continuity demo.
7. **B5:** Add only the browser evidence/recovery views needed to inspect the demo.
8. **Gate 1 + Gate 2:** Run full local verification, commit, immutable-range verification, then exact-SHA Buildbox verification.
9. **Gate 3:** Recruit the first five coding-agent alpha users.
10. **In parallel after A1:** Run C1 physical workflow discovery.
11. **Only if C1 supports it:** Implement C2 and C3 as a read-only LeRobot experiment.
12. **Only after Gate 4:** Consider C4 Hermes operator-copilot integration.

The next production implementation task is **A1: public product boundary and license**, followed immediately by **B1/B2: the read-only Project Memory MCP slice**. The next physical-intelligence task is **C1: firsthand workflow validation**, not robot control.
