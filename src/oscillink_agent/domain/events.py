"""Immutable execution event contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from datetime import datetime
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Literal, Self, SupportsIndex, cast
from weakref import ReferenceType, ref

import rfc8785
from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
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
ActorId = Annotated[
    str, Field(pattern=r"^(human|model|tool|system)_[a-z0-9][a-z0-9_-]{1,62}$")
]
_SERIALIZING: ContextVar[bool] = ContextVar("_SERIALIZING", default=False)
MAX_EVENT_PAYLOAD_BYTES = 64 * 1024
MAX_INTEROPERABLE_JSON_INTEGER = 9_007_199_254_740_991
StateLock = tuple[bytes, object]
CONTRACT_DATETIME_PATTERN = (
    r"^(?!0000-)[0-9]{4}-(?:0[1-9]|1[0-2])-"
    r"(?:0[1-9]|[12][0-9]|3[01])T(?:[01][0-9]|2[0-3]):"
    r"[0-5][0-9]:[0-5][0-9](?:\.[0-9]{1,6})?"
    r"(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)
_CONTRACT_DATETIME = re.compile(CONTRACT_DATETIME_PATTERN)


def typed_state_fingerprint(value: Any) -> object:
    """Capture concrete model/container/scalar types before serialization."""

    if isinstance(value, BaseModel):
        state = object.__getattribute__(value, "__dict__")
        fields = tuple(
            sorted((name, typed_state_fingerprint(item)) for name, item in state.items())
        )
        return ("model", type(value), fields)
    if isinstance(value, Enum):
        return ("enum", type(value))
    if isinstance(value, Mapping):
        items = [
            (typed_state_fingerprint(key), typed_state_fingerprint(item))
            for key, item in value.items()
        ]
        items.sort(key=lambda item: repr(item[0]))
        return ("mapping", type(value), tuple(items))
    if isinstance(value, (list, tuple)):
        return ("sequence", type(value), tuple(typed_state_fingerprint(item) for item in value))
    return ("scalar", type(value))


def create_snapshot_registry() -> tuple[
    Callable[[Any, StateLock], None],
    Callable[[Any], StateLock],
]:
    snapshots: dict[int, StateLock] = {}
    references: dict[int, ReferenceType[Any]] = {}

    def store(instance: Any, snapshot: StateLock) -> None:
        key = id(instance)

        def remove(_reference: ReferenceType[Any]) -> None:
            snapshots.pop(key, None)
            references.pop(key, None)

        snapshots[key] = snapshot
        references[key] = ref(instance, remove)

    def load(instance: Any) -> StateLock:
        key = id(instance)
        reference = references.get(key)
        if reference is None or reference() is not instance:
            raise ValueError("contract is missing its construction-time state lock")
        return snapshots[key]

    return store, load


_store_snapshot, _load_snapshot = create_snapshot_registry()


def require_exact_integer(value: Any) -> Any:
    if type(value) is bool:
        raise ValueError("value must be a JSON integer, not a Boolean")
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    return value


def require_exact_boolean(value: Any) -> Any:
    if type(value) is not bool:
        raise ValueError("value must be a JSON Boolean")
    return value


def require_contract_datetime(value: Any) -> Any:
    """Accept only the shared schema/runtime RFC 3339 timestamp subset."""

    if type(value) is datetime:
        serialized = value.isoformat()
        if _CONTRACT_DATETIME.fullmatch(serialized) is None:
            raise ValueError("date-time must fit the canonical RFC 3339 subset")
        return datetime.fromisoformat(serialized)
    if isinstance(value, datetime):
        raise ValueError("date-time values must use the built-in datetime type")
    if type(value) is not str or _CONTRACT_DATETIME.fullmatch(value) is None:
        raise ValueError("value must be a canonical RFC 3339 date-time")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


SchemaVersion = Annotated[Literal[1], BeforeValidator(require_exact_integer)]
JsonInteger = Annotated[
    int,
    BeforeValidator(require_exact_integer),
    Field(
        ge=-MAX_INTEROPERABLE_JSON_INTEGER,
        le=MAX_INTEROPERABLE_JSON_INTEGER,
    ),
]
ExactOne = Annotated[Literal[1], BeforeValidator(require_exact_integer)]
ExactZero = Annotated[Literal[0], BeforeValidator(require_exact_integer)]
ExactTrue = Annotated[Literal[True], BeforeValidator(require_exact_boolean)]
ExactFalse = Annotated[Literal[False], BeforeValidator(require_exact_boolean)]
ContractDatetime = Annotated[
    AwareDatetime,
    BeforeValidator(require_contract_datetime),
]


def reject_duplicate_object_names(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting parser-dependent duplicate names."""

    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object name: {key}")
        value[key] = item
    return value


