from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from oscillink_agent.storage.migrations import MigrationStep, apply_sqlite_migrations


def _version(database: Path) -> int:
    with sqlite3.connect(database) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def test_ordered_migration_preserves_v1_data_and_records_v2(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE records (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO records VALUES ('record-1', 'preserved')")
        connection.execute("PRAGMA user_version = 1")

    apply_sqlite_migrations(
        database,
        store_name="memory",
        target_version=2,
        steps=(
            MigrationStep(
                target_version=2,
                apply=lambda connection: connection.execute(
                    "ALTER TABLE records ADD COLUMN reviewed INTEGER NOT NULL DEFAULT 0"
                ),
            ),
        ),
    )

    assert _version(database) == 2
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT id, value, reviewed FROM records"
        ).fetchall() == [("record-1", "preserved", 0)]


def test_interrupted_migration_rolls_back_and_keeps_verified_backup(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE events (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO events VALUES ('evt-preserved')")
        connection.execute("PRAGMA user_version = 1")

    def fail_after_ddl(connection: sqlite3.Connection) -> None:
        connection.execute("ALTER TABLE events ADD COLUMN detail TEXT")
        raise RuntimeError("simulated migration interruption")

    with pytest.raises(RuntimeError, match="simulated migration interruption"):
        apply_sqlite_migrations(
            database,
            store_name="events",
            target_version=2,
            steps=(MigrationStep(target_version=2, apply=fail_after_ddl),),
        )

    assert _version(database) == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA table_info(events)").fetchall() == [
            (0, "id", "TEXT", 0, None, 1)
        ]
        assert connection.execute("SELECT id FROM events").fetchall() == [
            ("evt-preserved",)
        ]
    backups = tuple(tmp_path.glob("events.sqlite3.v1.*.backup"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert backup.execute("SELECT id FROM events").fetchall() == [
            ("evt-preserved",)
        ]
