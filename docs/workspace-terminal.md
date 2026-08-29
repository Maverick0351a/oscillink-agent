# Governed Workspace Terminal

## Decision

Oscillink Agent can incorporate terminal functionality, but it must not expose an unrestricted host shell through the browser or grant a model arbitrary shell authority. The safe product is a **governed workspace terminal**: an inspectable, bounded execution surface subordinate to workspace scope, capability policy, actor identity, and append-only run history.

Terminal work is not part of the current pilot-critical path. It begins only after authenticated workspace identity, the capability broker, process supervision, cancellation, and run inspection exist. The initial pilot tool remains a narrow read-only capability.

## User value

A governed terminal can help customers building AI infrastructure:

- inspect a workspace and its dependency state;
- run tests, linters, builds, evaluations, and local services;
- inspect logs and generated artifacts;
- operate model-serving or data-processing workflows through reviewed commands;
- associate command outputs with the exact run, context, code, and artifacts that produced them;
- let an agent propose a command without silently obtaining permission to execute it.

The product value is not “a terminal in a browser.” It is reproducible workspace operation connected to governance and provenance.

## Non-goals

The terminal must not become:

- arbitrary browser-accessible host shell access;
- a way to bypass typed capability grants;
- unrestricted credential, filesystem, process, device, or network access;
- an implicit deployment or production-mutation permission;
- a channel through which retrieved content or model output can execute commands;
- a hidden self-modification or self-deployment mechanism;
- a replacement for product-owned memory, context manifests, or run records.

## Modes and authority

Human and agent execution are distinct modes with different authorization semantics.

### Human-interactive mode

A signed-in human opens a terminal for an explicit workspace. Human keystrokes are attributable to that user, but workspace, isolation, resource, secret, network, and destructive-operation policies still apply. Typing a command authorizes only that command under the effective policy; it does not grant the agent a reusable shell capability.

### Agent-proposed mode

The agent can produce a structured command proposal containing purpose, executable, arguments, relative working directory, expected outputs, requested network policy, resource budget, and risk classification. The proposal is inert until policy permits it and any required human confirmation is recorded.

### Agent-invoked mode

Later, narrowly scoped commands may execute through typed, expiring grants. A grant identifies allowed executable/operation, argument constraints, workspace, working-directory scope, network policy, resource budget, expiry, invocation count, and actor/run identity. Free-form model text cannot create or widen a grant.

## Recommended delivery sequence

### Phase 0: prerequisites

Before terminal implementation:

1. authenticate the workspace and actor;
2. implement the capability broker and typed grants;
3. implement process supervision and full process-tree cancellation;
4. persist run/tool events and expose them in the run inspector;
5. define secret-redaction, retention, deletion, and workspace-export policy;
6. prove one bounded read-only tool end to end.

### Phase 1: governed command runner

Start with a non-interactive structured command runner rather than a persistent shell. A request declares executable, arguments, relative `cwd`, environment allowlist, timeout, output limit, network policy, and expected artifacts. This is easier to authorize, record, test, cancel, and replay than shell syntax containing pipes, redirection, substitutions, and background processes.

Initial capabilities should target known development operations such as configured test, lint, build, evaluation, and log-inspection commands. Do not permit arbitrary Python, PowerShell, `cmd.exe`, Bash `-c`, package installation, credential tools, Docker socket access, or host-service control in the first slice.

### Phase 2: human-interactive PTY

Add a persistent pseudo-terminal only after the structured runner is reliable. The terminal session receives an explicit identity, sandbox, workspace mount, lifecycle, idle timeout, output budget, and authenticated streaming channel. Process state is server-owned; closing a browser tab does not leave an untracked orphan.

### Phase 3: bounded agent invocation

Permit agent invocation only for reviewed command classes and argument schemas. High-impact classes remain human-only or confirmation-gated. Promotion, deployment, governance changes, secrets, billing, destructive operations, and external publication never inherit permission from ordinary development commands.

## Execution record

Every command or interactive session records:

