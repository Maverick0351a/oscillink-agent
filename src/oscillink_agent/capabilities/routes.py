"""Authenticated routes for exact governed capability decisions."""

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from oscillink_agent.capabilities.contracts import (
    CapabilityDecisionRequest,
    CapabilityDecisionResponse,
)
from oscillink_agent.capabilities.service import CapabilityLoopError, decide_file_read_request
from oscillink_agent.chat.contracts import ChatMessageResponse
from oscillink_agent.domain.events import EventId, RunId, SessionId
from oscillink_agent.providers.base import ChatProvider, ProviderResponseError
from oscillink_agent.workspaces.contracts import LocalWorkspacePrincipal
from oscillink_agent.workspaces.service import LocalWorkspaceAuth

_IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"


def build_capability_router(
    data_root: Path,
    *,
    scope_roots: Mapping[str, Path],
    provider: ChatProvider,
    workspace_auth: LocalWorkspaceAuth,
) -> APIRouter:
    """Bind one human decision route; never accept caller-created grant objects."""

    router = APIRouter(prefix="/api/v1/capabilities", tags=["capabilities"])

    @router.post(
        "/sessions/{session_id}/runs/{run_id}/requests/{tool_request_event_id}/decision",
        response_model=ChatMessageResponse | CapabilityDecisionResponse,
    )
    def decide_request(
        session_id: SessionId,
        run_id: RunId,
        tool_request_event_id: EventId,
        request: CapabilityDecisionRequest,
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
    ) -> ChatMessageResponse | CapabilityDecisionResponse:
        try:
            return decide_file_read_request(
                data_root=data_root,
                scope_roots=scope_roots,
                provider=provider,
                session_id=session_id,
                run_id=run_id,
                tool_request_event_id=tool_request_event_id,
                decision=request,
                idempotency_key=idempotency_key,
                actor_id=principal.actor_id,
            )
        except CapabilityLoopError as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": error.code,
                    "message": "Governed capability request could not be completed.",
                },
            ) from None
        except ProviderResponseError:
            raise HTTPException(
                status_code=502,
                detail="configured chat provider failed",
            ) from None

    return router
