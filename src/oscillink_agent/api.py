"""FastAPI application composition for Oscillink Agent."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from oscillink_agent import __version__
from oscillink_agent.artifact_imports.routes import build_artifact_import_router
from oscillink_agent.capabilities.routes import build_capability_router
from oscillink_agent.chat.routes import build_chat_router
from oscillink_agent.health.routes import build_health_router
from oscillink_agent.memory.routes import build_memory_router
from oscillink_agent.proposals.routes import build_proposal_router
from oscillink_agent.providers.base import ChatProvider
from oscillink_agent.providers.config import build_chat_provider
from oscillink_agent.status.routes import build_status_router
from oscillink_agent.workspaces.routes import build_workspace_router
from oscillink_agent.workspaces.service import LocalWorkspaceAuth


def _default_data_root() -> Path:
    configured = os.environ.get("OSCILLINK_AGENT_DATA_DIR")
    return Path(configured) if configured else Path.home() / ".oscillink-agent"


def _default_vault_root() -> Path | None:
    configured = os.environ.get("OSCILLINK_AGENT_VAULT_DIR")
    return Path(configured) if configured else None


def _default_import_scopes() -> dict[str, Path]:
    configured = os.environ.get("OSCILLINK_AGENT_IMPORT_DIR")
    return {"user_selection": Path(configured)} if configured else {}


def _csv_setting(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    configured = os.environ.get(name)
    if configured is None:
        return default
    return tuple(item.strip() for item in configured.split(",") if item.strip())


def create_app(
    *,
    data_root: Path | None = None,
    vault_root: Path | None = None,
    import_scopes: Mapping[str, Path] | None = None,
    capability_scopes: Mapping[str, Path] | None = None,
    chat_provider: ChatProvider | None = None,
    workspace_credential: str | None = None,
    workspace_id: str = "ws_local",
    workspace_actor_id: str = "human_local_user",
    allowed_origins: tuple[str, ...] | None = None,
    trusted_hosts: tuple[str, ...] | None = None,
    static_root: Path | None = None,
) -> FastAPI:
    """Create an API without initializing or mutating durable storage."""

    root = data_root if data_root is not None else _default_data_root()
    configured_import_scopes = dict(import_scopes or {})
    configured_capability_scopes = dict(capability_scopes or {})
    application = FastAPI(title="Oscillink Agent API", version=__version__)
    configured_origins = (
        allowed_origins
        if allowed_origins is not None
        else _csv_setting(
            "OSCILLINK_AGENT_ALLOWED_ORIGINS",
            ("http://localhost:5173", "http://127.0.0.1:5173"),
        )
    )
    configured_hosts = (
        trusted_hosts
        if trusted_hosts is not None
        else _csv_setting(
            "OSCILLINK_AGENT_TRUSTED_HOSTS",
            ("localhost", "127.0.0.1", "testserver"),
        )
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(configured_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(configured_hosts),
    )
    configured_chat_provider = chat_provider or build_chat_provider(os.environ)
    configured_workspace_credential = (
        workspace_credential
        if workspace_credential is not None
        else os.environ.get("OSCILLINK_AGENT_WORKSPACE_CREDENTIAL")
    )
    workspace_auth = LocalWorkspaceAuth(
        credential=configured_workspace_credential,
        workspace_id=workspace_id,
        actor_id=workspace_actor_id,
    )
    application.include_router(
        build_health_router(
            root,
            provider=configured_chat_provider,
            configured_scope_count=len(configured_capability_scopes),
        )
    )
    application.include_router(
        build_status_router(root, workspace_auth=workspace_auth)
    )
    application.include_router(build_workspace_router(root, workspace_auth))
    application.include_router(
        build_chat_router(
            root,
            provider=configured_chat_provider,
            workspace_auth=workspace_auth,
        )
    )
    application.include_router(
        build_capability_router(
            root,
            scope_roots=configured_capability_scopes,
            provider=configured_chat_provider,
            workspace_auth=workspace_auth,
        )
    )
    application.include_router(
        build_memory_router(
            root,
            vault_root,
            workspace_auth=workspace_auth,
        )
    )
    application.include_router(
        build_artifact_import_router(
            root,
            vault_root,
            configured_import_scopes,
            workspace_auth=workspace_auth,
        )
    )
    application.include_router(
        build_proposal_router(root, workspace_auth=workspace_auth)
    )
    if static_root is not None:
        application.mount(
            "/",
            StaticFiles(directory=static_root, html=True, check_dir=True),
            name="private-pilot-ui",
        )
    return application


app = create_app(
    vault_root=_default_vault_root(),
    import_scopes=_default_import_scopes(),
)
