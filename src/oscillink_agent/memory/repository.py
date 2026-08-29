"""Product-owned memory records and local persistence."""

from __future__ import annotations

import re
import secrets
import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from oscillink_agent.domain.events import Digest, FrozenModel
from oscillink_agent.memory.obsidian import (
    IndexedObsidianNote,
    MemoryCategory,
    MemoryDomain,
)

MemoryRecordId = Annotated[str, Field(pattern=r"^mem_[0-9A-HJKMNP-TV-Z]{26}$")]
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class MemoryRecordNotFoundError(ValueError):
    """A review targeted a record absent from the product repository."""


class MemoryReviewConflictError(ValueError):
    """A review idempotency key or event ID was reused incompatibly."""


class MemorySyncConflictError(ValueError):
    """A source-sync identity was reused for a different snapshot."""


class MemoryTransitionConflictError(ValueError):
    """A review decision violates the governed authority-state machine."""


class MemoryAuthorityState(StrEnum):
    """Human-governed eligibility state independent of source presence."""

    CURATED = "curated"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    RETRACTED = "retracted"


class MemorySourceKind(StrEnum):
    """Bounded origin vocabulary for product-owned records."""

    NATIVE = "native"
    OBSIDIAN = "obsidian"


class ProductMemoryRecord(FrozenModel):
    """Stable product record; source location is provenance, not identity."""

    schema_version: Literal[1] = 1
    id: MemoryRecordId
    title: Annotated[str, Field(min_length=1, max_length=512)]
    content: Annotated[str, Field(min_length=1, max_length=2 * 1024 * 1024)]
    authority_state: MemoryAuthorityState
    source_kind: MemorySourceKind
    source_key: str
    source_path: str | None
    source_status: str | None
    category: MemoryCategory
    domains: tuple[MemoryDomain, ...]
    topics: tuple[str, ...]
    content_hash: Digest
    wikilinks: tuple[str, ...] = ()
    classification_basis: tuple[str, ...] = ()


