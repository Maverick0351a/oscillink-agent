"""Credential verification for one private local workspace."""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Header, HTTPException

from oscillink_agent.workspaces.contracts import (
    LocalWorkspacePrincipal,
    WorkspaceAuthStatus,
)


@dataclass(frozen=True)
class LocalWorkspaceAuth:
    """Verify a bearer credential without exposing it through public state."""

    credential: str | None = field(repr=False)
    workspace_id: str = "ws_local"
    actor_id: str = "human_local_user"

    def status(self, authorization: str | None = None) -> WorkspaceAuthStatus:
        """Project request-scoped readiness without exposing credential material."""
        if not self.credential:
            return WorkspaceAuthStatus(state="unavailable")
        return WorkspaceAuthStatus(
            state="ready" if self._matches(authorization) else "locked"
        )

    def _matches(self, authorization: str | None) -> bool:
        if not self.credential or authorization is None:
            return False
        scheme, separator, supplied = authorization.partition(" ")
        return (
            separator == " "
            and scheme.lower() == "bearer"
            and hmac.compare_digest(supplied, self.credential)
        )

    def require_principal(
        self,
        authorization: Annotated[str | None, Header()] = None,
    ) -> LocalWorkspacePrincipal:
        """Authenticate one request and return only server-derived identity."""
        if not self._matches(authorization):
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "workspace_auth_required",
                    "message": "A valid local workspace credential is required.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        return LocalWorkspacePrincipal(
            workspace_id=self.workspace_id,
            actor_id=self.actor_id,
        )
