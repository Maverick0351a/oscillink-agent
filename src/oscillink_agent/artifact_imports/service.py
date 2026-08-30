"""Governed artifact-import orchestration and durable replay."""

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException

from oscillink_agent.artifact_imports.contracts import (
    ArtifactImportRequest,
    ArtifactImportResponse,
    ArtifactImportScopeProjection,
    ArtifactImportSourceCollection,
    ArtifactImportTargetProjection,
    CandidateArtifactAssociation,
    ImportedArtifactProjection,
    UnattachedArtifactAssociation,
)
from oscillink_agent.domain.events import (
    Actor,
    ActorType,
    Event,
    EventType,
    Sensitivity,
    TrustClass,
    canonical_payload_hash,
)
from oscillink_agent.domain.imports import (
    FileImportAuditContext,
    FileImportPolicy,
    FileImportSelection,
)
from oscillink_agent.memory.repository import SQLiteMemoryRepository
from oscillink_agent.memory.service import load_memory_index
from oscillink_agent.storage.artifacts import LocalArtifactStore
from oscillink_agent.storage.imports import (
    FileImportError,
    GovernedFileImporter,
    ImportExtensionNotAllowedError,
    ImportPathEscapeError,
    ImportScopeNotFoundError,
    ImportSourceTooLargeError,
    ImportSourceUnavailableError,
)
from oscillink_agent.storage.sqlite import SQLiteEventStore

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_IMPORT_POLICY = FileImportPolicy.model_validate(
    {
        "schema_version": 1,
        "max_bytes": 256 * 1024 * 1024,
        "chunk_bytes": 1024 * 1024,
        "allowed_extensions": (".csv", ".json", ".jsonl", ".md", ".parquet", ".txt"),
    }
)
_IMPORT_HTTP_ERRORS: tuple[tuple[type[FileImportError], int, str], ...] = (
    (ImportScopeNotFoundError, 404, "source_scope_not_found"),
    (ImportPathEscapeError, 422, "source_path_rejected"),
    (ImportExtensionNotAllowedError, 415, "extension_not_allowed"),
    (ImportSourceTooLargeError, 413, "source_too_large"),
    (ImportSourceUnavailableError, 409, "source_unavailable"),
)
_IMPORT_REPLAY_ERRORS: dict[str, tuple[int, str]] = {
    "scope_unavailable": (404, "source_scope_not_found"),
    "path_escape": (422, "source_path_rejected"),
    "extension_not_allowed": (415, "extension_not_allowed"),
    "source_too_large": (413, "source_too_large"),
    "source_unavailable": (409, "source_unavailable"),
}

_MAX_EXPOSED_TARGETS_PER_SCOPE = 512


def list_import_sources(
    import_scopes: Mapping[str, Path],
) -> ArtifactImportSourceCollection:
    """Enumerate bounded portable choices without exposing configured host roots."""

    scopes: list[ArtifactImportScopeProjection] = []
    for scope_id, root in sorted(import_scopes.items()):
        if not root.is_dir():
            scopes.append(
                ArtifactImportScopeProjection(
                    scope_id=scope_id,
                    state="unavailable",
                    targets=(),
                )
            )
            continue
        resolved_root = root.resolve()
        targets: list[ArtifactImportTargetProjection] = []
        for candidate in sorted(root.rglob("*")):
            if len(targets) >= _MAX_EXPOSED_TARGETS_PER_SCOPE:
                break
            if candidate.is_symlink() or not candidate.is_file():
                continue
            if candidate.suffix.lower() not in _IMPORT_POLICY.allowed_extensions:
                continue
            try:
                resolved_candidate = candidate.resolve(strict=True)
                relative = resolved_candidate.relative_to(resolved_root)
                logical_bytes = resolved_candidate.stat().st_size
            except (OSError, ValueError):
                continue
            targets.append(
                ArtifactImportTargetProjection(
                    target=relative.as_posix(),
                    source_name=relative.name,
                    logical_bytes=logical_bytes,
                )
            )
        scopes.append(
            ArtifactImportScopeProjection(
                scope_id=scope_id,
                state="configured",
                targets=tuple(targets),
            )
        )
    return ArtifactImportSourceCollection(count=len(scopes), scopes=tuple(scopes))


