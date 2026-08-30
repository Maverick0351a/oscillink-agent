from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from oscillink_agent.agent_runtime.errors import ChatRunIncompleteError
from oscillink_agent.agent_runtime.repository import SQLiteChatRunRepository
from oscillink_agent.api import create_app
from oscillink_agent.domain.context import ContextManifest
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
from oscillink_agent.storage.artifacts import LocalArtifactStore


def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request_headers = {
        "Authorization": "Bearer oscillink-test-workspace-credential",
        **(headers or {}),
    }

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json, headers=request_headers)

    return asyncio.run(send())


def test_approved_memory_is_cited_in_a_persisted_fake_provider_run(tmp_path: Any) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)
    created = request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        json={
            "schema_version": 1,
            "title": "Approved continuity",
            "content": "The customer requires every answer to cite approved memory.",
            "category": "governance",
            "domains": ["software"],
            "topics": ["citations"],
        },
    ).json()["node"]
    approved = request(
        app,
        "POST",
        f"/api/v1/memory/nodes/{created['id']}/reviews",
        headers={"Idempotency-Key": "approve-chat-memory"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC0",
            "decision": "approved",
        },
    )
    assert approved.status_code == 200

    response = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={"Idempotency-Key": "chat-approved-memory"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC1",
            "session_id": "ses_01ARZ3NDEKTSV4RRFFQ69G5FC1",
            "message": "What continuity rule applies?",
            "token_budget": 256,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider"] == {"kind": "fake", "model": "deterministic-v1"}
    assert payload["answer"] == "Grounded in approved memory: Approved continuity."
    assert payload["citations"] == [
        {
            "record_id": created["id"],
            "content_hash": created["content_hash"],
            "title": "Approved continuity",
            "retrieval_rank": 1,
            "retrieval_score": 4,
        }
    ]
    assert payload["context_manifest"]["items"] == [
        {
            "record_id": created["id"],
            "content_hash": created["content_hash"],
            "title": "Approved continuity",
            "category": "governance",
            "domains": ["software"],
            "inclusion_reason": "approved lexical evidence rank=1 score=4",
            "trust_class": "human_verified",
            "status": "approved",
            "token_count": 9,
            "source_refs": [created["id"]],
            "retrieval_rank": 1,
            "retrieval_score": 4,
        }
    ]
    replay = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={"Idempotency-Key": "chat-approved-memory"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC1",
            "session_id": "ses_01ARZ3NDEKTSV4RRFFQ69G5FC1",
            "message": "What continuity rule applies?",
            "token_budget": 256,
        },
    )
    assert replay.status_code == 200
    assert replay.json() == payload

    restarted = create_app(data_root=data_root, vault_root=None)
    inspected = request(
        restarted,
        "GET",
        f"/api/v1/chat/sessions/{payload['session_id']}/runs/{payload['run_id']}",
    )

    assert inspected.status_code == 200, inspected.text
    run = inspected.json()
    assert run["run_id"] == payload["run_id"]
    assert [event["event_type"] for event in run["events"]] == [
        "message",
        "model_call",
        "message",
    ]
    assert run["context_manifest"] == payload["context_manifest"]
    assert run["events"][1]["payload"]["context_manifest_ref"] == (
        run["events"][1]["artifact_refs"][0]
    )
    assert run["events"][2]["payload"]["answer"] == payload["answer"]
    assert run["reconstruction"] == {
        "schema_version": 1,
        "session_id": payload["session_id"],
        "run_id": payload["run_id"],
        "task_id": payload["task_id"],
        "state": "completed",
        "pending_action": None,
        "steps": [
            {
                "sequence": 0,
                "event_id": run["events"][0]["id"],
                "kind": "request_recorded",
                "event_type": "message",
                "causal_parent_ids": [],
            },
            {
                "sequence": 1,
                "event_id": run["events"][1]["id"],
                "kind": "model_call_succeeded",
                "event_type": "model_call",
                "causal_parent_ids": [run["events"][0]["id"]],
            },
            {
                "sequence": 2,
                "event_id": run["events"][2]["id"],
                "kind": "final_response",
                "event_type": "message",
                "causal_parent_ids": [run["events"][1]["id"]],
            },
        ],
        "context_manifest_ref": run["events"][1]["artifact_refs"][0],
        "final_response_event_id": run["events"][2]["id"],
        "model_call_count": 1,
        "tool_call_count": 0,
    }


