"""Ledger-derived memory-proposal read projections."""

from collections.abc import Iterable

from oscillink_agent.domain.events import Event, EventType
from oscillink_agent.proposals.contracts import (
    MemoryProposalCollection,
    MemoryProposalProjection,
)


def project_memory_proposals(events: Iterable[Event]) -> MemoryProposalCollection:
    """Rebuild proposal state from immutable import, proposal, and decision events."""

    ordered = tuple(events)
    events_by_id = {event.id: event for event in ordered}
    decisions = {
        str(event.payload.get("proposal_id")): event
        for event in ordered
        if event.payload.get("operation") == "artifact_association_review"
        and event.event_type in (EventType.APPROVAL, EventType.RETRACTION)
    }
    proposals: list[MemoryProposalProjection] = []
    for event in ordered:
        if (
            event.event_type is not EventType.MEMORY_PROPOSAL
            or event.payload.get("operation") != "artifact_association"
            or event.payload.get("status") != "pending_review"
            or len(event.artifact_refs) != 1
            or len(event.causal_parent_ids) != 1
        ):
            continue
        imported = events_by_id.get(event.causal_parent_ids[0])
        if imported is None or imported.payload.get("operation") != "artifact_import":
            continue
        decision = decisions.get(event.id)
        state = "pending_review"
        if decision is not None:
            state = str(decision.payload.get("decision"))
        proposals.append(
            MemoryProposalProjection.model_validate(
                {
                    "proposal_id": event.id,
                    "state": state,
                    "target_record_id": event.payload["target_record_id"],
                    "artifact_ref": event.artifact_refs[0],
                    "source_name": imported.payload["source_name"],
                    "created_at": event.observed_at,
                    "decision_event_id": decision.id if decision is not None else None,
                    "decided_at": decision.observed_at if decision is not None else None,
                    "decided_by": decision.actor.id if decision is not None else None,
                }
            )
        )
    return MemoryProposalCollection(count=len(proposals), proposals=tuple(proposals))