def _derived_event_id(request_id: str, purpose: str) -> str:
    digest = hashlib.sha256(f"{request_id}:{purpose}".encode()).digest()
    value = int.from_bytes(digest[:17], "big") >> 6
    token = ""
    for _ in range(26):
        token = _CROCKFORD[value & 31] + token
        value >>= 5
    return f"evt_{token}"


def _association_idempotency_key(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"association-{digest}"


def _import_event_matches_request(event: Event, request: ArtifactImportRequest) -> bool:
    payload = event.payload
    expected_name = request.target.rsplit("/", maxsplit=1)[-1]
    expected_selection_hash = canonical_payload_hash(
        {"scope_id": request.scope_id, "target": request.target}
    )
    return not (
        event.id != request.request_id
        or event.observed_at != request.observed_at
        or payload.get("operation") != "artifact_import"
        or payload.get("source_scope_id") != request.scope_id
        or payload.get("source_name") != expected_name
        or payload.get("selection_hash") != expected_selection_hash
    )


def _replayed_artifact(
    event: Event,
    request: ArtifactImportRequest,
) -> ImportedArtifactProjection:
    payload = event.payload
    if (
        not _import_event_matches_request(event, request)
        or payload.get("status") != "imported"
        or len(event.artifact_refs) != 1
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_conflict",
                "message": "Idempotency key belongs to another import request.",
            },
        )
    return ImportedArtifactProjection(
        artifact_ref=event.artifact_refs[0],
        source_scope_id=payload["source_scope_id"],
        source_name=payload["source_name"],
        media_type=payload["media_type"],
        logical_bytes=payload["logical_bytes"],
        unique_physical_bytes=payload["unique_physical_bytes"],
        deduplicated=payload["deduplicated"],
    )


