# Deterministic Review Process

Oscillink Agent uses local, reproducible review gates instead of reviewer subagents.
The objective is to verify exact Git ranges without temporary worktrees, shared-status
interference, or unverifiable model self-report.

## Rules

1. Reproduce suspected defects with a focused failing test before changing production code.
2. Apply the smallest fix that closes the demonstrated defect class.
3. Run `scripts/verify.py` on the exact candidate range.
4. Commit only after the local candidate gate passes.
5. Review the immutable commit range with a clean worktree.
6. Investigate only deterministic failures or findings that can be reproduced locally.
7. Stop after two unsuccessful remediation cycles and report the remaining evidence instead
   of expanding scope indefinitely.

Reviewer subagents and temporary Git worktrees are not part of this process.

## Candidate gate

From the repository root on Windows:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
```

On Linux:

```bash
PYTHONPATH= .venv/bin/python scripts/verify.py --base HEAD
```

This reviews committed `HEAD` against the current candidate worktree. It runs:

- locked dependency synchronization;
- the complete pytest suite;
- Ruff;
- strict mypy;
- `git diff --check`;
- JSON parsing for every contract schema;
- build-plan mirror equality;
- LF-only validation for changed files;
- an added-line scan for secrets, shell injection, dynamic execution, unsafe pickle loading,
  and interpolated SQL;
- SHA-256 identification of the exact binary Git diff.

## Stable post-commit gate

After committing, require a clean worktree and review the immutable commit:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD^ --require-clean
```

Record the commit ID, test count, and reported diff SHA-256 in the milestone result. Do not
amend the commit after this gate; a changed commit requires a fresh stable-range run.

## Troubleshooting

When a gate fails:

1. Read the exact command and error emitted by `scripts/verify.py`.
2. Re-run only that failing command to isolate the cause.
3. For behavioral defects, add a focused RED test.
4. Fix the root cause, then rerun the focused test.
5. Rerun the complete candidate or stable gate.

Do not treat stale cache files, temporary checkout results, or model assertions as evidence of
a repository failure. The current repository command output is authoritative.
