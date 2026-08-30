"""Transport contracts for governed local chat runs."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from oscillink_agent.agent_runtime.contracts import RunReconstruction
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.domain.events import Event, EventId, RunId, SessionId, TaskId

MemoryNodeId = Annotated[str, Field(pattern=r"^mem_[0-9A-HJKMNP-TV-Z]{26}$")]


class ChatMessageRequest(BaseModel):
    """One governed local chat turn with an explicit context budget."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    request_id: EventId
    session_id: SessionId
    message: Annotated[str, Field(min_length=1, max_length=16_384)]
    token_budget: Annotated[int, Field(ge=1, le=32_768)]


class ChatProviderProjection(BaseModel):
    """Public non-secret identity of the configured generation provider."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    kind: Literal["fake", "ollama", "openai_compatible"] = "fake"
    model: Annotated[str, Field(min_length=1, max_length=512)] = "deterministic-v1"


class ChatCitation(BaseModel):
    """Revision-bound citation emitted by one chat turn."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    record_id: MemoryNodeId
    content_hash: str
    title: str
    retrieval_rank: Annotated[int, Field(ge=1)]
    retrieval_score: Annotated[int, Field(ge=1)]


class ChatMessageResponse(BaseModel):
    """Completed provider turn plus its exact governed context manifest."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    session_id: SessionId
    run_id: RunId
    task_id: TaskId
    provider: ChatProviderProjection
    answer: str
    citations: tuple[ChatCitation, ...]
    context_manifest: ContextManifest

    @field_serializer("context_manifest")
    def serialize_context_manifest(self, value: ContextManifest) -> dict[str, object]:
        return value.model_dump(mode="json")


class ChatRunInspectionResponse(BaseModel):
    """Restart-safe run trajectory and verified context artifact."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    session_id: SessionId
    run_id: RunId
    events: tuple[Event, ...]
    context_manifest: ContextManifest
    reconstruction: RunReconstruction

    @field_serializer("events")
    def serialize_events(self, value: tuple[Event, ...]) -> list[dict[str, object]]:
        return [event.model_dump(mode="json") for event in value]

    @field_serializer("context_manifest")
    def serialize_context_manifest(self, value: ContextManifest) -> dict[str, object]:
        return value.model_dump(mode="json")
