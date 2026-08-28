from __future__ import annotations

import copy
import hashlib
import io
import json
import pickle
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import TypeVar

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import BaseModel, ValidationError

from oscillink_agent.domain.capabilities import CapabilityGrant
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.domain.events import MAX_INTEROPERABLE_JSON_INTEGER, Actor, Event
from oscillink_agent.domain.events import canonical_payload_hash as domain_payload_hash
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


def test_event_json_loader_rejects_duplicate_object_names() -> None:
    data = event_data()
    payload: dict[str, object] = {"x": 2}
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)
    encoded = json.dumps(data)
    duplicate_payload = '"payload": {"x": 1, "x": 2}'
    encoded = encoded.replace('"payload": {"x": 2}', duplicate_payload)

    with pytest.raises(ValueError, match="duplicate JSON object name"):
        Event.model_validate_json(encoded)


def test_event_payload_hash_uses_rfc_8785_number_canonicalization() -> None:
    expected = "sha256:" + hashlib.sha256(b'{"x":1}').hexdigest()

    assert domain_payload_hash({"x": 1}) == expected
    assert domain_payload_hash({"x": 1.0}) == expected


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


def test_event_rejects_oversized_nested_mapping_payload_objects() -> None:
    event = from_json(Event, event_data())
    data = event.model_dump()
    payload: dict[str, object] = {
        "nested": MappingProxyType({f"field_{index}": index for index in range(65)})
    }
    data["payload"] = payload
    data["payload_hash"] = domain_payload_hash(payload)

    with pytest.raises(ValidationError, match="64 properties"):
        Event.model_validate(data)


def test_event_snapshots_stateful_mapping_once_before_bounds_validation() -> None:
    class StatefulMapping(Mapping[str, object]):
        def __init__(self) -> None:
            self.safe = {"safe": 1}
            self.unsafe = {f"field_{index}": index for index in range(65)}

        def __getitem__(self, key: str) -> object:
            return self.safe[key]

        def __iter__(self):  # type: ignore[no-untyped-def]
            return iter(self.safe)

        def __len__(self) -> int:
            return len(self.safe)

        def items(self):  # type: ignore[no-untyped-def]
            return self.unsafe.items()

    event = from_json(Event, event_data())
    data = event.model_dump()
    payload: dict[str, object] = {"nested": StatefulMapping()}
    data["payload"] = payload
    data["payload_hash"] = domain_payload_hash(payload)

    with pytest.raises(ValidationError, match="64 properties"):
        Event.model_validate(data)


def test_event_rejects_string_subclasses_that_spoof_length() -> None:
    class LiarStr(str):
        def __len__(self) -> int:
            return 1

    event = from_json(Event, event_data())
    data = event.model_dump()
    payload: dict[str, object] = {"text": LiarStr("x" * 16_385)}
    data["payload"] = payload
    data["payload_hash"] = domain_payload_hash(payload)

    with pytest.raises(ValidationError):
        Event.model_validate(data)


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


def test_event_rejects_payload_over_64_kib_in_aggregate() -> None:
    data = event_data()
    payload: dict[str, object] = {f"field_{index}": "x" * 16_384 for index in range(5)}
    data["payload"] = payload
    data["payload_hash"] = canonical_payload_hash(payload)

    with pytest.raises(ValidationError, match="64 KiB"):
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


@pytest.mark.parametrize(
    "invalid_datetime",
    [
        "1990-12-31T23:59:60Z",
        "0000-01-01T00:00:00Z",
        "2026-08-27T18:45:00.1234567Z",
    ],
)
def test_event_datetime_schema_model_boundary_parity(invalid_datetime: str) -> None:
    data = event_data()
    data["observed_at"] = invalid_datetime
    data["recorded_at"] = invalid_datetime
    validator = Draft202012Validator(
        load_schema("event.schema.json"), format_checker=FormatChecker()
    )

    with pytest.raises(ValidationError):
        from_json(Event, data)
    with pytest.raises(SchemaValidationError):
        validator.validate(data)


