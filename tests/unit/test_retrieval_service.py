from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.repository import (
    MemoryAuthorityState,
    MemorySourceKind,
    ProductMemoryRecord,
)
from oscillink_agent.retrieval import service as retrieval_service


def _record(
    suffix: str,
    *,
    authority: MemoryAuthorityState,
    source_status: str | None = None,
) -> ProductMemoryRecord:
    return ProductMemoryRecord(
        id=f"mem_01J0000000000000000000000{suffix}",
        title="Resonance evidence",
        content="resonance oscillator",
        authority_state=authority,
        source_kind=MemorySourceKind.NATIVE,
        source_key="native",
        source_path=None,
        source_status=source_status,
        category=MemoryCategory.GOVERNANCE,
        domains=(MemoryDomain.SOFTWARE,),
        topics=(),
        content_hash="sha256:" + suffix.lower() * 64,
    )


def test_ranker_summarizes_stale_and_conflicting_authority_without_exposing_it() -> None:
    rank_records = getattr(retrieval_service, "rank_memory_records", None)
    assert rank_records is not None
    result = rank_records(
        (
            _record("A", authority=MemoryAuthorityState.APPROVED),
            _record(
                "B",
                authority=MemoryAuthorityState.APPROVED,
                source_status="missing",
            ),
            _record("C", authority=MemoryAuthorityState.SUPERSEDED),
            _record("D", authority=MemoryAuthorityState.CONTRADICTED),
            _record("E", authority=MemoryAuthorityState.CANDIDATE),
        ),
        "resonance",
    )

    assert [evidence.record.id for evidence in result.ranked] == [
        "mem_01J0000000000000000000000A"
    ]
    assert result.unmatched == ()
    assert result.exclusion_summary.model_dump(mode="json") == {
        "not_approved_count": 1,
        "missing_source_count": 1,
        "superseded_count": 1,
        "conflict_count": 1,
    }
