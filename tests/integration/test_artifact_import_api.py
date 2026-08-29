from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from oscillink_agent.api import create_app
from oscillink_agent.memory.obsidian import build_reviewed_obsidian_index


def post_import(
    app: FastAPI,
    payload: dict[str, object],
    *,
    idempotency_key: str = "import-evidence-001",
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/api/v1/artifact-imports",
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
            )

    return asyncio.run(send())


def test_import_api_publishes_scoped_file_and_sanitized_event(tmp_path: Path) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    source = source_root / "evidence.txt"
    source.write_text("governed evidence\n", encoding="utf-8", newline="\n")
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
    )

    response = post_import(
        app,
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000100",
            "observed_at": "2000-01-01T00:00:00Z",
            "scope_id": "user_selection",
            "target": "evidence.txt",
            "target_record_id": None,
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["schema_version"] == 1
    assert payload["state"] == "imported"
    assert payload["event_id"] == "evt_01J00000000000000000000100"
    assert payload["artifact"]["source_scope_id"] == "user_selection"
    assert payload["artifact"]["source_name"] == "evidence.txt"
    assert payload["artifact"]["media_type"] == "text/plain"
    assert payload["artifact"]["logical_bytes"] == len(b"governed evidence\n")
    assert payload["artifact"]["unique_physical_bytes"] == len(b"governed evidence\n")
    assert payload["artifact"]["deduplicated"] is False
    assert payload["artifact"]["artifact_ref"].startswith("sha256:")
    assert payload["association"] == {"state": "unattached"}
    assert str(source_root) not in response.text
    assert source.read_bytes() == b"governed evidence\n"

    with sqlite3.connect(data_root / "events.sqlite3") as connection:
        event_row = connection.execute("SELECT event_json FROM events").fetchone()
    assert event_row is not None
    assert payload["artifact"]["artifact_ref"] in event_row[0]
    assert str(source_root) not in event_row[0]
    assert json.loads(event_row[0])["recorded_at"] != "2000-01-01T00:00:00Z"


def test_import_api_creates_pending_candidate_for_stable_record(tmp_path: Path) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    (source_root / "evidence.md").write_text("# Supporting evidence\n", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Record.md").write_text(
        """---
type: research-note
status: active
domains: [science]
---
# Stable Record
""",
        encoding="utf-8",
        newline="\n",
    )
    record_id = build_reviewed_obsidian_index(vault).notes[0].id
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=vault,
        import_scopes={"user_selection": source_root},
    )

    request_payload = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000101",
        "observed_at": "2026-08-28T19:31:00Z",
        "scope_id": "user_selection",
        "target": "evidence.md",
        "target_record_id": record_id,
    }
    response = post_import(
        app,
        request_payload,
        idempotency_key="import-associated-001",
    )
    replay = post_import(
        app,
        request_payload,
        idempotency_key="import-associated-001",
    )

    assert response.status_code == 201, response.text
    assert replay.status_code == 201, replay.text
    assert replay.json() == response.json()
    payload = response.json()
    assert payload["association"]["state"] == "candidate"
    assert payload["association"]["review_state"] == "pending_review"
    assert payload["association"]["target_record_id"] == record_id
    assert payload["association"]["event_id"].startswith("evt_")
    assert str(vault) not in response.text
    assert "Record.md" not in response.text

    with sqlite3.connect(data_root / "events.sqlite3") as connection:
        rows = connection.execute("SELECT event_json FROM events ORDER BY sequence").fetchall()
    assert len(rows) == 2
    import_event = json.loads(rows[0][0])
    candidate_event = json.loads(rows[1][0])
    assert candidate_event["event_type"] == "memory_proposal"
    assert candidate_event["causal_parent_ids"] == [import_event["id"]]
    assert candidate_event["artifact_refs"] == import_event["artifact_refs"]
    assert candidate_event["payload"] == {
        "operation": "artifact_association",
        "status": "pending_review",
        "target_record_id": record_id,
    }


def test_import_api_is_unavailable_without_configured_scope(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)

    response = post_import(
        app,
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000102",
            "observed_at": "2026-08-28T19:32:00Z",
            "scope_id": "user_selection",
            "target": "evidence.txt",
            "target_record_id": None,
        },
        idempotency_key="import-unconfigured-001",
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "import_unavailable",
            "message": "No local import scope is configured.",
        }
    }
    assert not data_root.exists()


