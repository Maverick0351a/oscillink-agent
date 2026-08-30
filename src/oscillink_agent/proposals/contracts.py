"""Transport contracts for durable memory-proposal review."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict

from oscillink_agent.domain.events import ActorId, EventId
from oscillink_agent.memory.contracts import MemoryNodeId


def _parse_transport_datetime(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("timestamp must be an RFC 3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp must be a valid RFC 3339 string") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed


TransportDatetime = Annotated[datetime, BeforeValidator(_parse_transport_datetime)]


class MemoryProposalDecisionRequest(BaseModel):
    """One explicit, attributed, idempotent human review decision."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    request_id: EventId
    observed_at: TransportDatetime
    decision: Literal["approved", "rejected"]


class MemoryProposalProjection(BaseModel):
    """Sanitized relationship candidate and its durable review outcome."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    proposal_id: EventId
    state: Literal["pending_review", "approved", "rejected"]
    target_record_id: MemoryNodeId
    artifact_ref: str
    source_name: str
    created_at: datetime
    decision_event_id: EventId | None = None
    decided_at: datetime | None = None
    decided_by: ActorId | None = None


class MemoryProposalCollection(BaseModel):
    """Bounded collection of ledger-backed proposal projections."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    count: int
    proposals: tuple[MemoryProposalProjection, ...]
