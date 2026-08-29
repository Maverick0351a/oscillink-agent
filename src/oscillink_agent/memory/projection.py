"""Typed, rebuildable HTTP projection models for reviewed memory."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from oscillink_agent.domain.events import Digest
from oscillink_agent.memory.obsidian import (
    CATEGORY_LEGEND,
    IndexedObsidianNote,
    IndexIssueCode,
    MemoryCategory,
    MemoryDomain,
    ReviewedObsidianIndex,
)

NonNegativeInt = Annotated[int, Field(ge=0)]


class ProjectionModel(BaseModel):
    """Strict immutable DTO base compatible with FastAPI serialization."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class MemoryProjectionState(StrEnum):
    """Availability and health state of a memory projection."""

    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class MemoryUnavailableReason(StrEnum):
    """Sanitized reasons for an unavailable projection."""

    VAULT_NOT_CONFIGURED = "vault_not_configured"
    VAULT_NOT_FOUND = "vault_not_found"
    INDEX_BUILD_FAILED = "index_build_failed"


class CategoryLegendProjection(ProjectionModel):
    """Accessible presentation for one controlled primary category."""

    category: MemoryCategory
    label: str
    color: str
    symbol: str


class DomainLegendEntry(ProjectionModel):
    """Accessible presentation label for a controlled subject domain."""

    domain: MemoryDomain
    label: str


DOMAIN_LEGEND = (
    DomainLegendEntry(domain=MemoryDomain.AI_ML, label="AI / ML"),
    DomainLegendEntry(domain=MemoryDomain.RF_EM, label="RF / EM"),
    DomainLegendEntry(domain=MemoryDomain.SCIENCE, label="Science"),
    DomainLegendEntry(domain=MemoryDomain.MATHEMATICS, label="Mathematics"),
    DomainLegendEntry(domain=MemoryDomain.ENGINEERING, label="Engineering"),
    DomainLegendEntry(domain=MemoryDomain.SOFTWARE, label="Software"),
    DomainLegendEntry(domain=MemoryDomain.BUSINESS, label="Business"),
    DomainLegendEntry(domain=MemoryDomain.GENERAL, label="General"),
)


class IndexIssueProjection(ProjectionModel):
    """Sanitized transport form of an omitted-source issue."""

    source_path: str
    code: IndexIssueCode
    message: str


class MemoryIndexProjection(ProjectionModel):
    """Index health, legends, and sanitized source issues."""

    schema_version: Literal[1] = 1
    state: MemoryProjectionState
    reason: MemoryUnavailableReason | None
    index_hash: Digest | None
    node_count: NonNegativeInt
    issue_count: NonNegativeInt
    categories: tuple[CategoryLegendProjection, ...]
    domains: tuple[DomainLegendEntry, ...]
    issues: tuple[IndexIssueProjection, ...]


class MemoryNodeSummary(ProjectionModel):
    """Bounded collection projection for one indexed memory node."""

    id: str
    title: str
    source_path: str
    source_status: str | None
    category: MemoryCategory
    domains: tuple[MemoryDomain, ...]
    topics: tuple[str, ...]
    content_hash: Digest
    wikilink_count: NonNegativeInt


class MemoryNodeDetail(MemoryNodeSummary):
    """Inspector projection with source classification and exact wiki targets."""

    frontmatter_type: str
    wikilinks: tuple[str, ...]
    classification_basis: tuple[str, ...]


class MemoryNodeFilters(ProjectionModel):
    """Filters applied to a collection response."""

    category: MemoryCategory | None
    domain: MemoryDomain | None


class MemoryNodeCollection(ProjectionModel):
    """Filtered node collection with explicit projection availability."""

    schema_version: Literal[1] = 1
    state: MemoryProjectionState
    reason: MemoryUnavailableReason | None
    index_hash: Digest | None
    count: NonNegativeInt
    applied_filters: MemoryNodeFilters
    nodes: tuple[MemoryNodeSummary, ...]


class MemoryNodeDetailResponse(ProjectionModel):
    """Focused inspector response."""

    schema_version: Literal[1] = 1
    state: Literal[MemoryProjectionState.READY] = MemoryProjectionState.READY
    node: MemoryNodeDetail


def project_index(index: ReviewedObsidianIndex) -> MemoryIndexProjection:
    """Project a complete index snapshot without host-local configuration."""
    state = MemoryProjectionState.DEGRADED if index.issues else MemoryProjectionState.READY
    return MemoryIndexProjection(
        state=state,
        reason=None,
        index_hash=index.index_hash,
        node_count=len(index.notes),
        issue_count=len(index.issues),
        categories=tuple(
            CategoryLegendProjection(**entry.model_dump()) for entry in index.category_legend
        ),
        domains=DOMAIN_LEGEND,
        issues=tuple(IndexIssueProjection(**issue.model_dump()) for issue in index.issues),
    )


def unavailable_index(reason: MemoryUnavailableReason) -> MemoryIndexProjection:
    """Return an honest empty index projection for unavailable source memory."""
    return MemoryIndexProjection(
        state=MemoryProjectionState.UNAVAILABLE,
        reason=reason,
        index_hash=None,
        node_count=0,
        issue_count=0,
        categories=tuple(
            CategoryLegendProjection(**entry.model_dump()) for entry in CATEGORY_LEGEND
        ),
        domains=DOMAIN_LEGEND,
        issues=(),
    )


def _summarize(note: IndexedObsidianNote) -> MemoryNodeSummary:
    return MemoryNodeSummary(
        id=note.id,
        title=note.title,
        source_path=note.source_path,
        source_status=note.source_status,
        category=note.category,
        domains=note.domains,
        topics=note.topics,
        content_hash=note.content_hash,
        wikilink_count=len(note.wikilinks),
    )


def project_nodes(
    index: ReviewedObsidianIndex,
    *,
    category: MemoryCategory | None,
    domain: MemoryDomain | None,
) -> MemoryNodeCollection:
    """Apply controlled filters and return source-order node summaries."""
    notes = tuple(
        note
        for note in index.notes
        if (category is None or note.category is category)
        and (domain is None or domain in note.domains)
    )
    state = MemoryProjectionState.DEGRADED if index.issues else MemoryProjectionState.READY
    return MemoryNodeCollection(
        state=state,
        reason=None,
        index_hash=index.index_hash,
        count=len(notes),
        applied_filters=MemoryNodeFilters(category=category, domain=domain),
        nodes=tuple(_summarize(note) for note in notes),
    )


def unavailable_nodes(
    reason: MemoryUnavailableReason,
    *,
    category: MemoryCategory | None,
    domain: MemoryDomain | None,
) -> MemoryNodeCollection:
    """Return an honest empty collection while preserving requested filters."""
    return MemoryNodeCollection(
        state=MemoryProjectionState.UNAVAILABLE,
        reason=reason,
        index_hash=None,
        count=0,
        applied_filters=MemoryNodeFilters(category=category, domain=domain),
        nodes=(),
    )


def project_node(note: IndexedObsidianNote) -> MemoryNodeDetailResponse:
    """Return focused inspector metadata for one node."""
    return MemoryNodeDetailResponse(
        node=MemoryNodeDetail(
            **_summarize(note).model_dump(),
            frontmatter_type=note.frontmatter_type,
            wikilinks=note.wikilinks,
            classification_basis=note.classification_basis,
        )
    )
