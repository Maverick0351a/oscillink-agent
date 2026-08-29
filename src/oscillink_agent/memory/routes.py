"""FastAPI routes for governed product-memory lifecycle operations."""

import hashlib
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from fastapi import status as http_status

from oscillink_agent.memory.contracts import (
    MemoryNodeId,
    MemoryReviewRequest,
    MemorySourceSyncRequest,
    MemorySourceSyncResponse,
    NativeMemoryCreateRequest,
)
from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.projection import (
    MemoryIndexProjection,
    MemoryNodeCollection,
    MemoryNodeDetailResponse,
    MemoryUnavailableReason,
    project_index,
    project_node,
    project_nodes,
    project_product_index,
    project_product_node,
    project_product_nodes,
    unavailable_index,
    unavailable_nodes,
)
from oscillink_agent.memory.repository import (
    MemoryAuthorityState,
    MemoryRecordNotFoundError,
    MemoryReviewConflictError,
    MemorySyncConflictError,
    MemoryTransitionConflictError,
    SQLiteMemoryRepository,
)
from oscillink_agent.memory.service import load_memory_index

_IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"


def build_memory_router(data_root: Path, vault_root: Path | None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/memory/index", response_model=MemoryIndexProjection)
    def memory_index() -> MemoryIndexProjection:
        memory_database = data_root / "memory.sqlite3"
        if memory_database.is_file():
            repository = SQLiteMemoryRepository(memory_database)
            try:
                return project_product_index(repository.list())
            finally:
                repository.close()
        index, reason = load_memory_index(vault_root)
        if index is None:
            assert reason is not None
            return unavailable_index(reason)
        return project_index(index)

    @router.get("/api/v1/memory/nodes", response_model=MemoryNodeCollection)
    def memory_nodes(
        category: MemoryCategory | None = None,
        domain: MemoryDomain | None = None,
    ) -> MemoryNodeCollection:
        memory_database = data_root / "memory.sqlite3"
        if memory_database.is_file():
            repository = SQLiteMemoryRepository(memory_database)
            try:
                return project_product_nodes(
                    repository.list(),
                    category=category,
                    domain=domain,
                )
            finally:
                repository.close()
        index, reason = load_memory_index(vault_root)
        if index is None:
            assert reason is not None
            return unavailable_nodes(reason, category=category, domain=domain)
        return project_nodes(index, category=category, domain=domain)

    @router.get(
        "/api/v1/memory/nodes/{node_id}",
        response_model=MemoryNodeDetailResponse,
    )
    def memory_node(node_id: MemoryNodeId) -> MemoryNodeDetailResponse:
        memory_database = data_root / "memory.sqlite3"
        if node_id.startswith("mem_"):
            if not memory_database.is_file():
                raise HTTPException(
                    status_code=404,
                    detail={"code": "node_not_found", "message": "Memory node was not found."},
                )
            repository = SQLiteMemoryRepository(memory_database)
            try:
                record = repository.get(node_id)
            finally:
                repository.close()
            if record is not None:
                return project_product_node(record)
            raise HTTPException(
                status_code=404,
                detail={"code": "node_not_found", "message": "Memory node was not found."},
            )
        index, reason = load_memory_index(vault_root)
        if index is None:
            message = (
                "Reviewed memory is not configured."
                if reason is MemoryUnavailableReason.VAULT_NOT_CONFIGURED
                else "Reviewed memory is unavailable."
            )
            raise HTTPException(
                status_code=503,
                detail={"code": "memory_unavailable", "message": message},
            )
        note = next((candidate for candidate in index.notes if candidate.id == node_id), None)
        if note is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "node_not_found", "message": "Memory node was not found."},
            )
        return project_node(note)

    @router.post(
        "/api/v1/memory/nodes",
        response_model=MemoryNodeDetailResponse,
        status_code=http_status.HTTP_201_CREATED,
    )
    def create_memory_node(request: NativeMemoryCreateRequest) -> MemoryNodeDetailResponse:
        repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
        try:
            record = repository.create_native(
                title=request.title,
                content=request.content,
                category=request.category,
                domains=request.domains,
                topics=request.topics,
                content_hash=(
                    "sha256:" + hashlib.sha256(request.content.encode("utf-8")).hexdigest()
                ),
                architecture_node_ids=request.architecture_node_ids,
            )
            return project_product_node(record)
        finally:
            repository.close()

    @router.post(
        "/api/v1/memory/nodes/{node_id}/reviews",
        response_model=MemoryNodeDetailResponse,
    )
    def review_memory_node(
        node_id: MemoryNodeId,
        request: MemoryReviewRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=128,
                pattern=_IDEMPOTENCY_KEY_PATTERN,
            ),
        ],
    ) -> MemoryNodeDetailResponse:
        if not node_id.startswith("mem_"):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "source_record_not_reviewable",
                    "message": "Synchronize the source into product memory before review.",
                },
            )
        repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
        try:
            try:
                record = repository.review(
                    node_id,
                    decision=MemoryAuthorityState(request.decision),
                    event_id=request.request_id,
                    idempotency_key=idempotency_key,
                    replacement_record_id=request.replacement_record_id,
                )
            except MemoryRecordNotFoundError:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "node_not_found", "message": "Memory node was not found."},
                ) from None
            except MemoryReviewConflictError:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "idempotency_conflict",
                        "message": "Idempotency key belongs to another review request.",
                    },
                ) from None
            except MemoryTransitionConflictError:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "invalid_transition",
                        "message": "Review decision violates the authority-state contract.",
                    },
                ) from None
            return project_product_node(record)
        finally:
            repository.close()

    @router.post(
        "/api/v1/memory/sources/obsidian/sync",
        response_model=MemorySourceSyncResponse,
    )
    def sync_obsidian_memory(
        request: MemorySourceSyncRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=128,
                pattern=_IDEMPOTENCY_KEY_PATTERN,
            ),
        ],
    ) -> MemorySourceSyncResponse:
        index, reason = load_memory_index(vault_root)
        if index is None:
            message = (
                "Obsidian source is not configured."
                if reason is MemoryUnavailableReason.VAULT_NOT_CONFIGURED
                else "Obsidian source is unavailable."
            )
            raise HTTPException(
                status_code=503,
                detail={"code": "source_unavailable", "message": message},
            )
        repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
        try:
            try:
                records = repository.sync_obsidian(
                    source_key="obsidian_primary",
                    notes=index.notes,
                    event_id=request.request_id,
                    idempotency_key=idempotency_key,
                    snapshot_hash=index.index_hash,
                )
            except MemorySyncConflictError:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "idempotency_conflict",
                        "message": "Idempotency key belongs to another source snapshot.",
                    },
                ) from None
            return MemorySourceSyncResponse(record_count=len(records))
        finally:
            repository.close()

    return router
