# Oscillink Agent Buildbox-Backed Continuation Plan

> **For Hermes:** Execute this plan task-by-task using strict RED → GREEN → REFACTOR, deterministic local review, and exact-SHA buildbox verification. Do not use reviewer subagents or temporary review worktrees; `docs/review-process.md` and `AGENTS.md` are authoritative.

**Goal:** Advance Oscillink Agent from the verified browser-memory baseline at `81965dd45730b5f786985f2e5d40dacb4892bf06` to a browser-complete governed-memory release, then a crash-safe governed tool loop, and finally a reproducible private pilot—with buildbox providing independent Linux evidence for every promoted milestone.

**Architecture:** Predator remains the authoring and governance machine. Git identifies immutable candidates. Buildbox imports exact commits into detached, clean checkouts and runs them as the locked `builder` account inside a bounded systemd slice. Passing evidence informs human promotion but never authorizes buildbox to repair, push, tag, deploy, or promote code.

**Tech Stack:** Python 3.11.15, uv 0.12.0, FastAPI, Pydantic, SQLite, React 19, TypeScript, Vite, Vitest, Node 24.18.1, npm 11.16.0, Git bundles over SSH, buildbox systemd resource controls.

---

## 1. Current verified baseline

- Predator repository: `C:\Users\Maverick\Projects\oscillink-agent`
- Branch: `main`
- HEAD: `81965dd45730b5f786985f2e5d40dacb4892bf06`
- Remote: `https://github.com/Maverick0351a/oscillink-agent.git`
- Divergence: local `main` is four commits ahead of `origin/main`; worktree is clean.
- Completed commits:
  1. `62651af` — roadmap reconciliation
  2. `eff6625` — authenticated workspace boundary
  3. `7281542` — persisted context-manifest parity
  4. `81965dd` — browser-native candidate memory creation
- Latest Linux evidence: 256 Python tests, 33 frontend tests, Ruff, strict mypy, TypeScript, Vite, npm audit, schemas, LF checks, security scan, clean Git checks, and bounded headless API smoke all passed on buildbox after reboot.
- Buildbox checkout: `/srv/buildbox/checkouts/oscillink-agent-81965dd45730b5f786985f2e5d40dacb4892bf06`
- Active detailed implementation plan: `.hermes/plans/2026-08-29_134700-oscillink-agent-maturation.md`
- Next unfinished product task: Task 1.5, explicit source synchronization.

## 2. Operating discipline from this point forward

Keep one product outcome active at a time. The maximum three active workstreams remain:

1. **Trustworthy Memory** — current priority through Milestone 1.
2. **Provider and Runtime** — begins only after Milestone 1 is accepted.
3. **Private Pilot Operations and Evaluation** — begins only after Milestone 2 is accepted.

For every task commit:

```text
Predator RED test
→ confirm RED for the intended reason
→ minimal GREEN implementation
→ focused regression suite
→ full local candidate gate
→ deterministic self-review
→ commit
→ immutable local gate
→ exact-SHA buildbox import
→ bounded full Linux gate
→ optional bounded smoke/acceptance journey
→ human promotion/push/tag decision
```

Do not develop directly on buildbox. A Linux-only failure returns to Predator as a failing test and normal TDD change.

---

# Phase A — Publish and freeze the four-commit verified baseline

**Outcome:** The remote repository exposes the exact buildbox-proven baseline so future builds do not depend on recreating local-only history.

**Finish line:** `origin/main` points to `81965dd`, Predator and buildbox evidence agree on the cumulative four-commit range, hosted CI passes, and no history was rewritten.

### Task A1: Verify the cumulative local range

**Files:** No production changes.

1. Reconfirm the Predator worktree and exact divergence:

   ```bash
   git status --short --branch
   git rev-list --left-right --count origin/main...HEAD
   git log --oneline origin/main..HEAD
   ```

   Expected: clean worktree, `0 4`, and exactly the four known commits.

