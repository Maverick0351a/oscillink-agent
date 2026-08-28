"""Capability grant contracts."""

from __future__ import annotations

from pathlib import PurePath
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from oscillink_agent.domain.events import ActorId, EventId, FrozenModel

GrantId = Annotated[str, Field(pattern=r"^grt_[0-9A-HJKMNP-TV-Z]{26}$")]
Extension = Annotated[str, Field(pattern=r"^\.[A-Za-z0-9]+$")]


class FileResource(FrozenModel):
    root: Annotated[str, Field(min_length=1)]
    target: Annotated[str, Field(min_length=1)]

    @field_validator("target")
    @classmethod
    def require_relative_target(cls, value: str) -> str:
        path = PurePath(value)
        if path.is_absolute() or path.drive or ".." in path.parts:
            raise ValueError("capability target must be a relative, traversal-free path")
        return value


class CapabilityConstraints(FrozenModel):
    max_bytes: Annotated[int, Field(ge=1, le=1_048_576)]
    allowed_extensions: Annotated[tuple[Extension, ...], Field(min_length=1)]
    network_allowed: Literal[False]


class CapabilityGrant(FrozenModel):
    id: GrantId
    schema_version: Literal[1]
    subject_actor_id: ActorId
    capability: Literal["file.read"]
    resource: FileResource
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    issued_by: ActorId
    authorization_event_id: EventId
    max_uses: Literal[1]
    constraints: CapabilityConstraints

    @model_validator(mode="after")
    def require_future_expiration(self) -> CapabilityGrant:
        if self.expires_at <= self.issued_at:
            raise ValueError("capability grant must expire after it is issued")
        return self
