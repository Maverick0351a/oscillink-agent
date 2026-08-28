from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

SCHEMA_ROOT = Path(__file__).parents[2] / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_ROOT / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate(name: str, instance: dict[str, Any]) -> None:
    Draft202012Validator(load_schema(name), format_checker=FormatChecker()).validate(instance)


def complete_event() -> dict[str, Any]:
    return {
        "id": "evt_01J00000000000000000000000",
        "schema_version": 1,
        "session_id": "ses_01J00000000000000000000000",
        "run_id": "run_01J00000000000000000000000",
        "task_id": "tsk_01J00000000000000000000000",
        "actor": {"id": "human_maverick", "type": "human"},
        "event_type": "observation",
        "observed_at": "2026-08-27T18:45:00Z",
        "recorded_at": "2026-08-27T18:45:01Z",
        "payload_hash": "sha256:" + "a" * 64,
        "artifact_refs": ["sha256:" + "b" * 64],
        "causal_parent_ids": [],
        "trust_class": "human_verified",
        "sensitivity": "private",
        "payload": {"text": "Oscillink Agent project approved."},
    }


def test_event_schema_accepts_complete_event() -> None:
    validate("event.schema.json", complete_event())


def test_event_schema_requires_model_provenance_for_model_calls() -> None:
    event = complete_event()
    event["event_type"] = "model_call"

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def complete_context_manifest() -> dict[str, Any]:
    return {
        "id": "ctx_01J00000000000000000000000",
        "schema_version": 1,
        "task_id": "tsk_01J00000000000000000000000",
        "compiled_at": "2026-08-27T18:50:00Z",
        "token_budget": 8192,
        "total_token_count": 512,
        "policy_hash": "sha256:" + "c" * 64,
        "items": [
            {
                "record_id": "clm_01J00000000000000000000000",
                "content_hash": "sha256:" + "d" * 64,
                "inclusion_reason": "Approved project outcome is required for task orientation.",
                "trust_class": "human_verified",
                "status": "approved",
                "token_count": 64,
                "source_refs": ["evt_01J00000000000000000000000"],
            }
        ],
    }


def test_context_manifest_schema_accepts_cited_items() -> None:
    validate("context-manifest.schema.json", complete_context_manifest())


def complete_capability_grant() -> dict[str, Any]:
    return {
        "id": "grt_01J00000000000000000000000",
        "schema_version": 1,
        "subject_actor_id": "model_qwen3_14b",
        "capability": "file.read",
        "resource": {
            "root": "C:/Users/Maverick/Projects/oscillink-agent",
            "target": "README.md",
        },
        "issued_at": "2026-08-27T18:55:00Z",
        "expires_at": "2026-08-27T19:00:00Z",
        "issued_by": "human_maverick",
        "authorization_event_id": "evt_01J00000000000000000000000",
        "max_uses": 1,
        "constraints": {
            "max_bytes": 65536,
            "allowed_extensions": [".md"],
            "network_allowed": False,
        },
    }


def test_capability_grant_schema_accepts_single_use_file_read() -> None:
    validate("capability-grant.schema.json", complete_capability_grant())


def complete_benchmark_manifest() -> dict[str, Any]:
    return {
        "id": "bmk_01J00000000000000000000000",
        "schema_version": 1,
        "name": "oscillink-agent-public-smoke",
        "version": "0.1.0",
        "created_at": "2026-08-27T19:00:00Z",
        "task_set_hash": "sha256:" + "e" * 64,
        "hidden_labels": "external",
        "conditions": ["no_memory", "raw_transcript", "fts5_evidence"],
        "metrics": [
            {"name": "task_success", "direction": "maximize"},
            {"name": "critical_provenance_failures", "direction": "minimize"},
        ],
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


def test_benchmark_manifest_schema_accepts_frozen_external_evaluation() -> None:
    validate("benchmark-manifest.schema.json", complete_benchmark_manifest())


@pytest.mark.parametrize(
    "schema_name",
    [
        "event.schema.json",
        "context-manifest.schema.json",
        "capability-grant.schema.json",
        "benchmark-manifest.schema.json",
    ],
)
def test_schema_is_valid_draft_2020_12(schema_name: str) -> None:
    Draft202012Validator.check_schema(load_schema(schema_name))


def test_event_schema_rejects_unknown_trust_class() -> None:
    event = complete_event()
    event["trust_class"] = "implicitly_trusted"

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_capability_grant_rejects_undeclared_permission_fields() -> None:
    grant = complete_capability_grant()
    grant["allow_shell"] = True

    with pytest.raises(ValidationError):
        validate("capability-grant.schema.json", grant)
