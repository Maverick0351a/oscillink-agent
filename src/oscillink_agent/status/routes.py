"""FastAPI routes for truthful local service readiness."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header

from oscillink_agent import __version__
from oscillink_agent.status.contracts import ServiceStatus
from oscillink_agent.status.service import inspect_artifacts, inspect_ledger, inspect_memory
from oscillink_agent.workspaces.service import LocalWorkspaceAuth


def build_status_router(
    data_root: Path,
    *,
    workspace_auth: LocalWorkspaceAuth,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/status", response_model=ServiceStatus)
    def status(
        authorization: Annotated[str | None, Header()] = None,
    ) -> ServiceStatus:
        memory_status = inspect_memory(data_root / "memory.sqlite3")
        return ServiceStatus(
            version=__version__,
            workspace_auth=workspace_auth.status(authorization),
            storage={
                "ledger": inspect_ledger(data_root / "events.sqlite3"),
                "artifacts": inspect_artifacts(data_root / "artifacts"),
                "memory": memory_status,
            },
            features={
                "chat": "ready",
                "capability_broker": "preview",
                "memory_lattice": (
                    "ready" if memory_status.state == "ready" else "preview"
                ),
                "appearance": "preview",
                "workspace_terminal": "preview",
            },
        )

    return router
