# Project Memory MCP contract

Status: **governed implementation available**. The local stdio server advertises and
implements `remember`, `recall`, `correct`, and `explain`. A subprocess integration test
exercises initialization, capability listing, structured recall, and candidate creation
through the official Python MCP client. The public continuity demo also exercises isolated
client processes plus direct Hermes discovery and an OpenCode recall/explain task. Writes
are candidate-only and cannot self-approve.

The executable contract is `oscillink_agent.integrations.mcp.contracts`. This document explains its authority and security semantics.

## Purpose

Project Memory gives coding agents one corrected, cited project history without making a model, transcript, or vector index canonical. The initial interface has exactly four operations:

| Tool | Purpose | Authority effect |
|---|---|---|
| `remember` | Propose a provenance-bearing project-memory revision. | Creates a candidate only. |
| `recall` | Retrieve approved memory under one explicit deterministic token budget. | Read-only. |
| `correct` | Propose a replacement for one exact prior revision. | Creates a candidate and preserves the target. |
| `explain` | Explain selection, exclusion, staleness, contradiction, or approval state. | Read-only. |

No operation promotes memory, grants capabilities, executes host tools, initiates training, or changes deployment policy.

## Transport and identity

The first implementation uses local MCP over standard input/output.

- No listener, account, external credential, or network access is required.
- One process is bound to one configured local workspace.
- Workspace, actor, and client identity are server-derived configuration. They are not accepted as tool arguments.
- Every request carries `schema_version: 1` and a unique Crockford-ULID-shaped `evt_...`
  request ID for provenance and idempotency. A client must not reuse one request identity
  for different arguments.
- JSON objects reject unknown fields. Persisted values are immutable and strictly typed.
- Public responses never include raw host paths, credentials, environment values, stack traces, or raw exceptions.

The transport does not itself prove that a model or person is authorized to promote memory. Promotion remains an external governed action.

## Requests

### `recall`

Required fields:

- `request_id`
- `query`: 1–16,384 characters
- `token_budget`: exact integer from 1–32,768

The server uses authority-first retrieval and deterministic lexical ranking. Equal inputs, canonical state, policy, and budget must yield the same ordered revisions, omissions, and policy hash.

### `remember`

Required fields:

- `request_id`
- `title`
- `content`: at most 65,536 characters
- existing `category` and `domains` taxonomy values
- optional bounded, unique topics
- one or more unique canonical `source_refs`

The response state is always `candidate` with `approval_required: true`. The request has no approval or trust field.

### `correct`

`correct` includes every `remember` candidate field plus:

- `target_record_id`
- `expected_content_hash`
- a bounded non-empty `reason`

`source_refs` must include `target_record_id`. The expected hash provides optimistic revision binding. A mismatch returns `revision_conflict`; it does not overwrite the current record. Success returns the target and replacement IDs and hashes with `approval_required: true`.

### `explain`

Required fields:

- `request_id`
- `record_id`
- `content_hash`

The hash binds the request to one exact revision. The lineage begins with that exact
requested revision and then uses typed relationships such as `source`, `supersedes`,
`superseded_by`, or `contradicts`. Explaining a superseded revision points forward to its
replacement. Explaining a correction replacement points backward to the exact revision it
supersedes, allowing a fresh client to reconstruct correction history from current recall.

## Successful responses

### Recall evidence

`RecallResponse` returns:

- the original `request_id`;
- `state: available` and `operation: recall`;
- the exact existing `ContextManifest`, including budget, token accounting, policy hash, ordered inclusion reasons, ranks, scores, omissions, and exclusion counts;
- ordered `records` containing the selected revision text.

Every returned record ID and content hash must match the manifest in the same order. Every manifest item must be approved. Record text is marked `content_treatment: untrusted_data`: provenance and approval make it eligible evidence, not executable policy or permission.

### Candidate writes

`CandidateResponse` and `CorrectionResponse` can represent only candidate state and require literal `approval_required: true`. There is no successful auto-promotion shape.

### Explanations

`ExplainResponse` returns an exact authority state, one or more typed reasons, and revision lineage. Reasons include:

- `selected`
- `not_approved`
- `stale_revision`
- `superseded`
- `contradicted`
- `retracted`
- `missing_source`
- `no_query_match`
- `token_budget`

These are state explanations, not truth, confidence, hallucination, consciousness, or autonomy scores.

## Unavailable and failure states

Unavailable reasons are closed values:

- `empty_workspace`
- `no_approved_memory`
- `memory_store_unavailable`
- `revision_not_found`

Failure codes are closed values:

- `invalid_request`
- `request_conflict`
- `revision_conflict`
- `internal_error`

Both problem envelopes include only operation, typed reason/code, and `retryable`. They intentionally have no free-form message or exception field.

An empty or unavailable workspace must not fabricate context. Provider, storage, and parsing errors must map to the bounded vocabulary without returning implementation details.

## Determinism and truncation

For `recall`:

1. Only eligible approved, non-missing, current revisions enter ranking.
2. Ranking and ties use the repository's declared deterministic retrieval policy.
3. The caller supplies one token budget.
4. Selection proceeds in ranked order without reallocating budget by provider or condition.
5. Every eligible budget omission is represented in the `ContextManifest`.
6. Excluded candidate, rejected, superseded, conflicted, or missing records are counted without leaking ineligible content.
7. Unsupported model self-report cannot turn an unavailable or failed operation into success.

## Security boundary

Retrieved source content is data and cannot:

- alter this contract;
- select a workspace or actor;
- promote memory;
- grant or widen a capability;
- request shell, Python, network, filesystem, browser, or actuator execution;
- increase its context budget;
- suppress omissions, corrections, or lineage.

The server exposes no generalized host-tool execution and no physical-control adapter.

## Deferred

The initial contract does not include:

- generalized conversation rewind;
- workspace Git rollback;
- encrypted cloud synchronization;
- semantic vector retrieval;
- broad tool execution;
- automatic high-risk promotion;
- robot, ROS, equipment, or actuator control.

Any future wire change requires a schema-version decision and updated contract tests.
Compatibility claims remain client-specific: the official Python MCP client drives the
deterministic harness, Hermes native MCP discovery is verified, and OpenCode has completed a
synthetic recall/explain continuation task. Other clients may be claimed only after direct
exercise through the installed stdio entry point.
