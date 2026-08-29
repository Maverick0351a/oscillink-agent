import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
from fastapi import FastAPI

from oscillink_agent.api import create_app
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.repository import (
    MemoryAuthorityState,
    MemorySourceKind,
    ProductMemoryRecord,
)
from oscillink_agent.providers import config as provider_config
from oscillink_agent.providers import openai_compatible


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


class _CompletionHandler(BaseHTTPRequestHandler):
    request_body: dict[str, Any] | None = None

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        type(self).request_body = json.loads(self.rfile.read(length))
        body = json.dumps(
            {"choices": [{"message": {"content": "grounded provider answer"}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class _MalformedCompletionHandler(_CompletionHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _approved_record() -> ProductMemoryRecord:
    return ProductMemoryRecord(
        id="mem_01J0000000000000000000000A",
        title="Approved resonance rule",
        content="Only approved resonance evidence may enter model context.",
        authority_state=MemoryAuthorityState.APPROVED,
        source_kind=MemorySourceKind.NATIVE,
        source_key="native",
        source_path=None,
        source_status=None,
        category=MemoryCategory.GOVERNANCE,
        domains=(MemoryDomain.SOFTWARE,),
        topics=(),
        content_hash="sha256:" + "a" * 64,
    )


def _manifest() -> ContextManifest:
    return ContextManifest(
        id="ctx_01J0000000000000000000000A",
        schema_version=1,
        task_id="tsk_01J0000000000000000000000A",
        compiled_at="2026-08-29T09:00:00Z",
        token_budget=128,
        total_token_count=0,
        policy_hash="sha256:" + "b" * 64,
        items=(),
    )


def test_openai_compatible_adapter_sends_only_compiled_selected_evidence() -> None:
    adapter_type = getattr(openai_compatible, "OpenAICompatibleProvider", None)
    assert adapter_type is not None
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CompletionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        adapter = adapter_type(
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            model="local-contract-model",
            timeout_seconds=2,
        )
        result = adapter.generate(
            message="What resonance rule applies?",
            context_manifest=_manifest(),
            records=(_approved_record(),),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.answer == "grounded provider answer"
    assert adapter.projection.model_dump(mode="json") == {
        "kind": "openai_compatible",
        "model": "local-contract-model",
    }
    sent = _CompletionHandler.request_body
    assert sent is not None
    assert sent["model"] == "local-contract-model"
    assert sent["stream"] is False
    system_content = sent["messages"][0]["content"]
    assert "Only approved resonance evidence may enter model context." in system_content
    assert "mem_01J0000000000000000000000A" in system_content


def test_configured_provider_runs_through_governed_api_and_replays_after_restart(
    tmp_path: Any,
) -> None:
    adapter_type = getattr(openai_compatible, "OpenAICompatibleProvider", None)
    assert adapter_type is not None
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CompletionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    adapter = adapter_type(
        base_url=f"http://127.0.0.1:{server.server_port}/v1",
        model="local-contract-model",
        timeout_seconds=2,
    )
    data_root = tmp_path / "runtime"
    try:
        app = create_app(data_root=data_root, vault_root=None, chat_provider=adapter)
        node = request(
            app,
            "POST",
            "/api/v1/memory/nodes",
            json={
                "schema_version": 1,
                "title": "Approved resonance rule",
                "content": "resonance answers must cite approved evidence",
                "category": "governance",
                "domains": ["software"],
                "topics": [],
            },
        ).json()["node"]
        approved = request(
            app,
            "POST",
            f"/api/v1/memory/nodes/{node['id']}/reviews",
            headers={"Idempotency-Key": "approve-provider-contract"},
            json={
                "schema_version": 1,
                "request_id": "evt_01J0000000000000000000000B",
                "decision": "approved",
            },
        )
        assert approved.status_code == 200
        payload = {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000C",
            "session_id": "ses_01J0000000000000000000000C",
            "message": "What resonance rule applies?",
            "token_budget": 64,
        }
        created = request(
            app,
            "POST",
            "/api/v1/chat/messages",
            headers={"Idempotency-Key": "configured-provider-chat"},
            json=payload,
        )
        assert created.status_code == 200, created.text
        assert created.json()["provider"] == {
            "kind": "openai_compatible",
            "model": "local-contract-model",
        }
        assert created.json()["answer"] == "grounded provider answer"

        restarted = create_app(
            data_root=data_root,
            vault_root=None,
            chat_provider=adapter,
        )
        replayed = request(
            restarted,
            "POST",
            "/api/v1/chat/messages",
            headers={"Idempotency-Key": "configured-provider-chat"},
            json=payload,
        )
        assert replayed.status_code == 200, replayed.text
        assert replayed.json() == created.json()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_provider_configuration_selects_ollama_without_exposing_secrets() -> None:
    build_provider = getattr(provider_config, "build_chat_provider", None)
    assert build_provider is not None
    provider = build_provider(
        {
            "OSCILLINK_CHAT_PROVIDER": "ollama",
            "OSCILLINK_CHAT_BASE_URL": "http://127.0.0.1:11434/v1",
            "OSCILLINK_CHAT_MODEL": "qwen3:14b",
            "OSCILLINK_CHAT_API_KEY": "[REDACTED]",
        }
    )

    assert isinstance(provider, openai_compatible.OpenAICompatibleProvider)
    assert provider.projection.model_dump(mode="json") == {
        "kind": "openai_compatible",
        "model": "qwen3:14b",
    }
    assert "[REDACTED]" not in repr(provider.projection)


def test_provider_protocol_failure_is_a_bounded_bad_gateway_response(tmp_path: Any) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MalformedCompletionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    adapter = openai_compatible.OpenAICompatibleProvider(
        base_url=f"http://127.0.0.1:{server.server_port}/v1",
        model="local-contract-model",
        timeout_seconds=2,
    )
    try:
        app = create_app(
            data_root=tmp_path / "runtime",
            vault_root=None,
            chat_provider=adapter,
        )
        response = request(
            app,
            "POST",
            "/api/v1/chat/messages",
            headers={"Idempotency-Key": "malformed-provider-chat"},
            json={
                "schema_version": 1,
                "request_id": "evt_01J0000000000000000000000D",
                "session_id": "ses_01J0000000000000000000000D",
                "message": "Can this provider answer?",
                "token_budget": 64,
            },
        )
        assert response.status_code == 502
        assert response.json() == {"detail": "configured chat provider failed"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