2. Run the candidate verifier over the complete unpublished range:

   ```bash
   PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base origin/main --require-clean --skip-sync
   ```

   Expected: all deterministic gates pass and a cumulative diff SHA-256 is reported.

3. Record in the milestone result:
   - base SHA `75664d847ba26f8493397e339754475258e1ed47`;
   - candidate SHA `81965dd45730b5f786985f2e5d40dacb4892bf06`;
   - Python/frontend test counts;
   - cumulative reviewed diff digest.

### Task A2: Verify the same cumulative range on buildbox

1. Use the existing detached checkout and bounded runner:

   ```bash
   ssh buildbox \
     'sudo buildbox-run oscillink-agent 81965dd45730b5f786985f2e5d40dacb4892bf06 -- \
      /opt/buildbox/bin/uv run --python 3.11.15 python scripts/verify.py \
      --base 75664d847ba26f8493397e339754475258e1ed47 --require-clean --skip-sync'
   ```

2. Expected:
   - 256 Python tests pass;
   - 33 frontend tests pass;
   - all four Linux symlink cases execute;
   - cumulative diff digest matches Predator;
   - checkout remains clean.

### Task A3: Promote the baseline to GitHub

1. Obtain explicit human approval in the active conversation immediately before pushing.
2. Push without force:

   ```bash
   git push origin main
   ```

3. Confirm:

   ```bash
   git fetch origin
   git rev-parse HEAD origin/main
   gh run list --branch main --limit 5
   ```

4. Require hosted Ubuntu and Windows CI to pass.
5. Do not tag a release yet; Milestone 1 is not complete.

---

# Phase B — Complete Milestone 1: browser-complete governed memory

**Outcome:** An authenticated user can create candidate memory, explicitly synchronize a configured source, import configured-scope evidence, review proposals, approve governed memory, chat with approved-only context, inspect citations/runs, restart, and recover state.

**Finish line:** The empty-workspace browser/API journey passes on Predator and buildbox, including restart recovery, with no absolute source path, credential, or candidate content crossing the wrong authority boundary.

## Task B1: Explicit source synchronization controls

Use Task 1.5 in the maturation plan as the detailed contract.

**Likely files:**
- Create: `apps/web/src/SourceSyncPanel.tsx`
- Create: `apps/web/src/SourceSyncPanel.test.tsx`
- Modify: `apps/web/src/memoryApi.ts`
- Modify: `apps/web/src/MemoryWorkspace.tsx`
- Modify: `src/oscillink_agent/memory/contracts.py`
- Modify: `src/oscillink_agent/memory/routes.py`
- Modify: `src/oscillink_agent/memory/service.py`
- Modify: `src/oscillink_agent/memory/repository.py` only if durable accounting requires it
- Modify: `tests/integration/test_product_memory_api.py`

### RED

Add focused tests proving:

1. Synchronization never occurs on API construction or browser page load.
2. Anonymous synchronization fails before repositories or data roots initialize.
3. The browser sees opaque source kind/status, never an absolute vault path.
4. Explicit confirmation is required before mutation.
5. Typed results distinguish `created`, `revised`, `unchanged`, `missing`, and `issues`.
6. Idempotent retry creates no duplicate revision.
7. Source changes create new candidate revisions and never inherit approval.
8. Mutation success plus lattice-refresh failure remains distinguishable.
9. A stale asynchronous completion cannot replace newer workspace state.

Run:

```bash
PYTHONPATH= .venv/Scripts/python.exe -m pytest tests/integration/test_product_memory_api.py -q
npm --prefix apps/web test -- --run SourceSyncPanel MemoryWorkspace memoryApi
```

Expected before implementation: focused failures for missing typed accounting and browser control.

### GREEN

1. Extend the synchronization response contract with deterministic per-outcome counts.
2. Compute accounting from actual repository outcomes, not requested item count.
3. Preserve source identity and lineage without serializing host paths.
4. Add an authenticated explicit route; do not add background/page-load synchronization.
5. Implement the typed browser client and confirmation UI.
6. Refresh the lattice only after mutation succeeds while preserving independent refresh errors.

