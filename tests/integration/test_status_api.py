import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx

from oscillink_agent.api import create_app
from oscillink_agent.domain.events import (
    Actor,
    ActorType,
    Event,
    EventType,
    Sensitivity,
    TrustClass,
    canonical_payload_hash,
)
from oscillink_agent.storage.artifacts import LocalArtifactStore
from oscillink_agent.storage.sqlite import SQLiteEventStore


def request_status(data_root: Path) -> httpx.Response:
    app = create_app(data_root=data_root)

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/api/v1/status")

    return asyncio.run(request())


def test_status_reports_workspace_auth_readiness_without_credential(
    tmp_path: Path,
) -> None:
    credential = "private-status-credential"
    app = create_app(
        data_root=tmp_path / "runtime",
        workspace_credential=credential,
    )

    async def request(authorization: str | None = None) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            headers = (
                {"Authorization": authorization}
                if authorization is not None
                else None
            )
            return await client.get("/api/v1/status", headers=headers)

    locked_response = asyncio.run(request())
    ready_response = asyncio.run(request(f"Bearer {credential}"))

    assert locked_response.status_code == 200
    assert locked_response.json()["workspace_auth"] == {"state": "locked"}
    assert ready_response.status_code == 200
    assert ready_response.json()["workspace_auth"] == {"state": "ready"}
    assert credential not in locked_response.text
    assert credential not in ready_response.text


def test_status_reports_uninitialized_storage_without_creating_it(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"

    response = request_status(data_root)

    assert response.status_code == 200
    assert response.json() == {
        "service": "oscillink-agent",
        "version": "0.1.0",
        "api_state": "online",
        "workspace_auth": {"state": "locked"},
        "storage": {
            "ledger": {"state": "not_initialized", "record_count": 0},
            "artifacts": {"state": "not_initialized", "record_count": 0},
            "memory": {"state": "not_initialized", "record_count": 0},
        },
        "features": {
            "chat": "ready",
            "capability_broker": "preview",
            "memory_lattice": "preview",
            "appearance": "preview",
            "workspace_terminal": "preview",
        },
    }
    assert not data_root.exists()


def test_status_reports_records_from_initialized_storage(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    artifacts = LocalArtifactStore(data_root / "artifacts")
    reference = artifacts.put(b"verified status artifact")
    payload = {"message": "status probe"}
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    event = Event(
        id="evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        schema_version=1,
        session_id="ses_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        run_id="run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        task_id="tsk_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        actor=Actor(id="human_maverick", type=ActorType.HUMAN),
        event_type=EventType.OBSERVATION,
        observed_at=timestamp,
        recorded_at=timestamp,
        payload_hash=canonical_payload_hash(payload),
        artifact_refs=(reference,),
        causal_parent_ids=(),
        trust_class=TrustClass.HUMAN_VERIFIED,
        sensitivity=Sensitivity.INTERNAL,
        payload=payload,
    )
    ledger = SQLiteEventStore(data_root / "events.sqlite3", artifacts=artifacts)
    ledger.append(event, idempotency_key="status-probe")
    ledger.close()

    response = request_status(data_root)

    assert response.status_code == 200
    assert response.json()["storage"] == {
        "ledger": {"state": "ready", "record_count": 1},
        "artifacts": {"state": "ready", "record_count": 1},
        "memory": {"state": "not_initialized", "record_count": 0},
    }


def test_status_reports_a_malformed_memory_database_as_an_error(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    data_root.mkdir()
    (data_root / "memory.sqlite3").write_bytes(b"not a sqlite database")

    response = request_status(data_root)

    assert response.status_code == 200
    assert response.json()["storage"]["memory"] == {
        "state": "error",
        "record_count": 0,
    }
    assert response.json()["features"]["memory_lattice"] == "preview"
