from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from oscillink_agent.api import create_app
from oscillink_agent.memory.repository import ProductMemoryRecord, SQLiteMemoryRepository


def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json, headers=headers)

    return asyncio.run(send())


def write_note(vault: Path, relative_path: str, content: str) -> None:
    path = vault / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def test_native_candidate_survives_restart_without_obsidian(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    first_app = create_app(data_root=data_root, vault_root=None)

    created = request(
        first_app,
        "POST",
        "/api/v1/memory/nodes",
        json={
            "schema_version": 1,
            "title": "Customer memory",
            "content": "The customer requires inspectable provenance.",
            "category": "project",
            "domains": ["business", "software"],
            "topics": ["customer memory"],
        },
    )

    assert created.status_code == 201, created.text
    node = created.json()["node"]
    assert node["id"].startswith("mem_")
    assert node["authority_state"] == "candidate"
    assert node["source_kind"] == "native"
    assert node["source_path"] is None

    restarted_app = create_app(data_root=data_root, vault_root=None)
    collection = request(restarted_app, "GET", "/api/v1/memory/nodes")

    assert collection.status_code == 200
    assert collection.json()["state"] == "ready"
    assert collection.json()["count"] == 1
    assert collection.json()["nodes"][0]["id"] == node["id"]
    assert collection.json()["nodes"][0]["authority_state"] == "candidate"
    index = request(restarted_app, "GET", "/api/v1/memory/index")
    assert index.status_code == 200
    assert index.json()["state"] == "ready"
    assert index.json()["node_count"] == 1
    service_status = request(restarted_app, "GET", "/api/v1/status")
    assert service_status.json()["features"]["memory_lattice"] == "ready"


def test_native_memory_persists_explicit_architecture_associations(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)

    created = request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        json={
            "schema_version": 1,
            "title": "Architecture-bound memory",
            "content": "This record belongs to governed memory and provenance containers.",
            "category": "governance",
            "domains": ["software"],
            "topics": ["architecture association"],
            "architecture_node_ids": ["projects-work", "decisions-lessons"],
        },
    )

    assert created.status_code == 201, created.text
    node = created.json()["node"]
    assert node["architecture_node_ids"] == ["projects-work", "decisions-lessons"]

    restarted = create_app(data_root=data_root, vault_root=None)
    recovered = request(restarted, "GET", f"/api/v1/memory/nodes/{node['id']}")
    assert recovered.status_code == 200
    assert recovered.json()["node"]["architecture_node_ids"] == [
        "projects-work",
        "decisions-lessons",
    ]

    invalid = request(
        restarted,
        "POST",
        "/api/v1/memory/nodes",
        json={
            "schema_version": 1,
            "title": "Invalid architecture association",
            "content": "Unknown containers must fail closed.",
            "category": "governance",
            "domains": ["software"],
            "architecture_node_ids": ["invented-component"],
        },
    )
    assert invalid.status_code == 422


def test_missing_product_record_read_does_not_initialize_storage(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)

    missing = request(
        app,
        "GET",
        "/api/v1/memory/nodes/mem_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )

    assert missing.status_code == 404
    assert not data_root.exists()


def test_human_review_is_append_only_and_survives_restart(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)
    created = request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        json={
            "schema_version": 1,
            "title": "Approved customer memory",
            "content": "Approval is a separate human decision.",
            "category": "governance",
            "domains": ["software"],
            "topics": ["review"],
        },
    ).json()["node"]

    reviewed = request(
        app,
        "POST",
        f"/api/v1/memory/nodes/{created['id']}/reviews",
        headers={"Idempotency-Key": "review-approved-memory"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "decision": "approved",
        },
    )

    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["node"]["id"] == created["id"]
    assert reviewed.json()["node"]["authority_state"] == "approved"

    restarted = create_app(data_root=data_root, vault_root=None)
    recovered = request(restarted, "GET", f"/api/v1/memory/nodes/{created['id']}")
    assert recovered.status_code == 200
    assert recovered.json()["node"]["authority_state"] == "approved"

    replay = request(
        restarted,
        "POST",
        f"/api/v1/memory/nodes/{created['id']}/reviews",
        headers={"Idempotency-Key": "review-approved-memory"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "decision": "approved",
        },
    )
    assert replay.status_code == 200
    with sqlite3.connect(data_root / "memory.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM memory_reviews").fetchone() == (
            1,
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM memory_record_revisions"
        ).fetchone() == (1,)