### REFACTOR and gate

1. Remove duplicate frontend request/error handling only where existing patterns already support extraction.
2. Run focused backend/frontend suites.
3. Run the full local candidate gate:

   ```bash
   PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
   ```

4. Commit:

   ```bash
   git commit -m "feat: add explicit browser source synchronization"
   ```

5. Run immutable local verification:

   ```bash
   PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD^ --require-clean --skip-sync
   ```

6. Transfer/import exact HEAD through a verified Git bundle and run the same immutable range on buildbox.
7. Push only after Predator, buildbox, and hosted CI evidence pass.

## Task B2: Browser file import and durable proposal review

Use Task 1.6 in the maturation plan as the detailed contract.

**Likely files:**
- Create: `apps/web/src/ArtifactImportPanel.tsx`
- Create: `apps/web/src/artifactApi.ts`
- Create: `apps/web/src/ProposalQueue.tsx`
- Create: `apps/web/src/ArtifactImportPanel.test.tsx`
- Create: `apps/web/src/ProposalQueue.test.tsx`
- Create: `src/oscillink_agent/proposals/contracts.py`
- Create: `src/oscillink_agent/proposals/repository.py`
- Create: `src/oscillink_agent/proposals/routes.py`
- Modify: `src/oscillink_agent/artifact_imports/service.py`
- Modify: `src/oscillink_agent/api.py`
- Modify: `apps/web/src/MemoryWorkspace.tsx`
- Modify: `tests/integration/test_artifact_import_api.py`
- Create: `tests/integration/test_memory_proposal_api.py`

### RED

Freeze tests for:

1. Opaque configured import targets only; caller-supplied absolute paths are rejected.
2. Imported bytes become immutable content-addressed artifacts.
3. Imported evidence remains `external_untrusted` and cannot enter approved context.
4. Association begins as `pending_review`.
5. Proposal identity, target association, and decision are idempotent.
6. Authenticated human actor can approve/reject exactly once.
7. Approval creates a consumable governed-memory revision or explicit governed relationship.
8. Restart recovers pending, approved, and rejected projections.
9. Traversal, symlink escape, oversized content, extension mismatch, and changed-file races fail closed.
10. Browser pending/mutation/refresh/stale-selection behavior remains deterministic.

### GREEN

Implement the smallest state machine:

```text
artifact_imported
→ proposal_pending
→ proposal_approved | proposal_rejected
→ governed_memory_revision_created (approval only)
```

Do not add arbitrary upload paths, automatic approval, embeddings, generalized proposal types, or cloud object storage.

### Gate

1. Run artifact, proposal, product-memory, adversarial, and frontend focused suites.
2. Run a scripted empty-data-root import/restart/review journey.
3. Run the full local candidate gate.
4. Commit:

   ```bash
   git commit -m "feat: complete governed browser import and proposal review"
   ```

5. Run immutable local verification.
6. Import exact SHA into buildbox and run full Linux verification plus bounded headless API smoke.
7. Push only after all evidence passes.

## Task B3: Milestone 1 acceptance and v0.2 release candidate

Run from a fresh temporary data root:

```text
locked workspace
→ authenticate
→ create candidate memory
→ explicitly sync configured source
→ import configured-scope file
→ inspect pending proposal
→ approve governed memory
→ chat
→ inspect approved revision citation and persisted run
→ restart
→ confirm memory, proposal, artifact, and run recovery
```

Acceptance assertions:

- anonymous mutations fail before storage initialization;
- no automatic sync/import occurs;
- candidate/untrusted content never enters model context;
- only approved revision content is retrieved and cited;
- no absolute source path or credential reaches browser/events/logs;
- restart preserves canonical state and proposal resolution;
- all expected ports are closed after smoke cleanup;
- Predator and buildbox report matching deterministic diff evidence;
- both worktrees are clean.

After acceptance:

