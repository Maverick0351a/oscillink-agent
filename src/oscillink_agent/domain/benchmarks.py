"""Immutable benchmark manifest contracts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, cast

from pydantic import AwareDatetime, Field, field_serializer, field_validator

from oscillink_agent.domain.events import Digest, FrozenDict, FrozenModel

BenchmarkId = Annotated[str, Field(pattern=r"^bmk_[0-9A-HJKMNP-TV-Z]{26}$")]
BenchmarkName = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]
SemanticVersion = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
MetricName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")]


class BenchmarkCondition(StrEnum):
    NO_MEMORY = "no_memory"
    RAW_TRANSCRIPT = "raw_transcript"
    HAND_MARKDOWN = "hand_markdown"
    GENERATED_SUMMARY = "generated_summary"
    FTS5_EVIDENCE = "fts5_evidence"
    PROVENANCE_EVIDENCE = "provenance_evidence"


class MetricDirection(StrEnum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ThreatCase(StrEnum):
    MEMORY_POISONING = "memory_poisoning"
    STALE_STATE = "stale_state"
    PERMISSION_ESCALATION = "permission_escalation"
    CROSS_SCOPE_RETRIEVAL = "cross_scope_retrieval"
    UNSUPPORTED_COMPLETION = "unsupported_completion"
    SECRET_EXPOSURE = "secret_exposure"


class BenchmarkBudgets(FrozenModel):
    max_tokens: Annotated[int, Field(ge=1)]
    max_seconds: Annotated[int, Field(ge=1)]
    max_tool_calls: Annotated[int, Field(ge=0)]
    max_retries: Annotated[int, Field(ge=0)]


class PromotionGate(FrozenModel):
    max_critical_failures: Literal[0]
    require_equal_budgets: Literal[True]
    require_external_verification: Literal[True]


class BenchmarkManifest(FrozenModel):
    id: BenchmarkId
    schema_version: Literal[1]
    name: BenchmarkName
    version: SemanticVersion
    created_at: AwareDatetime
    task_set_hash: Digest
    hidden_labels: Literal["external"]
    conditions: Annotated[tuple[BenchmarkCondition, ...], Field(min_length=1)]
    metrics: Annotated[Mapping[MetricName, MetricDirection], Field(min_length=1)]
    budgets: BenchmarkBudgets
    promotion_gate: PromotionGate
    threat_cases: Annotated[tuple[ThreatCase, ...], Field(min_length=1)]

    @field_validator("conditions")
    @classmethod
    def require_unique_conditions(
        cls, value: tuple[BenchmarkCondition, ...]
    ) -> tuple[BenchmarkCondition, ...]:
        if len(value) != len(set(value)):
            raise ValueError("benchmark conditions must be unique")
        return value

    @field_validator("threat_cases")
    @classmethod
    def require_unique_threat_cases(
        cls, value: tuple[ThreatCase, ...]
    ) -> tuple[ThreatCase, ...]:
        if len(value) != len(set(value)):
            raise ValueError("benchmark threat cases must be unique")
        return value

    @field_validator("metrics")
    @classmethod
    def freeze_metrics(
        cls, value: Mapping[MetricName, MetricDirection]
    ) -> Mapping[MetricName, MetricDirection]:
        return cast(Mapping[MetricName, MetricDirection], FrozenDict(value))

    @field_serializer("metrics")
    def serialize_metrics(
        self, value: Mapping[MetricName, MetricDirection]
    ) -> dict[MetricName, MetricDirection]:
        return dict(value)
