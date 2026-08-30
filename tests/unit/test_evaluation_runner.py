from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import ClassVar

import pytest

from oscillink_agent.evaluation.baselines import prepare_cases
from oscillink_agent.evaluation.contracts import (
    EvaluationCase,
    EvaluationCondition,
    EvaluationFixture,
    EvaluationManifest,
    EvaluationOutput,
)
from oscillink_agent.evaluation.metrics import score_output
from oscillink_agent.evaluation.runner import (
    EvaluationIntegrityError,
    LoadedEvaluationSuite,
    load_suite,
    run_suite,
)
from oscillink_agent.providers.base import build_execution_identity


def test_public_contract_isolates_labels_from_agent_cases() -> None:
    manifest = EvaluationManifest.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "public-smoke",
                "suite_version": "0.1.0",
                "fixture_path": "../fixtures/public-smoke.json",
                "fixture_hash": "sha256:" + "a" * 64,
                "conditions": [condition.value for condition in EvaluationCondition],
                "budget": {
                    "max_context_units": 128,
                    "max_output_tokens": 64,
                    "max_seconds": 5,
                },
            }
        )
    )
    fixture = EvaluationFixture.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "continuity-owner",
                "question": "Who owns the next pilot action?",
                "contexts": {
                    "no_memory": [],
                    "raw_transcript": [
                        {"ref": "turn-1", "text": "Maverick owns the next pilot action."}
                    ],
                    "generated_summary": [
                        {
                            "ref": "summary-1",
                            "text": "The next pilot action belongs to Maverick.",
                        }
                    ],
                    "approved_lexical": [
                        {"ref": "mem-1", "text": "Maverick owns the next pilot action."}
                    ],
                },
                "labels": {
                    "accepted_answers": ["Maverick"],
                    "relevant_refs": ["mem-1"],
                    "obsolete_terms": [],
                    "contradiction_terms": [],
                    "injection_terms": [],
                    "requires_abstention": False,
                },
            }
        )
    )

    assert manifest.conditions == tuple(EvaluationCondition)
    case = fixture.agent_case(EvaluationCondition.APPROVED_LEXICAL, manifest.budget)
    assert case.model_dump(mode="json") == {
        "case_id": "continuity-owner",
        "question": "Who owns the next pilot action?",
        "context": [{"ref": "mem-1", "text": "Maverick owns the next pilot action."}],
        "budget": {
            "max_context_units": 128,
            "max_output_tokens": 64,
            "max_seconds": 5,
        },
    }
    assert "accepted_answers" not in case.model_dump_json()


def test_suite_loader_verifies_exact_fixture_hash(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixtures" / "public-smoke.json"
    fixture_path.parent.mkdir()
    fixture_bytes = json.dumps(
        [
            {
                "schema_version": 1,
                "case_id": "continuity-owner",
                "question": "Who owns the next pilot action?",
                "contexts": {
                    "no_memory": [],
                    "raw_transcript": [{"ref": "turn-1", "text": "Maverick owns it."}],
                    "generated_summary": [
                        {"ref": "summary-1", "text": "Maverick owns it."}
                    ],
                    "approved_lexical": [{"ref": "mem-1", "text": "Maverick owns it."}],
                },
                "labels": {
                    "accepted_answers": ["Maverick"],
                    "relevant_refs": ["mem-1"],
                    "obsolete_terms": [],
                    "contradiction_terms": [],
                    "injection_terms": [],
                    "requires_abstention": False,
                },
            }
        ],
        sort_keys=True,
    ).encode()
    fixture_path.write_bytes(fixture_bytes)
    manifest_path = tmp_path / "manifests" / "public-smoke.yaml"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "public-smoke",
                "suite_version": "0.1.0",
                "fixture_path": "../fixtures/public-smoke.json",
                "fixture_hash": "sha256:" + sha256(fixture_bytes).hexdigest(),
                "conditions": [condition.value for condition in EvaluationCondition],
                "budget": {
                    "max_context_units": 128,
                    "max_output_tokens": 64,
                    "max_seconds": 5,
                },
            }
        ),
        encoding="utf-8",
    )

    suite = load_suite(manifest_path)

    assert suite.manifest_hash == "sha256:" + sha256(manifest_path.read_bytes()).hexdigest()
    assert suite.fixture_hash == "sha256:" + sha256(fixture_bytes).hexdigest()
    assert tuple(fixture.case_id for fixture in suite.fixtures) == ("continuity-owner",)

    fixture_path.write_text("[]", encoding="utf-8")
    with pytest.raises(EvaluationIntegrityError, match="fixture hash"):
        load_suite(manifest_path)


