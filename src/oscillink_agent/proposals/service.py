"""Governed memory-proposal decision orchestration."""

from datetime import UTC, datetime

from fastapi import HTTPException

from oscillink_agent.domain.events import (
    Actor,
    ActorType,
    Event,
    EventType,
    TrustClass,
    canonical_payload_hash,
)
from oscillink_agent.proposals.contracts import (
    MemoryProposalDecisionRequest,
    MemoryProposalProjection,
)
from oscillink_agent.proposals.repository import project_memory_proposals
from oscillink_agent.storage.sqlite import (
    EventConstraintError,
    IdempotencyConflictError,
    SQLiteEventStore,
)


def _projection(
    events: SQLiteEventStore,
    proposal_id: str,
) -> MemoryProposalProjection | None:
    collection = project_memory_proposals(events.iter_all())
    return next(
        (proposal for proposal in collection.proposals if proposal.proposal_id == proposal_id),
        None,
    )


def decide_memory_proposal(
    *,
    events: SQLiteEventStore,
    proposal_id: str,
    request: MemoryProposalDecisionRequest,
    idempotency_key: str,
    actor_id: str,
) -> MemoryProposalProjection:
    """Append exactly one human decision and return its consumable relationship projection."""

    existing = events.get_by_idempotency(idempotency_key)
    if existing is not None:
        expected_event_type = (
            EventType.APPROVAL if request.decision == "approved" else EventType.RETRACTION
        )
        if (
            existing.id != request.request_id
            or existing.observed_at != request.observed_at
            or existing.actor.id != actor_id
            or existing.event_type is not expected_event_type
            or existing.causal_parent_ids != (proposal_id,)
            or existing.payload.get("operation") != "artifact_association_review"
            or existing.payload.get("proposal_id") != proposal_id
            or existing.payload.get("decision") != request.decision
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": "Idempotency key belongs to another proposal decision.",
                },
            )
        replayed = _projection(events, proposal_id)
        if (
            replayed is None
            or replayed.state != request.decision
            or replayed.decision_event_id != existing.id
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": "Idempotent proposal decision is not reconstructable.",
                },
            )
        return replayed

    proposal = _projection(events, proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "proposal_not_found", "message": "Proposal was not found."},
        )
    if proposal.state != "pending_review":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "proposal_already_resolved",
                "message": "Proposal already has a durable decision.",
            },
        )
    proposal_event = events.get(proposal_id)
    if proposal_event is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "proposal_unreadable", "message": "Proposal is not readable."},
        )
    payload = {
        "operation": "artifact_association_review",
        "proposal_id": proposal_id,
        "decision": request.decision,
        "target_record_id": proposal.target_record_id,
    }
    decision = Event.model_validate(
        {
            "id": request.request_id,
            "schema_version": 1,
            "session_id": proposal_event.session_id,
            "run_id": proposal_event.run_id,
            "task_id": proposal_event.task_id,
            "actor": Actor(id=actor_id, type=ActorType.HUMAN),
            "event_type": (
                EventType.APPROVAL if request.decision == "approved" else EventType.RETRACTION
            ),
            "observed_at": request.observed_at,
            "recorded_at": datetime.now(tz=UTC),
            "payload_hash": canonical_payload_hash(payload),
            "artifact_refs": proposal_event.artifact_refs,
            "causal_parent_ids": (proposal_id,),
            "trust_class": TrustClass.HUMAN_VERIFIED,
            "sensitivity": proposal_event.sensitivity,
            "payload": payload,
        }
    )
    try:
        events.append(decision, idempotency_key=idempotency_key)
    except EventConstraintError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "proposal_already_resolved",
                "message": "Proposal already has a durable decision.",
            },
        ) from None
    except IdempotencyConflictError:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_conflict",
                "message": "Idempotency key belongs to another proposal decision.",
            },
        ) from None
    resolved = _projection(events, proposal_id)
    if resolved is None or resolved.state != request.decision:
        raise RuntimeError("persisted proposal decision could not be projected")
    return resolved
