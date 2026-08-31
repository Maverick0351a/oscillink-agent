## Outcome

Describe the bounded user or contract outcome. Link the issue when one exists.

## Evidence

- [ ] Production behavior followed RED → GREEN → REFACTOR TDD where applicable.
- [ ] `PYTHONPATH= .venv/Scripts/python.exe scripts/verify.py --base HEAD` passes locally.
- [ ] Claims are bounded to behavior exercised by deterministic tests or direct receipts.
- [ ] New dependencies, external assets, and integrations include source, license, version, and security review.

## Governance and security

- [ ] No secret, credential, private prompt, hidden label, runtime database, or customer artifact is included.
- [ ] Retrieved/model-generated content cannot grant authority or promote itself.
- [ ] Memory, capability, recovery, and provenance boundaries remain explicit and reversible.
- [ ] No arbitrary host execution, browser shell, actuator control, or unrestricted network authority was added.

## Compatibility and recovery

- [ ] Exact revisions, fixtures, budgets, and providers are recorded where relevant.
- [ ] Restart/replay, failure, and rollback behavior is tested where state changes.
- [ ] Documentation and public compatibility claims match executable behavior.