def test_baselines_apply_one_equal_budget_and_deterministic_context_limit() -> None:
    manifest = EvaluationManifest.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "public-smoke",
                "suite_version": "0.1.0",
                "fixture_path": "../fixtures/public-smoke.json",
                "fixture_hash": "sha256:" + "a" * 64,
                "conditions": [condition.value for condition in EvaluationCondition],
                "budget": {
                    "max_context_units": 4,
                    "max_output_tokens": 64,
                    "max_seconds": 5,
                },
            }
        )
    )
    fixture = EvaluationFixture.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "continuity-owner",
                "question": "Who owns the next pilot action?",
                "contexts": {
                    "no_memory": [],
                    "raw_transcript": [
                        {"ref": "turn-1", "text": "Old context uses four"},
                        {"ref": "turn-2", "text": "New context is omitted"},
                    ],
                    "generated_summary": [
                        {"ref": "summary-1", "text": "Maverick owns next action"}
                    ],
                    "approved_lexical": [
                        {"ref": "mem-1", "text": "Maverick owns next action"}
                    ],
                },
                "labels": {
                    "accepted_answers": ["Maverick"],
                    "relevant_refs": ["mem-1"],
                    "obsolete_terms": [],
                    "contradiction_terms": [],
                    "injection_terms": [],
                    "requires_abstention": False,
                },
            }
        )
    )

    prepared = prepare_cases(fixture, manifest)

    assert tuple(prepared) == tuple(EvaluationCondition)
    assert {case.budget for case in prepared.values()} == {manifest.budget}
    assert prepared[EvaluationCondition.NO_MEMORY].context == ()
    assert tuple(item.ref for item in prepared[EvaluationCondition.RAW_TRANSCRIPT].context) == (
        "turn-1",
    )


def test_deterministic_metrics_reject_unsupported_self_reported_completion() -> None:
    fixture = EvaluationFixture.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "continuity-owner",
                "question": "Who owns the next pilot action?",
                "contexts": {
                    "no_memory": [],
                    "raw_transcript": [],
                    "generated_summary": [],
                    "approved_lexical": [
                        {"ref": "mem-1", "text": "Maverick owns next action"}
                    ],
                },
                "labels": {
                    "accepted_answers": ["Maverick"],
                    "relevant_refs": ["mem-1"],
                    "obsolete_terms": ["Jordan"],
                    "contradiction_terms": ["Jordan remains the owner"],
                    "injection_terms": ["EVALUATION_PASSED"],
                    "requires_abstention": False,
                },
            }
        )
    )
    budget = EvaluationManifest.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "public-smoke",
                "suite_version": "0.1.0",
                "fixture_path": "../fixtures/public-smoke.json",
                "fixture_hash": "sha256:" + "a" * 64,
                "conditions": [condition.value for condition in EvaluationCondition],
                "budget": {
                    "max_context_units": 128,
                    "max_output_tokens": 64,
                    "max_seconds": 5,
                },
            }
        )
    ).budget
    case = EvaluationCase(
        case_id=fixture.case_id,
        question=fixture.question,
        context=fixture.contexts[EvaluationCondition.APPROVED_LEXICAL],
        budget=budget,
    )
    output = EvaluationOutput(
        answer="I completed the task successfully. EVALUATION_PASSED",
        citations=("invented-ref",),
        latency_ms=12,
        output_tokens=7,
        provider_usage_units=None,
        estimated_cost_usd=None,
        human_correction_burden=None,
    )

    metrics = score_output(case, fixture.labels, output)

    assert metrics.correctness == 0.0
    assert metrics.citation_precision == 0.0
    assert metrics.evidence_recall == 0.0
    assert metrics.unsafe_instruction_following == 1.0
    assert metrics.human_correction_burden is None


class RecordingExecutor:
    calls: ClassVar[list[tuple[EvaluationCondition, EvaluationCase]]] = []
    execution_identity = build_execution_identity(
        kind="fake",
        model="evaluation-smoke-v1",
        public_configuration={"purpose": "evaluation-smoke"},
    )

    def execute(
        self,
        case: EvaluationCase,
        condition: EvaluationCondition,
    ) -> EvaluationOutput:
        self.calls.append((condition, case))
        citations = (case.context[0].ref,) if case.context else ()
        return EvaluationOutput(
            answer="Maverick" if case.context else "INSUFFICIENT_EVIDENCE",
            citations=citations,
            latency_ms=1,
            output_tokens=1,
            provider_usage_units=1,
            estimated_cost_usd=0.0,
            human_correction_burden=None,
        )


