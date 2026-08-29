"""Authenticated local-workspace identity route."""

from typing import Annotated

from fastapi import APIRouter, Depends

from oscillink_agent.workspaces.contracts import LocalWorkspacePrincipal
from oscillink_agent.workspaces.service import LocalWorkspaceAuth


def build_workspace_router(workspace_auth: LocalWorkspaceAuth) -> APIRouter:
    """Expose only the principal derived from the configured credential."""
    router = APIRouter()

    @router.get("/api/v1/workspace", response_model=LocalWorkspacePrincipal)
    def get_workspace(
        principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> LocalWorkspacePrincipal:
        return principal

    return router
