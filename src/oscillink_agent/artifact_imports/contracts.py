"""Transport contracts for governed artifact imports."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from oscillink_agent.domain.capabilities import PortableTarget, ScopeId
from oscillink_agent.domain.events import EventId
from oscillink_agent.memory.contracts import MemoryNodeId


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


class ArtifactImportTargetProjection(BaseModel):
    """One server-enumerated portable target without a host path."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    target: PortableTarget
    source_name: str
    logical_bytes: Annotated[int, Field(ge=0)]


class ArtifactImportScopeProjection(BaseModel):
    """Opaque configured scope and its currently selectable targets."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    scope_id: ScopeId
    state: Literal["configured", "unavailable"]
    targets: tuple[ArtifactImportTargetProjection, ...]


class ArtifactImportSourceCollection(BaseModel):
    """Browser-safe configured import choices."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    count: Annotated[int, Field(ge=0)]
    scopes: tuple[ArtifactImportScopeProjection, ...]


class ArtifactImportRequest(BaseModel):
    """Strict browser-safe request for one configured scoped source."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    request_id: EventId
    observed_at: TransportDatetime
    scope_id: ScopeId
    target: PortableTarget
    target_record_id: MemoryNodeId | None = None


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
    target_record_id: MemoryNodeId
    event_id: EventId


class ArtifactImportResponse(BaseModel):
    """Typed successful import response."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    state: Literal["imported"] = "imported"
    event_id: EventId
    artifact: ImportedArtifactProjection
    association: UnattachedArtifactAssociation | CandidateArtifactAssociation
