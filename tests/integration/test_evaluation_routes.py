from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx

from oscillink_agent.api import create_app
from oscillink_agent.evaluation.baselines import DeterministicSmokeExecutor
from oscillink_agent.evaluation.runner import load_suite, run_suite

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_MANIFEST = ROOT / "evaluations" / "manifests" / "public-smoke.yaml"


def request(app: object, path: str, *, authenticated: bool = True) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        headers = (
            {"Authorization": "Bearer test-private-credential"}
            if authenticated
            else None
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path, headers=headers)

    return asyncio.run(send())


def test_latest_evaluation_is_authenticated_fixed_location_and_freshness_aware(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        workspace_credential="test-private-credential",
        code_revision="b" * 40,
    )

    anonymous = request(app, "/api/v1/evaluations/latest", authenticated=False)
    assert anonymous.status_code == 401

    missing = request(app, "/api/v1/evaluations/latest")
    assert missing.status_code == 200
    assert missing.json() == {
        "schema_version": 1,
        "state": "unavailable",
        "freshness": "unknown",
        "reason": "report_missing",
        "report": None,
    }
    assert not data_root.exists()

    report = run_suite(
        load_suite(PUBLIC_MANIFEST),
        DeterministicSmokeExecutor(),
        code_revision="a" * 40,
    )
    report_path = data_root / "evaluations" / "latest.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")

    loaded = request(app, "/api/v1/evaluations/latest")
    assert loaded.status_code == 200
    payload = loaded.json()
    assert payload["state"] == "available"
    assert payload["freshness"] == "stale"
    assert payload["reason"] == "code_revision_mismatch"
    assert payload["report"]["suite_id"] == "public-smoke"
    assert payload["report"]["code_revision"] == "a" * 40
    assert payload["report"]["passed"] is True
    assert {result["condition"] for result in payload["report"]["results"]} == {
        "no_memory",
        "raw_transcript",
        "generated_summary",
        "approved_lexical",
    }
    assert str(data_root) not in loaded.text
    assert "accepted_answers" not in loaded.text

    current_app = create_app(
        data_root=data_root,
        vault_root=None,
        workspace_credential="test-private-credential",
        code_revision="a" * 40,
    )
    current = request(current_app, "/api/v1/evaluations/latest").json()
    assert current["freshness"] == "current"
    assert current["reason"] is None


def test_invalid_oversized_or_out_of_root_report_fails_closed(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    report_path = data_root / "evaluations" / "latest.json"
    report_path.parent.mkdir(parents=True)
    app = create_app(
        data_root=data_root,
        vault_root=None,
        workspace_credential="test-private-credential",
        code_revision="a" * 40,
    )

    report_path.write_text('{"accepted_answers":["hidden"]}', encoding="utf-8")
    invalid = request(app, "/api/v1/evaluations/latest")
    assert invalid.json()["reason"] == "report_invalid"
    assert "accepted_answers" not in invalid.text
    assert str(report_path) not in invalid.text

    report_path.write_bytes(b"x" * (16 * 1024 * 1024 + 1))
    oversized = request(app, "/api/v1/evaluations/latest")
    assert oversized.json()["reason"] == "report_invalid"

    report_path.unlink()
    outside = tmp_path / "outside-report.json"
    outside.write_text('{"accepted_answers":["hidden"]}', encoding="utf-8")
    try:
        os.symlink(outside, report_path)
    except OSError:
        return
    escaped = request(app, "/api/v1/evaluations/latest")
    assert escaped.json()["reason"] == "report_invalid"
    assert str(outside) not in escaped.text
    assert "accepted_answers" not in escaped.text
