from __future__ import annotations

import asyncio
import json
import secrets
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI

from oscillink_agent.api import create_app
from oscillink_agent.storage.artifacts import LocalArtifactStore


def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    credential: str | None = None,
    idempotency_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        headers: dict[str, str] = {}
        if credential is not None:
            headers["Authorization"] = f"Bearer {credential}"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers, json=payload)

    return asyncio.run(send())


def _expect(response: httpx.Response, status_code: int) -> dict[str, Any]:
    if response.status_code != status_code:
        raise AssertionError(
            f"{response.request.method} {response.request.url.path} returned "
            f"{response.status_code}: {response.text}"
        )
    value = response.json()
    if not isinstance(value, dict):
        raise AssertionError("API response was not a JSON object")
    return value


def _run_journey(root: Path) -> dict[str, bool | int | str]:
    data_root = root / "runtime"
    vault_root = root / "reviewed-source"
    import_root = root / "selected-evidence"
    vault_root.mkdir()
    import_root.mkdir()
    (vault_root / "Reviewed.md").write_text(
        """---
type: research-note
status: active
domains: [software]
---
# Reviewed source connector

This curated connector record still requires explicit product approval.
""",
        encoding="utf-8",
        newline="\n",
    )
    (import_root / "evidence.md").write_text(
        "# External evidence\n\nUntrusted evidence cannot authorize itself.\n",
        encoding="utf-8",
        newline="\n",
    )
    credential = secrets.token_urlsafe(32)
    app = create_app(
        data_root=data_root,
        vault_root=vault_root,
        import_scopes={"user_selection": import_root},
        workspace_credential=credential,
        workspace_actor_id="human_milestone_reviewer",
    )
    observed_responses: list[httpx.Response] = []

    anonymous = _request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        payload={
            "schema_version": 1,
            "title": "Unauthorized candidate",
            "content": "This must not be persisted.",
            "category": "governance",
            "domains": ["software"],
        },
    )
    observed_responses.append(anonymous)
    if anonymous.status_code != 401 or data_root.exists():
        raise AssertionError("anonymous mutation did not fail before storage initialization")

    source_status = _request(
        app,
        "GET",
        "/api/v1/memory/sources/obsidian",
        credential=credential,
    )
    import_sources = _request(
        app,
        "GET",
        "/api/v1/artifact-imports/sources",
        credential=credential,
    )
    observed_responses.extend((source_status, import_sources))
    if _expect(source_status, 200)["state"] != "configured":
        raise AssertionError("reviewed source was not reported as configured")
    sources_payload = _expect(import_sources, 200)
    if sources_payload["scopes"][0]["targets"][0]["target"] != "evidence.md":
        raise AssertionError("portable import target was not enumerated")
    if data_root.exists():
        raise AssertionError("read-only source discovery initialized storage")

    created_response = _request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        credential=credential,
        payload={
            "schema_version": 1,
            "title": "Phase coherence policy",
            "content": "Phase coherence policy requires approved revision citations.",
            "category": "governance",
            "domains": ["software"],
            "topics": ["phase coherence"],
        },
    )
    observed_responses.append(created_response)
    created = _expect(created_response, 201)["node"]
    if created["authority_state"] != "candidate":
        raise AssertionError("native memory did not begin as a candidate")

    before_sync = _request(app, "GET", "/api/v1/memory/nodes", credential=credential)
    observed_responses.append(before_sync)
    if _expect(before_sync, 200)["count"] != 1:
        raise AssertionError("configured source synchronized automatically")

    sync_payload = {
        "schema_version": 1,
        "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC3",
    }
    sync_response = _request(
        app,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        credential=credential,
        idempotency_key="milestone-one-source-sync",
        payload=sync_payload,
    )
    observed_responses.append(sync_response)
    synchronized = _expect(sync_response, 200)
    if synchronized["created"] != 1 or synchronized["issues"] != 0:
        raise AssertionError("explicit source synchronization did not persist cleanly")

    import_response = _request(
        app,
        "POST",
        "/api/v1/artifact-imports",
        credential=credential,
        idempotency_key="milestone-one-artifact-import",
        payload={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC4",
            "observed_at": "2026-08-30T05:30:00Z",
            "scope_id": "user_selection",
            "target": "evidence.md",
            "target_record_id": created["id"],
        },
    )
    observed_responses.append(import_response)
    imported = _expect(import_response, 201)
    if imported["association"]["state"] != "candidate":
        raise AssertionError("artifact import did not create a pending relationship")
    proposal_id = imported["association"]["event_id"]

    pending_response = _request(
        app,
        "GET",
        "/api/v1/memory-proposals",
        credential=credential,
    )
    observed_responses.append(pending_response)
    pending = _expect(pending_response, 200)["proposals"]
    if len(pending) != 1 or pending[0]["state"] != "pending_review":
        raise AssertionError("pending proposal was not projected durably")

    decision_response = _request(
        app,
        "POST",
        f"/api/v1/memory-proposals/{proposal_id}/decisions",
        credential=credential,
        idempotency_key="milestone-one-proposal-decision",
        payload={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC5",
            "observed_at": "2026-08-30T05:31:00Z",
            "decision": "approved",
        },
    )
    observed_responses.append(decision_response)
    if _expect(decision_response, 200)["state"] != "approved":
        raise AssertionError("proposal relationship was not approved")

    still_candidate_response = _request(
        app,
        "GET",
        f"/api/v1/memory/nodes/{created['id']}",
        credential=credential,
    )
    observed_responses.append(still_candidate_response)
    if _expect(still_candidate_response, 200)["node"]["authority_state"] != "candidate":
        raise AssertionError("proposal approval silently promoted memory authority")

    before_approval_response = _request(
        app,
        "POST",
        "/api/v1/chat/messages",
        credential=credential,
        idempotency_key="milestone-one-chat-before-approval",
        payload={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC6",
            "session_id": "ses_01ARZ3NDEKTSV4RRFFQ69G5FC6",
            "message": "What phase coherence policy applies?",
            "token_budget": 256,
        },
    )
    observed_responses.append(before_approval_response)
    before_approval = _expect(before_approval_response, 200)
    if before_approval["citations"] != [] or before_approval["context_manifest"]["items"] != []:
        raise AssertionError("candidate or untrusted content entered model context")

    review_response = _request(
        app,
        "POST",
        f"/api/v1/memory/nodes/{created['id']}/reviews",
        credential=credential,
        idempotency_key="milestone-one-memory-approval",
        payload={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC7",
            "decision": "approved",
        },
    )
    observed_responses.append(review_response)
    if _expect(review_response, 200)["node"]["authority_state"] != "approved":
        raise AssertionError("explicit memory approval was not persisted")

    chat_response = _request(
        app,
        "POST",
        "/api/v1/chat/messages",
        credential=credential,
        idempotency_key="milestone-one-chat-after-approval",
        payload={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FC8",
            "session_id": "ses_01ARZ3NDEKTSV4RRFFQ69G5FC8",
            "message": "What phase coherence policy applies?",
            "token_budget": 256,
        },
    )
    observed_responses.append(chat_response)
    chat = _expect(chat_response, 200)
    items = chat["context_manifest"]["items"]
    citations = chat["citations"]
    approved_only_context = (
        len(items) == 1
        and len(citations) == 1
        and items[0]["record_id"] == created["id"]
        and items[0]["content_hash"] == created["content_hash"]
        and items[0]["status"] == "approved"
        and citations[0]["record_id"] == created["id"]
        and citations[0]["content_hash"] == created["content_hash"]
    )
    if not approved_only_context:
        raise AssertionError("chat did not use only the approved immutable revision")

    restarted = create_app(
        data_root=data_root,
        vault_root=vault_root,
        import_scopes={"user_selection": import_root},
        workspace_credential=credential,
        workspace_actor_id="human_milestone_reviewer",
    )
    recovered_memory_response = _request(
        restarted,
        "GET",
        f"/api/v1/memory/nodes/{created['id']}",
        credential=credential,
    )
    recovered_proposal_response = _request(
        restarted,
        "GET",
        "/api/v1/memory-proposals",
        credential=credential,
    )
    recovered_run_response = _request(
        restarted,
        "GET",
        f"/api/v1/chat/sessions/{chat['session_id']}/runs/{chat['run_id']}",
        credential=credential,
    )
    replayed_sync_response = _request(
        restarted,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        credential=credential,
        idempotency_key="milestone-one-source-sync",
        payload=sync_payload,
    )
    observed_responses.extend(
        (
            recovered_memory_response,
            recovered_proposal_response,
            recovered_run_response,
            replayed_sync_response,
        )
    )
    recovered_memory = _expect(recovered_memory_response, 200)
    recovered_proposals = _expect(recovered_proposal_response, 200)
    recovered_run = _expect(recovered_run_response, 200)
    replayed_sync = _expect(replayed_sync_response, 200)
    canonical_state_recovered = (
        recovered_memory["node"]["authority_state"] == "approved"
        and replayed_sync == synchronized
    )
    proposal_recovered = (
        len(recovered_proposals["proposals"]) == 1
        and recovered_proposals["proposals"][0]["state"] == "approved"
    )
    run_recovered = (
        recovered_run["context_manifest"] == chat["context_manifest"]
        and [event["event_type"] for event in recovered_run["events"]]
        == ["message", "outcome", "model_call", "outcome", "message"]
    )
    if not canonical_state_recovered or not proposal_recovered or not run_recovered:
        raise AssertionError("restart did not recover canonical Milestone 1 state")

    artifact_store = LocalArtifactStore(data_root / "artifacts")
    artifact_store.verify(imported["artifact"]["artifact_ref"])
    artifact_recovered = True

    exposed = "\n".join(response.text for response in observed_responses)
    with closing(sqlite3.connect(data_root / "events.sqlite3")) as connection:
        exposed += "\n" + "\n".join(
            row[0] for row in connection.execute("SELECT event_json FROM events")
        )
    with closing(sqlite3.connect(data_root / "memory.sqlite3")) as connection:
        exposed += "\n" + "\n".join(
            row[0]
            for row in connection.execute(
                """
                SELECT record_json FROM memory_records
                UNION ALL
                SELECT record_json FROM memory_record_revisions
                UNION ALL
                SELECT source_key || ':' || source_locator FROM memory_source_bindings
                UNION ALL
                SELECT event_id || ':' || idempotency_key || ':' || source_key || ':'
                    || snapshot_hash FROM memory_source_syncs
                UNION ALL
                SELECT event_id || ':' || idempotency_key || ':' || record_id || ':'
                    || content_hash || ':' || decision FROM memory_reviews
                """
            )
        )
    sanitized = all(
        secret not in exposed
        for secret in (credential, str(root), str(vault_root), str(import_root), str(data_root))
    )
    if not sanitized:
        raise AssertionError("credential or absolute source path crossed a durable boundary")

    return {
        "anonymous_fail_closed": True,
        "approved_only_context": approved_only_context,
        "artifact_recovered": artifact_recovered,
        "canonical_state_recovered": canonical_state_recovered,
        "proposal_recovered": proposal_recovered,
        "run_recovered": run_recovered,
        "sanitized": sanitized,
        "schema_version": 1,
        "state": "passed",
    }


def main() -> None:
    temporary_path: Path
    with tempfile.TemporaryDirectory(prefix="oscillink-m1-") as directory:
        temporary_path = Path(directory)
        result = _run_journey(temporary_path)
    result["temporary_state_removed"] = not temporary_path.exists()
    if not result["temporary_state_removed"]:
        raise AssertionError("temporary acceptance state was not removed")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
