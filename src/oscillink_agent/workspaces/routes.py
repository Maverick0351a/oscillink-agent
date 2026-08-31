"""Authenticated local-workspace identity route."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from oscillink_agent.workspaces.contracts import (
    LocalWorkspacePrincipal,
    WorkspaceExportRequest,
    WorkspaceExportResponse,
    WorkspaceExportView,
    WorkspaceRestoreRequest,
    WorkspaceRestoreResponse,
)
from oscillink_agent.workspaces.export import (
    WorkspaceExportError,
    WorkspaceRestoreError,
    export_workspace,
    inspect_workspace_export,
    restore_workspace,
)
from oscillink_agent.workspaces.service import LocalWorkspaceAuth


def build_workspace_router(
    data_root: Path,
    workspace_auth: LocalWorkspaceAuth,
) -> APIRouter:
    """Expose only the principal derived from the configured credential."""
    router = APIRouter()
    export_root = data_root.parent / ".oscillink-exports"

    def managed_bundle(export_id: str) -> Path | None:
        candidate = export_root / export_id
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            return None
        if not resolved.is_dir() or not resolved.is_relative_to(export_root.resolve()):
            return None
        return resolved

    @router.get("/api/v1/workspace", response_model=LocalWorkspacePrincipal)
    def get_workspace(
        principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> LocalWorkspacePrincipal:
        return principal

    @router.get(
        "/api/v1/workspace/exports/latest",
        response_model=WorkspaceExportView,
    )
    def latest_export(
        _principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> WorkspaceExportView:
        if not export_root.is_dir():
            return WorkspaceExportView(
                state="unavailable",
                reason="export_missing",
                export=None,
            )
        candidates = sorted(
            (
                entry
                for entry in export_root.iterdir()
                if entry.name.startswith("exp_") and entry.is_dir()
            ),
            key=lambda entry: (entry.stat().st_mtime_ns, entry.name),
            reverse=True,
        )
        if not candidates:
            return WorkspaceExportView(
                state="unavailable",
                reason="export_missing",
                export=None,
            )
        export_id = candidates[0].name
        bundle = managed_bundle(export_id)
        if bundle is None:
            return WorkspaceExportView(
                state="unavailable",
                reason="export_invalid",
                export=None,
            )
        try:
            manifest = inspect_workspace_export(bundle)
        except WorkspaceRestoreError:
            return WorkspaceExportView(
                state="unavailable",
                reason="export_invalid",
                export=None,
            )
        return WorkspaceExportView(
            state="available",
            reason=None,
            export=WorkspaceExportResponse(export_id=export_id, manifest=manifest),
        )

    @router.post("/api/v1/workspace/exports", response_model=WorkspaceExportResponse)
    def create_export(
        request: WorkspaceExportRequest,
        _principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> WorkspaceExportResponse:
        export_id = "exp_" + request.request_id.removeprefix("evt_")
        destination = export_root / export_id
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
        bundle = managed_bundle(request.export_id)
        if bundle is None:
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
