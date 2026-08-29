"""Typed observations emitted by bounded capabilities."""

from typing import Annotated, Literal

from pydantic import Field

from oscillink_agent.domain.capabilities import GrantId, PortableTarget, ScopeId
from oscillink_agent.domain.events import (
    Digest,
    ExactFalse,
    FrozenModel,
    JsonInteger,
    SchemaVersion,
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
