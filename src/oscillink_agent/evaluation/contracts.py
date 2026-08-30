"""Longitudinal public-evaluation contracts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import Field, field_serializer, field_validator

from oscillink_agent.domain.events import FrozenModel
from oscillink_agent.providers.base import ProviderExecutionIdentity


class EvaluationCondition(StrEnum):
    """Minimum baselines required for the first public longitudinal suite."""

    NO_MEMORY = "no_memory"
    RAW_TRANSCRIPT = "raw_transcript"
    GENERATED_SUMMARY = "generated_summary"
    APPROVED_LEXICAL = "approved_lexical"


class EvaluationBudget(FrozenModel):
    max_context_units: Annotated[int, Field(ge=1, le=1_000_000)]
    max_output_tokens: Annotated[int, Field(ge=1, le=1_000_000)]
    max_seconds: Annotated[int, Field(ge=1, le=86_400)]


class EvaluationManifest(FrozenModel):
    schema_version: Literal[1]
    suite_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]
    suite_version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    fixture_path: Annotated[str, Field(min_length=1, max_length=512)]
    fixture_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    conditions: tuple[EvaluationCondition, ...]
    budget: EvaluationBudget

    @field_validator("conditions")
    @classmethod
    def require_all_conditions(
        cls, value: tuple[EvaluationCondition, ...]
    ) -> tuple[EvaluationCondition, ...]:
        if value != tuple(EvaluationCondition):
            raise ValueError("evaluation conditions must appear once in canonical order")
        return value


class EvaluationEvidence(FrozenModel):
    ref: Annotated[str, Field(min_length=1, max_length=256)]
    text: Annotated[str, Field(min_length=1, max_length=65_536)]


class EvaluationLabels(FrozenModel):
    accepted_answers: Annotated[tuple[str, ...], Field(min_length=1)]
    relevant_refs: tuple[str, ...] = ()
    obsolete_terms: tuple[str, ...] = ()
    contradiction_terms: tuple[str, ...] = ()
    injection_terms: tuple[str, ...] = ()
    requires_abstention: bool = False


class EvaluationCase(FrozenModel):
    """Agent-readable case. Deterministic labels are intentionally absent."""

    case_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]
    question: Annotated[str, Field(min_length=1, max_length=16_384)]
    context: tuple[EvaluationEvidence, ...]
    budget: EvaluationBudget


class EvaluationOutput(FrozenModel):
    """One provider result plus externally observed usage; no self-awarded score fields."""

    answer: Annotated[str, Field(min_length=1, max_length=1_048_576)]
    citations: tuple[Annotated[str, Field(min_length=1, max_length=256)], ...] = ()
    latency_ms: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]
    provider_usage_units: Annotated[int, Field(ge=0)] | None = None
    estimated_cost_usd: Annotated[float, Field(ge=0)] | None = None
    human_correction_burden: Annotated[int, Field(ge=0)] | None = None


class EvaluationMetrics(FrozenModel):
    correctness: Annotated[float, Field(ge=0, le=1)]
    citation_precision: Annotated[float, Field(ge=0, le=1)]
    evidence_recall: Annotated[float, Field(ge=0, le=1)]
    obsolete_memory_reuse: Annotated[float, Field(ge=0, le=1)]
    contradiction_handling: Annotated[float, Field(ge=0, le=1)] | None
    abstention: Annotated[float, Field(ge=0, le=1)] | None
    unsafe_instruction_following: Annotated[float, Field(ge=0, le=1)]
    latency_ms: Annotated[int, Field(ge=0)]
    context_units: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]
    provider_usage_units: Annotated[int, Field(ge=0)] | None
    estimated_cost_usd: Annotated[float, Field(ge=0)] | None
    human_correction_burden: Annotated[int, Field(ge=0)] | None
    critical_provenance_failures: Annotated[int, Field(ge=0)]


class EvaluationResult(FrozenModel):
    case_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]
    condition: EvaluationCondition
    state: Literal["succeeded", "failed"]
    output: EvaluationOutput | None
    metrics: EvaluationMetrics | None
    error_type: Annotated[str, Field(min_length=1, max_length=256)] | None = None


class EvaluationReport(FrozenModel):
    schema_version: Literal[1] = 1
    suite_id: str
    suite_version: str
    manifest_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    fixture_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    code_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{7,64}$")]
    worktree_dirty: bool
    provider: ProviderExecutionIdentity
    smoke_only: bool
    budget: EvaluationBudget
    results: tuple[EvaluationResult, ...]
    passed: bool


class EvaluationFixture(FrozenModel):
    schema_version: Literal[1]
    case_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]
    question: Annotated[str, Field(min_length=1, max_length=16_384)]
    contexts: Mapping[EvaluationCondition, tuple[EvaluationEvidence, ...]]
    labels: EvaluationLabels

    @field_validator("contexts")
    @classmethod
    def require_all_contexts(
        cls,
        value: Mapping[EvaluationCondition, tuple[EvaluationEvidence, ...]],
    ) -> Mapping[EvaluationCondition, tuple[EvaluationEvidence, ...]]:
        if set(value) != set(EvaluationCondition):
            raise ValueError("fixture must define every evaluation condition")
        return MappingProxyType(dict(value))

    @field_serializer("contexts")
    def serialize_contexts(
        self,
        value: Mapping[EvaluationCondition, tuple[EvaluationEvidence, ...]],
    ) -> dict[str, list[dict[str, str]]]:
        return {
            condition.value: [item.model_dump(mode="json") for item in evidence]
            for condition, evidence in value.items()
        }

    def agent_case(
        self,
        condition: EvaluationCondition,
        budget: EvaluationBudget,
    ) -> EvaluationCase:
        return EvaluationCase(
            case_id=self.case_id,
            question=self.question,
            context=self.contexts[condition],
            budget=budget,
        )
