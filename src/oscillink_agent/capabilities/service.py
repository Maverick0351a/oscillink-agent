"""Authenticated decision and execution service for one governed file-read loop."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from oscillink_agent.agent_runtime.contracts import RunState
from oscillink_agent.agent_runtime.repository import SQLiteChatRunRepository
from oscillink_agent.agent_runtime.tools import FileReadToolRequest
from oscillink_agent.capabilities.broker import CapabilityBroker, CapabilityDeniedError
from oscillink_agent.capabilities.contracts import (
    CapabilityDecisionRequest,
    CapabilityDecisionResponse,
)
from oscillink_agent.chat.contracts import (
    ChatCitation,
    ChatMessageResponse,
    ChatRunInspectionResponse,
)
from oscillink_agent.domain.capabilities import (
    CapabilityConstraints,
    CapabilityGrant,
    FileResource,
)
from oscillink_agent.domain.events import (
    Actor,
    ActorType,
    Event,
    EventType,
    ModelIdentity,
    RunId,
    Sensitivity,
    SessionId,
    TrustClass,
    canonical_payload_hash,
)
from oscillink_agent.memory.repository import (
    MemoryAuthorityState,
    ProductMemoryRecord,
    SQLiteMemoryRepository,
)
from oscillink_agent.providers.base import (
    ChatProvider,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
    ToolRequestResult,
)
from oscillink_agent.storage.artifacts import LocalArtifactStore
from oscillink_agent.storage.sqlite import IdempotencyConflictError

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class CapabilityLoopError(RuntimeError):
    """Stable fail-closed capability-loop error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _derived_id(request_id: str, prefix: str, purpose: str) -> str:
    digest = hashlib.sha256(f"{request_id}:{purpose}".encode()).digest()
    value = int.from_bytes(digest[:17], "big") >> 6
    token = ""
    for _ in range(26):
        token = _CROCKFORD[value & 31] + token
        value >>= 5
    return f"{prefix}_{token}"


def _event(
    *,
    event_id: str,
    session_id: str,
    run_id: str,
    task_id: str,
    actor: Actor,
    event_type: EventType,
    recorded_at: datetime,
    payload: Mapping[str, object],
    parent_id: str,
    trust_class: TrustClass,
    artifact_refs: tuple[str, ...] = (),
    model: ModelIdentity | None = None,
) -> Event:
    return Event(
        id=event_id,
        schema_version=1,
        session_id=session_id,
        run_id=run_id,
        task_id=task_id,
        actor=actor,
        event_type=event_type,
        observed_at=recorded_at,
        recorded_at=recorded_at,
        payload_hash=canonical_payload_hash(payload),
        artifact_refs=artifact_refs,
        causal_parent_ids=(parent_id,),
        trust_class=trust_class,
        sensitivity=Sensitivity.INTERNAL,
        payload=payload,
        model=model,
    )


def _load_selected_records(
    data_root: Path,
    inspection: ChatRunInspectionResponse,
) -> tuple[ProductMemoryRecord, ...]:
    manifest = inspection.context_manifest
    if not manifest.items:
        return ()
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        records: list[ProductMemoryRecord] = []
        for item in manifest.items:
            record = repository.get(item.record_id)
            if (
                record is None
                or record.content_hash != item.content_hash
                or record.authority_state is not MemoryAuthorityState.APPROVED
            ):
                raise CapabilityLoopError("context_revision_unavailable")
            records.append(record)
        return tuple(records)
    finally:
        repository.close()


def _citations(
    records: tuple[ProductMemoryRecord, ...],
    inspection: ChatRunInspectionResponse,
) -> tuple[ChatCitation, ...]:
    result: list[ChatCitation] = []
    for record, item in zip(records, inspection.context_manifest.items, strict=True):
        if item.retrieval_rank is None or item.retrieval_score is None:
            raise CapabilityLoopError("context_revision_unavailable")
        result.append(
            ChatCitation(
                record_id=record.id,
                content_hash=record.content_hash,
                title=record.title,
                retrieval_rank=item.retrieval_rank,
                retrieval_score=item.retrieval_score,
            )
        )
    return tuple(result)


