from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from oscillink_agent.agent_runtime.tools import FileReadToolRequest
from oscillink_agent.api import create_app
from oscillink_agent.capabilities.broker import CapabilityBroker, CapabilityDeniedError
from oscillink_agent.providers.fake import DeterministicFakeProvider


def request(
    app: object,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers, json=json_body)

    return asyncio.run(send())


def test_approved_file_read_runs_once_and_is_reconstructed_after_restart(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    scope_root = tmp_path / "portable-workspace"
    scope_root.mkdir()
    (scope_root / "evidence.txt").write_text(
        "untrusted observation content\n",
        encoding="utf-8",
    )
    provider = DeterministicFakeProvider(
        tool_request=FileReadToolRequest(
            schema_version=1,
            operation="file.read",
            scope_id="workspace_a",
            target="evidence.txt",
            max_bytes=4096,
        )
    )
    app = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        capability_scopes={"workspace_a": scope_root},
        workspace_credential="test-private-credential",
        workspace_actor_id="human_governor",
    )
    auth = {"Authorization": "Bearer test-private-credential"}

    pending = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={**auth, "Idempotency-Key": "governed-file-read-run"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000030",
            "session_id": "ses_01J00000000000000000000030",
            "message": "Use one approved file read.",
            "token_budget": 128,
        },
    )

    assert pending.status_code == 202, pending.text
    pending_payload = pending.json()
    assert pending_payload["state"] == "awaiting_approval"
    assert pending_payload["request"] == {
        "schema_version": 1,
        "operation": "file.read",
        "scope_id": "workspace_a",
        "target": "evidence.txt",
        "max_bytes": 4096,
    }
    assert str(scope_root) not in pending.text

    approved = request(
        app,
        "POST",
        (
            f"/api/v1/capabilities/sessions/{pending_payload['session_id']}"
            f"/runs/{pending_payload['run_id']}"
            f"/requests/{pending_payload['tool_request_event_id']}/decision"
        ),
        headers={**auth, "Idempotency-Key": "approve-governed-file-read"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000031",
            "decision": "approved",
        },
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["answer"] == (
        "Grounded in approved memory with one external untrusted file observation."
    )
    assert str(scope_root) not in approved.text

    restarted = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        capability_scopes={"workspace_a": scope_root},
        workspace_credential="test-private-credential",
        workspace_actor_id="human_governor",
    )
    inspected = request(
        restarted,
        "GET",
        (
            f"/api/v1/chat/sessions/{pending_payload['session_id']}"
            f"/runs/{pending_payload['run_id']}"
        ),
        headers=auth,
    )
    assert inspected.status_code == 200, inspected.text
    run = inspected.json()
    assert [event["payload"]["operation"] for event in run["events"]] == [
        "request_recorded",
        "context_compiled",
        "model_call_pending",
        "model_call_succeeded",
        "tool_requested",
        "grant_approved",
        "tool_call_claimed",
        "observation",
        "model_call_pending",
        "model_call_succeeded",
        "final_response",
    ]
    observation = run["events"][7]
    assert observation["trust_class"] == "external_untrusted"
    assert observation["payload"]["scope_id"] == "workspace_a"
    assert observation["payload"]["target"] == "evidence.txt"
    assert str(scope_root) not in json.dumps(run)
    assert run["reconstruction"]["state"] == "completed"
    assert run["reconstruction"]["model_call_count"] == 2
    assert run["reconstruction"]["tool_call_count"] == 1

    replayed = request(
        restarted,
        "POST",
        (
            f"/api/v1/capabilities/sessions/{pending_payload['session_id']}"
            f"/runs/{pending_payload['run_id']}"
            f"/requests/{pending_payload['tool_request_event_id']}/decision"
        ),
        headers={**auth, "Idempotency-Key": "approve-governed-file-read"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000031",
            "decision": "approved",
        },
    )
    assert replayed.status_code == 200
    assert replayed.json() == approved.json()

    grant_id = run["events"][5]["payload"]["grant_id"]
    broker = CapabilityBroker(
        data_root=data_root,
        scope_roots={"workspace_a": scope_root},
    )
    try:
        broker.execute_file_read(
            grant_id,
            subject_actor_id=run["events"][3]["actor"]["id"],
            now=datetime.now(UTC),
        )
    except CapabilityDeniedError as error:
        assert error.code == "grant_consumed"
    else:
        raise AssertionError("consumed grant was reusable after restart")


