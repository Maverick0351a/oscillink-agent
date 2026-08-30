"""FastAPI routes for the governed local chat runtime."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from oscillink_agent.agent_runtime.errors import (
    ChatIdempotencyConflictError,
    ChatProviderDispatchUncertainError,
    ChatProviderRunFailedError,
    ChatRunIncompleteError,
    ChatRunNotFoundError,
)
from oscillink_agent.agent_runtime.service import create_chat_message, inspect_chat_run
from oscillink_agent.chat.contracts import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatRunInspectionResponse,
    PendingToolRequestResponse,
)
from oscillink_agent.domain.events import RunId, SessionId
from oscillink_agent.providers.base import (
    ChatProvider,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from oscillink_agent.workspaces.contracts import LocalWorkspacePrincipal
from oscillink_agent.workspaces.service import LocalWorkspaceAuth

_IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"


def build_chat_router(
    data_root: Path,
    *,
    provider: ChatProvider | None = None,
    workspace_auth: LocalWorkspaceAuth,
) -> APIRouter:
    """Bind chat application services to one configured durable root."""

    router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

    @router.post(
        "/messages",
        response_model=ChatMessageResponse | PendingToolRequestResponse,
    )
    def post_message(
        request: ChatMessageRequest,
        response: Response,
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
    ) -> ChatMessageResponse | PendingToolRequestResponse:
        try:
            result = create_chat_message(
                data_root,
                request,
                idempotency_key=idempotency_key,
                provider_adapter=provider,
                actor_id=principal.actor_id,
            )
            if isinstance(result, PendingToolRequestResponse):
                response.status_code = 202
            return result
        except ChatIdempotencyConflictError:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": "Idempotency key belongs to another chat request.",
                },
            ) from None
        except ChatProviderRunFailedError as error:
            raise HTTPException(
                status_code=504 if error.failure_kind == "timeout" else 502,
                detail=(
                    "configured chat provider timed out"
                    if error.failure_kind == "timeout"
                    else "configured chat provider failed"
                ),
            ) from None
        except ChatProviderDispatchUncertainError:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "provider_dispatch_uncertain",
                    "message": "Provider dispatch cannot be safely repeated.",
                },
            ) from None
        except ProviderTimeoutError:
            raise HTTPException(
                status_code=504,
                detail="configured chat provider timed out",
            ) from None
        except (ProviderRequestError, ProviderResponseError):
            raise HTTPException(
                status_code=502,
                detail="configured chat provider failed",
            ) from None

    @router.get(
        "/sessions/{session_id}/runs/{run_id}",
        response_model=ChatRunInspectionResponse,
    )
    def get_run(
        session_id: SessionId,
        run_id: RunId,
        _principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> ChatRunInspectionResponse:
        try:
            return inspect_chat_run(data_root, session_id, run_id)
        except ChatRunNotFoundError:
            raise HTTPException(
                status_code=404,
                detail={"code": "run_not_found", "message": "Chat run was not found."},
            ) from None
        except ChatRunIncompleteError:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "run_incomplete",
                    "message": "Chat run is missing required persisted context.",
                },
            ) from None

    return router