def test_unknown_target_record_fails_before_import(tmp_path: Path) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    (source_root / "evidence.txt").write_text("not yet attached", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Record.md").write_text(
        """---
type: research-note
status: active
---
# Existing Record
""",
        encoding="utf-8",
        newline="\n",
    )
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=vault,
        import_scopes={"user_selection": source_root},
    )

    response = post_import(
        app,
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000103",
            "observed_at": "2026-08-28T19:33:00Z",
            "scope_id": "user_selection",
            "target": "evidence.txt",
            "target_record_id": "doc_00000000000000000000000000",
        },
        idempotency_key="import-unknown-node-001",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "node_not_found",
            "message": "Memory node was not found.",
        }
    }
    assert not data_root.exists()


def test_exact_idempotent_replay_returns_original_import(tmp_path: Path) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    (source_root / "evidence.txt").write_text("idempotent evidence", encoding="utf-8")
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
    )
    request_payload = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000104",
        "observed_at": "2026-08-28T19:34:00Z",
        "scope_id": "user_selection",
        "target": "evidence.txt",
        "target_record_id": None,
    }

    first = post_import(
        app,
        request_payload,
        idempotency_key="import-replay-001",
    )
    replay = post_import(
        app,
        request_payload,
        idempotency_key="import-replay-001",
    )

    assert first.status_code == 201, first.text
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()
    with sqlite3.connect(data_root / "events.sqlite3") as connection:
        count = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert count == (1,)


def test_failed_import_replay_returns_original_failure_without_retrying_source(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
    )
    request_payload = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000110",
        "observed_at": "2026-08-28T19:40:00Z",
        "scope_id": "user_selection",
        "target": "appears-later.txt",
        "target_record_id": None,
    }
    first = post_import(
        app,
        request_payload,
        idempotency_key="failed-replay-001",
    )
    (source_root / "appears-later.txt").write_text("late bytes", encoding="utf-8")
    replay = post_import(
        app,
        request_payload,
        idempotency_key="failed-replay-001",
    )

    assert first.status_code == 409
    assert first.json()["detail"]["code"] == "source_unavailable"
    assert replay.status_code == first.status_code
    assert replay.json() == first.json()
    with sqlite3.connect(data_root / "events.sqlite3") as connection:
        count = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert count == (1,)
    artifact_root = data_root / "artifacts" / "sha256"
    assert not artifact_root.exists() or not any(artifact_root.rglob("*"))


@pytest.mark.parametrize(
    ("scope_id", "target", "expected_status", "expected_code"),
    [
        ("missing_scope", "evidence.txt", 404, "source_scope_not_found"),
        ("user_selection", "script.py", 415, "extension_not_allowed"),
        ("user_selection", "missing.txt", 409, "source_unavailable"),
    ],
)
def test_selection_failures_are_sanitized_and_audited(
    tmp_path: Path,
    scope_id: str,
    target: str,
    expected_status: int,
    expected_code: str,
) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    (source_root / "script.py").write_text("raise SystemExit", encoding="utf-8")
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
    )

    response = post_import(
        app,
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000105",
            "observed_at": "2026-08-28T19:35:00Z",
            "scope_id": scope_id,
            "target": target,
            "target_record_id": None,
        },
        idempotency_key=f"selection-failure-{expected_code}",
    )

    assert response.status_code == expected_status
    assert response.json() == {
        "detail": {
            "code": expected_code,
            "message": "Selected file could not be imported.",
        }
    }
    assert str(tmp_path) not in response.text
    with sqlite3.connect(data_root / "events.sqlite3") as connection:
        event_json = connection.execute("SELECT event_json FROM events").fetchone()
    assert event_json is not None
    assert '"status":"failed"' in event_json[0]
    assert str(tmp_path) not in event_json[0]
    artifact_root = data_root / "artifacts" / "sha256"
    assert not artifact_root.exists() or not any(artifact_root.rglob("*"))