def _append_tool_failure(
    repository: SQLiteChatRunRepository,
    *,
    decision: CapabilityDecisionRequest,
    session_id: SessionId,
    run_id: RunId,
    task_id: str,
    parent_id: str,
    failure_kind: str,
    idempotency_key: str,
) -> None:
    failed_payload = {
        "operation": "tool_failed",
        "failure_kind": failure_kind,
    }
    failed_event = _event(
        event_id=_derived_id(
            decision.request_id,
            "evt",
            f"file-read-failed:{failure_kind}",
        ),
        session_id=session_id,
        run_id=run_id,
        task_id=task_id,
        actor=Actor(id="system_agent_runtime", type=ActorType.SYSTEM),
        event_type=EventType.OUTCOME,
        recorded_at=datetime.now(UTC),
        payload=failed_payload,
        parent_id=parent_id,
        trust_class=TrustClass.SYSTEM,
    )
    repository.append_many(((failed_event, f"{idempotency_key}:failed"),))


def decide_file_read_request(
    *,
    data_root: Path,
    scope_roots: Mapping[str, Path],
    provider: ChatProvider,
    session_id: SessionId,
    run_id: RunId,
    tool_request_event_id: str,
    decision: CapabilityDecisionRequest,
    idempotency_key: str,
    actor_id: str,
) -> ChatMessageResponse | CapabilityDecisionResponse:
    """Bind a human decision to one pending request and execute at most one read."""

    repository = SQLiteChatRunRepository(data_root)
    inspection = repository.inspect(session_id, run_id)
    existing = repository.get_by_idempotency(idempotency_key)
    if existing is not None:
        if (
            existing.id != decision.request_id
            or existing.session_id != session_id
            or existing.run_id != run_id
            or existing.payload.get("decision") != decision.decision
            or existing.payload.get("tool_request_event_id")
            != tool_request_event_id
        ):
            raise CapabilityLoopError("decision_conflict")
        if inspection.reconstruction.state is RunState.COMPLETED:
            return repository.response_from_run(inspection)
        if inspection.events[-1].payload.get("operation") == "grant_denied":
            return CapabilityDecisionResponse(
                session_id=session_id,
                run_id=run_id,
                tool_request_event_id=tool_request_event_id,
            )
        failure_kind = inspection.events[-1].payload.get("failure_kind")
        if isinstance(failure_kind, str):
            raise CapabilityLoopError(failure_kind)
        raise CapabilityLoopError("request_not_pending")
    if (
        inspection.reconstruction.state is not RunState.AWAITING_APPROVAL
        or inspection.events[-1].id != tool_request_event_id
    ):
        raise CapabilityLoopError("request_not_pending")
    tool_event = inspection.events[-1]
    try:
        raw_request = tool_event.payload["request"]
        if not isinstance(raw_request, Mapping):
            raise TypeError
        tool_request = FileReadToolRequest.model_validate(
            dict(raw_request),
            strict=True,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise CapabilityLoopError("request_corrupt") from error
    identity = provider.execution_identity
    if (
        tool_event.actor.id != identity.actor_id
        or tool_event.model is None
        or tool_event.model.provider != identity.kind
        or tool_event.model.name != identity.model
        or tool_event.model.configuration_hash != identity.configuration_hash
    ):
        raise CapabilityLoopError("provider_identity_mismatch")
    now = datetime.now(UTC)
    decision_operation = (
        "grant_approved" if decision.decision == "approved" else "grant_denied"
    )
    grant_id = _derived_id(decision.request_id, "grt", "file-read-grant")
    decision_payload = {
        "operation": decision_operation,
        "decision": decision.decision,
        "grant_id": grant_id,
        "tool_request_event_id": tool_request_event_id,
        "subject_actor_id": identity.actor_id,
        "scope_id": tool_request.scope_id,
        "target": tool_request.target,
        "max_bytes": tool_request.max_bytes,
    }
    decision_event = _event(
        event_id=decision.request_id,
        session_id=session_id,
        run_id=run_id,
        task_id=inspection.reconstruction.task_id,
        actor=Actor(id=actor_id, type=ActorType.HUMAN),
        event_type=EventType.APPROVAL,
        recorded_at=now,
        payload=decision_payload,
        parent_id=tool_request_event_id,
        trust_class=TrustClass.HUMAN_VERIFIED,
    )
    try:
        repository.append_many(((decision_event, idempotency_key),))
    except IdempotencyConflictError as error:
        raise CapabilityLoopError("decision_conflict") from error
    if decision.decision == "denied":
        return CapabilityDecisionResponse(
            session_id=session_id,
            run_id=run_id,
            tool_request_event_id=tool_request_event_id,
        )

    extension = Path(tool_request.target).suffix
    if not extension:
        _append_tool_failure(
            repository,
            decision=decision,
            session_id=session_id,
            run_id=run_id,
            task_id=inspection.reconstruction.task_id,
            parent_id=decision.request_id,
            failure_kind="extension_denied",
            idempotency_key=idempotency_key,
        )
        raise CapabilityLoopError("extension_denied")
    grant = CapabilityGrant(
        id=grant_id,
        schema_version=1,
        subject_actor_id=identity.actor_id,
        capability="file.read",
        resource=FileResource(
            scope_id=tool_request.scope_id,
            target=tool_request.target,
        ),
        issued_at=now,
        valid_for_seconds=60,
        issued_by=actor_id,
        authorization_event_id=decision.request_id,
        max_uses=1,
        constraints=CapabilityConstraints(
            max_bytes=tool_request.max_bytes,
            allowed_extensions=(extension,),
            network_allowed=False,
        ),
    )
    broker = CapabilityBroker(data_root=data_root, scope_roots=scope_roots)
    try:
        broker.register_grant(grant)
    except CapabilityDeniedError as error:
        _append_tool_failure(
            repository,
            decision=decision,
            session_id=session_id,
            run_id=run_id,
            task_id=inspection.reconstruction.task_id,
            parent_id=decision.request_id,
            failure_kind=error.code,
            idempotency_key=idempotency_key,
        )
        raise CapabilityLoopError(error.code) from error

    claimed_at = datetime.now(UTC)
    claimed_id = _derived_id(decision.request_id, "evt", "file-read-claimed")
    claimed_payload = {
        "operation": "tool_call_claimed",
        "grant_id": grant.id,
        "scope_id": tool_request.scope_id,
        "target": tool_request.target,
    }
    claimed_event = _event(
        event_id=claimed_id,
        session_id=session_id,
        run_id=run_id,
        task_id=inspection.reconstruction.task_id,
        actor=Actor(id="tool_file_read", type=ActorType.TOOL),
        event_type=EventType.TOOL_CALL,
        recorded_at=claimed_at,
        payload=claimed_payload,
        parent_id=decision.request_id,
        trust_class=TrustClass.TOOL_VERIFIED,
    )
    repository.append_many(((claimed_event, f"{idempotency_key}:claimed"),))
    try:
        observation = broker.execute_file_read(
            grant.id,
            subject_actor_id=identity.actor_id,
            now=datetime.now(UTC),
        )
    except CapabilityDeniedError as error:
        _append_tool_failure(
            repository,
            decision=decision,
            session_id=session_id,
            run_id=run_id,
            task_id=inspection.reconstruction.task_id,
            parent_id=claimed_id,
            failure_kind=error.code,
            idempotency_key=idempotency_key,
        )
        raise CapabilityLoopError(error.code) from error

    artifacts = LocalArtifactStore(data_root / "artifacts")
    observation_ref = artifacts.put(observation.model_dump_json().encode("utf-8"))
    observed_at = datetime.now(UTC)
    observation_id = _derived_id(decision.request_id, "evt", "file-read-observation")
    observation_payload = {
        "operation": "observation",
        "grant_id": grant.id,
        "scope_id": observation.scope_id,
        "target": observation.target,
        "byte_count": observation.byte_count,
        "content_hash": observation.content_hash,
        "observation_ref": observation_ref,
    }
    observation_event = _event(
        event_id=observation_id,
        session_id=session_id,
        run_id=run_id,
        task_id=inspection.reconstruction.task_id,
        actor=Actor(id="tool_file_read", type=ActorType.TOOL),
        event_type=EventType.OBSERVATION,
        recorded_at=observed_at,
        payload=observation_payload,
        parent_id=claimed_id,
        trust_class=TrustClass.EXTERNAL_UNTRUSTED,
        artifact_refs=(observation_ref,),
    )
    repository.append_many(((observation_event, f"{idempotency_key}:observation"),))

    context_manifest = inspection.context_manifest
    records = _load_selected_records(data_root, inspection)
    citations = _citations(records, inspection)
    model_identity = ModelIdentity(
        provider=identity.kind,
        name=identity.model,
        configuration_hash=identity.configuration_hash,
    )
    followup_pending_id = _derived_id(decision.request_id, "evt", "followup-pending")
    followup_payload = {
        "operation": "model_call_pending",
        "provider_kind": identity.kind,
        "provider_model": identity.model,
        "provider_actor_id": identity.actor_id,
        "provider_operation": identity.operation,
        "context_manifest_id": context_manifest.id,
        "context_manifest_ref": inspection.reconstruction.context_manifest_ref,
        "observation_ref": observation_ref,
    }
    followup_pending = _event(
        event_id=followup_pending_id,
        session_id=session_id,
        run_id=run_id,
        task_id=inspection.reconstruction.task_id,
        actor=Actor(id="system_agent_runtime", type=ActorType.SYSTEM),
        event_type=EventType.MODEL_CALL,
        recorded_at=datetime.now(UTC),
        payload=followup_payload,
        parent_id=observation_id,
        trust_class=TrustClass.SYSTEM,
        artifact_refs=(observation_ref,),
        model=model_identity,
    )
    repository.append_many(((followup_pending, f"{idempotency_key}:followup:pending"),))

    original_message = inspection.events[0].payload.get("message")
    if not isinstance(original_message, str):
        raise CapabilityLoopError("request_corrupt")
    repeated_tool_request = False
    try:
        result = provider.generate(
            message=original_message,
            context_manifest=context_manifest,
            records=records,
            observation=observation,
        )
        if isinstance(result, ToolRequestResult):
            repeated_tool_request = True
            raise ProviderResponseError("provider repeated a tool request")
    except (ProviderRequestError, ProviderResponseError) as error:
        if isinstance(error, ProviderTimeoutError):
            failure_kind = "timeout"
        elif isinstance(error, ProviderRequestError):
            failure_kind = "request"
        elif repeated_tool_request:
            failure_kind = "repeated_tool_request"
        else:
            failure_kind = "response"
        failed_payload = {
            "operation": "model_call_failed",
            "failure_kind": failure_kind,
        }
        failed_event = _event(
            event_id=_derived_id(decision.request_id, "evt", "followup-failed"),
            session_id=session_id,
            run_id=run_id,
            task_id=inspection.reconstruction.task_id,
            actor=Actor(id="system_agent_runtime", type=ActorType.SYSTEM),
            event_type=EventType.OUTCOME,
            recorded_at=datetime.now(UTC),
            payload=failed_payload,
            parent_id=followup_pending_id,
            trust_class=TrustClass.SYSTEM,
        )
        repository.append_many(
            ((failed_event, f"{idempotency_key}:followup:failed"),)
        )
        raise CapabilityLoopError("provider_followup_failed") from error
    completed_at = datetime.now(UTC)
    success_id = _derived_id(decision.request_id, "evt", "followup-succeeded")
    success_payload = {
        "operation": "model_call_succeeded",
        "provider_kind": identity.kind,
        "provider_model": identity.model,
        "provider_actor_id": identity.actor_id,
        "provider_operation": identity.operation,
    }
    response_id = _derived_id(decision.request_id, "evt", "followup-response")
    response_payload = {
        "operation": "final_response",
        "answer": result.answer,
        "citations": [citation.model_dump(mode="json") for citation in citations],
    }
    success_event = _event(
        event_id=success_id,
        session_id=session_id,
        run_id=run_id,
        task_id=inspection.reconstruction.task_id,
        actor=Actor(id=identity.actor_id, type=ActorType.MODEL),
        event_type=EventType.OUTCOME,
        recorded_at=completed_at,
        payload=success_payload,
        parent_id=followup_pending_id,
        trust_class=TrustClass.MODEL_GENERATED,
        model=model_identity,
    )
    response_event = _event(
        event_id=response_id,
        session_id=session_id,
        run_id=run_id,
        task_id=inspection.reconstruction.task_id,
        actor=Actor(id=identity.actor_id, type=ActorType.MODEL),
        event_type=EventType.MESSAGE,
        recorded_at=completed_at,
        payload=response_payload,
        parent_id=success_id,
        trust_class=TrustClass.MODEL_GENERATED,
        model=model_identity,
    )
    repository.append_many(
        (
            (success_event, f"{idempotency_key}:followup:success"),
            (response_event, f"{idempotency_key}:followup:response"),
        )
    )
    return ChatMessageResponse(
        session_id=session_id,
        run_id=run_id,
        task_id=inspection.reconstruction.task_id,
        provider=identity.projection,
        answer=result.answer,
        citations=citations,
        context_manifest=context_manifest,
    )
