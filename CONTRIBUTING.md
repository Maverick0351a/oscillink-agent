# Contributing to Oscillink Agent

Thank you for improving Oscillink Agent. The project welcomes focused bug reports, reproducible evaluation cases, documentation fixes, client and provider compatibility work, and narrowly scoped code contributions.

## Product boundary

Oscillink is a governed, model-neutral continuity layer. Contributions must not claim AGI, consciousness, identity transfer, safe recursive self-improvement, or physical safety from fluent model behavior.

Do not add:

- unrestricted host shell, network, filesystem, credential, or actuator access;
- a path by which retrieved content or model output can expand permissions;
- silent memory promotion, policy deployment, or benchmark-label exposure;
- secrets, private prompts, runtime databases, private customer data, or credentials;
- robot or equipment control without a separately reviewed safety contract.

Read [`AGENTS.md`](AGENTS.md), [`docs/open-source-boundary.md`](docs/open-source-boundary.md), and [`SECURITY.md`](SECURITY.md) before contributing.

## Before opening a change

1. Search existing issues and pull requests.
2. Open or comment on an issue before substantial architectural, dependency, schema, security, or user-interface work.
3. Keep the change to one observable behavior or documentation outcome.
4. Identify the exact user problem, current behavior, and acceptance criterion.
5. For fixtures or datasets, document origin, license, immutable revision, and SHA-256 digest.

A maintainer may decline a technically valid change that broadens the product beyond its current evidence or safety boundary.

## Development setup

Requirements:

- Python 3.11
- `uv`
- Node.js and npm for `apps/web`
- Git configured to preserve LF line endings

From the repository root on Windows Git Bash:

```bash
uv sync --locked --dev
npm --prefix apps/web ci
```

Run Python commands with an empty `PYTHONPATH` and the project interpreter to prevent environment contamination:

```bash
PYTHONPATH= .venv/Scripts/python.exe -m pytest
PYTHONPATH= .venv/Scripts/python.exe -m ruff check src tests --no-cache
PYTHONPATH= .venv/Scripts/python.exe -m mypy src --cache-dir .mypy_cache
```

Run frontend checks with:

```bash
npm --prefix apps/web test
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

The complete deterministic candidate gate is:

```bash
PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD
```

## Development discipline

Production behavior follows strict vertical RED → GREEN → REFACTOR TDD:

1. Write one focused failing test.
2. Run it and confirm it fails for the missing behavior.
3. Implement the smallest behavior that makes it pass.
4. Run the focused test.
5. Run affected and full verification.
6. Refactor only while green.

Keep domain contracts independent of infrastructure adapters. Reuse existing memory, event, context, capability, recovery, and evaluation contracts rather than creating a parallel state system.

## Tests and evidence

Tests should exercise observable behavior through real implementations where practical. Include failure, unavailable, malformed, stale, and boundary paths—not only success.

Security-sensitive changes should include adversarial tests for:

- authority and actor mismatch;
- scope escape;
- expiry, replay, and idempotency;
- prompt injection through retrieved content;
- secret and host-path leakage;
- malformed, oversized, non-finite, or ambiguous input;
- crash/restart behavior;
- fail-closed dependency failures.

Evaluation changes must preserve:

- exact fixture and manifest hashes;
- equal declared budgets across conditions;
- separation of smoke integrity from model quality;
- hidden labels outside agent-readable context;
- failed and unavailable provider results;
- exact provider, model, configuration, and code revision provenance.

## Pull requests

A pull request should state:

- the user-visible problem and outcome;
- the exact files and contracts affected;
- the RED failure observed before implementation;
- focused and full verification commands with real results;
- security, privacy, compatibility, and migration implications;
- fixture/data provenance where applicable;
- deferred work and known limitations.

Do not combine drive-by formatting, renaming, dependency upgrades, or unrelated refactors with a focused change.

Do not commit generated evaluation reports, credentials, local databases, caches, private artifacts, or build outputs.

## Licensing

Unless explicitly designated otherwise, contributions intentionally submitted for inclusion in this repository are provided under the [Apache License 2.0](LICENSE), consistent with Section 5 of that license. Third-party code and data must retain compatible attribution and license terms.
