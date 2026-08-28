"""Immutable execution event contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
EventId = Annotated[str, Field(pattern=r"^evt_[0-9A-HJKMNP-TV-Z]{26}$")]
SessionId = Annotated[str, Field(pattern=r"^ses_[0-9A-HJKMNP-TV-Z]{26}$")]
RunId = Annotated[str, Field(pattern=r"^run_[0-9A-HJKMNP-TV-Z]{26}$")]
TaskId = Annotated[str, Field(pattern=r"^tsk_[0-9A-HJKMNP-TV-Z]{26}$")]
ActorId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]


class FrozenModel(BaseModel):
    """Strict, assignment-frozen base for persisted contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ActorType(StrEnum):
    HUMAN = "human"
    MODEL = "model"
    TOOL = "tool"
    SYSTEM = "system"


class EventType(StrEnum):
    MESSAGE = "message"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    OBSERVATION = "observation"
    MEMORY_PROPOSAL = "memory_proposal"
    APPROVAL = "approval"
    CORRECTION = "correction"
    RETRACTION = "retraction"
    OUTCOME = "outcome"


class TrustClass(StrEnum):
    HUMAN_VERIFIED = "human_verified"
    TOOL_VERIFIED = "tool_verified"
    MODEL_GENERATED = "model_generated"
    EXTERNAL_UNTRUSTED = "external_untrusted"
    SYSTEM = "system"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    RESTRICTED = "restricted"


class Actor(FrozenModel):
    id: ActorId
    type: ActorType


class ModelIdentity(FrozenModel):
    provider: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    configuration_hash: Digest


class Event(FrozenModel):
    id: EventId
    schema_version: Literal[1]
    session_id: SessionId
    run_id: RunId
    task_id: TaskId
    actor: Actor
    event_type: EventType
    observed_at: AwareDatetime
    recorded_at: AwareDatetime
    payload_hash: Digest
    artifact_refs: tuple[Digest, ...]
    causal_parent_ids: tuple[EventId, ...]
    trust_class: TrustClass
    sensitivity: Sensitivity
    payload: dict[str, Any]
    model: ModelIdentity | None = None

    @model_validator(mode="after")
    def require_model_provenance(self) -> Event:
        if self.event_type is EventType.MODEL_CALL and self.model is None:
            raise ValueError("model_call events require model provenance")
        return self

    @property
    def observed_datetime(self) -> datetime:
        """Return the observed timestamp with a concrete datetime type."""

        return self.observed_at
