from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypeVar

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import BaseModel, ValidationError

from oscillink_agent.domain.capabilities import CapabilityGrant
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.domain.events import Event
from oscillink_agent.domain.memory import MemoryClaim

SCHEMA_ROOT = Path(__file__).parents[2] / "schemas"
ModelT = TypeVar("ModelT", bound=BaseModel)


def load_schema(name: str) -> dict[str, object]:
    with (SCHEMA_ROOT / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def from_json(model: type[ModelT], data: dict[str, object]) -> ModelT:
    return model.model_validate_json(json.dumps(data))


def canonical_payload_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def event_data() -> dict[str, object]:
    payload: dict[str, object] = {"text": "Oscillink Agent project approved."}
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
        "payload_hash": canonical_payload_hash(payload),
        "artifact_refs": ["sha256:" + "b" * 64],
        "causal_parent_ids": [],
        "trust_class": "human_verified",
        "sensitivity": "private",
        "payload": payload,
    }


def test_event_round_trips_through_schema_and_is_frozen() -> None:
    event = from_json(Event, event_data())
    dumped = event.model_dump(mode="json")
    schema = load_schema("event.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(dumped)

    with pytest.raises(ValidationError):
        event.event_type = "message"  # type: ignore[misc]


def test_event_rejects_payload_hash_mismatch() -> None:
    data = event_data()
    data["payload_hash"] = "sha256:" + "0" * 64

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_payloads_with_too_many_properties() -> None:
    data = event_data()
    payload: dict[str, object] = {f"field_{index}": index for index in range(65)}
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_oversized_nested_payload_arrays() -> None:
    data = event_data()
    payload: dict[str, object] = {"items": list(range(65))}
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_oversized_nested_payload_objects() -> None:
    data = event_data()
    payload: dict[str, object] = {
        "nested": {f"field_{index}": index for index in range(65)}
    }
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_payloads_nested_beyond_two_levels() -> None:
    data = event_data()
    payload: dict[str, object] = {
        "outer": {"middle": {"inner": {"value": 1}}}
    }
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_oversized_payload_strings() -> None:
    data = event_data()
    payload: dict[str, object] = {"text": "x" * 16_385}
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_oversized_payload_property_names() -> None:
    data = event_data()
    payload: dict[str, object] = {"k" * 129: "value"}
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_model_requires_model_provenance_for_model_calls() -> None:
    data = event_data()
    data["event_type"] = "model_call"

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_model_actor_requires_model_provenance() -> None:
    data = event_data()
    data["actor"] = {"id": "model_qwen3_14b", "type": "model"}
    data["trust_class"] = "model_generated"

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_model_actor_cannot_claim_human_verified_trust() -> None:
    data = event_data()
    data["actor"] = {"id": "model_qwen3_14b", "type": "model"}
    data["model"] = {
        "provider": "ollama",
        "name": "qwen3:14b",
        "configuration_hash": "sha256:" + "9" * 64,
    }

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_payload_is_deeply_immutable() -> None:
    event = from_json(Event, event_data())

    with pytest.raises(TypeError):
        event.payload["content"] = "tampered"  # type: ignore[index]


def test_event_payload_rejects_base_dict_mutation_bypass() -> None:
    event = from_json(Event, event_data())

    with pytest.raises(TypeError):
        dict.__setitem__(event.payload, "content", "tampered")


def test_event_payload_nested_containers_are_immutable() -> None:
    data = event_data()
    payload: dict[str, object] = {"nested": {"items": ["original"]}}
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)
    event = from_json(Event, data)

    with pytest.raises(TypeError):
        event.payload["nested"]["items"][0] = "tampered"


def test_event_rejects_duplicate_provenance_references() -> None:
    data = event_data()
    digest = "sha256:" + "b" * 64
    data["artifact_refs"] = [digest, digest]

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_duplicate_causal_parents() -> None:
    data = event_data()
    parent_id = "evt_01J00000000000000000000001"
    data["causal_parent_ids"] = [parent_id, parent_id]

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_itself_as_a_causal_parent() -> None:
    data = event_data()
    data["causal_parent_ids"] = [data["id"]]

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_recording_before_observation() -> None:
    data = event_data()
    data["recorded_at"] = "2026-08-27T18:44:59Z"

    with pytest.raises(ValidationError):
        from_json(Event, data)


def context_manifest_data() -> dict[str, object]:
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
                "inclusion_reason": "Approved state is required for task orientation.",
                "trust_class": "human_verified",
                "status": "approved",
                "token_count": 64,
                "source_refs": ["evt_01J00000000000000000000000"],
            }
        ],
    }