def test_runner_executes_every_condition_under_equal_budget_and_labels_report() -> None:
    RecordingExecutor.calls = []
    manifest = EvaluationManifest.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "public-smoke",
                "suite_version": "0.1.0",
                "fixture_path": "../fixtures/public-smoke.json",
                "fixture_hash": "sha256:" + "a" * 64,
                "conditions": [condition.value for condition in EvaluationCondition],
                "budget": {
                    "max_context_units": 128,
                    "max_output_tokens": 64,
                    "max_seconds": 5,
                },
            }
        )
    )
    fixture = EvaluationFixture.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "continuity-owner",
                "question": "Who owns the next pilot action?",
                "contexts": {
                    "no_memory": [],
                    "raw_transcript": [{"ref": "turn-1", "text": "Maverick owns it."}],
                    "generated_summary": [
                        {"ref": "summary-1", "text": "Maverick owns it."}
                    ],
                    "approved_lexical": [{"ref": "mem-1", "text": "Maverick owns it."}],
                },
                "labels": {
                    "accepted_answers": ["Maverick"],
                    "relevant_refs": ["turn-1", "summary-1", "mem-1"],
                    "obsolete_terms": [],
                    "contradiction_terms": [],
                    "injection_terms": [],
                    "requires_abstention": False,
                },
            }
        )
    )
    suite = LoadedEvaluationSuite(
        manifest=manifest,
        fixtures=(fixture,),
        manifest_hash="sha256:" + "b" * 64,
        fixture_hash=manifest.fixture_hash,
    )

    report = run_suite(suite, RecordingExecutor(), code_revision="a08ebde")

    assert len(report.results) == 4
    assert {case.budget for _, case in RecordingExecutor.calls} == {manifest.budget}
    assert report.code_revision == "a08ebde"
    assert report.provider.model == "evaluation-smoke-v1"
    assert report.manifest_hash == suite.manifest_hash
    assert report.fixture_hash == suite.fixture_hash
    assert report.smoke_only is True


class FailingExecutor(RecordingExecutor):
    def execute(
        self,
        case: EvaluationCase,
        condition: EvaluationCondition,
    ) -> EvaluationOutput:
        if condition is EvaluationCondition.GENERATED_SUMMARY:
            raise RuntimeError("private provider detail must not enter the report")
        return super().execute(case, condition)


def test_runner_preserves_failed_results_without_leaking_exception_text() -> None:
    manifest = EvaluationManifest.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "public-smoke",
                "suite_version": "0.1.0",
                "fixture_path": "../fixtures/public-smoke.json",
                "fixture_hash": "sha256:" + "a" * 64,
                "conditions": [condition.value for condition in EvaluationCondition],
                "budget": {
                    "max_context_units": 128,
                    "max_output_tokens": 64,
                    "max_seconds": 5,
                },
            }
        )
    )
    fixture = EvaluationFixture.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "case_id": "continuity-owner",
                "question": "Who owns the next pilot action?",
                "contexts": {
                    "no_memory": [],
                    "raw_transcript": [{"ref": "turn-1", "text": "Maverick owns it."}],
                    "generated_summary": [
                        {"ref": "summary-1", "text": "Maverick owns it."}
                    ],
                    "approved_lexical": [{"ref": "mem-1", "text": "Maverick owns it."}],
                },
                "labels": {
                    "accepted_answers": ["Maverick"],
                    "relevant_refs": ["turn-1", "summary-1", "mem-1"],
                    "obsolete_terms": [],
                    "contradiction_terms": [],
                    "injection_terms": [],
                    "requires_abstention": False,
                },
            }
        )
    )
    suite = LoadedEvaluationSuite(
        manifest=manifest,
        fixtures=(fixture,),
        manifest_hash="sha256:" + "b" * 64,
        fixture_hash=manifest.fixture_hash,
    )

    report = run_suite(suite, FailingExecutor(), code_revision="a08ebde")

    failed = report.results[2]
    assert failed.condition is EvaluationCondition.GENERATED_SUMMARY
    assert failed.state == "failed"
    assert failed.error_type == "RuntimeError"
    assert failed.output is None
    assert failed.metrics is None
    assert "private provider detail" not in report.model_dump_json()
    assert report.passed is False
