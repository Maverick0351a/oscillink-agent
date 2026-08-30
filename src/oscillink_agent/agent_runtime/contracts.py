"""Typed, provider-neutral reconstruction of append-only agent run events."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from oscillink_agent.domain.events import (
    ActorType,
    Digest,
    Event,
    EventId,
    EventType,
    RunId,
    SessionId,
    TaskId,
)


class RunReconstructionError(ValueError):
    """Persisted events do not form one valid typed run trajectory."""


class RunStepKind(StrEnum):
    """Durable semantic stages supported by the first governed tool trajectory."""

    REQUEST_RECORDED = "request_recorded"
    CONTEXT_COMPILED = "context_compiled"
    MODEL_CALL_PENDING = "model_call_pending"
    MODEL_CALL_SUCCEEDED = "model_call_succeeded"
    MODEL_CALL_FAILED = "model_call_failed"
    MODEL_CALL_INTERRUPTED = "model_call_interrupted"
    TOOL_REQUESTED = "tool_requested"
    GRANT_APPROVED = "grant_approved"
    GRANT_DENIED = "grant_denied"
    TOOL_CALL_CLAIMED = "tool_call_claimed"
    OBSERVATION = "observation"
    TOOL_FAILED = "tool_failed"
    FINAL_RESPONSE = "final_response"


class RunState(StrEnum):
    """Truthful lifecycle projection for a reconstructed run."""

    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class RunPendingAction(StrEnum):
    """Next external boundary implied by the latest durable step."""

    CONTEXT_COMPILATION = "context_compilation"
    PROVIDER_DISPATCH = "provider_dispatch"
    PROVIDER_RESULT = "provider_result"
    MODEL_CONTINUATION = "model_continuation"
    HUMAN_APPROVAL = "human_approval"
    TOOL_EXECUTION = "tool_execution"
    TOOL_RESULT = "tool_result"
    PROVIDER_FOLLOW_UP = "provider_follow_up"


class RunStep(BaseModel):
    """One ordered event projected into its typed run-stage meaning."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    sequence: Annotated[int, Field(ge=0)]
    event_id: EventId
    kind: RunStepKind
    event_type: EventType
    causal_parent_ids: tuple[EventId, ...]


