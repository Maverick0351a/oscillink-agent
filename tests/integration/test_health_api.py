from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

from oscillink_agent.api import create_app
from oscillink_agent.providers.fake import DeterministicFakeProvider
from oscillink_agent.providers.openai_compatible import OpenAICompatibleProvider


@contextmanager
def _provider_server() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/v1/models":
                self.send_error(404)
                return
            body = b'{"data":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(app: object, path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(send())


def test_liveness_is_minimal_and_does_not_initialize_workspace(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        chat_provider=DeterministicFakeProvider(),
        workspace_credential="private-health-credential",
    )

    response = _request(app, "/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": 1,
        "service": "oscillink-agent",
        "state": "alive",
    }
    assert not data_root.exists()


def test_readiness_distinguishes_api_stores_provider_and_broker(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    app = create_app(
        data_root=data_root,
        capability_scopes={"pilot_documents": tmp_path / "documents"},
        chat_provider=DeterministicFakeProvider(),
        workspace_credential="private-health-credential",
    )

    response = _request(app, "/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": 1,
        "service": "oscillink-agent",
        "state": "ready",
        "api": {"state": "ready"},
        "stores": {
            "ledger": {"state": "not_initialized", "record_count": 0},
            "artifacts": {"state": "not_initialized", "record_count": 0},
            "memory": {"state": "not_initialized", "record_count": 0},
        },
        "provider": {
            "state": "ready",
            "kind": "fake",
            "model": "deterministic-v1",
        },
        "capability_broker": {
            "state": "ready",
            "configured_scope_count": 1,
        },
    }
    assert not data_root.exists()


def test_readiness_probes_a_reachable_openai_compatible_provider(
    tmp_path: Path,
) -> None:
    with _provider_server() as base_url:
        provider = OpenAICompatibleProvider(
            base_url=base_url,
            model="pilot-model",
            timeout_seconds=5,
        )
        app = create_app(
            data_root=tmp_path / "runtime",
            chat_provider=provider,
            workspace_credential="private-health-credential",
        )

        response = _request(app, "/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["state"] == "ready"
    assert response.json()["provider"] == {
        "state": "ready",
        "kind": "openai_compatible",
        "model": "pilot-model",
    }


def test_provider_outage_degrades_readiness_without_initializing_storage(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runtime"
    provider = OpenAICompatibleProvider(
        base_url="http://127.0.0.1:1/v1",
        model="offline-model",
        timeout_seconds=0.1,
    )
    app = create_app(
        data_root=data_root,
        chat_provider=provider,
        workspace_credential="private-health-credential",
    )

    response = _request(app, "/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["state"] == "degraded"
    assert response.json()["provider"] == {
        "state": "unavailable",
        "kind": "openai_compatible",
        "model": "offline-model",
    }
    assert not data_root.exists()


def test_corrupt_capability_store_degrades_broker_readiness(tmp_path: Path) -> None:
    data_root = tmp_path / "runtime"
    data_root.mkdir()
    (data_root / "capabilities.sqlite3").write_bytes(b"not sqlite")
    app = create_app(
        data_root=data_root,
        chat_provider=DeterministicFakeProvider(),
        workspace_credential="private-health-credential",
    )

    response = _request(app, "/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["state"] == "degraded"
    assert response.json()["capability_broker"] == {
        "state": "error",
        "configured_scope_count": 0,
    }
