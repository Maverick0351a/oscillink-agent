from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from oscillink_agent.api import create_app
from oscillink_agent.chat.contracts import ChatProviderProjection
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.memory.repository import ProductMemoryRecord
from oscillink_agent.providers.base import ProviderResult
from oscillink_agent.providers.openai_compatible import (
    ProviderRequestError,
    ProviderTimeoutError,
)
from oscillink_agent.storage.artifacts import LocalArtifactStore
from oscillink_agent.storage.sqlite import SQLiteEventStore


class StorageObservingProvider:
    def __init__(self, data_root: Path, session_id: str) -> None:
        self._data_root = data_root
        self._session_id = session_id
        self.call_count = 0

    @property
    def projection(self) -> ChatProviderProjection:
        return ChatProviderProjection(kind="fake", model="intent-observer-v1")

    def generate(
        self,
        *,
        message: str,
        context_manifest: ContextManifest,
        records: tuple[ProductMemoryRecord, ...],
    ) -> ProviderResult:
        del message, records
        self.call_count += 1
        database = self._data_root / "events.sqlite3"
        assert database.is_file(), "provider dispatch occurred before durable intent"
        store = SQLiteEventStore(database)
        try:
            events = tuple(store.stream(self._session_id))
        finally:
            store.close()
        assert [event.payload.get("operation") for event in events] == [
            "request_recorded",
            "context_compiled",
            "model_call_pending",
        ]
        context_event = events[1]
        assert context_event.artifact_refs == (context_event.payload["context_manifest_ref"],)
        persisted_manifest = ContextManifest.model_validate_json(
            LocalArtifactStore(self._data_root / "artifacts").get(
                context_event.artifact_refs[0]
            )
        )
        assert persisted_manifest == context_manifest
        return ProviderResult(answer="Provider observed durable intent.")


class FailingProvider:
    def __init__(self) -> None:
        self.call_count = 0

    @property
    def projection(self) -> ChatProviderProjection:
        return ChatProviderProjection(kind="fake", model="failing-provider-v1")

    def generate(
        self,
        *,
        message: str,
        context_manifest: ContextManifest,
        records: tuple[ProductMemoryRecord, ...],
    ) -> ProviderResult:
        del message, context_manifest, records
        self.call_count += 1
        raise ProviderRequestError("private upstream failure detail")


class TimingOutProvider(FailingProvider):
    @property
    def projection(self) -> ChatProviderProjection:
        return ChatProviderProjection(kind="fake", model="timing-out-provider-v1")

    def generate(
        self,
        *,
        message: str,
        context_manifest: ContextManifest,
        records: tuple[ProductMemoryRecord, ...],
    ) -> ProviderResult:
        del message, context_manifest, records
        self.call_count += 1
        raise ProviderTimeoutError("private timeout detail")


class DispatchInterrupted(BaseException):
    pass


class InterruptingProvider:
    def __init__(self) -> None:
        self.call_count = 0

    @property
    def projection(self) -> ChatProviderProjection:
        return ChatProviderProjection(kind="fake", model="interrupting-provider-v1")

    def generate(
        self,
        *,
        message: str,
        context_manifest: ContextManifest,
        records: tuple[ProductMemoryRecord, ...],
    ) -> ProviderResult:
        del message, context_manifest, records
        self.call_count += 1
        raise DispatchInterrupted


class ShouldNotDispatchProvider:
    def __init__(self) -> None:
        self.call_count = 0

    @property
    def projection(self) -> ChatProviderProjection:
        raise AssertionError("provider accessed before durable retry resolution")

    def generate(
        self,
        *,
        message: str,
        context_manifest: ContextManifest,
        records: tuple[ProductMemoryRecord, ...],
    ) -> ProviderResult:
        del message, context_manifest, records
        self.call_count += 1
        raise AssertionError("unsafe provider redispatch")


def request(
    app: object,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers, json=json)

    return asyncio.run(send())


def test_provider_dispatch_observes_durable_request_context_and_pending_intent(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    session_id = "ses_01J00000000000000000000020"
    provider = StorageObservingProvider(data_root, session_id)
    app = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        workspace_credential="test-private-credential",
    )

    response = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers={
            "Authorization": "Bearer test-private-credential",
            "Idempotency-Key": "intent-before-dispatch",
        },
        json={
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000020",
            "session_id": session_id,
            "message": "Persist intent before dispatch.",
            "token_budget": 64,
        },
    )

    assert response.status_code == 200, response.text
    assert provider.call_count == 1
    inspected = request(
        app,
        "GET",
        f"/api/v1/chat/sessions/{response.json()['session_id']}"
        f"/runs/{response.json()['run_id']}",
        headers={"Authorization": "Bearer test-private-credential"},
    )
    assert inspected.status_code == 200, inspected.text
    assert [
        step["kind"] for step in inspected.json()["reconstruction"]["steps"]
    ] == [
        "request_recorded",
        "context_compiled",
        "model_call_pending",
        "model_call_succeeded",
        "final_response",
    ]


