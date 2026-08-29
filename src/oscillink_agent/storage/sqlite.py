"""Append-only SQLite event storage."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

from oscillink_agent.domain.events import Event, EventId, SessionId
from oscillink_agent.storage.interfaces import ArtifactStore, ArtifactStoreError

_MIGRATION = Path(__file__).with_name("migrations") / "001_events.sql"
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_SCHEMA_VERSION = 1


class IdempotencyConflictError(ValueError):
    """An idempotency key was reused for different event content."""


class DuplicateEventError(ValueError):
    """An event ID was already appended to the ledger."""


class InvalidIdempotencyKeyError(ValueError):
    """An idempotency key is not a bounded portable token."""


class MissingCausalParentError(ValueError):
    """An event references a causal parent absent from the ledger."""


class LedgerCorruptionError(ValueError):
    """Persisted event bytes no longer match their recorded digest."""


class InvalidEventError(ValueError):
    """Ledger ingress requires an exact validated Event value."""


class UnsupportedSchemaVersionError(ValueError):
    """The database schema is newer than this store understands."""


class UnresolvedArtifactReferenceError(ValueError):
    """An event artifact reference was not verified by canonical storage."""


class SQLiteEventStore:
    """Persist validated events and replay them in insertion order."""

    def __init__(self, database: Path, *, artifacts: ArtifactStore | None = None) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        version_row = connection.execute("PRAGMA user_version").fetchone()
        version = int(version_row[0])
        if version not in (0, _SCHEMA_VERSION):
            connection.close()
            raise UnsupportedSchemaVersionError(
                f"unsupported SQLite schema version: {version}"
            )
        self._connection = connection
        self._artifacts = artifacts
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(_MIGRATION.read_text(encoding="utf-8"))

    def append(self, event: Event, *, idempotency_key: str) -> str:
        return self.append_many(((event, idempotency_key),))[0]

    def append_many(self, entries: Iterable[tuple[Event, str]]) -> tuple[str, ...]:
        with self._connection:
            return tuple(
                self._append_one(event, idempotency_key)
                for event, idempotency_key in entries
            )

    def _append_one(self, event: Event, idempotency_key: str) -> str:
        if type(event) is not Event:
            raise InvalidEventError("ledger ingress requires an exact Event instance")
        if type(idempotency_key) is not str or _IDEMPOTENCY_KEY.fullmatch(
            idempotency_key
        ) is None:
            raise InvalidIdempotencyKeyError(
                "idempotency key must be a 1-128 character portable token"
            )
        for parent_id in event.causal_parent_ids:
            parent_exists = self._connection.execute(
                "SELECT 1 FROM events WHERE event_id = ?",
                (parent_id,),
            ).fetchone()
            if parent_exists is None:
                raise MissingCausalParentError(
                    f"causal parent does not exist: {parent_id}"
                )
        for reference in event.artifact_refs:
            if self._artifacts is None:
                raise UnresolvedArtifactReferenceError(
                    f"artifact store is required to verify reference: {reference}"
                )
            try:
                self._artifacts.verify(reference)
            except ArtifactStoreError as exc:
                raise UnresolvedArtifactReferenceError(
                    f"artifact reference could not be verified: {reference}"
                ) from exc
        encoded = event.model_dump_json()
        try:
            self._connection.execute(
                """
                INSERT INTO events (
                    event_id, idempotency_key, session_id, recorded_at,
                    payload_hash, event_json, event_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    idempotency_key,
                    event.session_id,
                    event.recorded_at.isoformat(),
                    event.payload_hash,
                    encoded,
                    hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                ),
            )
        except sqlite3.IntegrityError:
            existing = self._connection.execute(
                "SELECT event_id, event_json FROM events WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing == (event.id, encoded):
                return event.id
            if existing is not None:
                raise IdempotencyConflictError(
                    f"idempotency key already belongs to another event: {idempotency_key}"
                ) from None
            duplicate_event = self._connection.execute(
                "SELECT 1 FROM events WHERE event_id = ?",
                (event.id,),
            ).fetchone()
            if duplicate_event is not None:
                raise DuplicateEventError(f"event ID already exists: {event.id}") from None
            raise
        return event.id

    def stream(self, session_id: SessionId) -> Iterator[Event]:
        rows = self._connection.execute(
            """
            SELECT event_id, event_json, event_sha256, payload_hash
            FROM events
            WHERE session_id = ?
            ORDER BY sequence
            """,
            (session_id,),
        )
        for event_id, encoded, expected_digest, expected_payload_hash in rows:
            actual_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            if actual_digest != expected_digest:
                raise LedgerCorruptionError(f"event bytes changed after append: {event_id}")
            try:
                event = Event.model_validate_json(encoded)
            except (TypeError, ValueError) as exc:
                raise LedgerCorruptionError(
                    f"persisted event is malformed: {event_id}"
                ) from exc
            if event.payload_hash != expected_payload_hash:
                raise LedgerCorruptionError(f"payload hash changed after append: {event_id}")
            yield event

    def get(self, event_id: EventId) -> Event | None:
        """Resolve one immutable event by its product-owned identity."""

        row = self._connection.execute(
            """
            SELECT event_id, event_json, event_sha256, payload_hash
            FROM events
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
        if row is None:
            return None
        persisted_id, encoded, expected_digest, expected_payload_hash = row
        actual_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        if actual_digest != expected_digest:
            raise LedgerCorruptionError(
                f"event bytes changed after append: {persisted_id}"
            )
        try:
            event = Event.model_validate_json(encoded)
        except (TypeError, ValueError) as exc:
            raise LedgerCorruptionError(
                f"persisted event is malformed: {persisted_id}"
            ) from exc
        if event.payload_hash != expected_payload_hash:
            raise LedgerCorruptionError(
                f"payload hash changed after append: {persisted_id}"
            )
        return event

    def get_by_idempotency(self, idempotency_key: str) -> Event | None:
        if type(idempotency_key) is not str or _IDEMPOTENCY_KEY.fullmatch(
            idempotency_key
        ) is None:
            raise InvalidIdempotencyKeyError(
                "idempotency key must be a 1-128 character portable token"
            )
        row = self._connection.execute(
            """
            SELECT event_id, event_json, event_sha256, payload_hash
            FROM events
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        event_id, encoded, expected_digest, expected_payload_hash = row
        actual_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        if actual_digest != expected_digest:
            raise LedgerCorruptionError(f"event bytes changed after append: {event_id}")
        try:
            event = Event.model_validate_json(encoded)
        except (TypeError, ValueError) as exc:
            raise LedgerCorruptionError(
                f"persisted event is malformed: {event_id}"
            ) from exc
        if event.payload_hash != expected_payload_hash:
            raise LedgerCorruptionError(f"payload hash changed after append: {event_id}")
        return event

    def close(self) -> None:
        self._connection.close()
