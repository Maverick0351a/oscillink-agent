from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from oscillink_agent.domain.events import Event, canonical_payload_hash


def make_event(
    *,
    event_id: str = "evt_01J00000000000000000000000",
    text: str = "Oscillink Agent project approved.",
    artifact_refs: tuple[str, ...] = (),
    causal_parent_ids: tuple[str, ...] = (),
) -> Event:
    payload = {"text": text}
    return Event.model_validate_json(
        json.dumps(
            {
                "id": event_id,
                "schema_version": 1,
                "session_id": "ses_01J00000000000000000000000",
                "run_id": "run_01J00000000000000000000000",
                "task_id": "tsk_01J00000000000000000000000",
                "actor": {"id": "human_maverick", "type": "human"},
                "event_type": "observation",
                "observed_at": "2026-08-27T18:45:00Z",
                "recorded_at": "2026-08-27T18:45:01Z",
                "payload_hash": canonical_payload_hash(payload),
                "artifact_refs": artifact_refs,
                "causal_parent_ids": causal_parent_ids,
                "trust_class": "human_verified",
                "sensitivity": "private",
                "payload": payload,
            }
        )
    )


def test_event_store_replays_exact_event_after_restart(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    database = tmp_path / "events.sqlite3"
    event = make_event()

    store = SQLiteEventStore(database)
    assert store.append(event, idempotency_key="idem_first-event") == event.id
    store.close()

    reopened = SQLiteEventStore(database)
    replayed = list(reopened.stream(event.session_id))
    reopened.close()

    assert [item.model_dump_json() for item in replayed] == [event.model_dump_json()]


def test_event_store_retries_identical_idempotent_append_once(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    event = make_event()

    first = store.append(event, idempotency_key="idem_first-event")
    second = store.append(event, idempotency_key="idem_first-event")
    replayed = list(store.stream(event.session_id))
    store.close()

    assert first == second == event.id
    assert len(replayed) == 1


def test_event_store_rejects_idempotency_key_reuse_for_different_event(
    tmp_path: Path,
) -> None:
    from oscillink_agent.storage.sqlite import (
        IdempotencyConflictError,
        SQLiteEventStore,
    )

    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    store.append(make_event(), idempotency_key="idem_first-event")

    with pytest.raises(IdempotencyConflictError, match="idem_first-event"):
        store.append(
            make_event(event_id="evt_01J00000000000000000000001"),
            idempotency_key="idem_first-event",
        )

    store.close()


def test_event_store_rejects_duplicate_event_id(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import DuplicateEventError, SQLiteEventStore

    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    store.append(make_event(), idempotency_key="idem_original")

    with pytest.raises(DuplicateEventError, match="evt_01J00000000000000000000000"):
        store.append(
            make_event(text="Conflicting event content."),
            idempotency_key="idem_conflict",
        )

    store.close()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE events SET payload_hash = 'sha256:' || printf('%064d', 0)",
        "DELETE FROM events",
    ],
)
def test_event_ledger_database_rejects_mutation(tmp_path: Path, statement: str) -> None:
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database)
    store.append(make_event(), idempotency_key="idem_original")
    store.close()

    connection = sqlite3.connect(database)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"), connection:
        connection.execute(statement)
    connection.close()


def test_event_store_initializes_sqlite_wal_mode(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database)
    store.close()

    connection = sqlite3.connect(database)
    journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
    connection.close()

    assert journal_mode == ("wal",)


def test_event_store_records_schema_version(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database)
    store.close()

    connection = sqlite3.connect(database)
    schema_version = connection.execute("PRAGMA user_version").fetchone()
    connection.close()

    assert schema_version == (1,)


def test_event_store_rejects_newer_schema_version(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import (
        SQLiteEventStore,
        UnsupportedSchemaVersionError,
    )

    database = tmp_path / "events.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA user_version = 2")
    connection.close()

    with pytest.raises(UnsupportedSchemaVersionError, match="2"):
        SQLiteEventStore(database)


