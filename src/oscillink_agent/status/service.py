"""Read-only inspection of local durable storage."""

import re
import sqlite3
from pathlib import Path

from oscillink_agent.status.contracts import StorageComponentStatus

_HEX_DIRECTORY = re.compile(r"[0-9a-f]{2}")
_HEX_OBJECT = re.compile(r"[0-9a-f]{62}")


def inspect_ledger(database: Path) -> StorageComponentStatus:
    if not database.is_file():
        return StorageComponentStatus(state="not_initialized", record_count=0)
    try:
        connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        try:
            version_row = connection.execute("PRAGMA user_version").fetchone()
            if version_row != (1,):
                return StorageComponentStatus(state="error", record_count=0)
            count_row = connection.execute("SELECT COUNT(*) FROM events").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return StorageComponentStatus(state="error", record_count=0)
    return StorageComponentStatus(state="ready", record_count=int(count_row[0]))


def inspect_artifacts(root: Path) -> StorageComponentStatus:
    if not root.is_dir():
        return StorageComponentStatus(state="not_initialized", record_count=0)
    try:
        count = sum(
            1
            for directory in root.iterdir()
            if directory.is_dir() and _HEX_DIRECTORY.fullmatch(directory.name)
            for artifact in directory.iterdir()
            if artifact.is_file()
            and not artifact.is_symlink()
            and _HEX_OBJECT.fullmatch(artifact.name)
        )
    except OSError:
        return StorageComponentStatus(state="error", record_count=0)
    return StorageComponentStatus(state="ready", record_count=count)


def inspect_memory(database: Path) -> StorageComponentStatus:
    if not database.is_file():
        return StorageComponentStatus(state="not_initialized", record_count=0)
    try:
        connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        try:
            required_tables = {
                "memory_records",
                "memory_reviews",
                "memory_record_revisions",
                "memory_source_bindings",
                "memory_source_syncs",
            }
            table_rows = connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            ).fetchall()
            if not required_tables.issubset({str(row[0]) for row in table_rows}):
                return StorageComponentStatus(state="error", record_count=0)
            count_row = connection.execute("SELECT COUNT(*) FROM memory_records").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return StorageComponentStatus(state="error", record_count=0)
    return StorageComponentStatus(state="ready", record_count=int(count_row[0]))
