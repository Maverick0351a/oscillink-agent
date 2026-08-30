from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_milestone_one_acceptance_journey_is_recoverable_and_sanitized() -> None:
    repository = Path(__file__).resolve().parents[2]
    environment = {**os.environ, "PYTHONPATH": ""}

    completed = subprocess.run(
        [sys.executable, "scripts/milestone_one_acceptance.py"],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "anonymous_fail_closed": True,
        "approved_only_context": True,
        "artifact_recovered": True,
        "canonical_state_recovered": True,
        "proposal_recovered": True,
        "run_recovered": True,
        "sanitized": True,
        "schema_version": 1,
        "state": "passed",
        "temporary_state_removed": True,
    }
