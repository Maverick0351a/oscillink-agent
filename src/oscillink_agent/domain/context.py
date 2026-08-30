"""Context compilation contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from oscillink_agent.domain.events import (
    ContractDatetime,
    Digest,
    FrozenModel,
    JsonInteger,
    SchemaVersion,
    TaskId,
    TrustClass,
)

ContextId = Annotated[str, Field(pattern=r"^ctx_[0-9A-HJKMNP-TV-Z]{26}$")]
RecordId = Annotated[
    str,
    Field(pattern=r"^(evt|clm|doc|mem|prc)_[0-9A-HJKMNP-TV-Z]{26}$"),
]
ContextTitle = Annotated[str, Field(min_length=1, max_length=512)]
ContextCategory = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]
ContextDomain = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$"),
]


class ContextStatus(StrEnum):
    APPROVED = "approved"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class ContextOmissionReason(StrEnum):
    TOKEN_BUDGET = "token_budget"
    NO_QUERY_MATCH = "no_query_match"


class ContextItem(FrozenModel):
    record_id: RecordId
    content_hash: Digest
    title: ContextTitle | None = None
    category: ContextCategory | None = None
    domains: Annotated[tuple[ContextDomain, ...], Field(max_length=16)] = ()
    inclusion_reason: Annotated[str, Field(min_length=1)]
    trust_class: TrustClass
    status: ContextStatus
    token_count: Annotated[JsonInteger, Field(ge=0)]
    source_refs: Annotated[tuple[RecordId, ...], Field(min_length=1)]
    retrieval_rank: Annotated[JsonInteger, Field(ge=1)] | None = None
    retrieval_score: Annotated[JsonInteger, Field(ge=1)] | None = None

    @field_validator("source_refs")
    @classmethod
    def require_unique_source_refs(
        cls, value: tuple[RecordId, ...]
    ) -> tuple[RecordId, ...]:
        if len(value) != len(set(value)):
            raise ValueError("source references must be unique")
        return value

    @model_validator(mode="after")
    def require_complete_retrieval_metadata(self) -> ContextItem:
        if (self.retrieval_rank is None) != (self.retrieval_score is None):
            raise ValueError("retrieval rank and score must be recorded together")
        return self


class ContextOmission(FrozenModel):
    record_id: RecordId
    content_hash: Digest
    reason: ContextOmissionReason
    retrieval_rank: Annotated[JsonInteger, Field(ge=1)] | None = None
    retrieval_score: Annotated[JsonInteger, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def require_rank_for_budget_omission(self) -> ContextOmission:
        has_rank = self.retrieval_rank is not None and self.retrieval_score is not None
        if self.reason is ContextOmissionReason.TOKEN_BUDGET and not has_rank:
            raise ValueError("budget omissions require retrieval rank and score")
        if self.reason is ContextOmissionReason.NO_QUERY_MATCH and has_rank:
            raise ValueError("unmatched omissions cannot have retrieval rank or score")
        return self


class ContextExclusionSummary(FrozenModel):
    not_approved_count: Annotated[JsonInteger, Field(ge=0)] = 0
    missing_source_count: Annotated[JsonInteger, Field(ge=0)] = 0
    superseded_count: Annotated[JsonInteger, Field(ge=0)] = 0
    conflict_count: Annotated[JsonInteger, Field(ge=0)] = 0


class ContextManifest(FrozenModel):
    id: ContextId
    schema_version: SchemaVersion
    task_id: TaskId
    compiled_at: ContractDatetime
    token_budget: Annotated[JsonInteger, Field(ge=1)]
    total_token_count: Annotated[JsonInteger, Field(ge=0)]
    policy_hash: Digest
    items: tuple[ContextItem, ...]
    omissions: tuple[ContextOmission, ...] = ()
    exclusion_summary: ContextExclusionSummary = Field(
        default_factory=ContextExclusionSummary
    )

    @field_validator("items")
    @classmethod
    def require_unique_items(
        cls, value: tuple[ContextItem, ...]
    ) -> tuple[ContextItem, ...]:
        if len(value) != len(set(value)):
            raise ValueError("context items must be unique")
        return value

    @field_validator("omissions")
    @classmethod
    def require_unique_omissions(
        cls, value: tuple[ContextOmission, ...]
    ) -> tuple[ContextOmission, ...]:
        record_ids = tuple(item.record_id for item in value)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("context omissions must reference unique records")
        return value

    @model_validator(mode="after")
    def enforce_token_accounting(self) -> ContextManifest:
        if self.total_token_count > self.token_budget:
            raise ValueError("context token count exceeds its budget")
        if sum(item.token_count for item in self.items) != self.total_token_count:
            raise ValueError("item token counts must equal the manifest total")
        included = {item.record_id for item in self.items}
        omitted = {item.record_id for item in self.omissions}
        if included & omitted:
            raise ValueError("a context record cannot be both included and omitted")
        return self
