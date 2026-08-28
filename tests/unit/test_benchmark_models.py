from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import ValidationError

from oscillink_agent.domain.benchmarks import BenchmarkManifest

SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "benchmark-manifest.schema.json"


def benchmark_manifest_data() -> dict[str, object]:
    return {
        "id": "bmk_01J00000000000000000000000",
        "schema_version": 1,
        "name": "oscillink-agent-public-smoke",
        "version": "0.1.0",
        "created_at": "2026-08-27T19:00:00Z",
        "task_set_hash": "sha256:" + "e" * 64,
        "hidden_labels": "external",
        "conditions": ["no_memory", "raw_transcript", "fts5_evidence"],
        "metrics": {
            "task_success": "maximize",
            "critical_provenance_failures": "minimize",
        },
        "budgets": {
            "max_tokens": 8192,
            "max_seconds": 120,
            "max_tool_calls": 4,
            "max_retries": 1,
        },
        "promotion_gate": {
            "max_critical_failures": 0,
            "require_equal_budgets": True,
            "require_external_verification": True,
        },
        "threat_cases": ["memory_poisoning", "stale_state", "permission_escalation"],
    }


def test_benchmark_manifest_round_trips_through_schema_and_is_frozen() -> None:
    data = benchmark_manifest_data()
    manifest = BenchmarkManifest.model_validate_json(json.dumps(data))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        manifest.model_dump(mode="json")
    )

    with pytest.raises(ValidationError):
        manifest.name = "changed"  # type: ignore[misc]


def test_benchmark_metrics_are_immutable() -> None:
    manifest = BenchmarkManifest.model_validate_json(json.dumps(benchmark_manifest_data()))

    with pytest.raises(TypeError):
        manifest.metrics["task_success"] = "minimize"  # type: ignore[assignment]


def test_benchmark_rejects_duplicate_conditions() -> None:
    data = benchmark_manifest_data()
    data["conditions"] = ["no_memory", "no_memory"]

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate_json(json.dumps(data))


def test_benchmark_rejects_duplicate_threat_cases() -> None:
    data = benchmark_manifest_data()
    data["threat_cases"] = ["memory_poisoning", "memory_poisoning"]

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate_json(json.dumps(data))


def test_benchmark_requires_at_least_one_threat_case_at_both_boundaries() -> None:
    data = benchmark_manifest_data()
    data["threat_cases"] = []
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate_json(json.dumps(data))
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(schema).validate(data)


def test_benchmark_rejects_ambiguous_metric_list_at_both_boundaries() -> None:
    data = benchmark_manifest_data()
    data["metrics"] = [
        {"name": "task_success", "direction": "maximize"},
        {"name": "task_success", "direction": "minimize"},
    ]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    with pytest.raises(ValidationError):
        BenchmarkManifest.model_validate_json(json.dumps(data))
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(schema).validate(data)
