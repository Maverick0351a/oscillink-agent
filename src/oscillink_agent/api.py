"""Local HTTP API for Oscillink Agent."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from oscillink_agent import __version__
from oscillink_agent.memory.obsidian import (
    DocumentId,
    MemoryCategory,
    MemoryDomain,
    ReviewedObsidianIndex,
    build_reviewed_obsidian_index,
)
from oscillink_agent.memory.projection import (
    MemoryIndexProjection,
    MemoryNodeCollection,
    MemoryNodeDetailResponse,
    MemoryUnavailableReason,
    project_index,
    project_node,
    project_nodes,
    unavailable_index,
    unavailable_nodes,
)

ComponentState = Literal["not_initialized", "ready", "error"]
FeatureState = Literal["planned", "preview", "ready"]
_HEX_DIRECTORY = re.compile(r"[0-9a-f]{2}")
_HEX_OBJECT = re.compile(r"[0-9a-f]{62}")


class StorageComponentStatus(BaseModel):
    """Read-only status for one durable storage component."""

    model_config = ConfigDict(frozen=True)

    state: ComponentState
    record_count: int


class ServiceStatus(BaseModel):
    """Truthful readiness snapshot consumed by the local frontend."""

    model_config = ConfigDict(frozen=True)

    service: Literal["oscillink-agent"] = "oscillink-agent"
    version: str
    api_state: Literal["online"] = "online"
    storage: dict[str, StorageComponentStatus]
    features: dict[str, FeatureState]


def _default_data_root() -> Path:
    configured = os.environ.get("OSCILLINK_AGENT_DATA_DIR")
    return Path(configured) if configured else Path.home() / ".oscillink-agent"


def _default_vault_root() -> Path | None:
    configured = os.environ.get("OSCILLINK_AGENT_VAULT_DIR")
    return Path(configured) if configured else None


def _inspect_ledger(database: Path) -> StorageComponentStatus:
    if not database.is_file():
        return StorageComponentStatus(state="not_initialized", record_count=0)
    try:
        connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        try:
            version_row = connection.execute("PRAGMA user_version").fetchone()
            if version_row != (1,):
                return StorageComponentStatus(state="error", record_count=0)
            count_row = connection.execute("SELECT COUNT(*) FROM events").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return StorageComponentStatus(state="error", record_count=0)
    return StorageComponentStatus(state="ready", record_count=int(count_row[0]))


def _inspect_artifacts(root: Path) -> StorageComponentStatus:
    if not root.is_dir():
        return StorageComponentStatus(state="not_initialized", record_count=0)
    try:
        count = sum(
            1
            for directory in root.iterdir()
            if directory.is_dir() and _HEX_DIRECTORY.fullmatch(directory.name)
            for artifact in directory.iterdir()
            if artifact.is_file()
            and not artifact.is_symlink()
            and _HEX_OBJECT.fullmatch(artifact.name)
        )
    except OSError:
        return StorageComponentStatus(state="error", record_count=0)
    return StorageComponentStatus(state="ready", record_count=count)


def _load_memory_index(
    vault_root: Path | None,
) -> tuple[ReviewedObsidianIndex | None, MemoryUnavailableReason | None]:
    if vault_root is None:
        return None, MemoryUnavailableReason.VAULT_NOT_CONFIGURED
    if not vault_root.is_dir():
        return None, MemoryUnavailableReason.VAULT_NOT_FOUND
    try:
        return build_reviewed_obsidian_index(vault_root), None
    except (OSError, ValueError):
        return None, MemoryUnavailableReason.INDEX_BUILD_FAILED


def create_app(*, data_root: Path | None = None, vault_root: Path | None = None) -> FastAPI:
    """Create an API without initializing or mutating durable storage."""

    root = data_root if data_root is not None else _default_data_root()
    application = FastAPI(title="Oscillink Agent API", version=__version__)

    @application.get("/api/v1/status", response_model=ServiceStatus)
    def status() -> ServiceStatus:
        return ServiceStatus(
            version=__version__,
            storage={
                "ledger": _inspect_ledger(root / "events.sqlite3"),
                "artifacts": _inspect_artifacts(root / "artifacts"),
            },
            features={
                "chat": "planned",
                "memory_lattice": "planned",
                "appearance": "preview",
            },
        )

    @application.get("/api/v1/memory/index", response_model=MemoryIndexProjection)
    def memory_index() -> MemoryIndexProjection:
        index, reason = _load_memory_index(vault_root)
        if index is None:
            assert reason is not None
            return unavailable_index(reason)
        return project_index(index)

    @application.get("/api/v1/memory/nodes", response_model=MemoryNodeCollection)
    def memory_nodes(
        category: MemoryCategory | None = None,
        domain: MemoryDomain | None = None,
    ) -> MemoryNodeCollection:
        index, reason = _load_memory_index(vault_root)
        if index is None:
            assert reason is not None
            return unavailable_nodes(reason, category=category, domain=domain)
        return project_nodes(index, category=category, domain=domain)

    @application.get(
        "/api/v1/memory/nodes/{node_id}",
        response_model=MemoryNodeDetailResponse,
    )
    def memory_node(node_id: DocumentId) -> MemoryNodeDetailResponse:
        index, reason = _load_memory_index(vault_root)
        if index is None:
            message = (
                "Reviewed memory is not configured."
                if reason is MemoryUnavailableReason.VAULT_NOT_CONFIGURED
                else "Reviewed memory is unavailable."
            )
            raise HTTPException(
                status_code=503,
                detail={"code": "memory_unavailable", "message": message},
            )
        note = next((candidate for candidate in index.notes if candidate.id == node_id), None)
        if note is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "node_not_found",
                    "message": "Memory node was not found.",
                },
            )
        return project_node(note)

    return application


app = create_app(vault_root=_default_vault_root())
