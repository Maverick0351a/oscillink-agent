"""FastAPI application composition for Oscillink Agent."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI

from oscillink_agent import __version__
from oscillink_agent.artifact_imports.routes import build_artifact_import_router
from oscillink_agent.chat.routes import build_chat_router
from oscillink_agent.memory.routes import build_memory_router
from oscillink_agent.providers.base import ChatProvider
from oscillink_agent.providers.config import build_chat_provider
from oscillink_agent.status.routes import build_status_router


def _default_data_root() -> Path:
    configured = os.environ.get("OSCILLINK_AGENT_DATA_DIR")
    return Path(configured) if configured else Path.home() / ".oscillink-agent"


def _default_vault_root() -> Path | None:
    configured = os.environ.get("OSCILLINK_AGENT_VAULT_DIR")
    return Path(configured) if configured else None


def _default_import_scopes() -> dict[str, Path]:
    configured = os.environ.get("OSCILLINK_AGENT_IMPORT_DIR")
    return {"user_selection": Path(configured)} if configured else {}


def create_app(
    *,
    data_root: Path | None = None,
    vault_root: Path | None = None,
    import_scopes: Mapping[str, Path] | None = None,
    chat_provider: ChatProvider | None = None,
) -> FastAPI:
    """Create an API without initializing or mutating durable storage."""

    root = data_root if data_root is not None else _default_data_root()
    configured_import_scopes = dict(import_scopes or {})
    application = FastAPI(title="Oscillink Agent API", version=__version__)
    application.include_router(build_status_router(root))
    configured_chat_provider = chat_provider or build_chat_provider(os.environ)
    application.include_router(build_chat_router(root, provider=configured_chat_provider))
    application.include_router(build_memory_router(root, vault_root))
    application.include_router(
        build_artifact_import_router(root, vault_root, configured_import_scopes)
    )
    return application


app = create_app(
    vault_root=_default_vault_root(),
    import_scopes=_default_import_scopes(),
)