def test_context_manifest_round_trips_through_schema() -> None:
    manifest = from_json(ContextManifest, context_manifest_data())
    dumped = manifest.model_dump(mode="json")
    schema = load_schema("context-manifest.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(dumped)


def test_context_manifest_rejects_token_budget_overrun() -> None:
    data = context_manifest_data()
    data["token_budget"] = 128
    data["total_token_count"] = 129

    with pytest.raises(ValidationError):
        from_json(ContextManifest, data)


def test_context_manifest_requires_exact_token_accounting() -> None:
    data = context_manifest_data()
    data["total_token_count"] = 99

    with pytest.raises(ValidationError):
        from_json(ContextManifest, data)


def test_context_item_rejects_duplicate_source_references() -> None:
    data = context_manifest_data()
    item = data["items"][0]  # type: ignore[index]
    source_id = "evt_01J00000000000000000000000"
    item["source_refs"] = [source_id, source_id]

    with pytest.raises(ValidationError):
        from_json(ContextManifest, data)


def test_context_manifest_rejects_duplicate_items() -> None:
    data = context_manifest_data()
    item = data["items"][0]  # type: ignore[index]
    data["items"] = [item, item]
    data["total_token_count"] = 128

    with pytest.raises(ValidationError):
        from_json(ContextManifest, data)


def test_context_manifest_rejects_numeric_strings_at_json_boundary() -> None:
    data = context_manifest_data()
    data["token_budget"] = "8192"

    with pytest.raises(ValidationError):
        ContextManifest.model_validate_json(json.dumps(data))


def capability_grant_data() -> dict[str, object]:
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


def test_capability_grant_round_trips_through_schema() -> None:
    grant = from_json(CapabilityGrant, capability_grant_data())
    dumped = grant.model_dump(mode="json")
    schema = load_schema("capability-grant.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(dumped)


def test_capability_grant_rejects_zero_lifetime() -> None:
    data = capability_grant_data()
    data["valid_for_seconds"] = 0

    with pytest.raises(ValidationError):
        from_json(CapabilityGrant, data)


def test_capability_grant_rejects_duplicate_extensions() -> None:
    data = capability_grant_data()
    constraints = data["constraints"]  # type: ignore[assignment]
    constraints["allowed_extensions"] = [".md", ".md"]

    with pytest.raises(ValidationError):
        from_json(CapabilityGrant, data)


def test_capability_grant_rejects_path_traversal() -> None:
    data = capability_grant_data()
    resource = dict(data["resource"])  # type: ignore[arg-type]
    resource["target"] = "../secrets.txt"
    data["resource"] = resource

    with pytest.raises(ValidationError):
        from_json(CapabilityGrant, data)


def test_capability_grant_rejects_windows_device_names() -> None:
    data = capability_grant_data()
    resource = dict(data["resource"])  # type: ignore[arg-type]
    resource["target"] = "CON"
    data["resource"] = resource

    with pytest.raises(ValidationError):
        from_json(CapabilityGrant, data)


def test_capability_grant_rejects_targets_with_trailing_dots() -> None:
    data = capability_grant_data()
    resource = dict(data["resource"])  # type: ignore[arg-type]
    resource["target"] = "reports/result."
    data["resource"] = resource

    with pytest.raises(ValidationError):
        from_json(CapabilityGrant, data)


@pytest.mark.parametrize(
    ("target", "accepted"),
    [
        ("README.md", True),
        ("docs/build-plan.md", True),
        ("../secrets.txt", False),
        (r"..\secrets.txt", False),
        ("/etc/passwd", False),
        ("C:/secrets.txt", False),
        ("C:secrets.txt", False),
        (r"\\server\share\secret.txt", False),
        (r"\\?\C:\secret.txt", False),
        ("report.txt:alternate", False),
        ("CON", False),
        ("nested/NUL.txt", False),
        ("reports/result.", False),
    ],
)
def test_capability_target_has_schema_model_parity(target: str, accepted: bool) -> None:
    data = capability_grant_data()
    resource = dict(data["resource"])  # type: ignore[arg-type]
    resource["target"] = target
    data["resource"] = resource

    try:
        from_json(CapabilityGrant, data)
    except ValidationError:
        model_accepted = False
    else:
        model_accepted = True

    try:
        Draft202012Validator(
            load_schema("capability-grant.schema.json"),
            format_checker=FormatChecker(),
        ).validate(data)
    except SchemaValidationError:
        schema_accepted = False
    else:
        schema_accepted = True

    assert model_accepted is accepted
    assert schema_accepted is accepted


def memory_claim_data() -> dict[str, object]:
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
        "content_hash": "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "asserted_by": "human_maverick",
        "review_state": "approved",
        "sensitivity": "private",
    }


def test_memory_claim_preserves_valid_time_separately_from_record_time() -> None:
    claim = from_json(MemoryClaim, memory_claim_data())

    assert claim.valid_from is not None
    assert claim.valid_from < claim.recorded_at


def test_memory_claim_round_trips_through_schema() -> None:
    claim = from_json(MemoryClaim, memory_claim_data())

    schema = load_schema("memory-claim.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        claim.model_dump(mode="json")
    )


def test_memory_claim_rejects_content_hash_mismatch() -> None:
    data = memory_claim_data()
    data["content_hash"] = "sha256:" + "0" * 64

    with pytest.raises(ValidationError):
        from_json(MemoryClaim, data)


def test_memory_claim_rejects_duplicate_source_references() -> None:
    data = memory_claim_data()
    source_ref = data["source_refs"][0]  # type: ignore[index]
    data["source_refs"] = [source_ref, source_ref]

    with pytest.raises(ValidationError):
        from_json(MemoryClaim, data)


def test_memory_claim_rejects_reversed_validity_interval() -> None:
    data = memory_claim_data()
    data["valid_until"] = "2026-07-31T00:00:00Z"

    with pytest.raises(ValidationError):
        from_json(MemoryClaim, data)
