from __future__ import annotations

from pathlib import Path


def test_local_adapters_implement_storage_protocols(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.interfaces import ArtifactStore, EventStore
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    artifacts = LocalArtifactStore(tmp_path / "artifacts")
    events = SQLiteEventStore(tmp_path / "events.sqlite3")

    assert isinstance(artifacts, ArtifactStore)
    assert isinstance(events, EventStore)
    events.close()
