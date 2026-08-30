"""FastAPI routes for ledger-backed memory proposals."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from oscillink_agent.domain.events import EventId
from oscillink_agent.proposals.contracts import (
    MemoryProposalCollection,
    MemoryProposalDecisionRequest,
    MemoryProposalProjection,
)
from oscillink_agent.proposals.repository import project_memory_proposals
from oscillink_agent.proposals.service import decide_memory_proposal
from oscillink_agent.storage.artifacts import LocalArtifactStore
from oscillink_agent.storage.sqlite import SQLiteEventStore
from oscillink_agent.workspaces.contracts import LocalWorkspacePrincipal
from oscillink_agent.workspaces.service import LocalWorkspaceAuth

_IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"


def build_proposal_router(
    data_root: Path,
    *,
    workspace_auth: LocalWorkspaceAuth,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/api/v1/memory-proposals",
        response_model=MemoryProposalCollection,
    )
    def list_memory_proposals(
        _principal: Annotated[
            LocalWorkspacePrincipal,
            Depends(workspace_auth.require_principal),
        ],
    ) -> MemoryProposalCollection:
        database = data_root / "events.sqlite3"
        if not database.is_file():
            return MemoryProposalCollection(count=0, proposals=())
        events = SQLiteEventStore(database)
        try:
            return project_memory_proposals(events.iter_all())
        finally:
            events.close()

    @router.post(
        "/api/v1/memory-proposals/{proposal_id}/decisions",
        response_model=MemoryProposalProjection,
    )
    def post_memory_proposal_decision(
        proposal_id: EventId,
        request: MemoryProposalDecisionRequest,
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
    ) -> MemoryProposalProjection:
        database = data_root / "events.sqlite3"
        if not database.is_file():
            raise HTTPException(
                status_code=404,
                detail={"code": "proposal_not_found", "message": "Proposal was not found."},
            )
        events = SQLiteEventStore(
            database,
            artifacts=LocalArtifactStore(data_root / "artifacts"),
        )
        try:
            return decide_memory_proposal(
                events=events,
                proposal_id=proposal_id,
                request=request,
                idempotency_key=idempotency_key,
                actor_id=principal.actor_id,
            )
        finally:
            events.close()

    return router
