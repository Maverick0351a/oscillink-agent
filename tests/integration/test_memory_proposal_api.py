from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from oscillink_agent.api import create_app
from oscillink_agent.domain.events import Event, canonical_payload_hash
from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.repository import SQLiteMemoryRepository
from oscillink_agent.storage.artifacts import LocalArtifactStore
from oscillink_agent.storage.sqlite import EventConstraintError, SQLiteEventStore

_AUTHORIZATION = "Bearer oscillink-test-workspace-credential"


def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, object] | None = None,
    idempotency_key: str | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        headers = {"Authorization": _AUTHORIZATION}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, json=json, headers=headers)

    return asyncio.run(send())


def app_with_pending_proposal(tmp_path: Path) -> tuple[FastAPI, str, str, Path]:
    source_root = tmp_path / "selected"
    source_root.mkdir()
    source = source_root / "evidence.md"
    source.write_text("# Governed evidence\n", encoding="utf-8", newline="\n")
    data_root = tmp_path / "runtime"
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        record = repository.create_native(
            title="Target memory",
            content="Canonical target content.",
            category=MemoryCategory.PROJECT,
            domains=(MemoryDomain.SOFTWARE,),
            topics=("proposal",),
            content_hash=(
                "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
        )
    finally:
        repository.close()
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
        workspace_actor_id="human_proposal_reviewer",
    )
    imported = request(
        app,
        "POST",
        "/api/v1/artifact-imports",
        json={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000200",
            "observed_at": "2026-08-29T20:00:00Z",
            "scope_id": "user_selection",
            "target": "evidence.md",
            "target_record_id": record.id,
        },
        idempotency_key="proposal-import-001",
    )
    assert imported.status_code == 201, imported.text
    return app, record.id, imported.json()["association"]["event_id"], source_root


def test_pending_proposal_projection_is_durable_and_sanitized(tmp_path: Path) -> None:
    app, record_id, proposal_id, source_root = app_with_pending_proposal(tmp_path)

    response = request(app, "GET", "/api/v1/memory-proposals")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "schema_version": 1,
        "count": 1,
        "proposals": [
            {
                "proposal_id": proposal_id,
                "state": "pending_review",
                "target_record_id": record_id,
                "artifact_ref": response.json()["proposals"][0]["artifact_ref"],
                "source_name": "evidence.md",
                "created_at": "2026-08-29T20:00:00Z",
                "decision_event_id": None,
                "decided_at": None,
                "decided_by": None,
            }
        ],
    }
    assert response.json()["proposals"][0]["artifact_ref"].startswith("sha256:")
    assert str(source_root) not in response.text

    restarted_app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=None,
        import_scopes={"user_selection": source_root},
        workspace_actor_id="human_proposal_reviewer",
    )
    restarted = request(restarted_app, "GET", "/api/v1/memory-proposals")
    assert restarted.json() == response.json()


def test_empty_proposal_read_does_not_initialize_storage(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)

    response = request(app, "GET", "/api/v1/memory-proposals")

    assert response.status_code == 200
    assert response.json() == {"schema_version": 1, "count": 0, "proposals": []}
    assert not data_root.exists()


def test_approval_creates_one_attributed_governed_relationship(tmp_path: Path) -> None:
    app, record_id, proposal_id, _source_root = app_with_pending_proposal(tmp_path)
    decision_request = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000201",
        "observed_at": "2026-08-29T20:01:00Z",
        "decision": "approved",
    }

    approved = request(
        app,
        "POST",
        f"/api/v1/memory-proposals/{proposal_id}/decisions",
        json=decision_request,
        idempotency_key="proposal-decision-001",
    )
    replay = request(
        app,
        "POST",
        f"/api/v1/memory-proposals/{proposal_id}/decisions",
        json=decision_request,
        idempotency_key="proposal-decision-001",
    )

    assert approved.status_code == 200, approved.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == approved.json()
    projection = approved.json()
    assert projection["proposal_id"] == proposal_id
    assert projection["target_record_id"] == record_id
    assert projection["state"] == "approved"
    assert projection["decision_event_id"] == decision_request["request_id"]
    assert projection["decided_at"] == decision_request["observed_at"]
    assert projection["decided_by"] == "human_proposal_reviewer"

    target_memory = request(app, "GET", f"/api/v1/memory/nodes/{record_id}")
    assert target_memory.status_code == 200
    assert target_memory.json()["node"]["authority_state"] == "candidate"

    restarted_app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=None,
        import_scopes={"user_selection": tmp_path / "selected"},
        workspace_actor_id="human_proposal_reviewer",
    )
    recovered = request(restarted_app, "GET", "/api/v1/memory-proposals")
    assert recovered.status_code == 200
    assert recovered.json()["proposals"] == [projection]

    conflicting = request(
        app,
        "POST",
        f"/api/v1/memory-proposals/{proposal_id}/decisions",
        json={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000202",
            "observed_at": "2026-08-29T20:02:00Z",
            "decision": "rejected",
        },
        idempotency_key="proposal-decision-002",
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["detail"]["code"] == "proposal_already_resolved"

    with sqlite3.connect(tmp_path / "runtime" / "events.sqlite3") as connection:
        encoded = connection.execute(
            "SELECT event_json FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
    assert encoded is not None
    decision_event = json.loads(encoded[0])
    assert decision_event["event_type"] == "approval"
    assert decision_event["actor"] == {"id": "human_proposal_reviewer", "type": "human"}
    assert decision_event["trust_class"] == "human_verified"
    assert decision_event["causal_parent_ids"] == [proposal_id]
    assert decision_event["artifact_refs"] == [projection["artifact_ref"]]

    competing_payload = {
        **decision_event["payload"],
        "decision": "rejected",
    }
    competing_event = Event.model_validate_json(
        json.dumps(
            {
                **decision_event,
                "id": "evt_01J00000000000000000000204",
                "event_type": "retraction",
                "payload": competing_payload,
                "payload_hash": canonical_payload_hash(competing_payload),
            }
        )
    )
    event_store = SQLiteEventStore(
        tmp_path / "runtime" / "events.sqlite3",
        artifacts=LocalArtifactStore(tmp_path / "runtime" / "artifacts"),
    )
    try:
        with pytest.raises(EventConstraintError):
            event_store.append(competing_event, idempotency_key="competing-decision")
    finally:
        event_store.close()


def test_rejection_is_terminal_and_recovers_after_restart(tmp_path: Path) -> None:
    app, _record_id, proposal_id, _source_root = app_with_pending_proposal(tmp_path)

    rejected = request(
        app,
        "POST",
        f"/api/v1/memory-proposals/{proposal_id}/decisions",
        json={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000203",
            "observed_at": "2026-08-29T20:03:00Z",
            "decision": "rejected",
        },
        idempotency_key="proposal-rejection-001",
    )

    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["state"] == "rejected"
    restarted_app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=None,
        import_scopes={"user_selection": tmp_path / "selected"},
        workspace_actor_id="human_proposal_reviewer",
    )
    recovered = request(restarted_app, "GET", "/api/v1/memory-proposals")
    assert recovered.json()["proposals"] == [rejected.json()]

    with sqlite3.connect(tmp_path / "runtime" / "events.sqlite3") as connection:
        encoded = connection.execute(
            "SELECT event_json FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
    assert encoded is not None
    assert json.loads(encoded[0])["event_type"] == "retraction"
