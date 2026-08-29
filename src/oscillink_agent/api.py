"""Local HTTP API for Oscillink Agent."""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, BeforeValidator, ConfigDict

from oscillink_agent import __version__
from oscillink_agent.domain.capabilities import PortableTarget, ScopeId
from oscillink_agent.domain.events import (
    Actor,
    ActorType,
    Event,
    EventId,
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
from oscillink_agent.memory.obsidian import (
    DocumentId,
    MemoryCategory,
    MemoryDomain,
    ReviewedObsidianIndex,
    build_reviewed_obsidian_index,
)
from oscillink_agent.memory.projection import (
    MemoryIndexProjection,
    MemoryNodeCollection,
    MemoryNodeDetailResponse,
    MemoryUnavailableReason,
    project_index,
    project_node,
    project_nodes,
    unavailable_index,
    unavailable_nodes,
)
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

ComponentState = Literal["not_initialized", "ready", "error"]
FeatureState = Literal["planned", "preview", "ready"]
_HEX_DIRECTORY = re.compile(r"[0-9a-f]{2}")
_HEX_OBJECT = re.compile(r"[0-9a-f]{62}")
_IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"
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


def _parse_transport_datetime(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("timestamp must be an RFC 3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp must be a valid RFC 3339 string") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed


TransportDatetime = Annotated[datetime, BeforeValidator(_parse_transport_datetime)]


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


class StorageComponentStatus(BaseModel):
    """Read-only status for one durable storage component."""

    model_config = ConfigDict(frozen=True)

    state: ComponentState
    record_count: int


class ServiceStatus(BaseModel):
    """Truthful readiness snapshot consumed by the local frontend."""

    model_config = ConfigDict(frozen=True)

    service: Literal["oscillink-agent"] = "oscillink-agent"
    version: str
    api_state: Literal["online"] = "online"
    storage: dict[str, StorageComponentStatus]
    features: dict[str, FeatureState]


class ArtifactImportRequest(BaseModel):
    """Strict browser-safe request for one configured scoped source."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    request_id: EventId
    observed_at: TransportDatetime
    scope_id: ScopeId
    target: PortableTarget
    target_record_id: DocumentId | None = None


class ImportedArtifactProjection(BaseModel):
    """Sanitized artifact result returned across the HTTP boundary."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    artifact_ref: str
    source_scope_id: ScopeId
    source_name: str
    media_type: str
    logical_bytes: int
    unique_physical_bytes: int
    deduplicated: bool


class UnattachedArtifactAssociation(BaseModel):
    """Honest state before a candidate stable-record association exists."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    state: Literal["unattached"] = "unattached"


class CandidateArtifactAssociation(BaseModel):
    """A non-canonical artifact relationship awaiting external review."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    state: Literal["candidate"] = "candidate"
    review_state: Literal["pending_review"] = "pending_review"
    target_record_id: DocumentId
    event_id: EventId


class ArtifactImportResponse(BaseModel):
    """Typed successful import response."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    state: Literal["imported"] = "imported"
    event_id: EventId
    artifact: ImportedArtifactProjection
    association: UnattachedArtifactAssociation | CandidateArtifactAssociation


def _import_event_matches_request(event: Event, request: ArtifactImportRequest) -> bool:
    payload = event.payload
    expected_name = request.target.rsplit("/", maxsplit=1)[-1]
    expected_selection_hash = canonical_payload_hash(
        {
            "scope_id": request.scope_id,
            "target": request.target,
        }
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


def _default_data_root() -> Path:
    configured = os.environ.get("OSCILLINK_AGENT_DATA_DIR")
    return Path(configured) if configured else Path.home() / ".oscillink-agent"


def _default_vault_root() -> Path | None:
    configured = os.environ.get("OSCILLINK_AGENT_VAULT_DIR")
    return Path(configured) if configured else None


def _default_import_scopes() -> dict[str, Path]:
    configured = os.environ.get("OSCILLINK_AGENT_IMPORT_DIR")
    return {"user_selection": Path(configured)} if configured else {}


def _inspect_ledger(database: Path) -> StorageComponentStatus:
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


def _inspect_artifacts(root: Path) -> StorageComponentStatus:
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


def _load_memory_index(
    vault_root: Path | None,
) -> tuple[ReviewedObsidianIndex | None, MemoryUnavailableReason | None]:
    if vault_root is None:
        return None, MemoryUnavailableReason.VAULT_NOT_CONFIGURED
    if not vault_root.is_dir():
        return None, MemoryUnavailableReason.VAULT_NOT_FOUND
    try:
        return build_reviewed_obsidian_index(vault_root), None
    except (OSError, ValueError):
        return None, MemoryUnavailableReason.INDEX_BUILD_FAILED


def create_app(
    *,
    data_root: Path | None = None,
    vault_root: Path | None = None,
    import_scopes: Mapping[str, Path] | None = None,
) -> FastAPI:
    """Create an API without initializing or mutating durable storage."""

    root = data_root if data_root is not None else _default_data_root()
    configured_import_scopes = dict(import_scopes or {})
    application = FastAPI(title="Oscillink Agent API", version=__version__)

    @application.get("/api/v1/status", response_model=ServiceStatus)
    def status() -> ServiceStatus:
        return ServiceStatus(
            version=__version__,
            storage={
                "ledger": _inspect_ledger(root / "events.sqlite3"),
                "artifacts": _inspect_artifacts(root / "artifacts"),
            },
            features={
                "chat": "planned",
                "memory_lattice": "planned",
                "appearance": "preview",
            },
        )

    @application.get("/api/v1/memory/index", response_model=MemoryIndexProjection)
    def memory_index() -> MemoryIndexProjection:
        index, reason = _load_memory_index(vault_root)
        if index is None:
            assert reason is not None
            return unavailable_index(reason)
        return project_index(index)

    @application.get("/api/v1/memory/nodes", response_model=MemoryNodeCollection)
    def memory_nodes(
        category: MemoryCategory | None = None,
        domain: MemoryDomain | None = None,
    ) -> MemoryNodeCollection:
        index, reason = _load_memory_index(vault_root)
        if index is None:
            assert reason is not None
            return unavailable_nodes(reason, category=category, domain=domain)
        return project_nodes(index, category=category, domain=domain)

    @application.get(
        "/api/v1/memory/nodes/{node_id}",
        response_model=MemoryNodeDetailResponse,
    )
    def memory_node(node_id: DocumentId) -> MemoryNodeDetailResponse:
        index, reason = _load_memory_index(vault_root)
        if index is None:
            message = (
                "Reviewed memory is not configured."
                if reason is MemoryUnavailableReason.VAULT_NOT_CONFIGURED
                else "Reviewed memory is unavailable."
            )
            raise HTTPException(
                status_code=503,
                detail={"code": "memory_unavailable", "message": message},
            )
        note = next((candidate for candidate in index.notes if candidate.id == node_id), None)
        if note is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "node_not_found",
                    "message": "Memory node was not found.",
                },
            )
        return project_node(note)

    @application.post(
        "/api/v1/artifact-imports",
        response_model=ArtifactImportResponse,
        status_code=http_status.HTTP_201_CREATED,
    )
    def import_artifact(
        request: ArtifactImportRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=128,
                pattern=_IDEMPOTENCY_KEY_PATTERN,
            ),
        ],
    ) -> ArtifactImportResponse:
        if not configured_import_scopes:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "import_unavailable",
                    "message": "No local import scope is configured.",
                },
            )
        target_note = None
        if request.target_record_id is not None:
            index, _reason = _load_memory_index(vault_root)
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
            if target_note is None:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "node_not_found",
                        "message": "Memory node was not found.",
                    },
                )
        artifacts = LocalArtifactStore(root / "artifacts")
        events = SQLiteEventStore(root / "events.sqlite3", artifacts=artifacts)
        try:
            existing = events.get_by_idempotency(idempotency_key)
            if existing is not None:
                if not _import_event_matches_request(existing, request):
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "idempotency_conflict",
                            "message": (
                                "Idempotency key belongs to another import request."
                            ),
                        },
                    )
                if existing.payload.get("status") == "failed":
                    failure = _IMPORT_REPLAY_ERRORS.get(
                        str(existing.payload.get("error_code"))
                    )
                    if failure is None:
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "code": "idempotency_conflict",
                                "message": (
                                    "Idempotency key belongs to an unreadable import "
                                    "outcome."
                                ),
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
                replay_association: (
                    UnattachedArtifactAssociation | CandidateArtifactAssociation
                ) = UnattachedArtifactAssociation()
                if target_note is not None:
                    candidate_event_id = _derived_event_id(
                        request.request_id,
                        "association",
                    )
                    candidate_event = events.get_by_idempotency(
                        _association_idempotency_key(idempotency_key)
                    )
                    if (
                        candidate_event is None
                        or candidate_event.id != candidate_event_id
                        or candidate_event.event_type != EventType.MEMORY_PROPOSAL
                        or candidate_event.causal_parent_ids != (request.request_id,)
                        or candidate_event.artifact_refs != (artifact.artifact_ref,)
                        or candidate_event.payload.get("target_record_id")
                        != target_note.id
                        or candidate_event.payload.get("operation")
                        != "artifact_association"
                        or candidate_event.payload.get("status") != "pending_review"
                    ):
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "code": "idempotency_conflict",
                                "message": (
                                    "Idempotency key belongs to an incomplete or "
                                    "different association request."
                                ),
                            },
                        )
                    replay_association = CandidateArtifactAssociation(
                        target_record_id=target_note.id,
                        event_id=candidate_event_id,
                    )
                return ArtifactImportResponse(
                    event_id=request.request_id,
                    artifact=artifact,
                    association=replay_association,
                )
            importer = GovernedFileImporter(
                artifacts=artifacts,
                scopes=configured_import_scopes,
                policy=_IMPORT_POLICY,
            )
            token = request.request_id.removeprefix("evt_")
            audit = FileImportAuditContext(
                schema_version=1,
                event_id=request.request_id,
                session_id=f"ses_{token}",
                run_id=f"run_{token}",
                task_id=f"tsk_{token}",
                actor=Actor(id="human_local_user", type=ActorType.HUMAN),
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
            if target_note is None:
                association = UnattachedArtifactAssociation()
            else:
                candidate_event_id = _derived_event_id(request.request_id, "association")
                candidate_payload = {
                    "operation": "artifact_association",
                    "status": "pending_review",
                    "target_record_id": target_note.id,
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
                    target_record_id=target_note.id,
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

    return application


app = create_app(
    vault_root=_default_vault_root(),
    import_scopes=_default_import_scopes(),
)
