"""Context compilation contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from oscillink_agent.domain.events import Digest, FrozenModel, TaskId, TrustClass

ContextId = Annotated[str, Field(pattern=r"^ctx_[0-9A-HJKMNP-TV-Z]{26}$")]
RecordId = Annotated[str, Field(pattern=r"^(evt|clm|doc|prc)_[0-9A-HJKMNP-TV-Z]{26}$")]


class ContextStatus(StrEnum):
    APPROVED = "approved"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class ContextItem(FrozenModel):
    record_id: RecordId
    content_hash: Digest
    inclusion_reason: Annotated[str, Field(min_length=1)]
    trust_class: TrustClass
    status: ContextStatus
    token_count: Annotated[int, Field(ge=0)]
    source_refs: Annotated[tuple[RecordId, ...], Field(min_length=1)]

    @field_validator("source_refs")
    @classmethod
    def require_unique_source_refs(
        cls, value: tuple[RecordId, ...]
    ) -> tuple[RecordId, ...]:
        if len(value) != len(set(value)):
            raise ValueError("source references must be unique")
        return value


class ContextManifest(FrozenModel):
    id: ContextId
    schema_version: Literal[1]
    task_id: TaskId
    compiled_at: AwareDatetime
    token_budget: Annotated[int, Field(ge=1)]
    total_token_count: Annotated[int, Field(ge=0)]
    policy_hash: Digest
    items: tuple[ContextItem, ...]

    @field_validator("items")
    @classmethod
    def require_unique_items(
        cls, value: tuple[ContextItem, ...]
    ) -> tuple[ContextItem, ...]:
        if len(value) != len(set(value)):
            raise ValueError("context items must be unique")
        return value

    @model_validator(mode="after")
    def enforce_token_accounting(self) -> ContextManifest:
        if self.total_token_count > self.token_budget:
            raise ValueError("context token count exceeds its budget")
        if sum(item.token_count for item in self.items) != self.total_token_count:
            raise ValueError("item token counts must equal the manifest total")
        return self
