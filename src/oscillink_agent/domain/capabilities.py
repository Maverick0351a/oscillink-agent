"""Capability grant contracts."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, field_validator

from oscillink_agent.domain.events import ActorId, EventId, FrozenModel

GrantId = Annotated[str, Field(pattern=r"^grt_[0-9A-HJKMNP-TV-Z]{26}$")]
Extension = Annotated[str, Field(pattern=r"^\.[A-Za-z0-9]+$")]
ScopeId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]
PortableTarget = Annotated[
    str,
    Field(
        pattern=(
            r"^[A-Za-z0-9_-](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?"
            r"(?:/[A-Za-z0-9_-](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?)*$"
        )
    ),
]


class FileResource(FrozenModel):
    scope_id: ScopeId
    target: PortableTarget

    @field_validator("target")
    @classmethod
    def reject_windows_device_names(cls, value: str) -> str:
        for segment in value.split("/"):
            stem = segment.split(".", maxsplit=1)[0].upper()
            if stem in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(
                r"(?:COM|LPT)[1-9]", stem
            ):
                raise ValueError("target contains a reserved Windows device name")
        return value


class CapabilityConstraints(FrozenModel):
    max_bytes: Annotated[int, Field(ge=1, le=1_048_576)]
    allowed_extensions: Annotated[tuple[Extension, ...], Field(min_length=1)]
    network_allowed: Literal[False]

    @field_validator("allowed_extensions")
    @classmethod
    def require_unique_extensions(
        cls, value: tuple[Extension, ...]
    ) -> tuple[Extension, ...]:
        if len(value) != len(set(value)):
            raise ValueError("allowed extensions must be unique")
        return value


class CapabilityGrant(FrozenModel):
    """Non-authoritative grant record resolved and consumed by a trusted broker.

    Constructing this model never confers permission. A runtime broker must resolve
    its opaque ID from trusted storage and verify issuer, subject, scope, time,
    authorization event, and atomic use consumption.
    """

    id: GrantId
    schema_version: Literal[1]
    subject_actor_id: ActorId
    capability: Literal["file.read"]
    resource: FileResource
    issued_at: AwareDatetime
    valid_for_seconds: Annotated[int, Field(ge=1, le=300)]
    issued_by: ActorId
    authorization_event_id: EventId
    max_uses: Literal[1]
    constraints: CapabilityConstraints