1. Update `README.md`, `docs/build-plan.md`, and the roadmap mirror truthfully from `planned` to `implemented`/`preview` as supported by evidence.
2. Run local and buildbox cumulative Milestone 1 gates.
3. Commit roadmap/release truth separately if needed.
4. With explicit approval, push and create an annotated `v0.2.0-alpha` tag.
5. Do not call it private-pilot ready; Milestones 2 and 3 remain required.

---

# Phase C — Complete Milestone 2: crash-safe provider and one governed tool loop

**Outcome:** A provider-neutral run durably records intent before external dispatch, supports one human-approved `file.read`, persists the full causal trajectory, and reconstructs it after restart.

**Finish line:** One deterministic provider requests one exact file, one single-use grant is approved and consumed, one untrusted observation is persisted, a follow-up model call completes, reuse/retry fails closed, and the browser reconstructs the trajectory.

Execute the existing maturation tasks in this exact order:

1. **Task 2.1 — Typed multi-step run reconstruction**
   - Preserve compatibility with existing three-event runs.
   - Commit: `feat: reconstruct typed multi-step agent runs`.
2. **Task 2.2 — Durable provider intent before dispatch**
   - Test crash-before-dispatch, crash-after-dispatch, timeout, retry, and interruption.
   - Commit: `fix: persist provider intent before dispatch`.
3. **Task 2.3 — Truthful provider/model/actor provenance**
   - Server derives identity; real calls never claim fake-provider provenance.
   - Commit: `fix: record truthful provider and actor provenance`.
4. **Task 2.4 — Typed provider tool-request contract**
   - Permit only one exact registered `file.read`; malformed or repeated requests fail closed.
   - Commit: `feat: add bounded provider tool-request contract`.
5. **Task 2.5 — Human grant approval and broker invocation**
   - Authorization event precedes grant registration; observation remains untrusted; reuse fails after restart.
   - Commit: `feat: connect one governed file-read agent loop`.
6. **Task 2.6 — Browser approval and complete run inspector**
   - Show logical scope/target, actor, expiry, limits, decision, tool result, and causal timeline without host paths.
   - Commit: `feat: inspect and approve governed tool runs`.

For every task, require RED → GREEN → local full gate → immutable commit gate → buildbox exact-SHA full gate before starting the next task. Do not batch several runtime-state-machine changes into one unreviewable commit.

Milestone 2 remains explicitly limited to:

- one sequential `file.read`;
- no shell or PTY;
- no write/network tools;
- no parallel calls;
- no autonomous approval;
- no generalized tool marketplace;
- no multi-agent orchestration.

---

# Phase D — Complete Milestone 3: reproducible private pilot and measured value

**Outcome:** One design partner can install, operate, recover, export, and evaluate Oscillink Agent with evidence about whether governed memory improves a longitudinal workflow.

Execute in dependency order:

1. **Versioned migration and workspace export/restore**
   - Hash every exported database/artifact.
   - Exclude credentials, absolute host paths, caches, and derived indexes.
   - Stage and verify restore before atomically replacing active state.
   - Rehearse corruption and interrupted restore on buildbox.
2. **Reproducible private launcher and runbook**
   - Prefer a direct Python/Node launcher until Docker supplies concrete deployment parity.
   - Bind loopback by default and generate per-launch credentials outside logs.
   - Add readiness, liveness, bounded shutdown, backup, restore, and provider-outage procedures.
   - Rehearse from a clean buildbox checkout.
3. **Minimum longitudinal evaluation runner**
   - Compare governed memory against transcript-only and summary-only baselines under equal budgets.
   - Use prospective questions and deterministic scoring where possible.
   - Report continuity quality, citation correctness, contradiction handling, latency, and cost.
4. **Private-pilot release rehearsal**
   - Clean install, core journey, restart, backup, restore, provider switch, failure recovery, export, and deletion/rollback rehearsal.
   - Produce a signed-off report with one customer outcome, one next action, one finish line, and no more than three active risks.

Only after these pass should the project be described as `v0.4-private-pilot` ready.

---

# Buildbox protocol for each future candidate

## Import

On Predator, after commit and immutable local verification:

