"""FastAPI routes for governed local artifact imports."""

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi import status as http_status

from oscillink_agent.artifact_imports.contracts import (
    ArtifactImportRequest,
    ArtifactImportResponse,
)
from oscillink_agent.artifact_imports.service import import_artifact
from oscillink_agent.workspaces.contracts import LocalWorkspacePrincipal
from oscillink_agent.workspaces.service import LocalWorkspaceAuth

_IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"


def build_artifact_import_router(
    data_root: Path,
    vault_root: Path | None,
    import_scopes: Mapping[str, Path],
    *,
    workspace_auth: LocalWorkspaceAuth,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/v1/artifact-imports",
        response_model=ArtifactImportResponse,
        status_code=http_status.HTTP_201_CREATED,
    )
    def post_artifact_import(
        request: ArtifactImportRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=128,
                pattern=_IDEMPOTENCY_KEY_PATTERN,
            ),
        ],
        principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> ArtifactImportResponse:
        return import_artifact(
            data_root=data_root,
            vault_root=vault_root,
            import_scopes=import_scopes,
            request=request,
            idempotency_key=idempotency_key,
            actor_id=principal.actor_id,
        )

    return router
