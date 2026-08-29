"""Trusted local adapter for governed file imports."""

from __future__ import annotations

import mimetypes
import os
import stat
from collections.abc import Mapping
from pathlib import Path

from oscillink_agent.domain.events import Event, EventType, canonical_payload_hash
from oscillink_agent.domain.imports import (
    FileImportAuditContext,
    FileImportPolicy,
    FileImportSelection,
    ImportedArtifact,
)
from oscillink_agent.storage.interfaces import ArtifactStore, ArtifactStoreError, EventStore


class FileImportError(Exception):
    """A selected file could not be safely imported."""


class ImportScopeNotFoundError(FileImportError):
    """The selected opaque source scope is not configured."""


class ImportSourceUnavailableError(FileImportError):
    """The selected source cannot be opened as a regular file."""


class ImportPathEscapeError(FileImportError):
    """The selected path traverses a link, reparse point, or scope boundary."""


class ImportExtensionNotAllowedError(FileImportError):
    """The selected file extension is outside the configured allowlist."""


class ImportSourceTooLargeError(FileImportError):
    """The selected source exceeds its configured byte limit."""


_FAILURE_CODES: dict[type[BaseException], str] = {
    ImportScopeNotFoundError: "scope_unavailable",
    ImportSourceUnavailableError: "source_unavailable",
    ImportPathEscapeError: "path_escape",
    ImportExtensionNotAllowedError: "extension_not_allowed",
    ImportSourceTooLargeError: "source_too_large",
    ArtifactStoreError: "artifact_store_error",
    OSError: "source_read_failed",
}


