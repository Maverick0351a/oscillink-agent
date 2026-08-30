from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from oscillink_agent.api import create_app
from oscillink_agent.workspaces.service import LocalWorkspaceAuth


def request(
    app: object,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers, json=json)

    return asyncio.run(send())


def test_anonymous_memory_creation_fails_without_initializing_storage(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        workspace_credential="test-private-credential",
    )

    response = request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        json={
            "schema_version": 1,
            "title": "Candidate",
            "content": "Unapproved content",
            "category": "learning",
            "domains": ["ai"],
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "code": "workspace_auth_required",
            "message": "A valid local workspace credential is required.",
        }
    }
    assert not data_root.exists()


def test_anonymous_source_sync_fails_without_scanning_or_initializing_storage(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    vault = tmp_path / "vault"
    vault.mkdir()
    app = create_app(
        data_root=data_root,
        vault_root=vault,
        workspace_credential="test-private-credential",
    )

    response = request(
        app,
        "POST",
        "/api/v1/memory/sources/obsidian/sync",
        headers={"Idempotency-Key": "anonymous-source-sync"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FB9",
        },
    )

    assert response.status_code == 401, response.json()
    assert not data_root.exists()


@pytest.mark.parametrize(
    ("method", "path", "payload", "headers"),
    (
        ("GET", "/api/v1/artifact-imports/sources", None, None),
        ("GET", "/api/v1/memory-proposals", None, None),
        (
            "POST",
            "/api/v1/memory-proposals/evt_01J00000000000000000000600/decisions",
            {
                "schema_version": 1,
                "request_id": "evt_01J00000000000000000000601",
                "observed_at": "2026-08-29T23:00:00Z",
                "decision": "approved",
            },
            {"Idempotency-Key": "anonymous-proposal-decision"},
        ),
    ),
)
def test_anonymous_import_and_proposal_surfaces_fail_without_storage(
    tmp_path: Path,
    method: str,
    path: str,
    payload: dict[str, object] | None,
    headers: dict[str, str] | None,
) -> None:
    data_root = tmp_path / "runtime"
    source_root = tmp_path / "selected"
    source_root.mkdir()
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": source_root},
        workspace_credential="test-private-credential",
    )

    response = request(app, method, path, json=payload, headers=headers)

    assert response.status_code == 401
    assert not data_root.exists()


def test_anonymous_chat_fails_without_initializing_storage(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        workspace_credential="test-private-credential",
    )

    response = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={"Idempotency-Key": "anonymous-chat"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "session_id": "ses_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "message": "Do not persist this request.",
            "token_budget": 128,
        },
    )

    assert response.status_code == 401, response.json()
    assert not data_root.exists()


def test_anonymous_run_inspection_fails_without_initializing_storage(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        vault_root=None,
        workspace_credential="test-private-credential",
    )

    response = request(
        app,
        "GET",
        "/api/v1/chat/sessions/ses_01ARZ3NDEKTSV4RRFFQ69G5FAV/"
        "runs/run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )

    assert response.status_code == 401, response.json()
    assert not data_root.exists()


def test_anonymous_artifact_import_fails_without_initializing_storage(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    import_root = tmp_path / "selected"
    import_root.mkdir()
    app = create_app(
        data_root=data_root,
        vault_root=None,
        import_scopes={"user_selection": import_root},
        workspace_credential="test-private-credential",
    )

    response = request(
        app,
        "POST",
        "/api/v1/artifact-imports",
        headers={"Idempotency-Key": "anonymous-import"},
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "observed_at": "2026-08-29T14:00:00Z",
            "scope_id": "user_selection",
            "target": "missing.txt",
        },
    )

    assert response.status_code == 401, response.json()
    assert not data_root.exists()


def test_valid_workspace_credential_allows_candidate_creation(tmp_path: Path) -> None:
    app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=None,
        workspace_credential="test-private-credential",
    )

    response = request(
        app,
        "POST",
        "/api/v1/memory/nodes",
        headers={"Authorization": "Bearer test-private-credential"},
        json={
            "schema_version": 1,
            "title": "Authenticated candidate",
            "content": "Still requires human review.",
            "category": "note",
            "domains": ["ai_ml"],
        },
    )

    assert response.status_code == 201, response.json()
    assert response.json()["node"]["authority_state"] == "candidate"


def test_workspace_identity_is_server_derived(tmp_path: Path) -> None:
    app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=None,
        workspace_credential="test-private-credential",
    )

    response = request(
        app,
        "GET",
        "/api/v1/workspace",
        headers={
            "Authorization": "Bearer test-private-credential",
            "X-Actor-Id": "human_attacker",
            "X-Workspace-Id": "ws_attacker",
        },
    )

    assert response.status_code == 200, response.json()
    assert response.json() == {
        "schema_version": 1,
        "workspace_id": "ws_local",
        "actor_id": "human_local_user",
    }


def test_chat_events_use_the_server_derived_actor(tmp_path: Path) -> None:
    app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=None,
        workspace_credential="test-private-credential",
        workspace_actor_id="human_test_operator",
    )
    headers = {
        "Authorization": "Bearer test-private-credential",
        "Idempotency-Key": "server-actor-chat",
    }

    created = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers=headers,
        json={
            "schema_version": 1,
            "request_id": "evt_01ARZ3NDEKTSV4RRFFQ69G5FA0",
            "session_id": "ses_01ARZ3NDEKTSV4RRFFQ69G5FA0",
            "message": "Which actor submitted this?",
            "token_budget": 128,
        },
    )
    assert created.status_code == 200, created.json()

    inspected = request(
        app,
        "GET",
        (
            f"/api/v1/chat/sessions/{created.json()['session_id']}"
            f"/runs/{created.json()['run_id']}"
        ),
        headers={"Authorization": "Bearer test-private-credential"},
    )

    assert inspected.status_code == 200, inspected.json()
    assert inspected.json()["events"][0]["actor"]["id"] == "human_test_operator"


def test_transport_boundary_allows_only_configured_origin_and_host(
    tmp_path: Path,
) -> None:
    app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=None,
        workspace_credential="test-private-credential",
        allowed_origins=("http://localhost:5173",),
        trusted_hosts=("testserver",),
    )

    allowed = request(
        app,
        "OPTIONS",
        "/api/v1/memory/nodes",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    rejected_origin = request(
        app,
        "OPTIONS",
        "/api/v1/memory/nodes",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    rejected_host = request(
        app,
        "GET",
        "/api/v1/status",
        headers={"Host": "attacker.example"},
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert rejected_origin.status_code == 400
    assert "access-control-allow-origin" not in rejected_origin.headers
    assert rejected_host.status_code == 400


def test_wrong_or_malformed_credentials_fail_without_leaking_secret(
    tmp_path: Path,
) -> None:
    credential = "credential-that-must-not-leak"
    app = create_app(
        data_root=tmp_path / "runtime",
        vault_root=None,
        workspace_credential=credential,
    )

    for authorization in (
        None,
        "",
        "Basic credential-that-must-not-leak",
        "Bearer wrong-credential",
        "Bearer",
    ):
        headers = (
            {"Authorization": authorization}
            if authorization is not None
            else None
        )
        response = request(app, "GET", "/api/v1/workspace", headers=headers)
        assert response.status_code == 401
        assert credential not in response.text

    assert credential not in repr(LocalWorkspaceAuth(credential=credential))
    assert credential not in str(app.routes)
