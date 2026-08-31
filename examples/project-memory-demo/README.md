# Project Memory five-minute continuity demo

This example proves a bounded claim:

> Two independent MCP client processes can share corrected, cited project memory across
> process termination without replaying a transcript.

It runs locally over stdio, requires no account or model credential, and uses only the
synthetic input in [`project-fixture/scenario.json`](project-fixture/scenario.json).
The raw fixture bytes are pinned in [`manifest.json`](manifest.json).

## Run from a source checkout

Install the locked Python environment once:

```bash
uv sync --locked --dev
```

Then run the demo from the repository root.

Windows Git Bash:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/run_project_memory_demo.py \
  --data-root .demo/project-memory
```

Linux/macOS:

```bash
PYTHONPATH= .venv/bin/python scripts/run_project_memory_demo.py \
  --data-root .demo/project-memory
```

Use a new data root for each run. The command prints one JSON report to stdout.

## What happens

1. **Agent A** starts in one isolated OS process and uses the official Python MCP client
   over a fresh stdio server to propose three project decisions and one failed approach.
2. Agent A and its server exit. No transcript is retained or replayed.
3. External governance approves the initial candidates.
4. A separate post-compaction MCP client process proposes an exact-revision correction.
   External governance approves the replacement and supersedes the original revision.
5. **Agent B** starts in another isolated OS process with a fresh stdio server. It calls
   `recall`, then calls `explain` on the current replacement. It discovers the old revision
   through the replacement's typed `supersedes` lineage edge.

The report includes:

- independent client process IDs;
- current approved titles and text;
- exact record IDs and SHA-256 content citations in the context manifest;
- declared and consumed token counts;
- omissions and authority-state exclusion counts;
- correction lineage;
- elapsed wall-clock time;
- the exact fixture SHA-256.

The acceptance test runs the scenario against two independent data roots and requires the
same content-addressed context manifest under the same fixture, query, policy, and budget.

```bash
PYTHONPATH= .venv/Scripts/python.exe -m pytest \
  tests/acceptance/test_project_memory_demo.py -q
```

## Pinned input

The current raw-byte fixture digest is:

```text
sha256:c13b054b7db2f79bcd9468eae53e4758c70a9326ab4a6a3b60436b190495cd63
```

The fixture contains scenario inputs and provenance only. It contains no expected answer,
score label, or hidden benchmark key. Expected behavior lives in the acceptance test, not
in agent-readable input.

## Direct client receipts

These compatibility probes use disposable client homes and synthetic public data only.
They do not modify a user's active client profile.

- **Hermes native MCP:** connected without authentication on Windows, discovered all four
  tools (`remember`, `recall`, `correct`, `explain`), and reported a 1125 ms connection in
  an isolated `HERMES_HOME`.
- **Delegated Hermes Agent B:** a separate GPT-5.6-Sol Hermes agent received only the data
  root and continuation task, drove a fresh official MCP client, recovered all four current
  decisions with full citations and correction lineage, rejected the failed transcript-only
  approach, and chose immutable Windows/Buildbox/CI verification as its next action. Its
  exploratory run exceeded five minutes and is not counted as the timed demo result.
- **OpenCode 1.18.25:** connected through its native local-MCP configuration with
  `PYTHONPATH` cleared. An account-free OpenCode model performed one current recall and one
  current-revision explain, recovered all four current records, observed a 40-token context,
  identified one superseded exclusion and the exact backward correction edge, avoided the
  failed transcript-only approach, and selected immutable local/Buildbox/CI verification as
  the next action.
- **Codex CLI 0.151.0:** MCP configuration support was present, but the standalone CLI was
  not authenticated. No Codex task-continuity compatibility claim is made.

MCP clients should use a fresh valid `evt_` Crockford-ULID-shaped request ID for every
logically distinct tool call. Reusing one request identity with different arguments is a
conflict, not a new request.

## What this does not prove

- It does not evaluate general model answer quality.
- It does not prove compatibility with every advertised coding client.
- It does not make candidate writes canonical; promotion remains external governance.
- It does not upload the local database or open a network port.
- It does not show that a remote free model is suitable for private project data. The
  OpenCode receipt used only this committed synthetic fixture.
- It does not claim consciousness, identity transfer, AGI, or physical-action rewind.
