"""Product-owned memory records and local persistence."""

from __future__ import annotations

import re
import secrets
import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from oscillink_agent.domain.context import RecordId
from oscillink_agent.domain.events import ActorId, Digest, EventId, FrozenModel
from oscillink_agent.memory.obsidian import (
    IndexedObsidianNote,
    MemoryCategory,
    MemoryDomain,
)
from oscillink_agent.storage.migrations import (
    record_current_schema,
    require_compatible_schema,
)

MemoryRecordId = Annotated[str, Field(pattern=r"^mem_[0-9A-HJKMNP-TV-Z]{26}$")]
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class MemoryRecordNotFoundError(ValueError):
    """A review targeted a record absent from the product repository."""


class MemoryCreateConflictError(ValueError):
    """An explicit record identity was reused for incompatible content."""


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


class ArchitectureNodeId(StrEnum):
    """Stable product architecture containers available for explicit memory association."""

    IDENTITY_ROLE = "identity-role"
    GOALS_COMMITMENTS = "goals-commitments"
    PROJECTS_WORK = "projects-work"
    KNOWLEDGE_RESEARCH = "knowledge-research"
    PEOPLE_RELATIONSHIPS = "people-relationships"
    DECISIONS_LESSONS = "decisions-lessons"
    PREFERENCES_CONTEXT = "preferences-context"


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
    architecture_node_ids: tuple[ArchitectureNodeId, ...] = ()
    source_refs: tuple[RecordId, ...] = ()
    created_by: ActorId | None = None
    creation_request_id: EventId | None = None
    correction_target_id: MemoryRecordId | None = None
    correction_expected_hash: Digest | None = None
    correction_reason: str | None = None


class MemorySourceSyncResult(FrozenModel):
    """Repository accounting for one atomic configured-source synchronization."""

    records: tuple[ProductMemoryRecord, ...]
    created: int
    revised: int
    unchanged: int
    missing: int
    issues: int


class MemoryReviewRecord(FrozenModel):
    """Latest governed review decision for one exact memory revision."""

    event_id: str
    record_id: MemoryRecordId
    content_hash: Digest
    decision: MemoryAuthorityState
    replacement_record_id: MemoryRecordId | None