def freeze_json(value: Any) -> Any:
    """Recursively freeze JSON-shaped containers."""

    if isinstance(value, Mapping):
        frozen = {key: freeze_json(item) for key, item in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    return value


def thaw_json(value: Any) -> Any:
    """Convert immutable JSON containers back to ordinary JSON values."""

    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def freeze_bounded_payload(value: Any, depth: int = 0) -> Any:
    """Validate and freeze one snapshot of a potentially stateful JSON value."""

    if isinstance(value, Mapping):
        if depth > 2:
            raise ValueError("payload cannot contain more than two nested container levels")
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("payload property names must be strings")
            if key in frozen:
                raise ValueError(f"duplicate payload property name: {key}")
            if len(frozen) >= 64:
                raise ValueError("payload objects cannot contain more than 64 properties")
            if len(key) > 128:
                raise ValueError("payload property names cannot exceed 128 characters")
            frozen[key] = freeze_bounded_payload(item, depth + 1)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        if depth > 2:
            raise ValueError("payload cannot contain more than two nested container levels")
        frozen_items: list[Any] = []
        for item in value:
            if len(frozen_items) >= 64:
                raise ValueError("payload arrays cannot contain more than 64 items")
            frozen_items.append(freeze_bounded_payload(item, depth + 1))
        return tuple(frozen_items)
    if type(value) is str:
        if len(value) > 16_384:
            raise ValueError("payload strings cannot exceed 16384 characters")
        return value
    if type(value) is int:
        if abs(value) > MAX_INTEROPERABLE_JSON_INTEGER:
            raise ValueError("payload integers must remain within the RFC 8785 safe range")
        return value
    if type(value) is float:
        if not math.isfinite(value) or abs(value) > MAX_INTEROPERABLE_JSON_INTEGER:
            raise ValueError("payload numbers must be finite and interoperable")
        return value
    if value is None or type(value) is bool:
        return value
    raise ValueError("payload values must use JSON-compatible primitive types")


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    """Hash the RFC 8785 canonical JSON form of an event payload."""

    encoded = rfc8785.dumps(thaw_json(payload))
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class FrozenModel(BaseModel):
    """Strict, assignment-frozen base for persisted contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    def model_post_init(self, _context: Any) -> None:
        _store_snapshot(self, self._state_lock())

    @classmethod
    def model_validate_json(
        cls, json_data: str | bytes | bytearray, **kwargs: Any
    ) -> Self:
        json.loads(json_data, object_pairs_hook=reject_duplicate_object_names)
        return super().model_validate_json(json_data, **kwargs)

    @classmethod
    def model_construct(
        cls, _fields_set: set[str] | None = None, **values: Any
    ) -> Self:
        del _fields_set
        return cls.model_validate(values)

    def __getattribute__(self, name: str) -> Any:
        if name == "__dict__" and not _SERIALIZING.get():
            state = object.__getattribute__(self, "__dict__")
            return MappingProxyType(state)
        return super().__getattribute__(name)

    def _snapshot_bytes(self) -> bytes:
        token = _SERIALIZING.set(True)
        try:
            snapshot = super().model_dump(mode="json", round_trip=True)
        finally:
            _SERIALIZING.reset(token)
        return rfc8785.dumps(snapshot)

    def _state_lock(self) -> StateLock:
        return self._snapshot_bytes(), typed_state_fingerprint(self)

    def _validate_current_state(self) -> None:
        expected_snapshot, expected_types = _load_snapshot(self)
        if typed_state_fingerprint(self) != expected_types:
            raise ValueError("contract state changed after construction")
        snapshot = self._snapshot_bytes()
        type(self).model_validate_json(snapshot)
        if snapshot != expected_snapshot:
            raise ValueError("contract state changed after construction")

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._validate_current_state()
        token = _SERIALIZING.set(True)
        try:
            return super().model_dump(*args, **kwargs)
        finally:
            _SERIALIZING.reset(token)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:
        self._validate_current_state()
        token = _SERIALIZING.set(True)
        try:
            return super().model_dump_json(*args, **kwargs)
        finally:
            _SERIALIZING.reset(token)

    def __copy__(self) -> Self:
        return type(self).model_validate_json(self.model_dump_json())

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> Self:
        clone = type(self).model_validate_json(self.model_dump_json())
        if memo is None:
            memo = {}
        memo[id(self)] = clone
        return clone

    def __reduce__(self) -> tuple[Callable[..., Any], tuple[Any, ...]]:
        return restore_frozen_model, (type(self), self.model_dump_json())

    def __reduce_ex__(
        self, _protocol: SupportsIndex
    ) -> tuple[Callable[..., Any], tuple[Any, ...]]:
        return self.__reduce__()

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> Self:
        del deep
        data = self.model_dump(mode="python", round_trip=True)
        if update is not None:
            data.update(update)
        return type(self).model_validate(data)

    def copy(
        self,
        *,
        include: Any = None,
        exclude: Any = None,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        del deep
        data = self.model_dump(
            mode="python",
            round_trip=True,
            include=include,
            exclude=exclude,
        )
        if update is not None:
            data.update(update)
        return type(self).model_validate(data)


def restore_frozen_model(
    model_type: type[FrozenModel], encoded: str
) -> FrozenModel:
    """Reconstruct a copied or pickled contract through its strict JSON boundary."""

    return model_type.model_validate_json(encoded)


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

    @model_validator(mode="after")
    def require_matching_id_prefix(self) -> Actor:
        if not self.id.startswith(f"{self.type.value}_"):
            raise ValueError("actor ID prefix must match actor type")
        return self


class ModelIdentity(FrozenModel):
    provider: Annotated[str, Field(min_length=1, max_length=128, pattern=r".*\S.*")]
    name: Annotated[str, Field(min_length=1, max_length=128, pattern=r".*\S.*")]
    configuration_hash: Digest


class Event(FrozenModel):
    """Immutable snapshot with declared, not self-authenticating, provenance.

    Trusted ledger ingress must revalidate the serialized snapshot and bind actor,
    authorization, artifact, and causal references to canonical records. This value
    object alone does not prove identity, trust, authority, or referenced existence.
    """

    id: EventId
    schema_version: SchemaVersion
    session_id: SessionId
    run_id: RunId
    task_id: TaskId
    actor: Actor
    event_type: EventType
    observed_at: ContractDatetime
    recorded_at: ContractDatetime
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
        frozen = freeze_bounded_payload(value)
        if len(rfc8785.dumps(thaw_json(frozen))) > MAX_EVENT_PAYLOAD_BYTES:
            raise ValueError("canonical event payload cannot exceed 64 KiB")
        return cast(Mapping[str, Any], frozen)

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
        if not model_identity_required and self.model is not None:
            raise ValueError("model identity is only valid for model-authored events")
        if (
            self.actor.type is ActorType.MODEL
            and self.trust_class is not TrustClass.MODEL_GENERATED
        ):
            raise ValueError("model-authored events must be marked model_generated")
        allowed_trust = {
            ActorType.HUMAN: {TrustClass.HUMAN_VERIFIED, TrustClass.EXTERNAL_UNTRUSTED},
            ActorType.MODEL: {TrustClass.MODEL_GENERATED},
            ActorType.TOOL: {TrustClass.TOOL_VERIFIED, TrustClass.EXTERNAL_UNTRUSTED},
            ActorType.SYSTEM: {TrustClass.SYSTEM, TrustClass.EXTERNAL_UNTRUSTED},
        }
        if self.trust_class not in allowed_trust[self.actor.type]:
            raise ValueError("trust_class is inconsistent with actor type")
        return self

    @property
    def observed_datetime(self) -> datetime:
        """Return the observed timestamp with a concrete datetime type."""

        return self.observed_at
