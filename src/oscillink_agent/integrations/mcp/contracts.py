"""Strict wire contracts for the local Project Memory MCP adapter."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from oscillink_agent.domain.context import ContextManifest, ContextStatus, RecordId
from oscillink_agent.domain.events import (
    Digest,
    EventId,
    FrozenModel,
    JsonInteger,
    SchemaVersion,
)
from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.repository import MemoryAuthorityState, MemoryRecordId

Topic = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$"),
]


class ProjectMemoryTool(StrEnum):
    """Initial bounded Project Memory operations exposed to MCP clients."""

    REMEMBER = "remember"
    RECALL = "recall"
    CORRECT = "correct"
    EXPLAIN = "explain"


class UnavailableReason(StrEnum):
    """Stable, sanitized reasons that an operation has no result."""

    EMPTY_WORKSPACE = "empty_workspace"
    NO_APPROVED_MEMORY = "no_approved_memory"
    MEMORY_STORE_UNAVAILABLE = "memory_store_unavailable"
    REVISION_NOT_FOUND = "revision_not_found"


class FailureCode(StrEnum):
    """Stable failure classes with no raw implementation details."""

    INVALID_REQUEST = "invalid_request"
    REQUEST_CONFLICT = "request_conflict"
    REVISION_CONFLICT = "revision_conflict"
    INTERNAL_ERROR = "internal_error"


class ExplanationReason(StrEnum):
    """Why one exact revision was selected, excluded, or is stale."""

    SELECTED = "selected"
    NOT_APPROVED = "not_approved"
    STALE_REVISION = "stale_revision"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    RETRACTED = "retracted"
    MISSING_SOURCE = "missing_source"
    NO_QUERY_MATCH = "no_query_match"
    TOKEN_BUDGET = "token_budget"


class LineageRelationship(StrEnum):
    """Typed relationship from the requested revision to one lineage entry."""

    REQUESTED = "requested"
    SOURCE = "source"
    SUPERSEDES = "supersedes"
    SUPERSEDED_BY = "superseded_by"
    CONTRADICTS = "contradicts"


class RecallRequest(FrozenModel):
    """Read approved project memory under one explicit deterministic budget."""

    schema_version: SchemaVersion
    request_id: EventId
    query: Annotated[str, Field(min_length=1, max_length=16_384)]
    token_budget: Annotated[JsonInteger, Field(ge=1, le=32_768)]


class RememberRequest(FrozenModel):
    """Propose one provenance-bearing project-memory candidate."""

    schema_version: SchemaVersion
    request_id: EventId
    title: Annotated[str, Field(min_length=1, max_length=512)]
    content: Annotated[str, Field(min_length=1, max_length=65_536)]
    category: MemoryCategory
    domains: Annotated[tuple[MemoryDomain, ...], Field(min_length=1, max_length=16)]
    topics: Annotated[tuple[Topic, ...], Field(max_length=32)] = ()
    source_refs: Annotated[tuple[RecordId, ...], Field(min_length=1, max_length=16)]

    @field_validator("domains", "topics", "source_refs")
    @classmethod
    def require_unique_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("memory candidate metadata must be unique")
        return value


class CorrectRequest(RememberRequest):
    """Propose a replacement bound to one exact prior memory revision."""

    target_record_id: MemoryRecordId
    expected_content_hash: Digest
    reason: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def require_target_as_lineage_source(self) -> "CorrectRequest":
        if self.target_record_id not in self.source_refs:
            raise ValueError("correction provenance must include its target record")
        return self


class ExplainRequest(FrozenModel):
    """Request governed lineage for one exact project-memory revision."""

    schema_version: SchemaVersion
    request_id: EventId
    record_id: MemoryRecordId
    content_hash: Digest


class UnavailableResponse(FrozenModel):
    """Typed absence without exception or host-detail leakage."""

    schema_version: SchemaVersion
    state: Literal["unavailable"]
    operation: ProjectMemoryTool
    reason: UnavailableReason
    retryable: bool


class FailureResponse(FrozenModel):
    """Typed failed operation without exception or host-detail leakage."""

    schema_version: SchemaVersion
    state: Literal["failure"]
    operation: ProjectMemoryTool
    code: FailureCode
    retryable: bool


ProjectMemoryProblem = Annotated[
    UnavailableResponse | FailureResponse,
    Field(discriminator="state"),
]


class RecalledMemory(FrozenModel):
    """Selected revision text, always treated as non-authoritative input data."""

    record_id: MemoryRecordId
    content_hash: Digest
    title: Annotated[str, Field(min_length=1, max_length=512)]
    content: Annotated[str, Field(min_length=1, max_length=65_536)]
    source_refs: Annotated[tuple[RecordId, ...], Field(min_length=1, max_length=16)]
    content_treatment: Literal["untrusted_data"]


class RecallResponse(FrozenModel):
    """Exact selected text plus the deterministic context evidence artifact."""

    schema_version: SchemaVersion
    state: Literal["available"]
    operation: Literal[ProjectMemoryTool.RECALL]
    request_id: EventId
    context_manifest: ContextManifest
    records: tuple[RecalledMemory, ...]

    @model_validator(mode="after")
    def bind_records_to_manifest_revisions(self) -> "RecallResponse":
        manifest_revisions = tuple(
            (item.record_id, item.content_hash) for item in self.context_manifest.items
        )
        response_revisions = tuple(
            (record.record_id, record.content_hash) for record in self.records
        )
        if response_revisions != manifest_revisions:
            raise ValueError("recalled records must match the context manifest revisions")
        if any(
            item.status is not ContextStatus.APPROVED
            for item in self.context_manifest.items
        ):
            raise ValueError("recalled records must be approved")
        for record, item in zip(self.records, self.context_manifest.items, strict=True):
            if len(record.content.split()) != item.token_count:
                raise ValueError("recalled content must match manifest token accounting")
        return self


class CandidateResponse(FrozenModel):
    """Candidate created by ``remember``; canonical promotion remains external."""

    schema_version: SchemaVersion
    state: Literal["candidate"]
    operation: Literal[ProjectMemoryTool.REMEMBER]
    request_id: EventId
    record_id: MemoryRecordId
    content_hash: Digest
    approval_required: Literal[True]


class CorrectionResponse(FrozenModel):
    """Replacement candidate created without mutating its exact target revision."""

    schema_version: SchemaVersion
    state: Literal["candidate"]
    operation: Literal[ProjectMemoryTool.CORRECT]
    request_id: EventId
    target_record_id: MemoryRecordId
    expected_content_hash: Digest
    replacement_record_id: MemoryRecordId
    replacement_content_hash: Digest
    approval_required: Literal[True]


class MemoryLineageEntry(FrozenModel):
    """One exact revision participating in a governed explanation."""

    record_id: MemoryRecordId
    content_hash: Digest
    authority_state: MemoryAuthorityState
    relationship: LineageRelationship


class ExplainResponse(FrozenModel):
    """Typed selection/exclusion reason and revision lineage."""

    schema_version: SchemaVersion
    state: Literal["available"]
    operation: Literal[ProjectMemoryTool.EXPLAIN]
    request_id: EventId
    record_id: MemoryRecordId
    content_hash: Digest
    authority_state: MemoryAuthorityState
    reasons: Annotated[tuple[ExplanationReason, ...], Field(min_length=1)]
    lineage: Annotated[tuple[MemoryLineageEntry, ...], Field(min_length=1)]

    @field_validator("reasons")
    @classmethod
    def require_unique_reasons(
        cls, value: tuple[ExplanationReason, ...]
    ) -> tuple[ExplanationReason, ...]:
        if len(value) != len(set(value)):
            raise ValueError("explanation reasons must be unique")
        return value

    @model_validator(mode="after")
    def require_requested_revision_first(self) -> "ExplainResponse":
        requested = self.lineage[0]
        if (
            requested.relationship is not LineageRelationship.REQUESTED
            or requested.record_id != self.record_id
            or requested.content_hash != self.content_hash
            or requested.authority_state is not self.authority_state
        ):
            raise ValueError("lineage must begin with the exact requested revision")
        return self


ProjectMemorySuccess = Annotated[
    CandidateResponse | RecallResponse | CorrectionResponse | ExplainResponse,
    Field(discriminator="operation"),
]

RecallToolResult = Annotated[
    RecallResponse | UnavailableResponse | FailureResponse,
    Field(discriminator="state"),
]
ExplainToolResult = Annotated[
    ExplainResponse | UnavailableResponse | FailureResponse,
    Field(discriminator="state"),
]