class SQLiteMemoryRepository:
    """Persist product-owned memory records independently of source adapters."""

    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database, timeout=10)
        try:
            require_compatible_schema(
                connection,
                store_name="memory",
                current_version=1,
            )
        except BaseException:
            connection.close()
            raise
        self._connection = connection
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
                snapshot_hash TEXT NOT NULL,
                created_count INTEGER NOT NULL DEFAULT 0,
                revised_count INTEGER NOT NULL DEFAULT 0,
                unchanged_count INTEGER NOT NULL DEFAULT 0,
                missing_count INTEGER NOT NULL DEFAULT 0,
                issue_count INTEGER NOT NULL DEFAULT 0
            ) STRICT
            """
        )
        sync_columns = {
            str(row[1])
            for row in self._connection.execute("PRAGMA table_info(memory_source_syncs)")
        }
        if "created_count" not in sync_columns:
            self._connection.execute(
                "ALTER TABLE memory_source_syncs ADD COLUMN created_count "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "revised_count" not in sync_columns:
            self._connection.execute(
                "ALTER TABLE memory_source_syncs ADD COLUMN revised_count "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "unchanged_count" not in sync_columns:
            self._connection.execute(
                "ALTER TABLE memory_source_syncs ADD COLUMN unchanged_count "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "missing_count" not in sync_columns:
            self._connection.execute(
                "ALTER TABLE memory_source_syncs ADD COLUMN missing_count "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "issue_count" not in sync_columns:
            self._connection.execute(
                "ALTER TABLE memory_source_syncs ADD COLUMN issue_count INTEGER NOT NULL DEFAULT 0"
            )
        record_current_schema(self._connection, current_version=1)

    def create_native(
        self,
        *,
        record_id: MemoryRecordId | None = None,
        title: str,
        content: str,
        category: MemoryCategory,
        domains: tuple[MemoryDomain, ...],
        topics: tuple[str, ...],
        content_hash: Digest,
        architecture_node_ids: tuple[ArchitectureNodeId, ...] = (),
        source_refs: tuple[RecordId, ...] = (),
        created_by: ActorId | None = None,
        creation_request_id: EventId | None = None,
        correction_target_id: MemoryRecordId | None = None,
        correction_expected_hash: Digest | None = None,
        correction_reason: str | None = None,
    ) -> ProductMemoryRecord:
        record = ProductMemoryRecord(
            id=_new_record_id() if record_id is None else record_id,
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
            architecture_node_ids=architecture_node_ids,
            source_refs=source_refs,
            created_by=created_by,
            creation_request_id=creation_request_id,
            correction_target_id=correction_target_id,
            correction_expected_hash=correction_expected_hash,
            correction_reason=correction_reason,
        )
        if record_id is not None:
            return self._insert_explicit_record(record)
        self._write_record(record)
        return record

    def _insert_explicit_record(
        self,
        record: ProductMemoryRecord,
    ) -> ProductMemoryRecord:
        encoded = record.model_dump_json()
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            existing_row = self._connection.execute(
                "SELECT record_json FROM memory_records WHERE record_id = ?",
                (record.id,),
            ).fetchone()
            if existing_row is not None:
                existing = ProductMemoryRecord.model_validate_json(str(existing_row[0]))
                if existing != record:
                    raise MemoryCreateConflictError(record.id)
                self._connection.commit()
                return existing
            self._connection.execute(
                "INSERT INTO memory_records (record_id, record_json) VALUES (?, ?)",
                (record.id, encoded),
            )
            self._connection.execute(
                """
                INSERT INTO memory_record_revisions (record_id, record_json)
                VALUES (?, ?)
                """,
                (record.id, encoded),
            )
        except Exception:
            self._connection.rollback()
            raise
        self._connection.commit()
        return record

    def _write_record(self, record: ProductMemoryRecord) -> None:
        with self._connection:
            self._write_record_locked(record)

    def _write_record_locked(self, record: ProductMemoryRecord) -> None:
        encoded = record.model_dump_json()
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
        issue_count: int,
    ) -> MemorySourceSyncResult:
        """Synchronize curated source records without granting approval."""

        try:
            self._connection.execute("BEGIN IMMEDIATE")
            synchronized = self._sync_obsidian_locked(
                source_key=source_key,
                notes=notes,
                event_id=event_id,
                idempotency_key=idempotency_key,
                snapshot_hash=snapshot_hash,
                issue_count=issue_count,
            )
        except Exception:
            self._connection.rollback()
            raise
        self._connection.commit()
        return synchronized

    def _sync_obsidian_locked(
        self,
        *,
        source_key: str,
        notes: tuple[IndexedObsidianNote, ...],
        event_id: str,
        idempotency_key: str,
        snapshot_hash: str,
        issue_count: int,
    ) -> MemorySourceSyncResult:

        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise ValueError("invalid source-sync idempotency key")
        expected = (event_id, source_key, snapshot_hash)
        existing = self._connection.execute(
            """
            SELECT event_id, source_key, snapshot_hash,
                   created_count, revised_count, unchanged_count, missing_count, issue_count
            FROM memory_source_syncs
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            if existing[:3] != expected:
                raise MemorySyncConflictError(idempotency_key)
            records = tuple(
                record for record in self.list() if record.source_key == source_key
            )
            return MemorySourceSyncResult(
                records=records,
                created=int(existing[3]),
                revised=int(existing[4]),
                unchanged=int(existing[5]),
                missing=int(existing[6]),
                issues=int(existing[7]),
            )
        event_owner = self._connection.execute(
            "SELECT idempotency_key FROM memory_source_syncs WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if event_owner is not None:
            raise MemorySyncConflictError(event_id)

        current_locators = {note.source_path for note in notes}
        synchronized: list[ProductMemoryRecord] = []
        created = 0
        revised = 0
        unchanged = 0
        missing = 0
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
                is_new = True
            else:
                is_new = False

            stored_row = self._connection.execute(
                "SELECT record_json FROM memory_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
            stored_record = (
                None
                if stored_row is None
                else ProductMemoryRecord.model_validate_json(stored_row[0])
            )

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
            if is_new:
                created += 1
            elif stored_record == record:
                unchanged += 1
            else:
                revised += 1
            self._write_record_locked(record)
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
        missing_bindings = self._connection.execute(
            """
            SELECT source_locator, record_id
            FROM memory_source_bindings
            WHERE source_key = ?
            """,
            (source_key,),
        ).fetchall()
        for source_locator, record_id in missing_bindings:
            if source_locator in current_locators:
                continue
            encoded_row = self._connection.execute(
                "SELECT record_json FROM memory_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
            if encoded_row is None:
                continue
            stored = ProductMemoryRecord.model_validate_json(encoded_row[0])
            if stored.source_status != "missing":
                self._write_record_locked(stored.model_copy(update={"source_status": "missing"}))
                missing += 1
        self._connection.execute(
            """
            INSERT INTO memory_source_syncs (
                event_id, idempotency_key, source_key, snapshot_hash,
                created_count, revised_count, unchanged_count, missing_count, issue_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                idempotency_key,
                source_key,
                snapshot_hash,
                created,
                revised,
                unchanged,
                missing,
                issue_count,
            ),
        )
        return MemorySourceSyncResult(
            records=tuple(synchronized),
            created=created,
            revised=revised,
            unchanged=unchanged,
            missing=missing,
            issues=issue_count,
        )

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

    def get_revision(
        self, record_id: str, content_hash: str
    ) -> ProductMemoryRecord | None:
        """Return one exact stored revision with its governed review state."""

        rows = self._connection.execute(
            """
            SELECT record_json
            FROM memory_record_revisions
            WHERE record_id = ?
            ORDER BY sequence DESC
            """,
            (record_id,),
        )
        for (encoded,) in rows:
            record = ProductMemoryRecord.model_validate_json(encoded)
            if record.content_hash == content_hash:
                return self._with_review_state(record_id, encoded)
        return None

    def latest_review(
        self, record_id: str, content_hash: str
    ) -> MemoryReviewRecord | None:
        """Return the latest review decision bound to one exact revision."""

        row = self._connection.execute(
            """
            SELECT event_id, record_id, content_hash, decision, replacement_record_id
            FROM memory_reviews
            WHERE record_id = ? AND content_hash = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (record_id, content_hash),
        ).fetchone()
        if row is None:
            return None
        return MemoryReviewRecord(
            event_id=str(row[0]),
            record_id=str(row[1]),
            content_hash=str(row[2]),
            decision=MemoryAuthorityState(row[3]),
            replacement_record_id=None if row[4] is None else str(row[4]),
        )

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
