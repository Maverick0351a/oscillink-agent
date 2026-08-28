from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from oscillink_agent.domain.capabilities import CapabilityGrant
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.domain.events import Event
from oscillink_agent.domain.memory import MemoryClaim

SCHEMA_ROOT = Path(__file__).parents[2] / "schemas"


def load_schema(name: str) -> dict[str, object]:
    with (SCHEMA_ROOT / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def event_data() -> dict[str, object]:
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


def test_event_round_trips_through_schema_and_is_frozen() -> None:
    event = Event.model_validate(event_data())
    dumped = event.model_dump(mode="json", exclude_none=True)
    schema = load_schema("event.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(dumped)

    with pytest.raises(ValidationError):
        event.event_type = "message"  # type: ignore[misc]


def test_event_model_requires_model_provenance_for_model_calls() -> None:
    data = event_data()
    data["event_type"] = "model_call"

    with pytest.raises(ValidationError):
        Event.model_validate(data)


def context_manifest_data() -> dict[str, object]:
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
                "inclusion_reason": "Approved state is required for task orientation.",
                "trust_class": "human_verified",
                "status": "approved",
                "token_count": 64,
                "source_refs": ["evt_01J00000000000000000000000"],
            }
        ],
    }


def test_context_manifest_round_trips_through_schema() -> None:
    manifest = ContextManifest.model_validate(context_manifest_data())
    dumped = manifest.model_dump(mode="json")
    schema = load_schema("context-manifest.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(dumped)


def test_context_manifest_rejects_token_budget_overrun() -> None:
    data = context_manifest_data()
    data["token_budget"] = 128
    data["total_token_count"] = 129

    with pytest.raises(ValidationError):
        ContextManifest.model_validate(data)


def capability_grant_data() -> dict[str, object]:
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


def test_capability_grant_round_trips_through_schema() -> None:
    grant = CapabilityGrant.model_validate(capability_grant_data())
    dumped = grant.model_dump(mode="json")
    schema = load_schema("capability-grant.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(dumped)


def test_capability_grant_rejects_non_future_expiration() -> None:
    data = capability_grant_data()
    data["expires_at"] = data["issued_at"]

    with pytest.raises(ValidationError):
        CapabilityGrant.model_validate(data)


def test_capability_grant_rejects_path_traversal() -> None:
    data = capability_grant_data()
    resource = dict(data["resource"])  # type: ignore[arg-type]
    resource["target"] = "../secrets.txt"
    data["resource"] = resource

    with pytest.raises(ValidationError):
        CapabilityGrant.model_validate(data)


def memory_claim_data() -> dict[str, object]:
    return {
        "id": "clm_01J00000000000000000000000",
        "schema_version": 1,
        "epistemic_class": "user_assertion",
        "status": "supported",
        "subject_id": "project_oscillink_agent",
        "content": "Oscillink Agent uses a local open-weight model first.",
        "valid_from": "2026-08-01T00:00:00Z",
        "valid_until": None,
        "recorded_at": "2026-08-27T19:05:00Z",
        "source_refs": ["evt_01J00000000000000000000000"],
        "content_hash": "sha256:" + "f" * 64,
        "asserted_by": "human_maverick",
        "review_state": "approved",
        "sensitivity": "private",
    }


def test_memory_claim_preserves_valid_time_separately_from_record_time() -> None:
    claim = MemoryClaim.model_validate(memory_claim_data())

    assert claim.valid_from is not None
    assert claim.valid_from < claim.recorded_at


def test_memory_claim_rejects_reversed_validity_interval() -> None:
    data = memory_claim_data()
    data["valid_until"] = "2026-07-31T00:00:00Z"

    with pytest.raises(ValidationError):
        MemoryClaim.model_validate(data)