@pytest.mark.parametrize(
    "invalid_update",
    [
        {"scope_id": "UPPER CASE"},
        {"target": "../secret.txt"},
        {"target": "C:/secret.txt"},
        {"target_record_id": "cluster_00000000000000000000000"},
        {"observed_at": 1_777_000_000},
    ],
)
def test_transport_invalid_imports_fail_before_storage(
    tmp_path: Path,
    invalid_update: dict[str, object],
) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
    )
    request_payload: dict[str, object] = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000106",
        "observed_at": "2026-08-28T19:36:00Z",
        "scope_id": "user_selection",
        "target": "evidence.txt",
        "target_record_id": None,
    }
    request_payload.update(invalid_update)

    response = post_import(
        app,
        request_payload,
        idempotency_key="transport-invalid-001",
    )

    assert response.status_code == 422
    assert not data_root.exists()


def test_idempotency_key_cannot_drop_existing_candidate_association(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    (source_root / "evidence.txt").write_text("association evidence", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Record.md").write_text(
        """---
type: research-note
status: active
---
# Stable Record
""",
        encoding="utf-8",
        newline="\n",
    )
    record_id = build_reviewed_obsidian_index(vault).notes[0].id
    app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=vault,
        import_scopes={"user_selection": source_root},
    )
    request_payload = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000111",
        "observed_at": "2026-08-28T19:41:00Z",
        "scope_id": "user_selection",
        "target": "evidence.txt",
        "target_record_id": record_id,
    }
    first = post_import(
        app,
        request_payload,
        idempotency_key="association-removal-conflict-001",
    )
    request_payload["target_record_id"] = None

    conflict = post_import(
        app,
        request_payload,
        idempotency_key="association-removal-conflict-001",
    )

    assert first.status_code == 201, first.text
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": {
            "code": "idempotency_conflict",
            "message": "Idempotency key belongs to another import request.",
        }
    }
    with sqlite3.connect(tmp_path / "runtime" / "events.sqlite3") as connection:
        count = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert count == (2,)


def test_idempotency_key_cannot_be_reused_for_same_named_different_target(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "selected"
    (source_root / "first").mkdir(parents=True)
    (source_root / "second").mkdir()
    (source_root / "first" / "evidence.txt").write_text("first", encoding="utf-8")
    (source_root / "second" / "evidence.txt").write_text("second", encoding="utf-8")
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
    )
    request_payload = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000107",
        "observed_at": "2026-08-28T19:37:00Z",
        "scope_id": "user_selection",
        "target": "first/evidence.txt",
        "target_record_id": None,
    }
    first = post_import(
        app,
        request_payload,
        idempotency_key="import-conflict-001",
    )
    request_payload["target"] = "second/evidence.txt"
    conflict = post_import(
        app,
        request_payload,
        idempotency_key="import-conflict-001",
    )

    assert first.status_code == 201, first.text
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": {
            "code": "idempotency_conflict",
            "message": "Idempotency key belongs to another import request.",
        }
    }
    assert str(source_root) not in conflict.text
    with sqlite3.connect(data_root / "events.sqlite3") as connection:
        count = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert count == (1,)


def test_duplicate_bytes_reuse_artifact_but_keep_import_provenance(tmp_path: Path) -> None:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    content = "duplicate evidence"
    (source_root / "first.txt").write_text(content, encoding="utf-8")
    (source_root / "second.txt").write_text(content, encoding="utf-8")
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
    )
    first = post_import(
        app,
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000108",
            "observed_at": "2026-08-28T19:38:00Z",
            "scope_id": "user_selection",
            "target": "first.txt",
            "target_record_id": None,
        },
        idempotency_key="duplicate-import-001",
    )
    second = post_import(
        app,
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000109",
            "observed_at": "2026-08-28T19:39:00Z",
            "scope_id": "user_selection",
            "target": "second.txt",
            "target_record_id": None,
        },
        idempotency_key="duplicate-import-002",
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_artifact = first.json()["artifact"]
    second_artifact = second.json()["artifact"]
    expected_size = len(content.encode("utf-8"))
    assert second_artifact["artifact_ref"] == first_artifact["artifact_ref"]
    assert first_artifact["logical_bytes"] == expected_size
    assert first_artifact["unique_physical_bytes"] == expected_size
    assert first_artifact["deduplicated"] is False
    assert second_artifact["logical_bytes"] == expected_size
    assert second_artifact["unique_physical_bytes"] == 0
    assert second_artifact["deduplicated"] is True
    with sqlite3.connect(data_root / "events.sqlite3") as connection:
        count = connection.execute("SELECT COUNT(*) FROM events").fetchone()
    assert count == (2,)