def test_event_store_rolls_back_entire_conflicting_batch(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import DuplicateEventError, SQLiteEventStore

    store = SQLiteEventStore(tmp_path / "events.sqlite3")

    with pytest.raises(DuplicateEventError):
        store.append_many(
            [
                (make_event(), "idem_original"),
                (make_event(text="Conflicting event content."), "idem_conflict"),
            ]
        )

    assert list(store.stream("ses_01J00000000000000000000000")) == []
    store.close()


@pytest.mark.parametrize("idempotency_key", ["", "contains space", "x" * 129])
def test_event_store_rejects_invalid_idempotency_keys(
    tmp_path: Path,
    idempotency_key: str,
) -> None:
    from oscillink_agent.storage.sqlite import (
        InvalidIdempotencyKeyError,
        SQLiteEventStore,
    )

    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    with pytest.raises(InvalidIdempotencyKeyError):
        store.append(make_event(), idempotency_key=idempotency_key)

    assert list(store.stream("ses_01J00000000000000000000000")) == []
    store.close()


def test_event_store_rejects_missing_causal_parent(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import (
        MissingCausalParentError,
        SQLiteEventStore,
    )

    missing_parent = "evt_01J00000000000000000000009"
    event = make_event(causal_parent_ids=(missing_parent,))
    store = SQLiteEventStore(tmp_path / "events.sqlite3")

    with pytest.raises(MissingCausalParentError, match=missing_parent):
        store.append(event, idempotency_key="idem_orphan")

    assert list(store.stream(event.session_id)) == []
    store.close()


def test_event_store_detects_tampered_event_bytes_on_replay(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import LedgerCorruptionError, SQLiteEventStore

    database = tmp_path / "events.sqlite3"
    event = make_event()
    store = SQLiteEventStore(database)
    store.append(event, idempotency_key="idem_original")
    store.close()

    connection = sqlite3.connect(database)
    with connection:
        connection.execute("DROP TRIGGER events_reject_update")
        connection.execute(
            """
            UPDATE events
            SET event_json = replace(event_json, 'human_maverick', 'human_intruder')
            """
        )
    connection.close()

    reopened = SQLiteEventStore(database)
    with pytest.raises(LedgerCorruptionError, match=event.id):
        list(reopened.stream(event.session_id))
    reopened.close()


def test_event_store_reports_malformed_persisted_event_as_corruption(
    tmp_path: Path,
) -> None:
    from oscillink_agent.storage.sqlite import LedgerCorruptionError, SQLiteEventStore

    database = tmp_path / "events.sqlite3"
    event = make_event()
    store = SQLiteEventStore(database)
    store.append(event, idempotency_key="idem_original")
    store.close()

    malformed = '{"id":'
    digest = hashlib.sha256(malformed.encode("utf-8")).hexdigest()
    connection = sqlite3.connect(database)
    with connection:
        connection.execute("DROP TRIGGER events_reject_update")
        connection.execute(
            "UPDATE events SET event_json = ?, event_sha256 = ?",
            (malformed, digest),
        )
    connection.close()

    reopened = SQLiteEventStore(database)
    with pytest.raises(LedgerCorruptionError, match=event.id):
        list(reopened.stream(event.session_id))
    reopened.close()


def test_event_store_rejects_event_subclasses(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import InvalidEventError, SQLiteEventStore

    class EventSubclass(Event):
        pass

    event = EventSubclass.model_validate_json(make_event().model_dump_json())
    store = SQLiteEventStore(tmp_path / "events.sqlite3")

    with pytest.raises(InvalidEventError):
        store.append(event, idempotency_key="idem_subclass")

    assert list(store.stream(event.session_id)) == []
    store.close()


def test_committed_event_survives_process_termination(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    database = tmp_path / "events.sqlite3"
    event = make_event()
    script = """
import os
import sys
from pathlib import Path

from oscillink_agent.domain.events import Event
from oscillink_agent.storage.sqlite import SQLiteEventStore

store = SQLiteEventStore(Path(sys.argv[1]))
store.append(Event.model_validate_json(sys.argv[2]), idempotency_key="idem_child")
os._exit(0)
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(database), event.model_dump_json()],
        check=False,
        env=environment,
    )

    assert completed.returncode == 0
    reopened = SQLiteEventStore(database)
    assert [item.model_dump_json() for item in reopened.stream(event.session_id)] == [
        event.model_dump_json()
    ]
    reopened.close()


def test_event_store_resolves_parent_then_child_in_same_batch(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    parent = make_event()
    child = make_event(
        event_id="evt_01J00000000000000000000001",
        causal_parent_ids=(parent.id,),
    )
    store = SQLiteEventStore(tmp_path / "events.sqlite3")

    appended = store.append_many(
        [(parent, "idem_parent"), (child, "idem_child")]
    )

    assert appended == (parent.id, child.id)
    assert [event.id for event in store.stream(parent.session_id)] == [
        parent.id,
        child.id,
    ]
    store.close()


def test_process_termination_rolls_back_partial_batch(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    database = tmp_path / "events.sqlite3"
    event = make_event()
    script = """
import os
import sys
from pathlib import Path

from oscillink_agent.domain.events import Event
from oscillink_agent.storage.sqlite import SQLiteEventStore

event = Event.model_validate_json(sys.argv[2])
store = SQLiteEventStore(Path(sys.argv[1]))

def interrupted_entries():
    yield event, "idem_uncommitted"
    os._exit(17)

store.append_many(interrupted_entries())
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(database), event.model_dump_json()],
        check=False,
        env=environment,
    )

    assert completed.returncode == 17
    reopened = SQLiteEventStore(database)
    assert list(reopened.stream(event.session_id)) == []
    reopened.close()


def test_event_store_rejects_unresolved_artifact_reference(tmp_path: Path) -> None:
    from oscillink_agent.storage.sqlite import (
        SQLiteEventStore,
        UnresolvedArtifactReferenceError,
    )

    reference = "sha256:" + "0" * 64
    event = make_event(artifact_refs=(reference,))
    store = SQLiteEventStore(tmp_path / "events.sqlite3")

    with pytest.raises(UnresolvedArtifactReferenceError, match=reference):
        store.append(event, idempotency_key="idem_missing-artifact")

    assert list(store.stream(event.session_id)) == []
    store.close()


def test_event_store_rejects_reference_missing_from_configured_store(
    tmp_path: Path,
) -> None:
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.sqlite import (
        SQLiteEventStore,
        UnresolvedArtifactReferenceError,
    )

    artifacts = LocalArtifactStore(tmp_path / "artifacts")
    reference = "sha256:" + "0" * 64
    event = make_event(artifact_refs=(reference,))
    store = SQLiteEventStore(tmp_path / "events.sqlite3", artifacts=artifacts)

    with pytest.raises(UnresolvedArtifactReferenceError, match=reference):
        store.append(event, idempotency_key="idem_missing-artifact")

    assert list(store.stream(event.session_id)) == []
    store.close()


def test_event_store_appends_event_with_verified_artifact(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import LocalArtifactStore
    from oscillink_agent.storage.sqlite import SQLiteEventStore

    artifacts = LocalArtifactStore(tmp_path / "artifacts")
    reference = artifacts.put(b"verified source artifact")
    event = make_event(artifact_refs=(reference,))
    store = SQLiteEventStore(tmp_path / "events.sqlite3", artifacts=artifacts)

    assert store.append(event, idempotency_key="idem_verified-artifact") == event.id
    assert [replayed.id for replayed in store.stream(event.session_id)] == [event.id]
    store.close()