class RunReconstruction(BaseModel):
    """Restart-safe state derived solely from one run's immutable events."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    session_id: SessionId
    run_id: RunId
    task_id: TaskId
    state: RunState
    pending_action: RunPendingAction | None
    steps: tuple[RunStep, ...]
    context_manifest_ref: Digest | None
    final_response_event_id: EventId | None
    model_call_count: Annotated[int, Field(ge=0)]
    tool_call_count: Annotated[int, Field(ge=0)]


_PENDING_ACTIONS = {
    RunStepKind.REQUEST_RECORDED: RunPendingAction.CONTEXT_COMPILATION,
    RunStepKind.CONTEXT_COMPILED: RunPendingAction.PROVIDER_DISPATCH,
    RunStepKind.MODEL_CALL_PENDING: RunPendingAction.PROVIDER_RESULT,
    RunStepKind.MODEL_CALL_SUCCEEDED: RunPendingAction.MODEL_CONTINUATION,
    RunStepKind.TOOL_REQUESTED: RunPendingAction.HUMAN_APPROVAL,
    RunStepKind.GRANT_APPROVED: RunPendingAction.TOOL_EXECUTION,
    RunStepKind.TOOL_CALL_CLAIMED: RunPendingAction.TOOL_RESULT,
    RunStepKind.OBSERVATION: RunPendingAction.PROVIDER_FOLLOW_UP,
}

_ALLOWED_TRANSITIONS = {
    RunStepKind.REQUEST_RECORDED: {
        RunStepKind.CONTEXT_COMPILED,
        RunStepKind.MODEL_CALL_SUCCEEDED,
    },
    RunStepKind.CONTEXT_COMPILED: {RunStepKind.MODEL_CALL_PENDING},
    RunStepKind.MODEL_CALL_PENDING: {
        RunStepKind.MODEL_CALL_SUCCEEDED,
        RunStepKind.MODEL_CALL_FAILED,
        RunStepKind.MODEL_CALL_INTERRUPTED,
    },
    RunStepKind.MODEL_CALL_SUCCEEDED: {
        RunStepKind.TOOL_REQUESTED,
        RunStepKind.FINAL_RESPONSE,
    },
    RunStepKind.TOOL_REQUESTED: {
        RunStepKind.GRANT_APPROVED,
        RunStepKind.GRANT_DENIED,
    },
    RunStepKind.GRANT_APPROVED: {RunStepKind.TOOL_CALL_CLAIMED},
    RunStepKind.TOOL_CALL_CLAIMED: {
        RunStepKind.OBSERVATION,
        RunStepKind.TOOL_FAILED,
    },
    RunStepKind.OBSERVATION: {RunStepKind.MODEL_CALL_PENDING},
}

_EVENT_TYPES = {
    RunStepKind.REQUEST_RECORDED: EventType.MESSAGE,
    RunStepKind.CONTEXT_COMPILED: EventType.OUTCOME,
    RunStepKind.MODEL_CALL_PENDING: EventType.MODEL_CALL,
    RunStepKind.MODEL_CALL_SUCCEEDED: EventType.OUTCOME,
    RunStepKind.MODEL_CALL_FAILED: EventType.OUTCOME,
    RunStepKind.MODEL_CALL_INTERRUPTED: EventType.OUTCOME,
    RunStepKind.TOOL_REQUESTED: EventType.TOOL_CALL,
    RunStepKind.GRANT_APPROVED: EventType.APPROVAL,
    RunStepKind.GRANT_DENIED: EventType.APPROVAL,
    RunStepKind.TOOL_CALL_CLAIMED: EventType.TOOL_CALL,
    RunStepKind.OBSERVATION: EventType.OBSERVATION,
    RunStepKind.TOOL_FAILED: EventType.OUTCOME,
    RunStepKind.FINAL_RESPONSE: EventType.MESSAGE,
}


def _step_kind(event: Event) -> RunStepKind:
    operation = event.payload.get("operation")
    if isinstance(operation, str):
        try:
            return RunStepKind(operation)
        except ValueError:
            pass
    if (
        event.event_type is EventType.MESSAGE
        and event.actor.type is ActorType.HUMAN
        and operation is None
    ):
        return RunStepKind.REQUEST_RECORDED
    if event.event_type is EventType.MODEL_CALL and operation == "fake_provider_chat":
        return RunStepKind.MODEL_CALL_SUCCEEDED
    if (
        event.event_type is EventType.MESSAGE
        and event.actor.type is ActorType.MODEL
        and operation is None
    ):
        return RunStepKind.FINAL_RESPONSE
    raise RunReconstructionError("event does not declare a recognized run operation")


def reconstruct_run(events: Iterable[Event]) -> RunReconstruction:
    """Project one insertion-ordered event stream into a typed run state."""

    run_events = tuple(events)
    if not run_events:
        raise RunReconstructionError("a run requires at least one persisted event")

    first = run_events[0]
    steps: list[RunStep] = []
    context_manifest_ref: str | None = None
    for sequence, event in enumerate(run_events):
        if (event.session_id, event.run_id, event.task_id) != (
            first.session_id,
            first.run_id,
            first.task_id,
        ):
            raise RunReconstructionError("all events must share one run identity")
        kind = _step_kind(event)
        legacy_model_call = (
            kind is RunStepKind.MODEL_CALL_SUCCEEDED
            and event.payload.get("operation") == "fake_provider_chat"
        )
        if event.event_type is not _EVENT_TYPES[kind] and not legacy_model_call:
            raise RunReconstructionError(
                f"{kind.value} requires event type {_EVENT_TYPES[kind].value}"
            )
        if sequence == 0:
            if kind is not RunStepKind.REQUEST_RECORDED:
                raise RunReconstructionError("a run must begin with request_recorded")
            if event.causal_parent_ids:
                raise RunReconstructionError("the request cannot have a causal parent")
        elif kind not in _ALLOWED_TRANSITIONS.get(steps[-1].kind, set()):
            raise RunReconstructionError(
                f"invalid run transition: {steps[-1].kind.value} -> {kind.value}"
            )
        elif event.causal_parent_ids != (steps[-1].event_id,):
            raise RunReconstructionError(
                "each run step must name the preceding event as its causal parent"
            )
        if kind is RunStepKind.CONTEXT_COMPILED:
            if len(event.artifact_refs) != 1:
                raise RunReconstructionError("compiled context requires one artifact reference")
            context_manifest_ref = event.artifact_refs[0]
        elif legacy_model_call:
            if len(event.artifact_refs) != 1:
                raise RunReconstructionError("legacy model call requires one context artifact")
            context_manifest_ref = event.artifact_refs[0]
        steps.append(
            RunStep(
                sequence=sequence,
                event_id=event.id,
                kind=kind,
                event_type=event.event_type,
                causal_parent_ids=event.causal_parent_ids,
            )
        )

    last_kind = steps[-1].kind
    if last_kind is RunStepKind.FINAL_RESPONSE:
        state = RunState.COMPLETED
    elif last_kind in {
        RunStepKind.MODEL_CALL_FAILED,
        RunStepKind.TOOL_FAILED,
        RunStepKind.GRANT_DENIED,
    }:
        state = RunState.FAILED
    elif last_kind is RunStepKind.MODEL_CALL_INTERRUPTED:
        state = RunState.INTERRUPTED
    elif last_kind is RunStepKind.TOOL_REQUESTED:
        state = RunState.AWAITING_APPROVAL
    else:
        state = RunState.IN_PROGRESS

    return RunReconstruction(
        session_id=first.session_id,
        run_id=first.run_id,
        task_id=first.task_id,
        state=state,
        pending_action=_PENDING_ACTIONS.get(last_kind),
        steps=tuple(steps),
        context_manifest_ref=context_manifest_ref,
        final_response_event_id=(
            run_events[-1].id if last_kind is RunStepKind.FINAL_RESPONSE else None
        ),
        model_call_count=sum(
            step.kind is RunStepKind.MODEL_CALL_SUCCEEDED for step in steps
        ),
        tool_call_count=sum(step.kind is RunStepKind.TOOL_CALL_CLAIMED for step in steps),
    )