def import_artifact(
    *,
    data_root: Path,
    vault_root: Path | None,
    import_scopes: Mapping[str, Path],
    request: ArtifactImportRequest,
    idempotency_key: str,
    actor_id: str = "human_local_user",
) -> ArtifactImportResponse:
    if not import_scopes:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "import_unavailable",
                "message": "No local import scope is configured.",
            },
        )
    target_record_id: str | None = None
    if request.target_record_id is not None:
        if request.target_record_id.startswith("mem_"):
            memory_database = data_root / "memory.sqlite3"
            if memory_database.is_file():
                repository = SQLiteMemoryRepository(memory_database)
                try:
                    target_record = repository.get(request.target_record_id)
                finally:
                    repository.close()
                if target_record is not None:
                    target_record_id = target_record.id
        else:
            index, _reason = load_memory_index(vault_root)
            if index is None:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "memory_unavailable",
                        "message": "Reviewed memory is unavailable for association.",
                    },
                )
            target_note = next(
                (note for note in index.notes if note.id == request.target_record_id),
                None,
            )
            if target_note is not None:
                target_record_id = target_note.id
        if target_record_id is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "node_not_found", "message": "Memory node was not found."},
            )
    artifacts = LocalArtifactStore(data_root / "artifacts")
    events = SQLiteEventStore(data_root / "events.sqlite3", artifacts=artifacts)
    try:
        existing = events.get_by_idempotency(idempotency_key)
        if existing is not None:
            if not _import_event_matches_request(existing, request):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "idempotency_conflict",
                        "message": "Idempotency key belongs to another import request.",
                    },
                )
            if existing.payload.get("status") == "failed":
                failure = _IMPORT_REPLAY_ERRORS.get(str(existing.payload.get("error_code")))
                if failure is None:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "idempotency_conflict",
                            "message": "Idempotency key belongs to an unreadable import outcome.",
                        },
                    )
                failure_status, failure_code = failure
                raise HTTPException(
                    status_code=failure_status,
                    detail={
                        "code": failure_code,
                        "message": "Selected file could not be imported.",
                    },
                )
            artifact = _replayed_artifact(existing, request)
            candidate_event = events.get_by_idempotency(
                _association_idempotency_key(idempotency_key)
            )
            replay_association: (
                UnattachedArtifactAssociation | CandidateArtifactAssociation
            ) = UnattachedArtifactAssociation()
            if target_record_id is None:
                if candidate_event is not None:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "idempotency_conflict",
                            "message": "Idempotency key belongs to another import request.",
                        },
                    )
            else:
                candidate_event_id = _derived_event_id(request.request_id, "association")
                if (
                    candidate_event is None
                    or candidate_event.id != candidate_event_id
                    or candidate_event.event_type != EventType.MEMORY_PROPOSAL
                    or candidate_event.causal_parent_ids != (request.request_id,)
                    or candidate_event.artifact_refs != (artifact.artifact_ref,)
                    or candidate_event.payload.get("target_record_id") != target_record_id
                    or candidate_event.payload.get("operation") != "artifact_association"
                    or candidate_event.payload.get("status") != "pending_review"
                ):
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "idempotency_conflict",
                            "message": (
                                "Idempotency key belongs to an incomplete or different "
                                "association request."
                            ),
                        },
                    )
                replay_association = CandidateArtifactAssociation(
                    target_record_id=target_record_id,
                    event_id=candidate_event_id,
                )
            return ArtifactImportResponse(
                event_id=request.request_id,
                artifact=artifact,
                association=replay_association,
            )
        importer = GovernedFileImporter(
            artifacts=artifacts,
            scopes=import_scopes,
            policy=_IMPORT_POLICY,
        )
        token = request.request_id.removeprefix("evt_")
        audit = FileImportAuditContext(
            schema_version=1,
            event_id=request.request_id,
            session_id=f"ses_{token}",
            run_id=f"run_{token}",
            task_id=f"tsk_{token}",
            actor=Actor(id=actor_id, type=ActorType.HUMAN),
            observed_at=request.observed_at,
            recorded_at=datetime.now(tz=UTC),
            trust_class=TrustClass.EXTERNAL_UNTRUSTED,
            sensitivity=Sensitivity.PRIVATE,
        )
        try:
            result = importer.import_and_record(
                FileImportSelection(
                    schema_version=1,
                    scope_id=request.scope_id,
                    target=request.target,
                ),
                audit=audit,
                events=events,
                idempotency_key=idempotency_key,
            )
        except FileImportError as error:
            error_status, error_code = next(
                (status_code, code)
                for error_type, status_code, code in _IMPORT_HTTP_ERRORS
                if isinstance(error, error_type)
            )
            raise HTTPException(
                status_code=error_status,
                detail={
                    "code": error_code,
                    "message": "Selected file could not be imported.",
                },
            ) from None
        association: UnattachedArtifactAssociation | CandidateArtifactAssociation
        if target_record_id is None:
            association = UnattachedArtifactAssociation()
        else:
            candidate_event_id = _derived_event_id(request.request_id, "association")
            candidate_payload = {
                "operation": "artifact_association",
                "status": "pending_review",
                "target_record_id": target_record_id,
            }
            events.append(
                Event.model_validate(
                    {
                        "id": candidate_event_id,
                        "schema_version": 1,
                        "session_id": audit.session_id,
                        "run_id": audit.run_id,
                        "task_id": audit.task_id,
                        "actor": audit.actor,
                        "event_type": EventType.MEMORY_PROPOSAL,
                        "observed_at": audit.observed_at,
                        "recorded_at": audit.recorded_at,
                        "payload_hash": canonical_payload_hash(candidate_payload),
                        "artifact_refs": (result.artifact_ref,),
                        "causal_parent_ids": (request.request_id,),
                        "trust_class": audit.trust_class,
                        "sensitivity": audit.sensitivity,
                        "payload": candidate_payload,
                    }
                ),
                idempotency_key=_association_idempotency_key(idempotency_key),
            )
            association = CandidateArtifactAssociation(
                target_record_id=target_record_id,
                event_id=candidate_event_id,
            )
    finally:
        events.close()
    return ArtifactImportResponse(
        event_id=request.request_id,
        artifact=ImportedArtifactProjection(
            artifact_ref=result.artifact_ref,
            source_scope_id=result.source_scope_id,
            source_name=result.source_name,
            media_type=result.media_type,
            logical_bytes=result.logical_bytes,
            unique_physical_bytes=result.unique_physical_bytes,
            deduplicated=result.deduplicated,
        ),
        association=association,
    )
