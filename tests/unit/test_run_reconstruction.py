from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from oscillink_agent.agent_runtime.contracts import RunState, RunStepKind, reconstruct_run
from oscillink_agent.domain.events import (
    Actor,
    ActorType,
    Event,
    EventType,
    ModelIdentity,
    Sensitivity,
    TrustClass,
    canonical_payload_hash,
)

_SESSION_ID = "ses_01ARZ3NDEKTSV4RRFFQ69G5FE0"
_RUN_ID = "run_01ARZ3NDEKTSV4RRFFQ69G5FE0"
_TASK_ID = "tsk_01ARZ3NDEKTSV4RRFFQ69G5FE0"
_MODEL = ModelIdentity(
    provider="fake",
    name="deterministic-tool-v1",
    configuration_hash="sha256:" + "a" * 64,
)


def event(
    suffix: str,
    *,
    event_type: EventType,
    operation: str,
    actor_type: ActorType,
    parent: str | None,
    sequence: int,
    artifact_refs: tuple[str, ...] = (),
    payload: dict[str, Any] | None = None,
) -> Event:
    actor_ids = {
        ActorType.HUMAN: "human_test_operator",
        ActorType.MODEL: "model_deterministic_tool",
        ActorType.TOOL: "tool_file_read",
        ActorType.SYSTEM: "system_agent_runtime",
    }
    trust_classes = {
        ActorType.HUMAN: TrustClass.HUMAN_VERIFIED,
        ActorType.MODEL: TrustClass.MODEL_GENERATED,
        ActorType.TOOL: TrustClass.EXTERNAL_UNTRUSTED,
        ActorType.SYSTEM: TrustClass.SYSTEM,
    }
    event_payload = {"operation": operation, **(payload or {})}
    occurred_at = datetime(2026, 8, 30, 6, 0, tzinfo=UTC) + timedelta(seconds=sequence)
    return Event(
        id=f"evt_01ARZ3NDEKTSV4RRFFQ69G5F{suffix}",
        schema_version=1,
        session_id=_SESSION_ID,
        run_id=_RUN_ID,
        task_id=_TASK_ID,
        actor=Actor(id=actor_ids[actor_type], type=actor_type),
        event_type=event_type,
        observed_at=occurred_at,
        recorded_at=occurred_at,
        payload_hash=canonical_payload_hash(event_payload),
        artifact_refs=artifact_refs,
        causal_parent_ids=() if parent is None else (parent,),
        trust_class=trust_classes[actor_type],
        sensitivity=Sensitivity.INTERNAL,
        payload=event_payload,
        model=(
            _MODEL
            if actor_type is ActorType.MODEL or event_type is EventType.MODEL_CALL
            else None
        ),
    )


def test_reconstructs_two_model_calls_and_one_governed_tool_call() -> None:
    manifest_ref = "sha256:" + "b" * 64
    events: list[Event] = []

    def append(
        suffix: str,
        event_type: EventType,
        operation: str,
        actor_type: ActorType,
        *,
        artifact_refs: tuple[str, ...] = (),
        payload: dict[str, Any] | None = None,
    ) -> None:
        events.append(
            event(
                suffix,
                event_type=event_type,
                operation=operation,
                actor_type=actor_type,
                parent=events[-1].id if events else None,
                sequence=len(events),
                artifact_refs=artifact_refs,
                payload=payload,
            )
        )

    append("E1", EventType.MESSAGE, "request_recorded", ActorType.HUMAN)
    append(
        "E2",
        EventType.OUTCOME,
        "context_compiled",
        ActorType.SYSTEM,
        artifact_refs=(manifest_ref,),
    )
    append("E3", EventType.MODEL_CALL, "model_call_pending", ActorType.SYSTEM)
    append("E4", EventType.OUTCOME, "model_call_succeeded", ActorType.MODEL)
    append("E5", EventType.TOOL_CALL, "tool_requested", ActorType.MODEL)
    append("E6", EventType.APPROVAL, "grant_approved", ActorType.HUMAN)
    append("E7", EventType.TOOL_CALL, "tool_call_claimed", ActorType.TOOL)
    append(
        "E8",
        EventType.OBSERVATION,
        "observation",
        ActorType.TOOL,
        artifact_refs=("sha256:" + "c" * 64,),
    )
    append("E9", EventType.MODEL_CALL, "model_call_pending", ActorType.SYSTEM)
    append("EA", EventType.OUTCOME, "model_call_succeeded", ActorType.MODEL)
    append(
        "EB",
        EventType.MESSAGE,
        "final_response",
        ActorType.MODEL,
        payload={"answer": "The governed file confirms the requested fact."},
    )

    reconstructed = reconstruct_run(events)

    assert reconstructed.state is RunState.COMPLETED
    assert reconstructed.context_manifest_ref == manifest_ref
    assert reconstructed.final_response_event_id == events[-1].id
    assert reconstructed.pending_action is None
    assert [step.kind for step in reconstructed.steps] == [
        RunStepKind.REQUEST_RECORDED,
        RunStepKind.CONTEXT_COMPILED,
        RunStepKind.MODEL_CALL_PENDING,
        RunStepKind.MODEL_CALL_SUCCEEDED,
        RunStepKind.TOOL_REQUESTED,
        RunStepKind.GRANT_APPROVED,
        RunStepKind.TOOL_CALL_CLAIMED,
        RunStepKind.OBSERVATION,
        RunStepKind.MODEL_CALL_PENDING,
        RunStepKind.MODEL_CALL_SUCCEEDED,
        RunStepKind.FINAL_RESPONSE,
    ]
    assert reconstructed.model_call_count == 2
    assert reconstructed.tool_call_count == 1