- terminal/session and run identity;
- authenticated actor and mode (`human`, `agent_proposed`, or `agent_invoked`);
- policy/grant version and authorization decision;
- executable, arguments, and exact raw command where applicable;
- shell/runtime name and version where applicable;
- workspace ID and relative working directory;
- bounded environment allowlist or redacted environment digest;
- network and filesystem policy;
- start/end time, timeout, cancellation, and process-tree outcome;
- exit status or termination reason;
- bounded sanitized stdout/stderr or content-addressed output artifact;
- produced and modified artifact associations;
- confirmation/denial decision and attributed reason;
- parent context manifest and causal run event.

Secrets are represented as `[REDACTED]`; they are not persisted in command text, environment snapshots, logs, manifests, or frontend state.

## Isolation and resource policy

The preferred execution target is a disposable container or equivalent sandbox with:

- an explicit workspace mounted read-only by default;
- narrowly scoped writable output directories;
- read-only root filesystem where compatible;
- dropped Linux capabilities and no privileged mode;
- no Docker/host daemon socket;
- bounded CPU, memory, process count, disk, runtime, and output;
- network disabled by default and allowlisted per operation when required;
- no host home directory, credential stores, SSH agents, browser profiles, or unrelated workspaces;
- deterministic cleanup of containers, processes, temporary files, and partial artifacts.

Where a required operation cannot run in the sandbox, host execution is a separate high-risk capability requiring an explicit policy and confirmation. It must not be the silent fallback.

## Browser and transport security

A future terminal frontend should use a maintained terminal renderer only after dependency and security review. The API owns process state and enforces:

- authenticated, workspace-bound session creation;
- strict origin checks and short-lived connection credentials;
- bounded input and output frames;
- rate and concurrent-session limits;
- sanitized titles, links, clipboard behavior, and terminal escape sequences;
- no direct browser access to filesystem paths, environment variables, or process handles;
- explicit upload/download through governed artifact APIs;
- reconnect semantics that cannot attach to another actor's session;
- cancellation that terminates the complete process tree.

Terminal output is untrusted data. ANSI/OSC sequences, hyperlinks, control characters, prompts, and output text cannot alter application policy, obtain clipboard contents, open arbitrary URLs, or impersonate trusted product UI.

## Risk and confirmation policy

Examples requiring denial or explicit confirmation include:

- writes outside approved workspace/output paths;
- recursive deletion, permission changes, disk formatting, or process/service control;
- package installation or execution of newly downloaded code;
- network egress, remote login, upload, publishing, or deployment;
- access to credentials, environment secrets, SSH agents, browser profiles, or cloud metadata;
- container privilege, host mounts, device access, or Docker socket access;
- commands that alter governance, promotion rules, hidden labels, budgets, or production deployment;
- long-running/background processes beyond an approved lifecycle.

A broad instruction such as “work autonomously” is not approval for any of these operations.

## Recovery and cleanup

The supervisor must:

1. assign every process to a tracked terminal/session identity;
2. terminate the complete child process tree on cancellation or timeout;
3. reap exited children and close streams;
4. detect browser disconnect without assuming the process should continue;
5. apply an explicit detach/continue policy for approved long-running work;
6. clean temporary files and reject partial artifact publication;
7. surface orphan detection and cleanup as health status;
8. preserve a sanitized terminal record even when execution fails.

## Acceptance criteria

A terminal slice is acceptable only when tests prove:

- workspace path traversal and symlink/reparse escape fail closed;
- a command cannot access another workspace or the host home directory;
- network is denied unless explicitly granted;
- expired, reused, mismatched, or widened grants are rejected;
- agent text and retrieved content cannot trigger execution;
- destructive/high-risk requests require the correct confirmation or are denied;
- output and runtime limits terminate work predictably;
- cancellation removes the complete child process tree;
- secrets are redacted from persisted and streamed records;
- escape sequences cannot alter trusted browser UI or clipboard state;
- restart reports interrupted sessions truthfully and leaves no hidden orphan;
- the complete command, policy, output, exit status, artifacts, and causal run are inspectable.

## Product boundary

The terminal is a subordinate workspace tool, not Oscillink's identity. The pilot remains successful without it. Implement it only when it measurably improves customers' ability to build and inspect AI infrastructure without weakening memory governance, authorization, provenance, recovery, or provider neutrality.
