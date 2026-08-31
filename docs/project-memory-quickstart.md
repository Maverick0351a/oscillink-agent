# Oscillink Project Memory quickstart

Use this path to see corrected, cited continuity across fresh agent processes in under five
minutes. It runs locally, opens no network port, and requires no account or model credential.

## Prerequisites

- Git
- [`uv`](https://docs.astral.sh/uv/)
- Windows, Linux, or macOS with a Python 3.11 runtime available to `uv`

## Run the continuity demo

Clone the repository and enter it. Then run one command:

```bash
PYTHONPATH= uv run --locked python scripts/run_project_memory_demo.py \
  --data-root .oscillink-demo
```

The command creates disposable project-memory state under `.oscillink-demo`, starts Agent A
in a fresh MCP client process, ends that process, applies an externally governed correction,
then starts Agent B in another fresh process. It does not replay Agent A's transcript.

A successful JSON report includes:

- `transcript_replayed: false`;
- distinct process IDs for Agent A, governance, and Agent B;
- three project decisions plus one recorded failed approach;
- only the corrected build-verification decision in current recall;
- an exact `supersedes` edge from the replacement to the prior revision;
- exact record/content-hash citations;
- context token cost, omissions, and authority exclusions; and
- elapsed time below 300 seconds.

The fixture and its SHA-256 manifest are committed under
[`examples/project-memory-demo/`](../examples/project-memory-demo/). The fixture contains
inputs and provenance, not expected labels or answers.

Use a new empty `--data-root` for each clean demonstration. Do not point the demo at an
existing project workspace.

## Start the real local MCP server

For an actual project, choose one persistent data root outside source-controlled files:

```bash
PYTHONPATH= uv run --locked oscillink-project-memory \
  --data-root /absolute/path/to/project/.oscillink-memory
```

Configure a compatible MCP client to launch that command over stdio. The human-selected
server process binds the data root and actor identity; MCP requests cannot switch either.
The process advertises exactly four operations:

| Operation | Authority |
| --- | --- |
| `recall` | Return only current approved, non-missing memory under an exact context budget |
| `explain` | Show inclusion/exclusion and correction lineage for an exact revision |
| `remember` | Create an idempotent provenance-bearing **candidate** only |
| `correct` | Create an exact-revision replacement **candidate** only |

MCP clients cannot approve, reject, promote, or supersede memory. Those governance actions
remain external. Retrieved memory is untrusted data and cannot grant tools or permissions.

## Compatibility boundary

The official Python MCP client, Hermes native MCP discovery, and OpenCode 1.18.25 have been
exercised directly using synthetic public data. A delegated Hermes agent also completed the
fresh-Agent-B task from MCP evidence alone. Codex, Claude Code, Cline, Cursor, and other
clients remain unclaimed until their paths are directly exercised.

See the exact receipts and caveats in the
[demo README](../examples/project-memory-demo/README.md). In particular, the deterministic
independent-process harness is the timed proof; exploratory model runs are not counted toward
the five-minute claim.

## What this proves—and does not prove

It proves that corrected governed project memory can survive process termination and be
recalled with exact evidence by a fresh client process. It does not prove model quality,
general agent compatibility, autonomous approval, cloud synchronization, arbitrary workspace
rewind, safe recursive self-improvement, AGI, consciousness, or physical safety.

## Next paths

- MCP authority and schemas: [`project-memory-contract.md`](project-memory-contract.md)
- Browser evaluation/recovery evidence: [`browser-evidence.md`](browser-evidence.md)
- Community alpha protocol: [`community-validation.md`](community-validation.md)
- Advanced private-pilot operation: [`private-pilot-runbook.md`](private-pilot-runbook.md)
- Development and contribution: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)

## Troubleshooting

- **`uv` is missing:** install it from the official `uv` documentation, then rerun the exact
  command.
- **Fixture integrity error:** restore the committed fixture and manifest; do not regenerate
  expected output inside the fixture.
- **Request conflict:** every changed MCP request needs a new valid `evt_` identity. Reusing an
  identity with different content fails closed.
- **Client process closes:** clear inherited `PYTHONPATH` in the MCP client environment and use
  an absolute Windows executable path rather than an MSYS `/c/...` command path.
- **No memory is recalled:** current recall intentionally excludes candidate, rejected,
  missing, contradicted, and superseded revisions.
