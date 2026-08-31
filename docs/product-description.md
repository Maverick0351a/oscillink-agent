# Product Description

## Positioning

Oscillink Agent is the **continuity and memory control plane for long-running AI agents**.
Its first product direction, **Oscillink Project Memory**, gives coding-agent users one
corrected, cited project history that can survive compaction, restart, and provider or
client changes. The broader platform gives agent developers, technical and research
teams, consultants, and sensitive internal deployments a governed workspace for durable
memory, deterministic context, interchangeable model providers, bounded tools, and
inspectable runs.

Most AI infrastructure helps teams call models, connect tools, and retrieve documents. It does not adequately govern what an agent learns, trusts, remembers, changes, or uses over time. Oscillink fills that missing control-plane layer. It is not a foundation model, vector database, generic autonomous-agent launcher, or terminal wrapper.

The public promise must lead with useful continuity rather than governance terminology:

> Install once, preserve corrected project history across compatible coding agents,
> survive compaction, and inspect why context was selected.

The intended operating principle is **autonomous by default, governed by exception, and
reversible at all times**. Low-risk maintenance should not create an approval queue for
every observation; contradictory, expensive, security-sensitive, or externally
consequential changes remain subject to explicit policy and human control.

## Open-source and commercial boundary

The repository is licensed under Apache-2.0. The local memory, provenance, correction,
context, evaluation, and adapter foundation is intended to be usable without a mandatory
hosted account. Expected paid value comes from operating the shared state reliably:
encrypted synchronization, hosted availability, team coordination, managed connectors,
enterprise deployment, audit, policy administration, and support. See
[`open-source-boundary.md`](open-source-boundary.md).

Physical-intelligence episode and dataset tooling is an evidence-gated adjacency. The
product does not currently control robots or equipment, and no software restore can undo
a completed physical action.

## User problems

### Fragmented and unstable continuity

Important decisions and corrections are scattered across transcripts, prompts, filenames, notes, vector stores, and provider-specific memory. Paths and external tools become accidental identity systems, and knowledge breaks when a source moves or a model changes.

Oscillink provides stable product-owned `mem_…` identities, immutable revisions, durable relationships, restart recovery, and portable source bindings.

### Opaque or poisoned memory

Retrieved or generated text is often treated as trusted merely because it exists. Users cannot reliably tell what an agent remembers, why it trusts a record, whether the record is current, or whether contradictory evidence exists.

Oscillink separates candidate, curated, approved, rejected, contradicted, superseded, stale, and retracted states. Source presence never grants authority. Model-generated durable changes remain proposals until governed review.

### Irreproducible answers and actions

A prompt alone does not explain which memory revisions, retrieval policy, model configuration, tools, or budgets produced an answer. Failures become difficult to debug and impossible to replay faithfully.

Oscillink records provenance-bearing evidence packets, deterministic context manifests, provider identity, tool activity, run events, failures, and review outcomes.

### Provider and connector lock-in

Customers should not lose operating memory when changing model vendors, inference runtimes, or knowledge tools.

Oscillink owns canonical memory and governance. Local Qwen, hosted APIs, vLLM, NVIDIA NIM, Obsidian, Markdown, uploads, and future connectors remain replaceable adapters behind product-owned contracts.

### Unsafe action surfaces

Agent frameworks commonly grant broad credentials, filesystem access, network access, or shell execution to accomplish narrow tasks. This makes retrieved prompt injection and model mistakes operationally dangerous.

Oscillink uses typed, scoped, expiring capability grants, explicit actor identity, bounded execution, approval policy, sanitized observations, and append-only run history. Retrieved content and model text cannot create or expand permissions.

### Weak recovery and customer control

Many agent systems do not provide complete export, deletion, rollback, or restore semantics for memory and runs.

Oscillink is designed around portable records, content-addressed artifacts, append-only decisions, deterministic projections, workspace backup/restore, and reversible promotion.

## Implemented foundation and bounded next layers

### Governed memory lifecycle

```text
native creation or source snapshot
→ stable product identity
→ immutable revision
→ candidate or curated state
→ human review
→ approved memory
→ governed retrieval
→ correction, contradiction, supersession or retraction
→ replayable history
```

