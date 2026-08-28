"""Immutable execution event contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, cast

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
EventId = Annotated[str, Field(pattern=r"^evt_[0-9A-HJKMNP-TV-Z]{26}$")]
SessionId = Annotated[str, Field(pattern=r"^ses_[0-9A-HJKMNP-TV-Z]{26}$")]
RunId = Annotated[str, Field(pattern=r"^run_[0-9A-HJKMNP-TV-Z]{26}$")]
TaskId = Annotated[str, Field(pattern=r"^tsk_[0-9A-HJKMNP-TV-Z]{26}$")]
ActorId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]


class FrozenDict(Mapping[str, Any]):
    """Tuple-backed mapping with no mutable dictionary storage."""

    __slots__ = ("_items",)
    _items: tuple[tuple[str, Any], ...]

    def __init__(self, value: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_items", tuple(value.items()))

    def __getitem__(self, key: str) -> Any:
        for item_key, item_value in self._items:
            if item_key == key:
                return item_value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _value in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("frozen dictionary does not support mutation")


def freeze_json(value: Any) -> Any:
    """Recursively freeze JSON-shaped containers."""

    if isinstance(value, Mapping):
        return FrozenDict({key: freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    return value


def thaw_json(value: Any) -> Any:
    """Convert frozen JSON containers to serialization-safe containers."""

    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def enforce_payload_bounds(value: Any, depth: int = 0) -> None:
    """Reject payloads with oversized containers or excessive nesting."""

    if isinstance(value, dict):
        if depth > 2:
            raise ValueError("payload cannot contain more than two nested container levels")
        if len(value) > 64:
            raise ValueError("payload objects cannot contain more than 64 properties")
        if any(len(key) > 128 for key in value):
            raise ValueError("payload property names cannot exceed 128 characters")
        for item in value.values():
            enforce_payload_bounds(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        if depth > 2:
            raise ValueError("payload cannot contain more than two nested container levels")
        if len(value) > 64:
            raise ValueError("payload arrays cannot contain more than 64 items")
        for item in value:
            enforce_payload_bounds(item, depth + 1)
    elif isinstance(value, str) and len(value) > 16_384:
        raise ValueError("payload strings cannot exceed 16384 characters")


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    """Hash the RFC 8259-compatible canonical JSON form of an event payload."""

    encoded = json.dumps(
        thaw_json(payload),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class FrozenModel(BaseModel):
    """Strict, assignment-frozen base for persisted contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


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
    payload: Annotated[Mapping[str, Any], Field(max_length=64)]
    model: ModelIdentity | None = None

    @field_validator("payload")
    @classmethod
    def freeze_payload(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        enforce_payload_bounds(value)
        return cast(Mapping[str, Any], freeze_json(value))

    @field_serializer("payload")
    def serialize_payload(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], thaw_json(value))

    @field_validator("artifact_refs")
    @classmethod
    def require_unique_artifact_refs(cls, value: tuple[Digest, ...]) -> tuple[Digest, ...]:
        if len(value) != len(set(value)):
            raise ValueError("artifact references must be unique")
        return value

    @field_validator("causal_parent_ids")
    @classmethod
    def require_unique_causal_parents(
        cls, value: tuple[EventId, ...]
    ) -> tuple[EventId, ...]:
        if len(value) != len(set(value)):
            raise ValueError("causal parent IDs must be unique")
        return value

    @model_validator(mode="after")
    def require_model_provenance(self) -> Event:
        if self.payload_hash != canonical_payload_hash(self.payload):
            raise ValueError("payload_hash does not match canonical payload content")
        if self.id in self.causal_parent_ids:
            raise ValueError("an event cannot be its own causal parent")
        if self.recorded_at < self.observed_at:
            raise ValueError("recorded_at cannot precede observed_at")
        model_identity_required = (
            self.event_type is EventType.MODEL_CALL or self.actor.type is ActorType.MODEL
        )
        if model_identity_required and self.model is None:
            raise ValueError("model calls and model-authored events require model provenance")
        if (
            self.actor.type is ActorType.MODEL
            and self.trust_class is not TrustClass.MODEL_GENERATED
        ):
            raise ValueError("model-authored events must be marked model_generated")
        return self

    @property
    def observed_datetime(self) -> datetime:
        """Return the observed timestamp with a concrete datetime type."""

        return self.observed_at
