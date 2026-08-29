"""Governed file-import contracts."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator

from oscillink_agent.domain.capabilities import PortableTarget, ScopeId
from oscillink_agent.domain.events import (
    Actor,
    ContractDatetime,
    Digest,
    EventId,
    FrozenModel,
    JsonInteger,
    RunId,
    SchemaVersion,
    Sensitivity,
    SessionId,
    TaskId,
    TrustClass,
)

ImportExtension = Annotated[str, Field(pattern=r"^\.[a-z0-9]+$", max_length=32)]
PortableFileName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        pattern=r"^[^/\\\x00-\x1f]+$",
    ),
]
MediaType = Annotated[
    str,
    Field(
        min_length=3,
        max_length=127,
        pattern=r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$",
    ),
]


class FileImportSelection(FrozenModel):
    """One explicit file selection within a trusted configured scope."""

    schema_version: SchemaVersion
    scope_id: ScopeId
    target: PortableTarget


class FileImportPolicy(FrozenModel):
    """Bounded import limits supplied by trusted local configuration."""

    schema_version: SchemaVersion
    max_bytes: Annotated[JsonInteger, Field(ge=1, le=1_099_511_627_776)]
    chunk_bytes: Annotated[JsonInteger, Field(ge=1, le=8_388_608)]
    allowed_extensions: Annotated[tuple[ImportExtension, ...], Field(min_length=1, max_length=64)]

    @field_validator("allowed_extensions")
    @classmethod
    def require_unique_extensions(
        cls, value: tuple[ImportExtension, ...]
    ) -> tuple[ImportExtension, ...]:
        if len(value) != len(set(value)):
            raise ValueError("allowed import extensions must be unique")
        return value


class FileImportAuditContext(FrozenModel):
    """Caller-supplied canonical identity and timing for one import attempt."""

    schema_version: SchemaVersion
    event_id: EventId
    session_id: SessionId
    run_id: RunId
    task_id: TaskId
    actor: Actor
    observed_at: ContractDatetime
    recorded_at: ContractDatetime
    trust_class: TrustClass
    sensitivity: Sensitivity


class ImportedArtifact(FrozenModel):
    """Sanitized result of publishing one explicitly selected file."""

    schema_version: SchemaVersion
    artifact_ref: Digest
    source_scope_id: ScopeId
    source_name: PortableFileName
    media_type: MediaType
    logical_bytes: Annotated[JsonInteger, Field(ge=0)]
    unique_physical_bytes: Annotated[JsonInteger, Field(ge=0)]
    deduplicated: bool
