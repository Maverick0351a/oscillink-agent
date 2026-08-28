"""Reviewed semantic-memory contracts."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from oscillink_agent.domain.events import ActorId, Digest, FrozenModel, Sensitivity

ClaimId = Annotated[str, Field(pattern=r"^clm_[0-9A-HJKMNP-TV-Z]{26}$")]
RecordRef = Annotated[str, Field(pattern=r"^(evt|clm|doc|prc)_[0-9A-HJKMNP-TV-Z]{26}$")]
SubjectId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{2,127}$")]


class EpistemicClass(StrEnum):
    USER_ASSERTION = "user_assertion"
    TOOL_OBSERVATION = "tool_observation"
    EXTERNAL_SOURCE = "external_source"
    MODEL_INFERENCE = "model_inference"
    HYPOTHESIS = "hypothesis"
    DECISION = "decision"
    PREFERENCE = "preference"
    POLICY = "policy"


class ClaimStatus(StrEnum):
    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    DISPUTED = "disputed"
    CONTRADICTED = "contradicted"
    RETRACTED = "retracted"
    SUPERSEDED = "superseded"


class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryClaim(FrozenModel):
    id: ClaimId
    schema_version: Literal[1]
    epistemic_class: EpistemicClass
    status: ClaimStatus
    subject_id: SubjectId
    content: Annotated[str, Field(min_length=1)]
    valid_from: AwareDatetime | None
    valid_until: AwareDatetime | None
    recorded_at: AwareDatetime
    source_refs: Annotated[tuple[RecordRef, ...], Field(min_length=1)]
    content_hash: Digest
    asserted_by: ActorId
    review_state: ReviewState
    sensitivity: Sensitivity

    @field_validator("source_refs")
    @classmethod
    def require_unique_source_refs(
        cls, value: tuple[RecordRef, ...]
    ) -> tuple[RecordRef, ...]:
        if len(value) != len(set(value)):
            raise ValueError("memory source references must be unique")
        return value

    @model_validator(mode="after")
    def require_ordered_validity(self) -> MemoryClaim:
        expected_hash = "sha256:" + hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if self.content_hash != expected_hash:
            raise ValueError("content_hash does not match claim content")
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until cannot precede valid_from")
        return self