def test_candidate_memory_is_excluded_from_chat_context(tmp_path: Any) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)
    created = request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        json={
            "schema_version": 1,
            "title": "Unreviewed instruction",
            "content": "This model-generated candidate must not become runtime authority.",
            "category": "governance",
            "domains": ["software"],
            "topics": [],
        },
    )
    assert created.status_code == 201

    response = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={"Idempotency-Key": "chat-excludes-candidate"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC2",
            "session_id": "ses_01ARZ3NDEKTSV4RRFFQ69G5FC2",
            "message": "What instructions apply?",
            "token_budget": 256,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "No approved memory was available for this request."
    assert payload["citations"] == []
    assert payload["context_manifest"]["items"] == []


def test_typed_multi_step_run_is_reconstructed_after_restart(tmp_path: Any) -> None:
    data_root = tmp_path / "runtime"
    session_id = "ses_01ARZ3NDEKTSV4RRFFQ69G5FM0"
    run_id = "run_01ARZ3NDEKTSV4RRFFQ69G5FM0"
    task_id = "tsk_01ARZ3NDEKTSV4RRFFQ69G5FM0"
    manifest = ContextManifest(
        id="ctx_01ARZ3NDEKTSV4RRFFQ69G5FM0",
        schema_version=1,
        task_id=task_id,
        compiled_at="2026-08-30T06:30:00Z",
        token_budget=256,
        total_token_count=0,
        policy_hash="sha256:" + "3" * 64,
        items=(),
    )
    repository = SQLiteChatRunRepository(data_root)
    manifest_ref = repository.put_context_manifest(manifest)
    observation_ref = LocalArtifactStore(data_root / "artifacts").put(b"governed evidence")
    model = ModelIdentity(
        provider="fake",
        name="deterministic-tool-v1",
        configuration_hash="sha256:" + "4" * 64,
    )
    actors = {
        ActorType.HUMAN: "human_test_operator",
        ActorType.MODEL: "model_deterministic_tool",
        ActorType.TOOL: "tool_file_read",
        ActorType.SYSTEM: "system_agent_runtime",
    }
    trust = {
        ActorType.HUMAN: TrustClass.HUMAN_VERIFIED,
        ActorType.MODEL: TrustClass.MODEL_GENERATED,
        ActorType.TOOL: TrustClass.EXTERNAL_UNTRUSTED,
        ActorType.SYSTEM: TrustClass.SYSTEM,
    }
    specifications = (
        ("M1", EventType.MESSAGE, "request_recorded", ActorType.HUMAN, ()),
        ("M2", EventType.OUTCOME, "context_compiled", ActorType.SYSTEM, (manifest_ref,)),
        ("M3", EventType.MODEL_CALL, "model_call_pending", ActorType.SYSTEM, ()),
        ("M4", EventType.OUTCOME, "model_call_succeeded", ActorType.MODEL, ()),
        ("M5", EventType.TOOL_CALL, "tool_requested", ActorType.MODEL, ()),
        ("M6", EventType.APPROVAL, "grant_approved", ActorType.HUMAN, ()),
        ("M7", EventType.TOOL_CALL, "tool_call_claimed", ActorType.TOOL, ()),
        ("M8", EventType.OBSERVATION, "observation", ActorType.TOOL, (observation_ref,)),
        ("M9", EventType.MODEL_CALL, "model_call_pending", ActorType.SYSTEM, ()),
        ("MA", EventType.OUTCOME, "model_call_succeeded", ActorType.MODEL, ()),
        ("MB", EventType.MESSAGE, "final_response", ActorType.MODEL, ()),
    )
    entries: list[tuple[Event, str]] = []
    parent: str | None = None
    for sequence, (suffix, event_type, operation, actor_type, artifact_refs) in enumerate(
        specifications
    ):
        payload = {"operation": operation}
        if operation == "final_response":
            payload.update({"answer": "Governed tool trajectory complete.", "citations": []})
        occurred_at = datetime(2026, 8, 30, 6, 30, tzinfo=UTC) + timedelta(
            seconds=sequence
        )
        run_event = Event(
            id=f"evt_01ARZ3NDEKTSV4RRFFQ69G5F{suffix}",
            schema_version=1,
            session_id=session_id,
            run_id=run_id,
            task_id=task_id,
            actor=Actor(id=actors[actor_type], type=actor_type),
            event_type=event_type,
            observed_at=occurred_at,
            recorded_at=occurred_at,
            payload_hash=canonical_payload_hash(payload),
            artifact_refs=artifact_refs,
            causal_parent_ids=() if parent is None else (parent,),
            trust_class=trust[actor_type],
            sensitivity=Sensitivity.INTERNAL,
            payload=payload,
            model=(
                model
                if actor_type is ActorType.MODEL or event_type is EventType.MODEL_CALL
                else None
            ),
        )
        entries.append((run_event, f"multi-step-run:{sequence}"))
        parent = run_event.id
    repository.append_many(entries)

    replayed = repository.response_from_run(repository.inspect(session_id, run_id))
    assert replayed.answer == "Governed tool trajectory complete."
    assert replayed.provider.model == "deterministic-tool-v1"

    restarted = create_app(data_root=data_root, vault_root=None)
    inspected = request(
        restarted,
        "GET",
        f"/api/v1/chat/sessions/{session_id}/runs/{run_id}",
    )

    assert inspected.status_code == 200, inspected.text
    payload = inspected.json()
    assert payload["context_manifest"] == manifest.model_dump(mode="json")
    assert payload["reconstruction"]["state"] == "completed"
    assert payload["reconstruction"]["model_call_count"] == 2
    assert payload["reconstruction"]["tool_call_count"] == 1
    assert [step["kind"] for step in payload["reconstruction"]["steps"]] == [
        specification[2] for specification in specifications
    ]

    mismatched_root = tmp_path / "mismatched-runtime"
    mismatched_repository = SQLiteChatRunRepository(mismatched_root)
    mismatched_manifest_ref = mismatched_repository.put_context_manifest(
        manifest.model_copy(update={"task_id": "tsk_01ARZ3NDEKTSV4RRFFQ69G5FM1"})
    )
    LocalArtifactStore(mismatched_root / "artifacts").put(b"governed evidence")
    mismatched_entries = tuple(
        (
            run_event.model_copy(
                update={"artifact_refs": (mismatched_manifest_ref,)}
            )
            if run_event.payload["operation"] == "context_compiled"
            else run_event,
            idempotency_key,
        )
        for run_event, idempotency_key in entries
    )
    mismatched_repository.append_many(mismatched_entries)

    with pytest.raises(ChatRunIncompleteError):
        mismatched_repository.inspect(session_id, run_id)


def test_retrieval_ranking_and_omissions_are_deterministic_and_inspectable(
    tmp_path: Any,
) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(data_root=data_root, vault_root=None)

    def create_memory(title: str, content: str, *, approve: bool, suffix: str) -> dict[str, Any]:
        node = request(
            app,
            "POST",
            "/api/v1/memory/nodes",
            json={
                "schema_version": 1,
                "title": title,
                "content": content,
                "category": "governance",
                "domains": ["software"],
                "topics": [],
            },
        ).json()["node"]
        if approve:
            reviewed = request(
                app,
                "POST",
                f"/api/v1/memory/nodes/{node['id']}/reviews",
                headers={"Idempotency-Key": f"approve-ranking-{suffix}"},
                json={
                    "schema_version": 1,
                    "request_id": f"evt_01ARZ3NDEKTSV4RRFFQ69G5F{suffix}",
                    "decision": "approved",
                },
            )
            assert reviewed.status_code == 200
        return node

    oversized = create_memory(
        "Detailed resonance appendix",
        " ".join(["resonance"] * 12),
        approve=True,
        suffix="D3",
    )
    selected = create_memory(
        "Resonance rule",
        "resonance oscillator",
        approve=True,
        suffix="D4",
    )
    irrelevant = create_memory(
        "Deployment process",
        "production releases require review",
        approve=True,
        suffix="D5",
    )
    create_memory(
        "Unapproved resonance instruction",
        "resonance candidate must not become authority",
        approve=False,
        suffix="D6",
    )

    response = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={"Idempotency-Key": "chat-ranked-evidence"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FD7",
            "session_id": "ses_01ARZ3NDEKTSV4RRFFQ69G5FD7",
            "message": "What resonance rule applies?",
            "token_budget": 4,
        },
    )

    assert response.status_code == 200, response.text
    manifest = response.json()["context_manifest"]
    assert [item["record_id"] for item in manifest["items"]] == [selected["id"]]
    assert manifest["items"][0]["inclusion_reason"].startswith(
        "approved lexical evidence rank="
    )
    assert {item["record_id"]: item["reason"] for item in manifest["omissions"]} == {
        oversized["id"]: "token_budget",
        irrelevant["id"]: "no_query_match",
    }
    assert manifest["exclusion_summary"] == {
        "not_approved_count": 1,
        "missing_source_count": 0,
        "superseded_count": 0,
        "conflict_count": 0,
    }
    assert response.json()["citations"] == [
        {
            "record_id": selected["id"],
            "content_hash": selected["content_hash"],
            "title": "Resonance rule",
            "retrieval_rank": 2,
            "retrieval_score": 9,
        }
    ]
