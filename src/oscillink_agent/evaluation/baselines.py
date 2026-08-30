"""Deterministic context preparation for longitudinal baselines."""

from __future__ import annotations

import re

from oscillink_agent.evaluation.contracts import (
    EvaluationCase,
    EvaluationCondition,
    EvaluationEvidence,
    EvaluationFixture,
    EvaluationManifest,
    EvaluationOutput,
)
from oscillink_agent.providers.base import ProviderExecutionIdentity, build_execution_identity

_DECLARED_ANSWER = re.compile(r"\banswer:\s*([^\n.]+)", re.IGNORECASE)


def context_units(evidence: tuple[EvaluationEvidence, ...]) -> int:
    """Count stable whitespace-delimited context units for budget parity."""

    return sum(len(item.text.split()) for item in evidence)


def _bounded_context(
    evidence: tuple[EvaluationEvidence, ...],
    max_context_units: int,
) -> tuple[EvaluationEvidence, ...]:
    selected: list[EvaluationEvidence] = []
    used = 0
    for item in evidence:
        item_units = len(item.text.split())
        if used + item_units > max_context_units:
            continue
        selected.append(item)
        used += item_units
    return tuple(selected)


def prepare_cases(
    fixture: EvaluationFixture,
    manifest: EvaluationManifest,
) -> dict[EvaluationCondition, EvaluationCase]:
    """Prepare every baseline under the one manifest-owned equal budget."""

    return {
        condition: EvaluationCase(
            case_id=fixture.case_id,
            question=fixture.question,
            context=_bounded_context(
                fixture.contexts[condition],
                manifest.budget.max_context_units,
            ),
            budget=manifest.budget,
        )
        for condition in manifest.conditions
    }


class DeterministicSmokeExecutor:
    """Exercise the harness deterministically; never treat this as model-quality evidence."""

    @property
    def execution_identity(self) -> ProviderExecutionIdentity:
        return build_execution_identity(
            kind="fake",
            model="evaluation-smoke-v1",
            public_configuration={"purpose": "harness-integrity-only"},
        )

    def execute(
        self,
        case: EvaluationCase,
        condition: EvaluationCondition,
    ) -> EvaluationOutput:
        del condition
        answer = "INSUFFICIENT_EVIDENCE"
        citations: tuple[str, ...] = ()
        for evidence in case.context:
            matches = tuple(_DECLARED_ANSWER.finditer(evidence.text))
            if matches:
                answer = matches[-1].group(1).strip()
                citations = (evidence.ref,)
        return EvaluationOutput(
            answer=answer,
            citations=citations,
            latency_ms=0,
            output_tokens=len(answer.split()),
            provider_usage_units=context_units(case.context),
            estimated_cost_usd=0.0,
            human_correction_burden=None,
        )
