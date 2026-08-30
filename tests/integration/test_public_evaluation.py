from __future__ import annotations

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_public_evaluation.py"
MANIFEST = ROOT / "evaluations" / "manifests" / "public-smoke.yaml"


def test_public_fake_provider_evaluation_writes_reproducible_report(tmp_path: Path) -> None:
    report_path = tmp_path / "public-smoke-report.json"

    completed = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(MANIFEST),
            "--output",
            str(report_path),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": ""},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fixture_path = (MANIFEST.parent / manifest["fixture_path"]).resolve()
    assert summary == {
        "passed": True,
        "report": str(report_path.resolve()),
        "results": 12,
        "smoke_only": True,
    }
    assert report["manifest_hash"] == "sha256:" + sha256(MANIFEST.read_bytes()).hexdigest()
    assert report["fixture_hash"] == "sha256:" + sha256(fixture_path.read_bytes()).hexdigest()
    assert report["provider"]["kind"] == "fake"
    assert report["provider"]["model"] == "evaluation-smoke-v1"
    assert report["passed"] is True
    assert len(report["results"]) == 12
    assert {result["condition"] for result in report["results"]} == {
        "no_memory",
        "raw_transcript",
        "generated_summary",
        "approved_lexical",
    }
    assert any(result["metrics"]["correctness"] == 0.0 for result in report["results"])
    assert all("labels" not in result for result in report["results"])
