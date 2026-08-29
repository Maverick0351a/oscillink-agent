"""Deterministic governed chat orchestration."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from oscillink_agent.agent_runtime.errors import ChatIdempotencyConflictError
from oscillink_agent.agent_runtime.repository import SQLiteChatRunRepository
from oscillink_agent.chat.contracts import (
    ChatCitation,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatRunInspectionResponse,
)
from oscillink_agent.context.compiler import compile_context
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
from oscillink_agent.providers.base import ChatProvider
from oscillink_agent.providers.fake import DeterministicFakeProvider
from oscillink_agent.retrieval.service import retrieve_memory_evidence
from oscillink_agent.storage.sqlite import IdempotencyConflictError

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _derived_token(request_id: str, purpose: str) -> str:
    digest = hashlib.sha256(f"{request_id}:{purpose}".encode()).digest()
    value = int.from_bytes(digest[:17], "big") >> 6
    token = ""
    for _ in range(26):
        token = _CROCKFORD[value & 31] + token
        value >>= 5
    return token


def _derived_id(request_id: str, prefix: str, purpose: str) -> str:
    return f"{prefix}_{_derived_token(request_id, purpose)}"


def inspect_chat_run(
    data_root: Path,
    session_id: SessionId,
    run_id: RunId,
) -> ChatRunInspectionResponse:
    """Load and verify one persisted run after any process restart."""

    return SQLiteChatRunRepository(data_root).inspect(session_id, run_id)


def create_chat_message(
    data_root: Path,
    request: ChatMessageRequest,
    *,
    idempotency_key: str,
    provider_adapter: ChatProvider | None = None,
) -> ChatMessageResponse:
    """Compile approved context, execute the configured provider, and append one run."""

    run_id = _derived_id(request.request_id, "run", "chat-run")
    task_id = _derived_id(request.request_id, "tsk", "chat-task")
    repository = SQLiteChatRunRepository(data_root)
    existing = repository.get_by_idempotency(idempotency_key)
    if existing is not None:
        if (
            existing.id != request.request_id
            or existing.session_id != request.session_id
            or existing.run_id != run_id
            or existing.payload.get("message") != request.message
            or existing.payload.get("token_budget") != request.token_budget
        ):
            raise ChatIdempotencyConflictError
        return repository.response_from_run(repository.inspect(request.session_id, run_id))

    compiled_at = datetime.now(UTC)
    context_manifest, selected = compile_context(
        retrieve_memory_evidence(data_root, request.message),
        context_id=_derived_id(request.request_id, "ctx", "chat-context"),
        task_id=task_id,
        compiled_at=compiled_at,
        token_budget=request.token_budget,
    )
    citations: list[ChatCitation] = []
    for record, context_item in zip(selected, context_manifest.items, strict=True):
        if context_item.retrieval_rank is None or context_item.retrieval_score is None:
            raise ValueError("selected context evidence lacks retrieval metadata")
        citations.append(
            ChatCitation(
                record_id=record.id,
                content_hash=record.content_hash,
                title=record.title,
                retrieval_rank=context_item.retrieval_rank,
                retrieval_score=context_item.retrieval_score,
            )
        )
    citation_tuple = tuple(citations)
    configured_provider = provider_adapter or DeterministicFakeProvider()
    provider_result = configured_provider.generate(
        message=request.message,
        context_manifest=context_manifest,
        records=selected,
    )
    answer = provider_result.answer
    provider = configured_provider.projection
    response = ChatMessageResponse(
        session_id=request.session_id,
        run_id=run_id,
        task_id=task_id,
        provider=provider,
        answer=answer,
        citations=citation_tuple,
        context_manifest=context_manifest,
    )
    context_manifest_ref = repository.put_context_manifest(context_manifest)
    model_identity = ModelIdentity(
        provider=provider.kind,
        name=provider.model,
        configuration_hash=canonical_payload_hash(
            {"provider": provider.kind, "model": provider.model}
        ),
    )
    model_call_id = _derived_id(request.request_id, "evt", "chat-model-call")
    response_id = _derived_id(request.request_id, "evt", "chat-response")
    user_payload = {"message": request.message, "token_budget": request.token_budget}
    model_call_payload = {
        "operation": "fake_provider_chat",
        "provider_kind": provider.kind,
        "provider_model": provider.model,
        "context_manifest_id": context_manifest.id,
        "context_manifest_ref": context_manifest_ref,
    }
    response_payload = {
        "answer": answer,
        "citations": [citation.model_dump(mode="json") for citation in citation_tuple],
    }
    entries = (
        (
            Event(
                id=request.request_id,
                schema_version=1,
                session_id=request.session_id,
                run_id=run_id,
                task_id=task_id,
                actor=Actor(id="human_local_user", type=ActorType.HUMAN),
                event_type=EventType.MESSAGE,
                observed_at=compiled_at,
                recorded_at=compiled_at,
                payload_hash=canonical_payload_hash(user_payload),
                artifact_refs=(),
                causal_parent_ids=(),
                trust_class=TrustClass.EXTERNAL_UNTRUSTED,
                sensitivity=Sensitivity.INTERNAL,
                payload=user_payload,
            ),
            idempotency_key,
        ),
        (
            Event(
                id=model_call_id,
                schema_version=1,
                session_id=request.session_id,
                run_id=run_id,
                task_id=task_id,
                actor=Actor(id="model_deterministic_fake", type=ActorType.MODEL),
                event_type=EventType.MODEL_CALL,
                observed_at=compiled_at,
                recorded_at=compiled_at,
                payload_hash=canonical_payload_hash(model_call_payload),
                artifact_refs=(context_manifest_ref,),
                causal_parent_ids=(request.request_id,),
                trust_class=TrustClass.MODEL_GENERATED,
                sensitivity=Sensitivity.INTERNAL,
                payload=model_call_payload,
                model=model_identity,
            ),
            f"{idempotency_key}:model",
        ),
        (
            Event(
                id=response_id,
                schema_version=1,
                session_id=request.session_id,
                run_id=run_id,
                task_id=task_id,
                actor=Actor(id="model_deterministic_fake", type=ActorType.MODEL),
                event_type=EventType.MESSAGE,
                observed_at=compiled_at,
                recorded_at=compiled_at,
                payload_hash=canonical_payload_hash(response_payload),
                artifact_refs=(),
                causal_parent_ids=(model_call_id,),
                trust_class=TrustClass.MODEL_GENERATED,
                sensitivity=Sensitivity.INTERNAL,
                payload=response_payload,
                model=model_identity,
            ),
            f"{idempotency_key}:response",
        ),
    )
    try:
        repository.append_many(entries)
    except IdempotencyConflictError as exc:
        raise ChatIdempotencyConflictError from exc
    return response
