"""Transport contracts for governed product-memory HTTP routes."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from oscillink_agent.domain.events import EventId
from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.repository import ArchitectureNodeId

MemoryNodeId = Annotated[str, Field(pattern=r"^(?:doc|mem)_[0-9A-HJKMNP-TV-Z]{26}$")]


class NativeMemoryCreateRequest(BaseModel):
    """Customer-authored candidate memory independent of external sources."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1]
    title: Annotated[str, Field(min_length=1, max_length=512)]
    content: Annotated[str, Field(min_length=1, max_length=2 * 1024 * 1024)]
    category: MemoryCategory
    domains: Annotated[tuple[MemoryDomain, ...], Field(min_length=1)]
    topics: tuple[str, ...] = ()
    architecture_node_ids: tuple[ArchitectureNodeId, ...] = ()


class MemoryReviewRequest(BaseModel):
    """One externally governed memory approval or rejection."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    request_id: EventId
    decision: Literal["approved", "rejected", "superseded"]
    replacement_record_id: MemoryNodeId | None = None


class MemorySourceSyncRequest(BaseModel):
    """Explicit synchronization request for one configured source adapter."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    request_id: EventId


class MemorySourceStatusResponse(BaseModel):
    """Opaque configuration state for one bounded source adapter."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    source_kind: Literal["obsidian"] = "obsidian"
    state: Literal["configured", "not_configured", "unavailable"]


class MemorySourceSyncResponse(BaseModel):
    """Sanitized result of a configured source synchronization."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    state: Literal["synced"] = "synced"
    source_kind: Literal["obsidian"] = "obsidian"
    created: Annotated[int, Field(ge=0)]
    revised: Annotated[int, Field(ge=0)]
    unchanged: Annotated[int, Field(ge=0)]
    missing: Annotated[int, Field(ge=0)]
    issues: Annotated[int, Field(ge=0)]