def test_denial_is_terminal_and_callers_cannot_submit_preapproved_grants(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    scope_root = tmp_path / "portable-workspace"
    scope_root.mkdir()
    (scope_root / "denied.txt").write_text("must not be read", encoding="utf-8")
    provider = DeterministicFakeProvider(
        tool_request=FileReadToolRequest(
            schema_version=1,
            operation="file.read",
            scope_id="workspace_a",
            target="denied.txt",
            max_bytes=1024,
        )
    )
    app = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        capability_scopes={"workspace_a": scope_root},
        workspace_credential="test-private-credential",
        workspace_actor_id="human_governor",
    )
    auth = {"Authorization": "Bearer test-private-credential"}
    pending = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={**auth, "Idempotency-Key": "denied-file-read-run"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000032",
            "session_id": "ses_01J00000000000000000000032",
            "message": "Request a file that will be denied.",
            "token_budget": 64,
        },
    ).json()
    decision_url = (
        f"/api/v1/capabilities/sessions/{pending['session_id']}"
        f"/runs/{pending['run_id']}"
        f"/requests/{pending['tool_request_event_id']}/decision"
    )

    fabricated = request(
        app,
        "POST",
        decision_url,
        headers={**auth, "Idempotency-Key": "fabricated-grant"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000033",
            "decision": "approved",
            "grant": {
                "capability": "file.read",
                "already_approved": True,
            },
        },
    )
    assert fabricated.status_code == 422

    denied = request(
        app,
        "POST",
        decision_url,
        headers={**auth, "Idempotency-Key": "deny-file-read"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000034",
            "decision": "denied",
        },
    )
    assert denied.status_code == 200, denied.text
    assert denied.json()["state"] == "denied"
    assert not (data_root / "capabilities.sqlite3").exists()

    inspected = request(
        app,
        "GET",
        f"/api/v1/chat/sessions/{pending['session_id']}/runs/{pending['run_id']}",
        headers=auth,
    )
    assert inspected.status_code == 200
    assert inspected.json()["events"][-1]["payload"]["operation"] == "grant_denied"
    assert inspected.json()["reconstruction"]["state"] == "failed"


def test_file_failure_is_terminal_inspectable_and_not_retried(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    scope_root = tmp_path / "portable-workspace"
    scope_root.mkdir()
    provider = DeterministicFakeProvider(
        tool_request=FileReadToolRequest(
            schema_version=1,
            operation="file.read",
            scope_id="workspace_a",
            target="missing.txt",
            max_bytes=1024,
        )
    )
    app = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        capability_scopes={"workspace_a": scope_root},
        workspace_credential="test-private-credential",
    )
    auth = {"Authorization": "Bearer test-private-credential"}
    pending = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={**auth, "Idempotency-Key": "missing-file-run"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000035",
            "session_id": "ses_01J00000000000000000000035",
            "message": "Read a missing portable file.",
            "token_budget": 64,
        },
    ).json()
    decision_url = (
        f"/api/v1/capabilities/sessions/{pending['session_id']}"
        f"/runs/{pending['run_id']}"
        f"/requests/{pending['tool_request_event_id']}/decision"
    )
    decision_body = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000036",
        "decision": "approved",
    }

    failed = request(
        app,
        "POST",
        decision_url,
        headers={**auth, "Idempotency-Key": "approve-missing-file"},
        json_body=decision_body,
    )
    assert failed.status_code == 409
    assert failed.json()["detail"]["code"] == "file_unavailable"
    assert str(scope_root) not in failed.text

    inspected = request(
        app,
        "GET",
        f"/api/v1/chat/sessions/{pending['session_id']}/runs/{pending['run_id']}",
        headers=auth,
    )
    run = inspected.json()
    assert [event["payload"]["operation"] for event in run["events"]][-3:] == [
        "grant_approved",
        "tool_call_claimed",
        "tool_failed",
    ]
    assert run["events"][-1]["payload"]["failure_kind"] == "file_unavailable"
    assert run["reconstruction"]["state"] == "failed"
    assert str(scope_root) not in json.dumps(run)

    retried = request(
        app,
        "POST",
        decision_url,
        headers={**auth, "Idempotency-Key": "approve-missing-file"},
        json_body=decision_body,
    )
    assert retried.status_code == 409
    assert retried.json()["detail"]["code"] == "file_unavailable"


@pytest.mark.parametrize("failure_code", ["grant_expired", "subject_mismatch"])
def test_broker_denials_are_terminal_run_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_code: str,
) -> None:
    data_root = tmp_path / "runtime"
    scope_root = tmp_path / "portable-workspace"
    scope_root.mkdir()
    (scope_root / "bounded.txt").write_text("bounded", encoding="utf-8")
    provider = DeterministicFakeProvider(
        tool_request=FileReadToolRequest(
            schema_version=1,
            operation="file.read",
            scope_id="workspace_a",
            target="bounded.txt",
            max_bytes=1024,
        )
    )

    def deny_execution(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise CapabilityDeniedError(failure_code)

    monkeypatch.setattr(CapabilityBroker, "execute_file_read", deny_execution)
    app = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        capability_scopes={"workspace_a": scope_root},
        workspace_credential="test-private-credential",
    )
    auth = {"Authorization": "Bearer test-private-credential"}
    pending = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={**auth, "Idempotency-Key": f"{failure_code}-run"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000037",
            "session_id": "ses_01J00000000000000000000037",
            "message": "Exercise a terminal broker denial.",
            "token_budget": 64,
        },
    ).json()
    denied = request(
        app,
        "POST",
        (
            f"/api/v1/capabilities/sessions/{pending['session_id']}"
            f"/runs/{pending['run_id']}"
            f"/requests/{pending['tool_request_event_id']}/decision"
        ),
        headers={**auth, "Idempotency-Key": f"approve-{failure_code}"},
        json_body={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000038",
            "decision": "approved",
        },
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == failure_code

    inspected = request(
        app,
        "GET",
        f"/api/v1/chat/sessions/{pending['session_id']}/runs/{pending['run_id']}",
        headers=auth,
    ).json()
    assert inspected["events"][-1]["payload"] == {
        "operation": "tool_failed",
        "failure_kind": failure_code,
    }
    assert inspected["reconstruction"]["state"] == "failed"
