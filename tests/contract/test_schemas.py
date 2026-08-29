from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

SCHEMA_ROOT = Path(__file__).parents[2] / "schemas"
FRONTEND_CONTEXT_FIXTURE = (
    Path(__file__).parents[2]
    / "apps"
    / "web"
    / "src"
    / "fixtures"
    / "persistedContextManifest.json"
)


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


@pytest.mark.parametrize(
    ("actor_id", "actor_type"),
    [
        ("tool_fetcher", "human"),
        ("human_maverick", "model"),
        ("system_runtime", "tool"),
        ("model_qwen3", "system"),
    ],
)
def test_event_schema_rejects_actor_id_type_mismatch(
    actor_id: str, actor_type: str
) -> None:
    actor_schema = load_schema("event.schema.json")["properties"]["actor"]

    with pytest.raises(ValidationError):
        Draft202012Validator(actor_schema).validate({"id": actor_id, "type": actor_type})


def test_event_schema_requires_model_provenance_for_model_calls() -> None:
    event = complete_event()
    event["event_type"] = "model_call"

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_requires_model_provenance_for_model_actors() -> None:
    event = complete_event()
    event["actor"] = {"id": "model_qwen3_14b", "type": "model"}
    event["trust_class"] = "model_generated"

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_prevents_model_actor_from_claiming_human_trust() -> None:
    event = complete_event()
    event["actor"] = {"id": "model_qwen3_14b", "type": "model"}
    event["model"] = {
        "provider": "ollama",
        "name": "qwen3:14b",
        "configuration_hash": "sha256:" + "9" * 64,
    }

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_rejects_model_identity_on_unrelated_human_event() -> None:
    event = complete_event()
    event["model"] = {
        "provider": "ollama",
        "name": "qwen3:14b",
        "configuration_hash": "sha256:" + "9" * 64,
    }

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_rejects_numbers_outside_rfc_8785_safe_range() -> None:
    event = complete_event()
    event["payload"] = {"value": 9_007_199_254_740_992}

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_rejects_payloads_with_too_many_properties() -> None:
    event = complete_event()
    event["payload"] = {f"field_{index}": index for index in range(65)}

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_rejects_oversized_nested_payload_arrays() -> None:
    event = complete_event()
    event["payload"] = {"items": list(range(65))}

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_rejects_payloads_nested_beyond_two_levels() -> None:
    event = complete_event()
    event["payload"] = {"outer": {"middle": {"inner": {"value": 1}}}}

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_rejects_oversized_payload_strings() -> None:
    event = complete_event()
    event["payload"] = {"text": "x" * 16_385}

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def test_event_schema_rejects_oversized_payload_property_names() -> None:
    event = complete_event()
    event["payload"] = {"k" * 129: "value"}

    with pytest.raises(ValidationError):
        validate("event.schema.json", event)


def complete_context_manifest() -> dict[str, Any]:
    return {
        "id": "ctx_01J00000000000000000000000",
        "schema_version": 1,
        "task_id": "tsk_01J00000000000000000000000",
        "compiled_at": "2026-08-27T18:50:00Z",
        "token_budget": 8192,
        "total_token_count": 64,
        "policy_hash": "sha256:" + "c" * 64,
        "items": [
            {
                "record_id": "clm_01J00000000000000000000000",
                "content_hash": "sha256:" + "d" * 64,
                "title": "Approved project outcome",
                "category": "governance",
                "domains": ["software"],
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


def test_frontend_persisted_context_fixture_matches_wire_schema() -> None:
    with FRONTEND_CONTEXT_FIXTURE.open(encoding="utf-8") as handle:
        fixture = json.load(handle)

    validate("context-manifest.schema.json", fixture)


def complete_capability_grant() -> dict[str, Any]:
    return {
        "id": "grt_01J00000000000000000000000",
        "schema_version": 1,
        "subject_actor_id": "model_qwen3_14b",
        "capability": "file.read",
        "resource": {
            "scope_id": "repo_oscillink_agent",
            "target": "README.md",
        },
        "issued_at": "2026-08-27T18:55:00Z",
        "valid_for_seconds": 300,
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


def test_capability_grant_schema_rejects_windows_device_names() -> None:
    grant = complete_capability_grant()
    grant["resource"]["target"] = "CON"

    with pytest.raises(ValidationError):
        validate("capability-grant.schema.json", grant)


def test_capability_grant_schema_rejects_targets_with_trailing_dots() -> None:
    grant = complete_capability_grant()
    grant["resource"]["target"] = "reports/result."

    with pytest.raises(ValidationError):
        validate("capability-grant.schema.json", grant)


def complete_benchmark_manifest() -> dict[str, Any]:
    return {
        "id": "bmk_01J00000000000000000000000",
        "schema_version": 1,
        "name": "oscillink-agent-public-smoke",
        "version": "0.1.0",
        "created_at": "2026-08-27T19:00:00Z",
        "task_set_hash": "sha256:" + "e" * 64,
        "hidden_labels": "external",
        "conditions": [
            "no_memory",
            "raw_transcript",
            "hand_markdown",
            "generated_summary",
            "fts5_evidence",
            "provenance_evidence",
        ],
        "metrics": {
            "correctness": "maximize",
            "citation_precision": "maximize",
            "evidence_recall": "maximize",
            "temporal_accuracy": "maximize",
            "obsolete_memory_reuse": "minimize",
            "contradiction_detection": "maximize",
            "abstention": "maximize",
            "unsafe_instruction_following": "minimize",
            "latency": "minimize",
            "tokens": "minimize",
            "correction_burden": "minimize",
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
        "threat_cases": [
            "memory_poisoning",
            "stale_state",
            "permission_escalation",
            "cross_scope_retrieval",
            "unsupported_completion",
            "secret_exposure",
            "contradiction_handling",
            "provenance_omission",
        ],
    }


def test_benchmark_manifest_schema_accepts_frozen_external_evaluation() -> None:
    validate("benchmark-manifest.schema.json", complete_benchmark_manifest())


def complete_memory_claim() -> dict[str, Any]:
    content = "Oscillink Agent uses a local open-weight model first."
    return {
        "id": "clm_01J00000000000000000000000",
        "schema_version": 1,
        "epistemic_class": "user_assertion",
        "status": "supported",
        "subject_id": "project_oscillink_agent",
        "content": content,
        "valid_from": "2026-08-01T00:00:00Z",
        "valid_until": None,
        "recorded_at": "2026-08-27T19:05:00Z",
        "source_refs": ["evt_01J00000000000000000000000"],
        "content_hash": "sha256:" + "f" * 64,
        "asserted_by": "human_maverick",
        "review_state": "approved",
        "review_event_id": "evt_01J00000000000000000000001",
        "sensitivity": "private",
    }


def test_memory_claim_schema_accepts_bitemporal_claim() -> None:
    validate("memory-claim.schema.json", complete_memory_claim())


@pytest.mark.parametrize(
    "schema_name",
    [
        "event.schema.json",
        "context-manifest.schema.json",
        "capability-grant.schema.json",
        "benchmark-manifest.schema.json",
        "memory-claim.schema.json",
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
