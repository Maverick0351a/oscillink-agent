"""Deterministic compilation of governed evidence into context manifests."""

from datetime import datetime

from oscillink_agent.domain.context import (
    ContextItem,
    ContextManifest,
    ContextOmission,
    ContextOmissionReason,
    ContextStatus,
)
from oscillink_agent.domain.events import TrustClass, canonical_payload_hash
from oscillink_agent.memory.repository import ProductMemoryRecord
from oscillink_agent.retrieval.contracts import MemoryRetrievalResult


def compile_context(
    retrieval: MemoryRetrievalResult,
    *,
    context_id: str,
    task_id: str,
    compiled_at: datetime,
    token_budget: int,
) -> tuple[ContextManifest, tuple[ProductMemoryRecord, ...]]:
    """Select ranked approved evidence under budget and record every eligible omission."""

    selected: list[tuple[ProductMemoryRecord, int, int, int]] = []
    omissions: list[ContextOmission] = []
    total_tokens = 0
    for evidence in retrieval.ranked:
        record = evidence.record
        token_count = len(record.content.split())
        if total_tokens + token_count > token_budget:
            omissions.append(
                ContextOmission(
                    record_id=record.id,
                    content_hash=record.content_hash,
                    reason=ContextOmissionReason.TOKEN_BUDGET,
                    retrieval_rank=evidence.rank,
                    retrieval_score=evidence.score,
                )
            )
            continue
        selected.append((record, token_count, evidence.rank, evidence.score))
        total_tokens += token_count
    omissions.extend(
        ContextOmission(
            record_id=record.id,
            content_hash=record.content_hash,
            reason=ContextOmissionReason.NO_QUERY_MATCH,
        )
        for record in retrieval.unmatched
    )
    manifest = ContextManifest(
        id=context_id,
        schema_version=1,
        task_id=task_id,
        compiled_at=compiled_at,
        token_budget=token_budget,
        total_token_count=total_tokens,
        policy_hash=canonical_payload_hash(
            {
                "authority": "approved",
                "ranking": "lexical-v1",
                "tie_break": "record_id",
                "source_status": "not_missing",
                "omissions": "explicit",
            }
        ),
        items=tuple(
            ContextItem(
                record_id=record.id,
                content_hash=record.content_hash,
                title=record.title,
                category=record.category,
                domains=record.domains,
                inclusion_reason=(
                    f"approved lexical evidence rank={rank} score={score}"
                ),
                trust_class=TrustClass.HUMAN_VERIFIED,
                status=ContextStatus.APPROVED,
                token_count=token_count,
                source_refs=(record.id,),
                retrieval_rank=rank,
                retrieval_score=score,
            )
            for record, token_count, rank, score in selected
        ),
        omissions=tuple(omissions),
        exclusion_summary=retrieval.exclusion_summary,
    )
    return manifest, tuple(record for record, _, _, _ in selected)