def test_provider_failure_is_durable_bounded_and_never_redispatched(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    provider = FailingProvider()
    app = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        workspace_credential="test-private-credential",
    )
    headers = {
        "Authorization": "Bearer test-private-credential",
        "Idempotency-Key": "durable-provider-failure",
    }
    payload = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000021",
        "session_id": "ses_01J00000000000000000000021",
        "message": "Record a bounded provider failure.",
        "token_budget": 64,
    }

    failed = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers=headers,
        json=payload,
    )

    assert failed.status_code == 502
    assert failed.json() == {"detail": "configured chat provider failed"}
    assert "private upstream failure detail" not in failed.text
    store = SQLiteEventStore(data_root / "events.sqlite3")
    try:
        events = tuple(store.stream(payload["session_id"]))
    finally:
        store.close()
    run_id = events[0].run_id
    inspected = request(
        app,
        "GET",
        f"/api/v1/chat/sessions/{payload['session_id']}/runs/{run_id}",
        headers={"Authorization": "Bearer test-private-credential"},
    )
    assert inspected.status_code == 200, inspected.text
    run = inspected.json()
    assert run["reconstruction"]["state"] == "failed"
    assert run["reconstruction"]["steps"][-1]["kind"] == "model_call_failed"
    assert run["events"][-1]["payload"] == {
        "operation": "model_call_failed",
        "failure_kind": "request",
    }

    retried = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers=headers,
        json=payload,
    )
    assert retried.status_code == 502
    assert retried.json() == {"detail": "configured chat provider failed"}
    assert provider.call_count == 1


def test_interrupted_dispatch_is_reconstructed_and_retry_fails_closed(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    provider = InterruptingProvider()
    app = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        workspace_credential="test-private-credential",
    )
    headers = {
        "Authorization": "Bearer test-private-credential",
        "Idempotency-Key": "interrupted-provider-dispatch",
    }
    payload = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000022",
        "session_id": "ses_01J00000000000000000000022",
        "message": "Do not redispatch after interruption.",
        "token_budget": 64,
    }

    with pytest.raises(DispatchInterrupted):
        request(
            app,
            "POST",
            "/api/v1/chat/messages",
            headers=headers,
            json=payload,
        )
    assert provider.call_count == 1

    store = SQLiteEventStore(data_root / "events.sqlite3")
    try:
        events = tuple(store.stream(payload["session_id"]))
    finally:
        store.close()
    run_id = events[0].run_id
    assert events[-1].payload == {"operation": "model_call_interrupted"}

    replacement = ShouldNotDispatchProvider()
    restarted = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=replacement,
        workspace_credential="test-private-credential",
    )
    inspected = request(
        restarted,
        "GET",
        f"/api/v1/chat/sessions/{payload['session_id']}/runs/{run_id}",
        headers={"Authorization": "Bearer test-private-credential"},
    )
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["reconstruction"]["state"] == "interrupted"

    retried = request(
        restarted,
        "POST",
        "/api/v1/chat/messages",
        headers=headers,
        json=payload,
    )
    assert retried.status_code == 409
    assert retried.json()["detail"]["code"] == "provider_dispatch_uncertain"
    assert replacement.call_count == 0


def test_provider_timeout_is_durable_and_replays_without_redispatch(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    provider = TimingOutProvider()
    app = create_app(
        data_root=data_root,
        vault_root=None,
        chat_provider=provider,
        workspace_credential="test-private-credential",
    )
    headers = {
        "Authorization": "Bearer test-private-credential",
        "Idempotency-Key": "durable-provider-timeout",
    }
    payload = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000023",
        "session_id": "ses_01J00000000000000000000023",
        "message": "Record a bounded timeout.",
        "token_budget": 64,
    }

    timed_out = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers=headers,
        json=payload,
    )
    assert timed_out.status_code == 504
    assert timed_out.json() == {"detail": "configured chat provider timed out"}

    store = SQLiteEventStore(data_root / "events.sqlite3")
    try:
        events = tuple(store.stream(payload["session_id"]))
    finally:
        store.close()
    assert events[-1].payload == {
        "operation": "model_call_failed",
        "failure_kind": "timeout",
    }

    retried = request(
        app,
        "POST",
        "/api/v1/chat/messages",
        headers=headers,
        json=payload,
    )
    assert retried.status_code == 504
    assert retried.json() == {"detail": "configured chat provider timed out"}
    assert provider.call_count == 1
