"""Ordered restart-safe SQLite schema migrations."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


class MigrationError(RuntimeError):
    """A store version or migration sequence is invalid."""


def _set_schema_version(connection: sqlite3.Connection, version: int) -> None:
    if version == 1:
        connection.execute("PRAGMA user_version = 1")
    elif version == 2:
        connection.execute("PRAGMA user_version = 2")
    else:
        raise MigrationError("schema version has no reviewed PRAGMA transition")


def require_compatible_schema(
    connection: sqlite3.Connection,
    *,
    store_name: str,
    current_version: int,
) -> int:
    """Reject future schemas while allowing one legacy unversioned baseline."""

    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version not in (0, current_version):
        raise MigrationError(
            f"{store_name} schema version {version} is incompatible with {current_version}"
        )
    return version


def record_current_schema(
    connection: sqlite3.Connection,
    *,
    current_version: int,
) -> None:
    """Record the exact initialized schema version in the canonical database."""

    _set_schema_version(connection, current_version)
    connection.commit()


@dataclass(frozen=True)
class MigrationStep:
    """One transaction-safe transition to an exact target version."""

    target_version: int
    apply: Callable[[sqlite3.Connection], object]


def _backup_database(database: Path, current_version: int) -> Path:
    backup = database.with_name(
        f"{database.name}.v{current_version}.{uuid.uuid4().hex}.backup"
    )
    with closing(sqlite3.connect(database)) as source, closing(
        sqlite3.connect(backup)
    ) as destination:
        source.backup(destination)
        destination.commit()
        if destination.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise MigrationError("migration backup failed integrity verification")
    return backup


def apply_sqlite_migrations(
    database: Path,
    *,
    store_name: str,
    target_version: int,
    steps: tuple[MigrationStep, ...],
) -> Path | None:
    """Apply a contiguous migration sequence atomically after a verified backup."""

    if not store_name or target_version < 1:
        raise MigrationError("store name and positive target version are required")
    if not database.is_file():
        raise MigrationError(f"{store_name} database does not exist")
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current_version > target_version:
            raise MigrationError(
                f"{store_name} schema version {current_version} is newer than {target_version}"
            )
        if current_version == target_version:
            return None
        applicable = tuple(
            step for step in steps if current_version < step.target_version <= target_version
        )
        expected_versions = tuple(range(current_version + 1, target_version + 1))
        if tuple(step.target_version for step in applicable) != expected_versions:
            raise MigrationError(f"{store_name} migration sequence is incomplete")
        backup = _backup_database(database, current_version)
        connection.execute("BEGIN IMMEDIATE")
        try:
            for step in applicable:
                step.apply(connection)
                _set_schema_version(connection, step.target_version)
            connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != target_version:
            raise MigrationError(f"{store_name} migration did not record target version")
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise MigrationError(f"{store_name} migration failed integrity verification")
        return backup
    finally:
        connection.close()