The implemented foundation includes product-owned memory identities, revision-bound
approve/reject/supersede decisions, candidate-only MCP writes, optional Obsidian
synchronization, artifact provenance, restart recovery, authority-aware Memory Lattice
projections, and browser review controls.

### Authority-aware retrieval

Default agent retrieval includes only authorized, current, authority-eligible records.
Similarity cannot promote a candidate, revive a rejected revision, hide a contradiction,
suppress mandatory policy, or bypass project scope. Every returned item retains its citation,
revision hash, provenance, authority state, and inclusion reason.

### Deterministic context manifests

Every governed model call carries a persisted `ContextManifest` identifying exact memory
revisions, retrieval policy, inclusion and omission reasons, budgets, and run identity.
Context is an inspectable build artifact rather than an ephemeral prompt.

### Provider-neutral chat

The fake, Ollama, and reviewed OpenAI-compatible adapters share the same memory-authority,
citation, typed-failure, and provider/model provenance boundary. Models are replaceable
compute; they do not own customer memory or governance. Broader streaming and provider
compatibility remain evidence-gated.

### Memory Lattice and review workspace

The first-party interface exposes graph/list navigation, provenance, authority, review
queues, context inclusion, run references, evaluation evidence, and verified recovery
manifests. Every visible state corresponds to typed backend state; graph prominence does not
imply truth.

### Governed ingestion

Explicit browser selection and configured connectors feed immutable content-addressed
storage, bounded validation, source snapshots, candidate associations, and human review.
Import or synchronization never silently approves or rewrites canonical memory.

### Run observability and replay

The run inspector connects user request, retrieval, context, provider call, bounded tool
request, observation, response, and restart state into one inspectable trajectory with exact
budgets and failures.

### Bounded capability broker

The first pilot tool, `file.read`, is exposed through typed single-use grants with resource
scope, actor, expiry, byte limits, and event provenance. Arbitrary host execution remains
outside the implemented boundary.

### Memory Focus

Memory Focus remains deferred. If validated, bounded focus levels may emphasize already
eligible memory but must remain separate from truth, approval, authorization, freshness,
contradiction handling, and explicit context pinning.

## Customer outcomes

Oscillink helps teams:

- preserve useful continuity across sessions, restarts, models, and source changes;
- prevent unreviewed or poisoned content from silently becoming durable truth;
- understand which evidence influenced an answer;
- reproduce and debug agent behavior from exact context and run records;
- change providers without migrating canonical memory;
- govern durable changes through human review and rollback;
- operate tools with bounded authority rather than unrestricted credentials;
- export, restore, delete, and recover a customer workspace predictably.

The target transition is:

```text
chatbot + prompt + vector database + broad tools
```

into:

```text
governed memory
+ deterministic context
+ interchangeable models
+ bounded capabilities
+ inspectable runs
+ human-controlled evolution
```

The goal is not merely for an agent to remember more. The goal is for it to maintain useful continuity without losing provenance, human control, portability, or the ability to explain and reverse what changed.

## Governed workspace terminal

A shell terminal is technically feasible, but an unrestricted browser-exposed host shell is outside the product safety boundary. If added, it will be a **governed workspace terminal** subordinate to the capability broker and run-history contracts.

The terminal must provide:

- an explicit workspace and workspace-scoped working directory;
- distinct human-interactive and agent-invoked execution modes;
- authenticated actor and process identity;
- parsed command/argument records rather than an opaque transcript alone;
- policy evaluation and confirmation for destructive, privileged, networked, or out-of-scope operations;
- bounded runtime, output, process count, storage, and network behavior;
- cancellation and full process-tree cleanup;
- environment-variable and secret redaction using `[REDACTED]`;
- sanitized output, exit status, produced-artifact associations, and append-only run events;
- isolation through a disposable container or equivalent sandbox where feasible;
- no ability for retrieved content, model output, or terminal escape sequences to grant additional authority.

A terminal should help customers inspect projects, run tests, build artifacts, and operate AI infrastructure. It must not silently grant an agent unrestricted host access, credentials, deployment authority, or governance mutation. Detailed requirements are defined in [`workspace-terminal.md`](workspace-terminal.md).
