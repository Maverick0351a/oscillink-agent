"""Internal contracts for deterministic authority-first retrieval."""

from dataclasses import dataclass

from oscillink_agent.domain.context import ContextExclusionSummary
from oscillink_agent.memory.repository import ProductMemoryRecord


@dataclass(frozen=True)
class RankedMemoryEvidence:
    record: ProductMemoryRecord
    rank: int
    score: int


@dataclass(frozen=True)
class MemoryRetrievalResult:
    ranked: tuple[RankedMemoryEvidence, ...]
    unmatched: tuple[ProductMemoryRecord, ...]
    exclusion_summary: ContextExclusionSummary