def test_event_rejects_subminute_timezone_offsets_on_python_ingress() -> None:
    event = from_json(Event, event_data())
    data = event.model_dump()
    subminute_offset = timezone(timedelta(seconds=1))
    data["observed_at"] = datetime(2026, 8, 27, 18, 45, tzinfo=subminute_offset)
    data["recorded_at"] = datetime(2026, 8, 27, 18, 46, tzinfo=subminute_offset)

    with pytest.raises(ValidationError):
        Event.model_validate(data)


def test_event_model_actor_requires_model_provenance() -> None:
    data = event_data()
    data["actor"] = {"id": "model_qwen3_14b", "type": "model"}
    data["trust_class"] = "model_generated"

    with pytest.raises(ValidationError):
        from_json(Event, data)


@pytest.mark.parametrize(
    ("actor_id", "actor_type"),
    [
        ("tool_fetcher", "human"),
        ("human_maverick", "model"),
        ("system_runtime", "tool"),
        ("model_qwen3", "system"),
    ],
)
def test_actor_id_prefix_must_match_actor_type(actor_id: str, actor_type: str) -> None:
    with pytest.raises(ValidationError, match="actor ID prefix"):
        from_json(Actor, {"id": actor_id, "type": actor_type})


@pytest.mark.parametrize(
    ("actor_id", "actor_type"),
    [
        ("human_maverick", "human"),
        ("model_qwen3", "model"),
        ("tool_fetcher", "tool"),
        ("system_runtime", "system"),
    ],
)
def test_actor_id_prefix_matches_actor_type_at_both_boundaries(
    actor_id: str, actor_type: str
) -> None:
    actor = from_json(Actor, {"id": actor_id, "type": actor_type})
    actor_schema = load_schema("event.schema.json")["properties"]["actor"]

    Draft202012Validator(actor_schema).validate(actor.model_dump(mode="json"))


def test_event_rejects_model_identity_on_unrelated_human_event() -> None:
    data = event_data()
    data["model"] = {
        "provider": "ollama",
        "name": "qwen3:14b",
        "configuration_hash": "sha256:" + "9" * 64,
    }

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

    assert isinstance(event.payload, Mapping)
    with pytest.raises(TypeError):
        event.payload["content"] = "tampered"  # type: ignore[index]


def test_event_payload_rejects_base_dict_mutation_bypass() -> None:
    event = from_json(Event, event_data())

    with pytest.raises(TypeError):
        dict.__setitem__(event.payload, "content", "tampered")


def test_event_payload_rejects_object_setattr_storage_bypass() -> None:
    event = from_json(Event, event_data())
    before = event.model_dump(mode="json")

    with pytest.raises((AttributeError, TypeError)):
        object.__setattr__(event.payload, "_items", (("text", "tampered"),))

    assert event.model_dump(mode="json") == before


def test_event_public_instance_dictionary_is_read_only() -> None:
    event = from_json(Event, event_data())
    before = event.model_dump(mode="json")

    with pytest.raises(TypeError):
        event.__dict__["payload_hash"] = "sha256:" + "0" * 64

    assert event.model_dump(mode="json") == before


def test_event_dump_detects_reflective_internal_state_tampering() -> None:
    event = from_json(Event, event_data())
    internal_state = object.__getattribute__(event, "__dict__")
    internal_state["payload_hash"] = "sha256:" + "0" * 64

    with pytest.raises(ValidationError, match="payload_hash"):
        event.model_dump(mode="json")


def test_event_dump_detects_valid_but_changed_internal_state() -> None:
    event = from_json(Event, event_data())
    internal_state = object.__getattribute__(event, "__dict__")
    internal_state["trust_class"] = type(event.trust_class).EXTERNAL_UNTRUSTED

    with pytest.raises(ValueError, match="changed after construction"):
        event.model_dump(mode="json")


