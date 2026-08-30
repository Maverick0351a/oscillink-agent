"""Authenticated local-workspace identity route."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from oscillink_agent.workspaces.contracts import (
    LocalWorkspacePrincipal,
    WorkspaceExportRequest,
    WorkspaceExportResponse,
    WorkspaceRestoreRequest,
    WorkspaceRestoreResponse,
)
from oscillink_agent.workspaces.export import (
    WorkspaceExportError,
    WorkspaceRestoreError,
    export_workspace,
    restore_workspace,
)
from oscillink_agent.workspaces.service import LocalWorkspaceAuth


def build_workspace_router(
    data_root: Path,
    workspace_auth: LocalWorkspaceAuth,
) -> APIRouter:
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

    @router.post("/api/v1/workspace/exports", response_model=WorkspaceExportResponse)
    def create_export(
        request: WorkspaceExportRequest,
        _principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> WorkspaceExportResponse:
        export_id = "exp_" + request.request_id.removeprefix("evt_")
        destination = data_root.parent / ".oscillink-exports" / export_id
        try:
            manifest = export_workspace(data_root, destination)
        except WorkspaceExportError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "workspace_export_failed", "message": str(error)},
            ) from None
        return WorkspaceExportResponse(export_id=export_id, manifest=manifest)

    @router.post("/api/v1/workspace/restores", response_model=WorkspaceRestoreResponse)
    def restore_export(
        request: WorkspaceRestoreRequest,
        _principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> WorkspaceRestoreResponse:
        bundle = data_root.parent / ".oscillink-exports" / request.export_id
        if not bundle.is_dir():
            raise HTTPException(
                status_code=404,
                detail={"code": "workspace_export_not_found"},
            )
        try:
            manifest = restore_workspace(bundle, data_root)
        except WorkspaceRestoreError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "workspace_restore_failed", "message": str(error)},
            ) from None
        return WorkspaceRestoreResponse(
            export_id=request.export_id,
            manifest=manifest,
        )

    return router