def _create_candidate(app: FastAPI, *, title: str, content: str) -> dict[str, Any]:
    response = request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        json={
            "schema_version": 1,
            "title": title,
            "content": content,
            "category": "project",
            "domains": ["software"],
            "topics": ["governance"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["node"]


def test_rejected_memory_cannot_be_reapproved_without_a_new_revision(
    tmp_path: Path,
) -> None:
    app = create_app(data_root=tmp_path / "runtime", vault_root=None)
    candidate = _create_candidate(
        app,
        title="Unsafe claim",
        content="A rejected claim must remain rejected.",
    )
    rejected = request(
        app,
        "POST",
        f"/api/v1/memory/nodes/{candidate['id']}/reviews",
        headers={"Idempotency-Key": "reject-memory-001"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAY",
            "decision": "rejected",
        },
    )
    invalid = request(
        app,
        "POST",
        f"/api/v1/memory/nodes/{candidate['id']}/reviews",
        headers={"Idempotency-Key": "approve-rejected-001"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAZ",
            "decision": "approved",
        },
    )

    assert rejected.status_code == 200
    assert rejected.json()["node"]["authority_state"] == "rejected"
    assert invalid.status_code == 409
    assert invalid.json()["detail"]["code"] == "invalid_transition"


def test_approved_memory_can_be_superseded_only_by_an_approved_replacement(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)
    original = _create_candidate(app, title="Original", content="Original guidance.")
    replacement = _create_candidate(
        app,
        title="Replacement",
        content="Replacement guidance with corrected evidence.",
    )
    premature = request(
        app,
        "POST",
        f"/api/v1/memory/nodes/{original['id']}/reviews",
        headers={"Idempotency-Key": "supersede-premature-001"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB0",
            "decision": "superseded",
            "replacement_record_id": replacement["id"],
        },
    )
    assert premature.status_code == 409

    for node, key, event_id in (
        (original, "approve-original-001", "evt_01ARZ3NDEKTSV4RRFFQ69G5FB1"),
        (replacement, "approve-replacement-001", "evt_01ARZ3NDEKTSV4RRFFQ69G5FB2"),
    ):
        approved = request(
            app,
            "POST",
            f"/api/v1/memory/nodes/{node['id']}/reviews",
            headers={"Idempotency-Key": key},
            json={
                "schema_version": 1,
                "request_id": event_id,
                "decision": "approved",
            },
        )
        assert approved.status_code == 200, approved.text

    superseded = request(
        app,
        "POST",
        f"/api/v1/memory/nodes/{original['id']}/reviews",
        headers={"Idempotency-Key": "supersede-approved-001"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB3",
            "decision": "superseded",
            "replacement_record_id": replacement["id"],
        },
    )

    assert superseded.status_code == 200, superseded.text
    assert superseded.json()["node"]["authority_state"] == "superseded"
    restarted = create_app(data_root=data_root, vault_root=None)
    recovered = request(
        restarted,
        "GET",
        f"/api/v1/memory/nodes/{original['id']}",
    )
    assert recovered.json()["node"]["authority_state"] == "superseded"


def test_obsidian_sync_keeps_product_identity_when_source_is_renamed(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    vault = tmp_path / "vault"
    source = """---
type: research-note
status: active
domains: [software]
---
# Durable identity

The source path is provenance, not product identity.
"""
    write_note(vault, "Notes/Original.md", source)
    app = create_app(data_root=data_root, vault_root=vault)

    first_sync = request(
        app,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        headers={"Idempotency-Key": "sync-original"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
        },
    )

    assert first_sync.status_code == 200, first_sync.text
    first_node = request(app, "GET", "/api/v1/memory/nodes").json()["nodes"][0]
    assert first_node["id"].startswith("mem_")
    assert first_node["authority_state"] == "curated"
    assert first_node["source_kind"] == "obsidian"
    assert first_node["source_path"] == "Notes/Original.md"

    write_note(vault, "Notes/Original.md", source + "Changed after the request.\n")
    conflicting_replay = request(
        app,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        headers={"Idempotency-Key": "sync-original"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAW",
        },
    )
    assert conflicting_replay.status_code == 409
    unchanged = request(app, "GET", "/api/v1/memory/nodes").json()["nodes"][0]
    assert unchanged["content_hash"] == first_node["content_hash"]

    write_note(vault, "Notes/Original.md", source)
    (vault / "Notes/Original.md").rename(vault / "Notes/Renamed.md")
    second_sync = request(
        app,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        headers={"Idempotency-Key": "sync-renamed"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAX",
        },
    )

    assert second_sync.status_code == 200, second_sync.text
    renamed_node = request(app, "GET", "/api/v1/memory/nodes").json()["nodes"][0]
    assert renamed_node["id"] == first_node["id"]
    assert renamed_node["source_path"] == "Notes/Renamed.md"

    approved = request(
        app,
        "POST",
        f"/api/v1/memory/nodes/{renamed_node['id']}/reviews",
        headers={"Idempotency-Key": "approve-synchronized-001"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB4",
            "decision": "approved",
        },
    )
    assert approved.json()["node"]["authority_state"] == "approved"

    write_note(vault, "Notes/Renamed.md", source + "New unreviewed evidence.\n")
    changed_sync = request(
        app,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        headers={"Idempotency-Key": "sync-changed"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB5",
        },
    )
    assert changed_sync.status_code == 200
    changed_node = request(app, "GET", "/api/v1/memory/nodes").json()["nodes"][0]
    assert changed_node["id"] == first_node["id"]
    assert changed_node["authority_state"] == "curated"
    with sqlite3.connect(data_root / "memory.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM memory_reviews").fetchone() == (
            1,
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM memory_record_revisions"
        ).fetchone() == (3,)


def test_obsidian_sync_rolls_back_every_record_when_one_record_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "runtime"
    vault = tmp_path / "vault"
    for name in ("Alpha", "Beta"):
        write_note(
            vault,
            f"Notes/{name}.md",
            f"""---
type: note
status: active
domains: [software]
---
# {name}

Atomic source synchronization fixture.
""",
        )
    original_write = SQLiteMemoryRepository._write_record_locked
    write_count = 0

    def fail_second_write(
        repository: SQLiteMemoryRepository,
        record: ProductMemoryRecord,
    ) -> None:
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise RuntimeError("injected source synchronization failure")
        original_write(repository, record)

    monkeypatch.setattr(SQLiteMemoryRepository, "_write_record_locked", fail_second_write)
    app = create_app(data_root=data_root, vault_root=vault)

    with pytest.raises(RuntimeError, match="injected source synchronization failure"):
        request(
            app,
            "POST",
            "/api/v1/memory/sources/obsidian/sync",
            headers={"Idempotency-Key": "sync-atomic-failure"},
            json={
                "schema_version": 1,
                "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB6",
            },
        )

    with sqlite3.connect(data_root / "memory.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM memory_records").fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM memory_record_revisions"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM memory_source_bindings"
        ).fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM memory_source_syncs").fetchone() == (0,)


def test_obsidian_sync_marks_records_missing_when_the_source_disappears(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    vault = tmp_path / "vault"
    source_path = vault / "Notes/Continuity.md"
    write_note(
        vault,
        "Notes/Continuity.md",
        """---
type: note
status: active
domains: [software]
---
# Continuity

Source absence must be visible without deleting product history.
""",
    )
    app = create_app(data_root=data_root, vault_root=vault)
    first = request(
        app,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        headers={"Idempotency-Key": "sync-source-present"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB7",
        },
    )
    assert first.status_code == 200
    present = request(app, "GET", "/api/v1/memory/nodes").json()["nodes"][0]
    source_path.unlink()

    removed = request(
        app,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        headers={"Idempotency-Key": "sync-source-missing"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB8",
        },
    )

    assert removed.status_code == 200
    missing = request(app, "GET", "/api/v1/memory/nodes").json()["nodes"][0]
    assert missing["id"] == present["id"]
    assert missing["content_hash"] == present["content_hash"]
    assert missing["source_path"] == "Notes/Continuity.md"
    assert missing["source_status"] == "missing"
