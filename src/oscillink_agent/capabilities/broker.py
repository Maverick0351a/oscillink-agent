"""Durable, single-use broker for the first bounded read-only capability."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from oscillink_agent.capabilities.contracts import FileReadObservation
from oscillink_agent.domain.capabilities import CapabilityGrant, GrantId
from oscillink_agent.domain.events import (
    ActorId,
    ActorType,
    Event,
    EventType,
    TrustClass,
)
from oscillink_agent.storage.migrations import (
    record_current_schema,
    require_compatible_schema,
)
from oscillink_agent.storage.sqlite import LedgerCorruptionError, SQLiteEventStore


class CapabilityDeniedError(PermissionError):
    """A stable denial code without leaking host paths or file contents."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CapabilityBroker:
    """Resolve trusted grants and atomically consume one exact file-read use."""

    def __init__(
        self,
        *,
        data_root: Path,
        scope_roots: Mapping[str, Path],
    ) -> None:
        self._data_root = data_root
        self._database = data_root / "capabilities.sqlite3"
        self._scope_roots = dict(scope_roots)

    def _connect(self) -> sqlite3.Connection:
        self._database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database, timeout=30, isolation_level=None)
        try:
            require_compatible_schema(
                connection,
                store_name="capabilities",
                current_version=1,
            )
        except BaseException:
            connection.close()
            raise
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS capability_grants (
                id TEXT PRIMARY KEY,
                document_json TEXT NOT NULL,
                consumed_at TEXT
            )
            """
        )
        record_current_schema(connection, current_version=1)
        return connection

    @staticmethod
    def _validate_authorization(grant: CapabilityGrant, event: Event) -> None:
        payload = event.payload
        if (
            event.id != grant.authorization_event_id
            or event.actor.id != grant.issued_by
            or event.actor.type is not ActorType.HUMAN
            or event.event_type is not EventType.APPROVAL
            or event.trust_class is not TrustClass.HUMAN_VERIFIED
            or payload.get("grant_id") != grant.id
            or payload.get("decision") != "approved"
            or event.observed_at != grant.issued_at
        ):
            raise CapabilityDeniedError("authorization_invalid")

    def register_grant(self, grant: CapabilityGrant) -> None:
        """Persist a grant only when bound to its exact human approval event."""

        event_store = SQLiteEventStore(self._data_root / "events.sqlite3")
        try:
            event = event_store.get(grant.authorization_event_id)
        except LedgerCorruptionError as error:
            raise CapabilityDeniedError("authorization_invalid") from error
        finally:
            event_store.close()
        if event is None:
            raise CapabilityDeniedError("authorization_invalid")
        self._validate_authorization(grant, event)
        if grant.resource.scope_id not in self._scope_roots:
            raise CapabilityDeniedError("scope_unknown")
        document = grant.model_dump_json()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT document_json FROM capability_grants WHERE id = ?",
                (grant.id,),
            ).fetchone()
            if row is not None:
                if row[0] != document:
                    raise CapabilityDeniedError("grant_conflict")
                connection.commit()
                return
            connection.execute(
                "INSERT INTO capability_grants (id, document_json, consumed_at) "
                "VALUES (?, ?, NULL)",
                (grant.id, document),
            )
            connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _validate_now(now: datetime) -> datetime:
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise CapabilityDeniedError("invalid_clock")
        return now.astimezone(UTC)

    def _claim_grant(
        self,
        grant_id: GrantId,
        *,
        subject_actor_id: ActorId,
        now: datetime,
    ) -> CapabilityGrant:
        current_time = self._validate_now(now)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT document_json, consumed_at FROM capability_grants WHERE id = ?",
                (grant_id,),
            ).fetchone()
            if row is None:
                raise CapabilityDeniedError("grant_not_found")
            try:
                grant = CapabilityGrant.model_validate_json(row[0])
            except ValidationError as error:
                raise CapabilityDeniedError("grant_corrupt") from error
            if row[1] is not None:
                raise CapabilityDeniedError("grant_consumed")
            if grant.subject_actor_id != subject_actor_id:
                raise CapabilityDeniedError("subject_mismatch")
            issued_at = grant.issued_at.astimezone(UTC)
            if current_time < issued_at:
                raise CapabilityDeniedError("grant_not_yet_valid")
            if current_time >= issued_at + timedelta(seconds=grant.valid_for_seconds):
                raise CapabilityDeniedError("grant_expired")
            if grant.capability != "file.read" or grant.max_uses != 1:
                raise CapabilityDeniedError("capability_mismatch")
            if grant.constraints.network_allowed is not False:
                raise CapabilityDeniedError("network_forbidden")
            if grant.resource.scope_id not in self._scope_roots:
                raise CapabilityDeniedError("scope_unknown")
            allowed_extensions = {
                extension.casefold() for extension in grant.constraints.allowed_extensions
            }
            if Path(grant.resource.target).suffix.casefold() not in allowed_extensions:
                raise CapabilityDeniedError("extension_denied")
            connection.execute(
                "UPDATE capability_grants SET consumed_at = ? "
                "WHERE id = ? AND consumed_at IS NULL",
                (current_time.isoformat(), grant.id),
            )
            connection.commit()
            return grant
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def execute_file_read(
        self,
        grant_id: GrantId,
        *,
        subject_actor_id: ActorId,
        now: datetime,
    ) -> FileReadObservation:
        """Consume one exact grant and return bounded UTF-8 as untrusted data."""

        grant = self._claim_grant(
            grant_id,
            subject_actor_id=subject_actor_id,
            now=now,
        )
        configured_root = self._scope_roots[grant.resource.scope_id]
        try:
            root = configured_root.resolve(strict=True)
        except OSError as error:
            raise CapabilityDeniedError("scope_unavailable") from error
        if not root.is_dir():
            raise CapabilityDeniedError("scope_unavailable")
        selected = root.joinpath(*grant.resource.target.split("/"))
        try:
            resolved = selected.resolve(strict=True)
        except OSError as error:
            raise CapabilityDeniedError("file_unavailable") from error
        if not resolved.is_relative_to(root):
            raise CapabilityDeniedError("scope_escape")
        if not resolved.is_file():
            raise CapabilityDeniedError("file_unavailable")
        try:
            before = resolved.stat()
        except OSError as error:
            raise CapabilityDeniedError("file_unavailable") from error
        if before.st_size > grant.constraints.max_bytes:
            raise CapabilityDeniedError("size_exceeded")
        try:
            with resolved.open("rb") as stream:
                content_bytes = stream.read(grant.constraints.max_bytes + 1)
                after_descriptor = os.fstat(stream.fileno())
            after_path = resolved.stat()
        except OSError as error:
            raise CapabilityDeniedError("file_unavailable") from error
        if len(content_bytes) > grant.constraints.max_bytes:
            raise CapabilityDeniedError("size_exceeded")
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
        descriptor_identity = (
            after_descriptor.st_dev,
            after_descriptor.st_ino,
            after_descriptor.st_size,
            after_descriptor.st_mtime_ns,
        )
        path_identity = (
            after_path.st_dev,
            after_path.st_ino,
            after_path.st_size,
            after_path.st_mtime_ns,
        )
        if before_identity != descriptor_identity or descriptor_identity != path_identity:
            raise CapabilityDeniedError("file_changed")
        try:
            content = content_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise CapabilityDeniedError("encoding_denied") from error
        return FileReadObservation(
            schema_version=1,
            grant_id=grant.id,
            scope_id=grant.resource.scope_id,
            target=grant.resource.target,
            byte_count=len(content_bytes),
            content_hash="sha256:" + hashlib.sha256(content_bytes).hexdigest(),
            content=content,
            trust_class="external_untrusted",
            network_used=False,
        )
