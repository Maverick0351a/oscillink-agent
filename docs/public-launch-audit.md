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