def _is_link_or_reparse(path: Path) -> bool:
    status = path.lstat()
    file_attributes = getattr(status, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(status.st_mode) or bool(file_attributes & reparse_flag)


class GovernedFileImporter:
    """Import one explicit scoped selection without exposing host paths."""

    def __init__(
        self,
        *,
        artifacts: ArtifactStore,
        scopes: Mapping[str, Path],
        policy: FileImportPolicy,
    ) -> None:
        if type(policy) is not FileImportPolicy:
            raise TypeError("file imports require an exact FileImportPolicy")
        configured_scopes: dict[str, Path] = {}
        for scope_id, source_root in scopes.items():
            if type(scope_id) is not str or not isinstance(source_root, Path):
                raise TypeError("import scopes require string IDs and pathlib paths")
            try:
                if _is_link_or_reparse(source_root):
                    raise ImportPathEscapeError(
                        f"configured import scope contains a link or reparse point: {scope_id}"
                    )
                resolved = source_root.resolve(strict=True)
            except FileNotFoundError:
                raise ImportScopeNotFoundError(
                    f"configured import scope is unavailable: {scope_id}"
                ) from None
            if not resolved.is_dir():
                raise ImportScopeNotFoundError(
                    f"configured import scope is not a directory: {scope_id}"
                )
            configured_scopes[scope_id] = resolved
        self._artifacts = artifacts
        self._scopes = configured_scopes
        self._policy = policy

    def import_selected(self, selection: FileImportSelection) -> ImportedArtifact:
        if type(selection) is not FileImportSelection:
            raise TypeError("file import requires an exact FileImportSelection")
        source_root = self._scopes.get(selection.scope_id)
        if source_root is None:
            raise ImportScopeNotFoundError(
                f"import scope is not configured: {selection.scope_id}"
            )

        source = source_root.joinpath(*selection.target.split("/"))
        try:
            current = source_root
            for segment in selection.target.split("/"):
                current = current / segment
                if _is_link_or_reparse(current):
                    raise ImportPathEscapeError(
                        "selected import target contains a link or reparse point: "
                        f"{selection.target}"
                    )
            resolved_source = source.resolve(strict=True)
        except FileNotFoundError:
            raise ImportSourceUnavailableError(
                f"selected import target is unavailable: {selection.target}"
            ) from None
        if not resolved_source.is_relative_to(source_root):
            raise ImportPathEscapeError(
                f"selected import target escapes its configured scope: {selection.target}"
            )

        extension = resolved_source.suffix.lower()
        if extension not in self._policy.allowed_extensions:
            raise ImportExtensionNotAllowedError(
                f"selected import extension is not allowed: {extension or '<none>'}"
            )

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(resolved_source, flags)
        except OSError:
            raise ImportSourceUnavailableError(
                f"selected import target could not be opened: {selection.target}"
            ) from None
        try:
            source_status = os.fstat(descriptor)
            if not stat.S_ISREG(source_status.st_mode):
                raise ImportSourceUnavailableError(
                    f"selected import target is not a regular file: {selection.target}"
                )
            if source_status.st_size > self._policy.max_bytes:
                raise ImportSourceTooLargeError(
                    f"selected import target exceeds {self._policy.max_bytes} bytes"
                )
            with os.fdopen(descriptor, "rb") as source_file:
                descriptor = -1
                publication = self._artifacts.put_stream(
                    source_file,
                    max_bytes=self._policy.max_bytes,
                    chunk_bytes=self._policy.chunk_bytes,
                    expected_bytes=source_status.st_size,
                )
        finally:
            if descriptor >= 0:
                os.close(descriptor)

        media_type = mimetypes.guess_type(resolved_source.name, strict=True)[0]
        return ImportedArtifact.model_validate(
            {
                "schema_version": 1,
                "artifact_ref": publication.reference,
                "source_scope_id": selection.scope_id,
                "source_name": resolved_source.name,
                "media_type": media_type or "application/octet-stream",
                "logical_bytes": publication.byte_count,
                "unique_physical_bytes": (
                    0 if publication.deduplicated else publication.byte_count
                ),
                "deduplicated": publication.deduplicated,
            }
        )

    def import_and_record(
        self,
        selection: FileImportSelection,
        *,
        audit: FileImportAuditContext,
        events: EventStore,
        idempotency_key: str,
    ) -> ImportedArtifact:
        """Import one selection and append its sanitized canonical outcome event."""

        if type(audit) is not FileImportAuditContext:
            raise TypeError("audited imports require an exact FileImportAuditContext")
        try:
            result = self.import_selected(selection)
        except (FileImportError, ArtifactStoreError, OSError) as error:
            error_code = next(
                code
                for error_type, code in _FAILURE_CODES.items()
                if isinstance(error, error_type)
            )
            failure_payload: dict[str, object] = {
                "operation": "artifact_import",
                "status": "failed",
                "error_code": error_code,
                "source_scope_id": selection.scope_id,
                "source_name": selection.target.rsplit("/", maxsplit=1)[-1],
            }
            events.append(
                self._outcome_event(audit, payload=failure_payload, artifact_refs=()),
                idempotency_key=idempotency_key,
            )
            raise

        success_payload: dict[str, object] = {
            "operation": "artifact_import",
            "status": "imported",
            "source_scope_id": result.source_scope_id,
            "source_name": result.source_name,
            "media_type": result.media_type,
            "logical_bytes": result.logical_bytes,
            "unique_physical_bytes": result.unique_physical_bytes,
            "deduplicated": result.deduplicated,
        }
        events.append(
            self._outcome_event(
                audit,
                payload=success_payload,
                artifact_refs=(result.artifact_ref,),
            ),
            idempotency_key=idempotency_key,
        )
        return result

    @staticmethod
    def _outcome_event(
        audit: FileImportAuditContext,
        *,
        payload: dict[str, object],
        artifact_refs: tuple[str, ...],
    ) -> Event:
        return Event.model_validate(
            {
                "id": audit.event_id,
                "schema_version": 1,
                "session_id": audit.session_id,
                "run_id": audit.run_id,
                "task_id": audit.task_id,
                "actor": audit.actor,
                "event_type": EventType.OBSERVATION,
                "observed_at": audit.observed_at,
                "recorded_at": audit.recorded_at,
                "payload_hash": canonical_payload_hash(payload),
                "artifact_refs": artifact_refs,
                "causal_parent_ids": (),
                "trust_class": audit.trust_class,
                "sensitivity": audit.sensitivity,
                "payload": payload,
            }
        )