def test_event_dump_detects_type_changes_with_identical_json() -> None:
    event = from_json(Event, event_data())
    event_state = object.__getattribute__(event, "__dict__")
    actor_state = object.__getattribute__(event.actor, "__dict__")
    event_state["trust_class"] = event.trust_class.value
    actor_state["type"] = event.actor.type.value
    event_state["artifact_refs"] = list(event.artifact_refs)

    with pytest.raises(ValueError, match="changed after construction"):
        event.model_dump(mode="python")


def test_event_model_copy_revalidates_updates() -> None:
    event = from_json(Event, event_data())

    with pytest.raises(ValidationError):
        event.model_copy(update={"recorded_at": "2026-08-27T18:44:59Z"})


def test_event_model_copy_rejects_lossy_datetime_updates() -> None:
    event = from_json(Event, event_data())
    subminute_offset = timezone(timedelta(seconds=1))

    with pytest.raises(ValidationError):
        event.model_copy(
            update={
                "observed_at": datetime(
                    2026, 8, 27, 18, 45, tzinfo=subminute_offset
                )
            }
        )


@pytest.mark.parametrize("copier", [copy.copy, copy.deepcopy])
def test_event_standard_copy_protocols_revalidate(copier: object) -> None:
    event = from_json(Event, event_data())

    clone = copier(event)  # type: ignore[operator]

    assert clone is not event
    assert clone.model_dump(mode="json") == event.model_dump(mode="json")


def test_event_pickle_round_trip_revalidates() -> None:
    event = from_json(Event, event_data())
    trusted_bytes = io.BytesIO(pickle.dumps(event))

    restored = pickle.Unpickler(trusted_bytes).load()

    assert restored is not event
    assert restored.model_dump(mode="json") == event.model_dump(mode="json")


def test_event_model_construct_cannot_bypass_validation() -> None:
    data = event_data()
    data["recorded_at"] = "2026-08-27T18:44:59Z"

    with pytest.raises(ValidationError):
        Event.model_construct(**data)


def test_event_model_construct_rejects_lossy_datetimes() -> None:
    event = from_json(Event, event_data())
    data = event.model_dump()
    data["observed_at"] = datetime(
        2026, 8, 27, 18, 45, tzinfo=timezone(timedelta(seconds=1))
    )

    with pytest.raises(ValidationError):
        Event.model_construct(**data)


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


def test_event_rejects_whitespace_only_model_identity() -> None:
    data = event_data()
    data["actor"] = {"id": "model_agent", "type": "model"}
    data["trust_class"] = "model_generated"
    data["model"] = {
        "provider": " ",
        "name": "\t",
        "configuration_hash": "sha256:" + "a" * 64,
    }

    with pytest.raises(ValidationError):
        from_json(Event, data)


def test_event_rejects_tool_actor_claiming_human_verification() -> None:
    data = event_data()
    data["actor"] = {"id": "tool_fetcher", "type": "tool"}
    data["trust_class"] = "human_verified"

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


def test_context_manifest_dump_detects_nested_token_tampering() -> None:
    manifest = from_json(ContextManifest, context_manifest_data())
    item_state = object.__getattribute__(manifest.items[0], "__dict__")
    item_state["token_count"] = 10_000

    with pytest.raises(ValidationError, match="token"):
        manifest.model_dump(mode="json")


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


def test_context_manifest_accepts_integral_json_float_as_schema_integer() -> None:
    data = context_manifest_data()
    data["token_budget"] = 8192.0

    manifest = ContextManifest.model_validate_json(json.dumps(data))

    assert manifest.token_budget == 8192


