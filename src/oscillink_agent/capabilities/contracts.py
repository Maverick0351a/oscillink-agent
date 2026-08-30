"""Typed observations emitted by bounded capabilities."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from oscillink_agent.domain.capabilities import GrantId, PortableTarget, ScopeId
from oscillink_agent.domain.events import (
    Digest,
    EventId,
    ExactFalse,
    FrozenModel,
    JsonInteger,
    RunId,
    SchemaVersion,
    SessionId,
)


class FileReadObservation(FrozenModel):
    schema_version: SchemaVersion
    grant_id: GrantId
    scope_id: ScopeId
    target: PortableTarget
    byte_count: Annotated[JsonInteger, Field(ge=0, le=1_048_576)]
    content_hash: Digest
    content: Annotated[str, Field(max_length=1_048_576)]
    trust_class: Literal["external_untrusted"]
    network_used: ExactFalse


class CapabilityDecisionRequest(BaseModel):
    """One server-bound human decision; callers cannot submit grant objects."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    request_id: EventId
    decision: Literal["approved", "denied"]


class CapabilityDecisionResponse(BaseModel):
    """A terminal denied decision without exposing infrastructure details."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    state: Literal["denied"] = "denied"
    session_id: SessionId
    run_id: RunId
    tool_request_event_id: EventId
