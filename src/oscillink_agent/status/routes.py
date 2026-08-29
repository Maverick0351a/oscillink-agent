"""FastAPI routes for truthful local service readiness."""

from pathlib import Path

from fastapi import APIRouter

from oscillink_agent import __version__
from oscillink_agent.status.contracts import ServiceStatus
from oscillink_agent.status.service import inspect_artifacts, inspect_ledger, inspect_memory


def build_status_router(data_root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/status", response_model=ServiceStatus)
    def status() -> ServiceStatus:
        memory_status = inspect_memory(data_root / "memory.sqlite3")
        return ServiceStatus(
            version=__version__,
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
