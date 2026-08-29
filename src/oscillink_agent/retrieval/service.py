"""Authority-first deterministic evidence retrieval services."""

import re
from pathlib import Path

from oscillink_agent.domain.context import ContextExclusionSummary
from oscillink_agent.memory.repository import (
    MemoryAuthorityState,
    ProductMemoryRecord,
    SQLiteMemoryRepository,
)
from oscillink_agent.retrieval.contracts import (
    MemoryRetrievalResult,
    RankedMemoryEvidence,
)

_TERM = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "apply",
        "applies",
        "are",
        "for",
        "is",
        "of",
        "or",
        "the",
        "to",
        "what",
        "which",
    }
)


def _terms(value: str) -> tuple[str, ...]:
    return tuple(term for term in _TERM.findall(value.casefold()) if term not in _STOP_WORDS)


def _lexical_score(record: ProductMemoryRecord, query_terms: frozenset[str]) -> int:
    if not query_terms:
        return 0
    title_terms = set(_terms(record.title))
    topic_terms = {term for topic in record.topics for term in _terms(topic)}
    classification_terms = set(_terms(record.category.value)) | {
        term for domain in record.domains for term in _terms(domain.value)
    }
    content_terms = _terms(record.content)
    return (
        4 * len(query_terms & title_terms)
        + 3 * len(query_terms & topic_terms)
        + 2 * len(query_terms & classification_terms)
        + min(8, sum(content_terms.count(term) for term in query_terms))
    )


def _all_memory(data_root: Path) -> tuple[ProductMemoryRecord, ...]:
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        return repository.list()
    finally:
        repository.close()


def retrieve_approved_memory(data_root: Path) -> tuple[ProductMemoryRecord, ...]:
    """Return only approved, source-available product memory."""

    return tuple(
        record
        for record in _all_memory(data_root)
        if record.authority_state is MemoryAuthorityState.APPROVED
        and record.source_status != "missing"
    )


def rank_memory_records(
    records: tuple[ProductMemoryRecord, ...], query: str
) -> MemoryRetrievalResult:
    """Rank approved evidence and summarize excluded authority states without content."""

    query_terms = frozenset(_terms(query))
    scored: list[tuple[int, ProductMemoryRecord]] = []
    unmatched: list[ProductMemoryRecord] = []
    not_approved_count = 0
    missing_source_count = 0
    superseded_count = 0
    conflict_count = 0

    for record in records:
        if record.authority_state is MemoryAuthorityState.SUPERSEDED:
            superseded_count += 1
            continue
        if record.authority_state is MemoryAuthorityState.CONTRADICTED:
            conflict_count += 1
            continue
        if record.authority_state is not MemoryAuthorityState.APPROVED:
            not_approved_count += 1
            continue
        if record.source_status == "missing":
            missing_source_count += 1
            continue
        score = _lexical_score(record, query_terms)
        if score == 0:
            unmatched.append(record)
        else:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1].id))
    ranked = tuple(
        RankedMemoryEvidence(record=record, rank=rank, score=score)
        for rank, (score, record) in enumerate(scored, start=1)
    )
    return MemoryRetrievalResult(
        ranked=ranked,
        unmatched=tuple(sorted(unmatched, key=lambda record: record.id)),
        exclusion_summary=ContextExclusionSummary(
            not_approved_count=not_approved_count,
            missing_source_count=missing_source_count,
            superseded_count=superseded_count,
            conflict_count=conflict_count,
        ),
    )


def retrieve_memory_evidence(data_root: Path, query: str) -> MemoryRetrievalResult:
    """Load product memory and apply deterministic authority-first ranking."""

    return rank_memory_records(_all_memory(data_root), query)