class SQLiteMemoryRepository:
    """Persist product-owned memory records independently of source adapters."""

    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database, timeout=10)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                record_id TEXT PRIMARY KEY,
                record_json TEXT NOT NULL
            ) STRICT
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_reviews (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                idempotency_key TEXT NOT NULL UNIQUE,
                record_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                decision TEXT NOT NULL CHECK (
                    decision IN ('approved', 'rejected', 'superseded')
                ),
                replacement_record_id TEXT,
                FOREIGN KEY (record_id) REFERENCES memory_records(record_id)
            ) STRICT
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_record_revisions (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL,
                record_json TEXT NOT NULL,
                UNIQUE (record_id, record_json),
                FOREIGN KEY (record_id) REFERENCES memory_records(record_id)
            ) STRICT
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_source_bindings (
                source_key TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                record_id TEXT NOT NULL UNIQUE,
                PRIMARY KEY (source_key, source_locator),
                FOREIGN KEY (record_id) REFERENCES memory_records(record_id)
            ) STRICT
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_source_syncs (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                idempotency_key TEXT NOT NULL UNIQUE,
                source_key TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL
            ) STRICT
            """
        )

    def create_native(
        self,
        *,
        title: str,
        content: str,
        category: MemoryCategory,
        domains: tuple[MemoryDomain, ...],
        topics: tuple[str, ...],
        content_hash: Digest,
    ) -> ProductMemoryRecord:
        record = ProductMemoryRecord(
            id=_new_record_id(),
            title=title,
            content=content,
            authority_state=MemoryAuthorityState.CANDIDATE,
            source_kind=MemorySourceKind.NATIVE,
            source_key="native",
            source_path=None,
            source_status=None,
            category=category,
            domains=domains,
            topics=topics,
            content_hash=content_hash,
            classification_basis=("customer:native",),
        )
        self._write_record(record)
        return record

    def _write_record(self, record: ProductMemoryRecord) -> None:
        encoded = record.model_dump_json()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO memory_records (record_id, record_json)
                VALUES (?, ?)
                ON CONFLICT(record_id) DO UPDATE SET record_json = excluded.record_json
                """,
                (record.id, encoded),
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO memory_record_revisions (record_id, record_json)
                VALUES (?, ?)
                """,
                (record.id, encoded),
            )

    def sync_obsidian(
        self,
        *,
        source_key: str,
        notes: tuple[IndexedObsidianNote, ...],
        event_id: str,
        idempotency_key: str,
        snapshot_hash: str,
    ) -> tuple[ProductMemoryRecord, ...]:
        """Synchronize curated source records without granting approval."""

        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise ValueError("invalid source-sync idempotency key")
        expected = (event_id, source_key, snapshot_hash)
        existing = self._connection.execute(
            """
            SELECT event_id, source_key, snapshot_hash
            FROM memory_source_syncs
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            if existing != expected:
                raise MemorySyncConflictError(idempotency_key)
            return tuple(
                record for record in self.list() if record.source_key == source_key
            )
        event_owner = self._connection.execute(
            "SELECT idempotency_key FROM memory_source_syncs WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if event_owner is not None:
            raise MemorySyncConflictError(event_id)

        current_locators = {note.source_path for note in notes}
        synchronized: list[ProductMemoryRecord] = []
        for note in notes:
            binding = self._connection.execute(
                """
                SELECT record_id
                FROM memory_source_bindings
                WHERE source_key = ? AND source_locator = ?
                """,
                (source_key, note.source_path),
            ).fetchone()
            record_id = str(binding[0]) if binding is not None else None
            previous_locator: str | None = None
            if record_id is None:
                candidates = self._connection.execute(
                    """
                    SELECT record_id, source_locator
                    FROM memory_source_bindings
                    WHERE source_key = ? AND content_hash = ?
                    """,
                    (source_key, note.content_hash),
                ).fetchall()
                renamed = [row for row in candidates if row[1] not in current_locators]
                if len(renamed) == 1:
                    record_id = str(renamed[0][0])
                    previous_locator = str(renamed[0][1])
            if record_id is None:
                record_id = _new_record_id()

            record = ProductMemoryRecord(
                id=record_id,
                title=note.title,
                content=note.content,
                authority_state=MemoryAuthorityState.CURATED,
                source_kind=MemorySourceKind.OBSIDIAN,
                source_key=source_key,
                source_path=note.source_path,
                source_status=note.source_status,
                category=note.category,
                domains=note.domains,
                topics=note.topics,
                content_hash=note.content_hash,
                wikilinks=note.wikilinks,
                classification_basis=note.classification_basis,
            )
            self._write_record(record)
            with self._connection:
                if previous_locator is not None:
                    self._connection.execute(
                        """
                        DELETE FROM memory_source_bindings
                        WHERE source_key = ? AND source_locator = ?
                        """,
                        (source_key, previous_locator),
                    )
                self._connection.execute(
                    """
                    INSERT INTO memory_source_bindings (
                        source_key, source_locator, content_hash, record_id
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_key, source_locator) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        record_id = excluded.record_id
                    """,
                    (source_key, note.source_path, note.content_hash, record_id),
                )
            synchronized.append(self.get(record_id) or record)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO memory_source_syncs (
                    event_id, idempotency_key, source_key, snapshot_hash
                ) VALUES (?, ?, ?, ?)
                """,
                (event_id, idempotency_key, source_key, snapshot_hash),
            )
        return tuple(synchronized)

    def list(self) -> tuple[ProductMemoryRecord, ...]:
        rows = self._connection.execute(
            "SELECT record_id, record_json FROM memory_records ORDER BY rowid"
        )
        return tuple(self._with_review_state(row[0], row[1]) for row in rows)

    def get(self, record_id: str) -> ProductMemoryRecord | None:
        row = self._connection.execute(
            "SELECT record_id, record_json FROM memory_records WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        return None if row is None else self._with_review_state(row[0], row[1])

    def review(
        self,
        record_id: str,
        *,
        decision: MemoryAuthorityState,
        event_id: str,
        idempotency_key: str,
        replacement_record_id: str | None = None,
    ) -> ProductMemoryRecord:
        if decision not in {
            MemoryAuthorityState.APPROVED,
            MemoryAuthorityState.REJECTED,
            MemoryAuthorityState.SUPERSEDED,
        }:
            raise ValueError("unsupported review decision")
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise ValueError("invalid review idempotency key")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            reviewed = self._review_locked(
                record_id,
                decision=decision,
                event_id=event_id,
                idempotency_key=idempotency_key,
                replacement_record_id=replacement_record_id,
            )
        except Exception:
            self._connection.rollback()
            raise
        self._connection.commit()
        return reviewed

    def _review_locked(
        self,
        record_id: str,
        *,
        decision: MemoryAuthorityState,
        event_id: str,
        idempotency_key: str,
        replacement_record_id: str | None,
    ) -> ProductMemoryRecord:
        current = self.get(record_id)
        if current is None:
            raise MemoryRecordNotFoundError(record_id)
        existing = self._connection.execute(
            """
            SELECT event_id, record_id, content_hash, decision, replacement_record_id
            FROM memory_reviews
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        expected = (
            event_id,
            record_id,
            current.content_hash,
            decision.value,
            replacement_record_id,
        )
        if existing is not None:
            if existing != expected:
                raise MemoryReviewConflictError(idempotency_key)
            reviewed = self.get(record_id)
            assert reviewed is not None
            return reviewed
        if decision in {
            MemoryAuthorityState.APPROVED,
            MemoryAuthorityState.REJECTED,
        }:
            if (
                current.authority_state
                not in {
                    MemoryAuthorityState.CANDIDATE,
                    MemoryAuthorityState.CURATED,
                }
                or replacement_record_id is not None
            ):
                raise MemoryTransitionConflictError(record_id)
        else:
            replacement = (
                None
                if replacement_record_id is None
                else self.get(replacement_record_id)
            )
            if (
                current.authority_state is not MemoryAuthorityState.APPROVED
                or replacement is None
                or replacement.id == record_id
                or replacement.authority_state is not MemoryAuthorityState.APPROVED
            ):
                raise MemoryTransitionConflictError(record_id)
        try:
            self._connection.execute(
                """
                INSERT INTO memory_reviews (
                    event_id, idempotency_key, record_id, content_hash, decision,
                    replacement_record_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    idempotency_key,
                    record_id,
                    current.content_hash,
                    decision.value,
                    replacement_record_id,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise MemoryReviewConflictError(event_id) from error
        reviewed = self.get(record_id)
        assert reviewed is not None
        return reviewed

    def _with_review_state(
        self,
        record_id: str,
        encoded: str,
    ) -> ProductMemoryRecord:
        record = ProductMemoryRecord.model_validate_json(encoded)
        review = self._connection.execute(
            """
            SELECT decision
            FROM memory_reviews
            WHERE record_id = ? AND content_hash = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (record_id, record.content_hash),
        ).fetchone()
        if review is None:
            return record
        return record.model_copy(
            update={"authority_state": MemoryAuthorityState(review[0])}
        )

    def close(self) -> None:
        self._connection.close()


def _new_record_id() -> str:
    value = int.from_bytes(secrets.token_bytes(17), "big") >> 6
    token = ""
    for _ in range(26):
        token = _CROCKFORD[value & 31] + token
        value >>= 5
    return f"mem_{token}"