def test_context_integer_bounds_match_schema_and_model() -> None:
    schema = load_schema("context-manifest.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    accepted = context_manifest_data()
    accepted["token_budget"] = MAX_INTEROPERABLE_JSON_INTEGER
    accepted["total_token_count"] = MAX_INTEROPERABLE_JSON_INTEGER
    item = accepted["items"][0]  # type: ignore[index]
    item["token_count"] = MAX_INTEROPERABLE_JSON_INTEGER

    from_json(ContextManifest, accepted)
    validator.validate(accepted)

    for path in ("token_budget", "total_token_count", "item_token_count"):
        rejected = context_manifest_data()
        if path == "item_token_count":
            rejected_item = rejected["items"][0]  # type: ignore[index]
            rejected_item["token_count"] = MAX_INTEROPERABLE_JSON_INTEGER + 1
        else:
            rejected[path] = MAX_INTEROPERABLE_JSON_INTEGER + 1
        with pytest.raises(ValidationError):
            from_json(ContextManifest, rejected)
        with pytest.raises(SchemaValidationError):
            validator.validate(rejected)


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


def test_capability_target_length_matches_schema_and_model() -> None:
    schema = load_schema("capability-grant.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    accepted = capability_grant_data()
    accepted["resource"]["target"] = "a" * 4096  # type: ignore[index]

    from_json(CapabilityGrant, accepted)
    validator.validate(accepted)

    rejected = capability_grant_data()
    rejected["resource"]["target"] = "a" * 4097  # type: ignore[index]
    with pytest.raises(ValidationError):
        from_json(CapabilityGrant, rejected)
    with pytest.raises(SchemaValidationError):
        validator.validate(rejected)


def test_capability_deprecated_copy_revalidates_updates() -> None:
    grant = from_json(CapabilityGrant, capability_grant_data())

    with pytest.raises(ValidationError):
        grant.copy(
            update={
                "resource": {
                    "scope_id": "repo_oscillink_agent",
                    "target": "../secrets.txt",
                }
            }
        )


@pytest.mark.parametrize("field", ["subject_actor_id", "issued_by"])
def test_capability_actor_id_schema_model_boundary_parity(field: str) -> None:
    schema = load_schema("capability-grant.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    accepted = capability_grant_data()
    accepted[field] = "human_" + "a" * 63
    from_json(CapabilityGrant, accepted)
    validator.validate(accepted)

    for invalid_id in ("agent_x", "alice"):
        rejected = capability_grant_data()
        rejected[field] = invalid_id
        with pytest.raises(ValidationError):
            from_json(CapabilityGrant, rejected)
        with pytest.raises(SchemaValidationError):
            validator.validate(rejected)


def test_capability_grant_dump_detects_nested_target_tampering() -> None:
    grant = from_json(CapabilityGrant, capability_grant_data())
    resource_state = object.__getattribute__(grant.resource, "__dict__")
    resource_state["target"] = "../secrets.txt"

    with pytest.raises(ValidationError, match="target"):
        grant.model_dump(mode="json")


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


def test_capability_grant_rejects_cross_type_literal_values() -> None:
    max_uses_data = capability_grant_data()
    max_uses_data["max_uses"] = True
    network_data = capability_grant_data()
    constraints = network_data["constraints"]  # type: ignore[assignment]
    constraints["network_allowed"] = 0

    with pytest.raises(ValidationError):
        from_json(CapabilityGrant, max_uses_data)
    with pytest.raises(ValidationError):
        from_json(CapabilityGrant, network_data)


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
        "review_event_id": "evt_01J00000000000000000000001",
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


def test_memory_claim_dump_detects_content_tampering() -> None:
    claim = from_json(MemoryClaim, memory_claim_data())
    claim_state = object.__getattribute__(claim, "__dict__")
    claim_state["content"] = "tampered"

    with pytest.raises(ValidationError, match="content_hash"):
        claim.model_dump(mode="json")


def test_memory_claim_rejects_content_hash_mismatch() -> None:
    data = memory_claim_data()
    data["content_hash"] = "sha256:" + "0" * 64

    with pytest.raises(ValidationError):
        from_json(MemoryClaim, data)


def test_memory_claim_rejects_self_support() -> None:
    data = memory_claim_data()
    data["source_refs"] = [data["id"]]

    with pytest.raises(ValidationError):
        from_json(MemoryClaim, data)


def test_approved_memory_claim_requires_review_event_reference() -> None:
    data = memory_claim_data()
    del data["review_event_id"]

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
