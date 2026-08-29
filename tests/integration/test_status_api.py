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


def test_status_reports_uninitialized_storage_without_creating_it(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"

    response = request_status(data_root)

    assert response.status_code == 200
    assert response.json() == {
        "service": "oscillink-agent",
        "version": "0.1.0",
        "api_state": "online",
        "storage": {
            "ledger": {"state": "not_initialized", "record_count": 0},
            "artifacts": {"state": "not_initialized", "record_count": 0},
        },
        "features": {
            "chat": "planned",
            "memory_lattice": "planned",
            "appearance": "preview",
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
    }
