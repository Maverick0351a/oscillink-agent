"""Strict provider-request contracts for bounded governed tools."""

from typing import Annotated, Literal

from pydantic import Field

from oscillink_agent.domain.capabilities import PortableTarget, ScopeId
from oscillink_agent.domain.events import FrozenModel, JsonInteger, SchemaVersion


class FileReadToolRequest(FrozenModel):
    """One portable file-read request with no grant or host authority."""

    schema_version: SchemaVersion
    operation: Literal["file.read"]
    scope_id: ScopeId
    target: PortableTarget
    max_bytes: Annotated[JsonInteger, Field(ge=1, le=1_048_576)]
