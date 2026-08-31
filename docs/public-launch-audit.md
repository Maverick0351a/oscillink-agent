# Public alpha launch audit

This record captures the fail-closed exposure review performed before publishing
`v0.2.0-alpha.1`. It is evidence for a bounded launch decision, not a penetration test or
security certification.

## Scope

- Complete Git history reachable from all local refs: 47 commits at the start of the audit.
- Current tracked and proposed launch files.
- Historical filenames and Git blob sizes.
- High-confidence credential patterns and Gitleaks' default rules.
- Locked runtime Python dependencies.
- Public documentation paths and GitHub contribution forms.

The audit did not inspect private runtime databases or customer data because those artifacts are
prohibited from the repository and ignored by default.

## Tool provenance

- Gitleaks `v8.30.1`, downloaded from the official `gitleaks/gitleaks` GitHub release.
- Published Windows x64 archive SHA-256:
  `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e`.
- The downloaded archive checksum was verified against the release's published checksum file
  before extracting only `gitleaks.exe` into a temporary directory.
- `pip-audit` was run against a frozen `uv export` that omitted the editable root project and
  retained the locked runtime dependency hashes.

## Results

| Check | Result |
| --- | --- |
| Historical high-confidence credential patterns | No findings |
| Gitleaks complete-history scan | Five findings, all classified as synthetic test idempotency keys |
| Risky historical filenames | None |
| Current risky tracked paths | None |
| Git blobs larger than 5 MiB | None |
| Locked runtime dependency advisories | No known vulnerabilities |
| GitHub issue-form syntax and required structure | Valid |
| Personal absolute paths in the current public documentation | Removed |

Gitleaks' five complete-history findings occur in
`tests/integration/test_memory_proposal_api.py` and
`tests/integration/test_product_memory_api.py`. Each matched value is a deterministic test-only
idempotency identifier such as `proposal-decision-001` or `review-approved-memory`. These values
are not credentials, do not authenticate to a service and grant no access authority.

A directory scan also saw the same synthetic identifiers and generic-key matches inside the
ignored local `.venv`. The virtual environment is not tracked or distributed. No proposed GitHub
launch file produced a finding.

## Launch decision

Proceed with the bounded public alpha only after:

1. the complete repository verifier passes;
2. the launch commit receives immutable local and detached Buildbox verification;
3. the private remote CI passes on the exact launch commit;
4. GitHub private vulnerability reporting and public branch protection are enabled; and
5. the unauthenticated repository view is checked after the visibility change.

If any gate fails, keep the repository private until the failure is resolved.

## Limitations

Secret scanners cannot prove that no sensitive value exists. Synthetic strings can create false
positives, and unknown credential formats can evade default rules. Contributors must continue to
keep credentials, private prompts, customer artifacts, hidden evaluation labels and runtime state
out of Git and must rotate any real credential that is ever exposed.

## Post-launch verification

The bounded public alpha launched from tag `v0.2.0-alpha.1` at exact commit
`87922b91c4a858469d9734609faf922de4513366`.

- Local immutable verification: Python 355 passed / 4 skipped; frontend 61 passed.
- Detached Buildbox verification: Python 358 passed / 1 skipped; frontend 61 passed.
- GitHub Actions run
  [`33387093925`](https://github.com/Maverick0351a/oscillink-agent/actions/runs/33387093925)
  passed both `quality (windows-latest)` and `quality (ubuntu-latest)` on the exact commit.
- A CI-only repair changed the workflow from the pytest console entry point to
  `python -m pytest`; the former excluded the repository root and could not import the demo
  script package on a clean runner. The differential reproduction failed with exit 2 through
  the console entry point and passed three acceptance tests through module invocation.
- An unauthenticated shallow clone resolved the exact public commit and completed the documented
  account-free continuity demonstration in 6.719 seconds with 40 context tokens, no transcript
  replay and exact `supersedes` lineage. This maintainer-run smoke test is launch evidence, not an
  external participant.
- GitHub reports public visibility, Apache-2.0 licensing, seven discovery topics and 100% community
  profile health.
- Private vulnerability reporting, Dependabot security updates, secret scanning and push
  protection are enabled.
- `main` requires strict Windows and Ubuntu CI, one non-admin approval, stale-review dismissal,
  linear history and resolved conversations; force-push and deletion are disabled.
- The published wheel and source distribution were downloaded into an isolated directory and
  verified against a portable two-entry `SHA256SUMS.txt` manifest.

Public launch surfaces:

- [Prerelease](https://github.com/Maverick0351a/oscillink-agent/releases/tag/v0.2.0-alpha.1)
- [Five-user enrollment issue](https://github.com/Maverick0351a/oscillink-agent/issues/1)
- [Public-alpha announcement](https://github.com/Maverick0351a/oscillink-agent/discussions/2)

The Gate 3 count remains **0/5 external users** until independent people use Project Memory on
their own project workflows.
