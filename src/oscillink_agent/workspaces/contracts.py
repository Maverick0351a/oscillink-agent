"""Authenticated local-workspace contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class LocalWorkspacePrincipal(BaseModel):
    """Server-derived identity for one authenticated local workspace request."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    workspace_id: Annotated[str, Field(pattern=r"^ws_[a-z0-9][a-z0-9_-]{0,62}$")]
    actor_id: Annotated[str, Field(pattern=r"^human_[a-z0-9][a-z0-9_-]{0,62}$")]


class WorkspaceAuthStatus(BaseModel):
    """Credential-free local-workspace authentication readiness."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    state: Literal["unavailable", "locked", "ready"]
