"""Integrity-checked execution for longitudinal public evaluations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from oscillink_agent.evaluation.baselines import prepare_cases
from oscillink_agent.evaluation.contracts import (
    EvaluationCase,
    EvaluationCondition,
    EvaluationFixture,
    EvaluationManifest,
    EvaluationOutput,
    EvaluationReport,
    EvaluationResult,
)
from oscillink_agent.evaluation.metrics import score_output
from oscillink_agent.providers.base import ProviderExecutionIdentity


class EvaluationIntegrityError(ValueError):
    """Evaluation inputs do not match their frozen integrity declaration."""


class EvaluationExecutor(Protocol):
    """Provider-neutral evaluation execution boundary."""

    @property
    def execution_identity(self) -> ProviderExecutionIdentity: ...

    def execute(
        self,
        case: EvaluationCase,
        condition: EvaluationCondition,
    ) -> EvaluationOutput: ...


@dataclass(frozen=True)
class LoadedEvaluationSuite:
    manifest: EvaluationManifest
    fixtures: tuple[EvaluationFixture, ...]
    manifest_hash: str
    fixture_hash: str


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def load_suite(manifest_path: Path) -> LoadedEvaluationSuite:
    """Load a JSON-compatible YAML manifest and its exact hashed public fixtures."""

    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = EvaluationManifest.model_validate_json(manifest_bytes)
    except ValidationError as error:
        raise EvaluationIntegrityError("invalid evaluation manifest") from error

    fixture_relative = Path(manifest.fixture_path)
    evaluation_root = manifest_path.resolve().parent.parent
    fixture_path = (manifest_path.parent / fixture_relative).resolve()
    if fixture_relative.is_absolute() or not fixture_path.is_relative_to(evaluation_root):
        raise EvaluationIntegrityError("fixture path escapes the evaluation root")

    fixture_bytes = fixture_path.read_bytes()
    fixture_hash = _digest(fixture_bytes)
    if fixture_hash != manifest.fixture_hash:
        raise EvaluationIntegrityError("fixture hash does not match the manifest")
    try:
        fixtures = TypeAdapter(tuple[EvaluationFixture, ...]).validate_json(fixture_bytes)
    except ValidationError as error:
        raise EvaluationIntegrityError("invalid evaluation fixtures") from error
    if not fixtures:
        raise EvaluationIntegrityError("evaluation suite must contain at least one fixture")
    case_ids = tuple(fixture.case_id for fixture in fixtures)
    if len(case_ids) != len(set(case_ids)):
        raise EvaluationIntegrityError("evaluation case identifiers must be unique")

    return LoadedEvaluationSuite(
        manifest=manifest,
        fixtures=fixtures,
        manifest_hash=_digest(manifest_bytes),
        fixture_hash=fixture_hash,
    )


def run_suite(
    suite: LoadedEvaluationSuite,
    executor: EvaluationExecutor,
    *,
    code_revision: str,
    worktree_dirty: bool = False,
) -> EvaluationReport:
    """Execute every fixture-condition pair and retain its machine-readable result."""

    results: list[EvaluationResult] = []
    for fixture in suite.fixtures:
        cases = prepare_cases(fixture, suite.manifest)
        for condition in suite.manifest.conditions:
            case = cases[condition]
            try:
                output = executor.execute(case, condition)
                if output.output_tokens > case.budget.max_output_tokens:
                    raise EvaluationIntegrityError(
                        "executor exceeded the equal output-token budget"
                    )
                if output.latency_ms > case.budget.max_seconds * 1000:
                    raise EvaluationIntegrityError("executor exceeded the equal time budget")
                metrics = score_output(case, fixture.labels, output)
                results.append(
                    EvaluationResult(
                        case_id=fixture.case_id,
                        condition=condition,
                        state="succeeded",
                        output=output,
                        metrics=metrics,
                        error_type=None,
                    )
                )
            except Exception as error:
                results.append(
                    EvaluationResult(
                        case_id=fixture.case_id,
                        condition=condition,
                        state="failed",
                        output=None,
                        metrics=None,
                        error_type=type(error).__name__[:256],
                    )
                )

    passed = all(
        result.state == "succeeded"
        and result.metrics is not None
        and result.metrics.critical_provenance_failures == 0
        for result in results
    )
    return EvaluationReport(
        suite_id=suite.manifest.suite_id,
        suite_version=suite.manifest.suite_version,
        manifest_hash=suite.manifest_hash,
        fixture_hash=suite.fixture_hash,
        code_revision=code_revision,
        worktree_dirty=worktree_dirty,
        provider=executor.execution_identity,
        smoke_only=executor.execution_identity.kind == "fake",
        budget=suite.manifest.budget,
        results=tuple(results),
        passed=passed,
    )