def test_rejects_a_tool_request_before_a_successful_model_call() -> None:
    request = event(
        "F1",
        event_type=EventType.MESSAGE,
        operation="request_recorded",
        actor_type=ActorType.HUMAN,
        parent=None,
        sequence=0,
    )
    context = event(
        "F2",
        event_type=EventType.OUTCOME,
        operation="context_compiled",
        actor_type=ActorType.SYSTEM,
        parent=request.id,
        sequence=1,
        artifact_refs=("sha256:" + "d" * 64,),
    )
    premature_tool_request = event(
        "F3",
        event_type=EventType.TOOL_CALL,
        operation="tool_requested",
        actor_type=ActorType.MODEL,
        parent=context.id,
        sequence=2,
    )

    with pytest.raises(ValueError, match="invalid run transition"):
        reconstruct_run((request, context, premature_tool_request))


def test_rejects_a_step_whose_causal_parent_is_missing() -> None:
    request = event(
        "G1",
        event_type=EventType.MESSAGE,
        operation="request_recorded",
        actor_type=ActorType.HUMAN,
        parent=None,
        sequence=0,
    )
    context = event(
        "G2",
        event_type=EventType.OUTCOME,
        operation="context_compiled",
        actor_type=ActorType.SYSTEM,
        parent="evt_01ARZ3NDEKTSV4RRFFQ69G5FG0",
        sequence=1,
        artifact_refs=("sha256:" + "e" * 64,),
    )

    with pytest.raises(ValueError, match="causal parent"):
        reconstruct_run((request, context))


def test_rejects_a_duplicate_final_response() -> None:
    request = event(
        "H1",
        event_type=EventType.MESSAGE,
        operation="request_recorded",
        actor_type=ActorType.HUMAN,
        parent=None,
        sequence=0,
    )
    context = event(
        "H2",
        event_type=EventType.OUTCOME,
        operation="context_compiled",
        actor_type=ActorType.SYSTEM,
        parent=request.id,
        sequence=1,
        artifact_refs=("sha256:" + "f" * 64,),
    )
    pending = event(
        "H3",
        event_type=EventType.MODEL_CALL,
        operation="model_call_pending",
        actor_type=ActorType.SYSTEM,
        parent=context.id,
        sequence=2,
    )
    succeeded = event(
        "H4",
        event_type=EventType.OUTCOME,
        operation="model_call_succeeded",
        actor_type=ActorType.MODEL,
        parent=pending.id,
        sequence=3,
    )
    final = event(
        "H5",
        event_type=EventType.MESSAGE,
        operation="final_response",
        actor_type=ActorType.MODEL,
        parent=succeeded.id,
        sequence=4,
    )
    duplicate = event(
        "H6",
        event_type=EventType.MESSAGE,
        operation="final_response",
        actor_type=ActorType.MODEL,
        parent=final.id,
        sequence=5,
    )

    with pytest.raises(ValueError, match="invalid run transition"):
        reconstruct_run((request, context, pending, succeeded, final, duplicate))


def test_projects_an_interrupted_provider_call_without_claiming_completion() -> None:
    request = event(
        "J1",
        event_type=EventType.MESSAGE,
        operation="request_recorded",
        actor_type=ActorType.HUMAN,
        parent=None,
        sequence=0,
    )
    context = event(
        "J2",
        event_type=EventType.OUTCOME,
        operation="context_compiled",
        actor_type=ActorType.SYSTEM,
        parent=request.id,
        sequence=1,
        artifact_refs=("sha256:" + "1" * 64,),
    )
    pending = event(
        "J3",
        event_type=EventType.MODEL_CALL,
        operation="model_call_pending",
        actor_type=ActorType.SYSTEM,
        parent=context.id,
        sequence=2,
    )
    interrupted = event(
        "J4",
        event_type=EventType.OUTCOME,
        operation="model_call_interrupted",
        actor_type=ActorType.SYSTEM,
        parent=pending.id,
        sequence=3,
    )

    reconstructed = reconstruct_run((request, context, pending, interrupted))

    assert reconstructed.state is RunState.INTERRUPTED
    assert reconstructed.pending_action is None
    assert reconstructed.final_response_event_id is None
    assert reconstructed.model_call_count == 0


def test_rejects_an_operation_encoded_as_the_wrong_event_type() -> None:
    request = event(
        "K1",
        event_type=EventType.MESSAGE,
        operation="request_recorded",
        actor_type=ActorType.HUMAN,
        parent=None,
        sequence=0,
    )
    context = event(
        "K2",
        event_type=EventType.OUTCOME,
        operation="context_compiled",
        actor_type=ActorType.SYSTEM,
        parent=request.id,
        sequence=1,
        artifact_refs=("sha256:" + "2" * 64,),
    )
    malformed_pending = event(
        "K3",
        event_type=EventType.MESSAGE,
        operation="model_call_pending",
        actor_type=ActorType.HUMAN,
        parent=context.id,
        sequence=2,
    )

    with pytest.raises(ValueError, match="event type"):
        reconstruct_run((request, context, malformed_pending))


def test_rejects_events_from_a_different_run_task() -> None:
    request = event(
        "N1",
        event_type=EventType.MESSAGE,
        operation="request_recorded",
        actor_type=ActorType.HUMAN,
        parent=None,
        sequence=0,
    )
    context = event(
        "N2",
        event_type=EventType.OUTCOME,
        operation="context_compiled",
        actor_type=ActorType.SYSTEM,
        parent=request.id,
        sequence=1,
        artifact_refs=("sha256:" + "5" * 64,),
    ).model_copy(update={"task_id": "tsk_01ARZ3NDEKTSV4RRFFQ69G5FE1"})

    with pytest.raises(ValueError, match="run identity"):
        reconstruct_run((request, context))
