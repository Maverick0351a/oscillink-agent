from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import FastAPI

from oscillink_agent.api import create_app


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
