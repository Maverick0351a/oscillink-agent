from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from oscillink_agent.api import create_app
from oscillink_agent.storage.artifacts import LocalArtifactStore
from oscillink_agent.workspaces.export import (
    WorkspaceExportError,
    WorkspaceRestoreError,
    export_workspace,
    restore_workspace,
)


def request(
    app: object,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers, json=json_body)

    return asyncio.run(send())


def _database(path: Path, *, version: int, marker: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker VALUES (?)", (marker,))
        if version == 1:
            connection.execute("PRAGMA user_version = 1")
        else:
            raise ValueError("test helper supports only schema version 1")


def test_workspace_export_restore_round_trip_is_hashed_portable_and_minimal(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-runtime"
    source.mkdir()
    _database(source / "events.sqlite3", version=1, marker="events")
    _database(source / "memory.sqlite3", version=1, marker="memory")
    _database(source / "capabilities.sqlite3", version=1, marker="capabilities")
    artifact_ref = LocalArtifactStore(source / "artifacts").put(b"portable artifact\n")
    (source / "credential.txt").write_text("must-not-export", encoding="utf-8")
    (source / "cache.sqlite3").write_bytes(b"derived-cache")

    bundle = tmp_path / "workspace-export"
    manifest = export_workspace(source, bundle)

    assert manifest.store_versions.model_dump() == {
        "events": 1,
        "memory": 1,
        "capabilities": 1,
        "proposals": 1,
    }
    exported_paths = {entry.path for entry in manifest.entries}
    assert exported_paths == {
        "databases/events.sqlite3",
        "databases/memory.sqlite3",
        "databases/capabilities.sqlite3",
        f"artifacts/{artifact_ref[7:9]}/{artifact_ref[9:]}",
    }
    encoded_manifest = (bundle / "manifest.json").read_text(encoding="utf-8")
    assert str(source) not in encoded_manifest
    assert "credential" not in encoded_manifest
    assert "cache" not in encoded_manifest

    active = tmp_path / "restored-runtime"
    active.mkdir()
    (active / "old-sentinel.txt").write_text("old", encoding="utf-8")
    restored = restore_workspace(bundle, active)

    assert restored == manifest
    assert not (active / "old-sentinel.txt").exists()
    with sqlite3.connect(active / "events.sqlite3") as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == ("events",)
    assert LocalArtifactStore(active / "artifacts").get(artifact_ref) == b"portable artifact\n"


def test_corrupt_or_traversing_restore_never_replaces_active_workspace(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-runtime"
    source.mkdir()
    _database(source / "events.sqlite3", version=1, marker="events")
    bundle = tmp_path / "workspace-export"
    export_workspace(source, bundle)
    active = tmp_path / "active-runtime"
    active.mkdir()
    sentinel = active / "sentinel.txt"
    sentinel.write_text("canonical-active-state", encoding="utf-8")

    (bundle / "databases" / "events.sqlite3").write_bytes(b"corrupt")
    with pytest.raises(WorkspaceRestoreError, match="hash"):
        restore_workspace(bundle, active)
    assert sentinel.read_text(encoding="utf-8") == "canonical-active-state"

    export_workspace(source, bundle, replace=True)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entries"][0]["path"] = "../escape.sqlite3"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(WorkspaceRestoreError, match="portable"):
        restore_workspace(bundle, active)
    assert sentinel.read_text(encoding="utf-8") == "canonical-active-state"
    assert not (tmp_path / "escape.sqlite3").exists()


def test_authenticated_human_can_select_server_managed_export_and_restore(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    data_root.mkdir()
    _database(data_root / "events.sqlite3", version=1, marker="api-events")
    app = create_app(
        data_root=data_root,
        vault_root=None,
        workspace_credential="test-private-credential",
    )
    auth = {"Authorization": "Bearer test-private-credential"}

    anonymous = request(
        app,
        "POST",
        "/api/v1/workspace/exports",
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000060",
        },
    )
    assert anonymous.status_code == 401
    assert not (tmp_path / ".oscillink-exports").exists()

    exported = request(
        app,
        "POST",
        "/api/v1/workspace/exports",
        headers=auth,
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000060",
        },
    )
    assert exported.status_code == 200, exported.text
    export_id = exported.json()["export_id"]
    assert export_id == "exp_01J00000000000000000000060"
    assert str(data_root) not in exported.text

    sentinel = data_root / "post-export-sentinel.txt"
    sentinel.write_text("replace me", encoding="utf-8")
    restored = request(
        app,
        "POST",
        "/api/v1/workspace/restores",
        headers=auth,
        json_body={"schema_version": 1, "export_id": export_id},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["state"] == "restored"
    assert not sentinel.exists()
    with sqlite3.connect(data_root / "events.sqlite3") as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == (
            "api-events",
        )


def test_export_rejects_absolute_host_paths_inside_canonical_databases(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-runtime"
    source.mkdir()
    _database(
        source / "events.sqlite3",
        version=1,
        marker=str(tmp_path / "private-source"),
    )

    with pytest.raises(WorkspaceExportError, match="absolute host path"):
        export_workspace(source, tmp_path / "unsafe-export")
    assert not (tmp_path / "unsafe-export").exists()