```bash
git bundle create <temporary-path>/oscillink-agent-<full-sha>.bundle HEAD
sha256sum <temporary-path>/oscillink-agent-<full-sha>.bundle
scp <temporary-path>/oscillink-agent-<full-sha>.bundle \
  buildbox:/srv/buildbox/incoming/
```

On buildbox:

```bash
sudo buildbox-import-bundle \
  oscillink-agent \
  <full-sha> \
  /srv/buildbox/incoming/oscillink-agent-<full-sha>.bundle \
  <bundle-sha256>
```

The importer must delete the transport bundle after proving the detached checkout.

## Verify

```bash
ssh buildbox \
  'sudo buildbox-run oscillink-agent <full-sha> -- \
   /opt/buildbox/bin/uv run --python 3.11.15 python scripts/verify.py \
   --base HEAD^ --require-clean'
```

For a multi-commit milestone, replace `HEAD^` with the immutable milestone base SHA.

## Runtime smoke

Use `/usr/local/libexec/buildbox/oscillink-headless-smoke.py` through `buildbox-run`. Require the status response plus post-run proof that ports 8765 and 5173 have no listener.

## Evidence record

For each promoted commit retain:

- project and full commit SHA;
- base SHA;
- runtime versions;
- Python/frontend test counts;
- deterministic diff digest;
- sanitized log path;
- smoke/acceptance result;
- clean-checkout result;
- hosted CI result after push.

Do not retain secrets, dependency trees, private source paths, canonical runtime databases, or personal vault data as build artifacts.

---

# Immediate next actions

1. **First:** Run the cumulative four-commit local and buildbox gates against `75664d8`.
2. **Second:** With explicit approval, push the four already-verified commits to `origin/main` and confirm hosted CI.
3. **Third:** Start Task 1.5 with the failing typed source-sync accounting tests—no UI implementation before RED.
4. **Fourth:** Complete Task 1.5 as one reviewed commit and prove it on buildbox.
5. **Fifth:** Complete Task 1.6 and the Milestone 1 acceptance journey.

The next concrete coding action is:

```text
Add failing integration assertions to tests/integration/test_product_memory_api.py
for created/revised/unchanged/missing/issues synchronization accounting,
idempotent retry, and approval reset on source revision.
```

# Risks and controls

| Risk | Control |
|---|---|
| Local `main` remains ahead of remote | Freeze cumulative evidence, then push only with explicit approval and no force |
| Linux-only behavior diverges | Exact-SHA buildbox gate after every task commit |
| Buildbox becomes a second mutable authority | Builder account cannot sudo; detached checkouts; no repair/push/promotion |
| Source sync leaks vault paths | Opaque configured source contracts and adversarial transport tests |
| Import becomes automatic approval | Separate immutable artifact, pending proposal, and governed-memory authority domains |
| Provider call occurs without durable intent | Milestone 2 prepare/dispatch/finalize state machine and crash tests |
| Scope expands into terminal/multi-agent/cloud work | Maintain explicit deferrals until the customer journey and recovery gates pass |
| Automatic host updates change system packages | Pinned `/opt/buildbox` toolchains, lockfiles, runtime-version evidence, and exact-SHA gates |
| 8 GiB buildbox exhaustion | One job at a time; 3-core quota; 6/7 GiB memory limits; persistent caches only |
| Private-pilot claims outrun evidence | Capability ledger validation and milestone-specific acceptance reports |

# Definition of project continuation success

The continuation is successful when:

1. Milestone 1 produces a browser-complete governed-memory journey at `v0.2.0-alpha`.
2. Milestone 2 produces one crash-safe, human-approved, fully reconstructable `file.read` trajectory.
3. Milestone 3 proves export/restore, clean deployment, and measured longitudinal value in a private-pilot rehearsal.
4. Every promoted milestone has matching Predator, buildbox, and hosted-CI evidence bound to an immutable commit.
5. Oscillink Agent remains governed, model-neutral, provenance-preserving, and free of unsupported AGI/consciousness/autonomous-self-improvement claims.
