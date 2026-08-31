"""Governed write lifecycle through the Project Memory MCP adapter."""

from hashlib import sha256
from pathlib import Path

import pytest

from oscillink_agent.integrations.mcp.server import execute_project_memory_tool
from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.repository import (
    MemoryAuthorityState,
    MemoryCreateConflictError,
    SQLiteMemoryRepository,
)


def test_project_memory_server_advertises_governed_reads_and_candidate_writes() -> None:
    from oscillink_agent.integrations.mcp.server import list_project_memory_tools

    tools = list_project_memory_tools().tools

    assert [tool.name for tool in tools] == ["remember", "recall", "correct", "explain"]
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.idempotent_hint is True
        assert tool.annotations.open_world_hint is False
        assert tool.annotations.read_only_hint is (tool.name in {"recall", "explain"})


def test_explicit_candidate_identity_cannot_overwrite_incompatible_content(
    tmp_path: Path,
) -> None:
    repository = SQLiteMemoryRepository(tmp_path / "memory.sqlite3")
    record_id = "mem_01J00000000000000000000000"
    first_content = "Preserve the first candidate."
    try:
        first = repository.create_native(
            record_id=record_id,
            title="Candidate",
            content=first_content,
            category=MemoryCategory.GOVERNANCE,
            domains=(MemoryDomain.SOFTWARE,),
            topics=("candidate",),
            content_hash="sha256:" + sha256(first_content.encode()).hexdigest(),
        )
        with pytest.raises(MemoryCreateConflictError):
            repository.create_native(
                record_id=record_id,
                title="Candidate",
                content="Overwrite attempt.",
                category=MemoryCategory.GOVERNANCE,
                domains=(MemoryDomain.SOFTWARE,),
                topics=("candidate",),
                content_hash="sha256:" + sha256(b"Overwrite attempt.").hexdigest(),
            )
        preserved = repository.get(record_id)
    finally:
        repository.close()

    assert preserved == first


def test_remember_creates_a_candidate_that_recall_cannot_promote(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace"
    request_id = "evt_01J0000000000000000000000D"

    created = execute_project_memory_tool(
        data_root,
        "remember",
        {
            "schema_version": 1,
            "request_id": request_id,
            "title": "Deployment decision",
            "content": "Deploy only after immutable verification.",
            "category": "governance",
            "domains": ["software"],
            "topics": ["deployment", "verification"],
            "source_refs": ["doc_01J00000000000000000000000"],
        },
    ).model_dump(mode="json")

    assert created["schema_version"] == 1
    assert created["state"] == "candidate"
    assert created["operation"] == "remember"
    assert created["request_id"] == request_id
    assert created["approval_required"] is True

    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        records = repository.list()
    finally:
        repository.close()
    assert len(records) == 1
    assert records[0].id == created["record_id"]
    assert records[0].content_hash == created["content_hash"]
    assert records[0].authority_state is MemoryAuthorityState.CANDIDATE

    recalled = execute_project_memory_tool(
        data_root,
        "recall",
        {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000E",
            "query": "deployment verification",
            "token_budget": 2048,
        },
    ).model_dump(mode="json")
    assert recalled == {
        "schema_version": 1,
        "state": "unavailable",
        "operation": "recall",
        "reason": "no_approved_memory",
        "retryable": False,
    }


def test_remember_replays_one_request_without_duplicate_candidates(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace"
    arguments = {
        "schema_version": 1,
        "request_id": "evt_01J0000000000000000000000F",
        "title": "Context budget",
        "content": "Keep deterministic context under 2048 tokens.",
        "category": "governance",
        "domains": ["software"],
        "topics": ["context"],
        "source_refs": ["doc_01J00000000000000000000001"],
    }

    first = execute_project_memory_tool(data_root, "remember", arguments).model_dump(
        mode="json"
    )
    replay = execute_project_memory_tool(data_root, "remember", arguments).model_dump(
        mode="json"
    )

    assert replay == first
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        records = repository.list()
    finally:
        repository.close()
    assert len(records) == 1


def test_remember_rejects_changed_payload_for_an_existing_request(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace"
    arguments = {
        "schema_version": 1,
        "request_id": "evt_01J0000000000000000000000G",
        "title": "Release policy",
        "content": "Require an immutable local gate.",
        "category": "governance",
        "domains": ["software"],
        "topics": ["release"],
        "source_refs": ["doc_01J00000000000000000000002"],
    }
    execute_project_memory_tool(data_root, "remember", arguments)

    conflict = execute_project_memory_tool(
        data_root,
        "remember",
        {**arguments, "content": "Skip verification."},
    ).model_dump(mode="json")

    assert conflict == {
        "schema_version": 1,
        "state": "failure",
        "operation": "remember",
        "code": "request_conflict",
        "retryable": False,
    }
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        records = repository.list()
    finally:
        repository.close()
    assert len(records) == 1
    assert records[0].content == arguments["content"]


def test_remember_persists_server_actor_request_and_source_provenance(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace"
    request_id = "evt_01J0000000000000000000000H"
    source_refs = (
        "doc_01J00000000000000000000003",
        "evt_01J00000000000000000000003",
    )

    created = execute_project_memory_tool(
        data_root,
        "remember",
        {
            "schema_version": 1,
            "request_id": request_id,
            "title": "Provider choice",
            "content": "Provider configuration is an adapter boundary.",
            "category": "project",
            "domains": ["software"],
            "topics": ["provider"],
            "source_refs": list(source_refs),
        },
        actor_id="model_codex",
    ).model_dump(mode="json")

    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        record = repository.get(created["record_id"])
    finally:
        repository.close()
    assert record is not None
    assert record.created_by == "model_codex"
    assert record.creation_request_id == request_id
    assert record.source_refs == source_refs


def test_correct_creates_replacement_candidate_without_mutating_approved_target(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "workspace"
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    original_content = "Deploy after CI passes."
    original_hash = "sha256:" + sha256(original_content.encode()).hexdigest()
    try:
        target = repository.create_native(
            title="Deployment policy",
            content=original_content,
            category=MemoryCategory.GOVERNANCE,
            domains=(MemoryDomain.SOFTWARE,),
            topics=("deployment",),
            content_hash=original_hash,
        )
        repository.review(
            target.id,
            decision=MemoryAuthorityState.APPROVED,
            event_id="evt_01J0000000000000000000000J",
            idempotency_key="approve-correction-target",
        )
    finally:
        repository.close()

    corrected = execute_project_memory_tool(
        data_root,
        "correct",
        {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000K",
            "title": "Deployment policy",
            "content": "Deploy only after local, Buildbox, and CI verification.",
            "category": "governance",
            "domains": ["software"],
            "topics": ["deployment"],
            "source_refs": [target.id],
            "target_record_id": target.id,
            "expected_content_hash": original_hash,
            "reason": "The earlier policy omitted immutable local and Linux verification.",
        },
        actor_id="model_codex",
    ).model_dump(mode="json")

    assert corrected["state"] == "candidate"
    assert corrected["operation"] == "correct"
    assert corrected["target_record_id"] == target.id
    assert corrected["expected_content_hash"] == original_hash
    assert corrected["approval_required"] is True

    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        current_target = repository.get(target.id)
        replacement = repository.get(corrected["replacement_record_id"])
    finally:
        repository.close()
    assert current_target is not None
    assert current_target.content_hash == original_hash
    assert current_target.authority_state is MemoryAuthorityState.APPROVED
    assert replacement is not None
    assert replacement.authority_state is MemoryAuthorityState.CANDIDATE
    assert replacement.source_refs == (target.id,)
    assert replacement.created_by == "model_codex"


def test_correct_rejects_changed_reason_for_an_existing_request(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace"
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    content = "Use the local gate."
    content_hash = "sha256:" + sha256(content.encode()).hexdigest()
    try:
        target = repository.create_native(
            title="Verification",
            content=content,
            category=MemoryCategory.GOVERNANCE,
            domains=(MemoryDomain.SOFTWARE,),
            topics=("verification",),
            content_hash=content_hash,
        )
    finally:
        repository.close()
    arguments = {
        "schema_version": 1,
        "request_id": "evt_01J0000000000000000000000N",
        "title": "Verification",
        "content": "Use local and Linux gates.",
        "category": "governance",
        "domains": ["software"],
        "topics": ["verification"],
        "source_refs": [target.id],
        "target_record_id": target.id,
        "expected_content_hash": content_hash,
        "reason": "Linux parity is required.",
    }
    execute_project_memory_tool(data_root, "correct", arguments)

    conflict = execute_project_memory_tool(
        data_root,
        "correct",
        {**arguments, "reason": "Changed justification."},
    ).model_dump(mode="json")

    assert conflict == {
        "schema_version": 1,
        "state": "failure",
        "operation": "correct",
        "code": "request_conflict",
        "retryable": False,
    }


def test_governed_correction_reconstructs_current_recall_and_old_lineage(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "workspace"
    original = execute_project_memory_tool(
        data_root,
        "remember",
        {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000P",
            "title": "Release verification",
            "content": "Run CI before release.",
            "category": "governance",
            "domains": ["software"],
            "topics": ["release", "verification"],
            "source_refs": ["doc_01J00000000000000000000005"],
        },
    ).model_dump(mode="json")
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        repository.review(
            original["record_id"],
            decision=MemoryAuthorityState.APPROVED,
            event_id="evt_01J0000000000000000000000Q",
            idempotency_key="approve-original-mcp-memory",
        )
    finally:
        repository.close()

    correction = execute_project_memory_tool(
        data_root,
        "correct",
        {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000R",
            "title": "Release verification",
            "content": "Run immutable local, Buildbox, and CI gates before release.",
            "category": "governance",
            "domains": ["software"],
            "topics": ["release", "verification"],
            "source_refs": [original["record_id"]],
            "target_record_id": original["record_id"],
            "expected_content_hash": original["content_hash"],
            "reason": "CI alone omitted local and independent Linux verification.",
        },
    ).model_dump(mode="json")
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        repository.review(
            correction["replacement_record_id"],
            decision=MemoryAuthorityState.APPROVED,
            event_id="evt_01J0000000000000000000000S",
            idempotency_key="approve-corrected-mcp-memory",
        )
        repository.review(
            original["record_id"],
            decision=MemoryAuthorityState.SUPERSEDED,
            event_id="evt_01J0000000000000000000000T",
            idempotency_key="supersede-original-mcp-memory",
            replacement_record_id=correction["replacement_record_id"],
        )
    finally:
        repository.close()

    recalled = execute_project_memory_tool(
        data_root,
        "recall",
        {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000V",
            "query": "release verification",
            "token_budget": 2048,
        },
    ).model_dump(mode="json")
    explained = execute_project_memory_tool(
        data_root,
        "explain",
        {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000W",
            "record_id": original["record_id"],
            "content_hash": original["content_hash"],
        },
    ).model_dump(mode="json")
    explained_replacement = execute_project_memory_tool(
        data_root,
        "explain",
        {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000X",
            "record_id": correction["replacement_record_id"],
            "content_hash": correction["replacement_content_hash"],
        },
    ).model_dump(mode="json")

    assert [record["record_id"] for record in recalled["records"]] == [
        correction["replacement_record_id"]
    ]
    assert explained["authority_state"] == "superseded"
    assert explained["reasons"] == ["superseded"]
    assert explained["lineage"][1] == {
        "record_id": correction["replacement_record_id"],
        "content_hash": correction["replacement_content_hash"],
        "authority_state": "approved",
        "relationship": "superseded_by",
    }
    assert explained_replacement["authority_state"] == "approved"
    assert explained_replacement["lineage"][1] == {
        "record_id": original["record_id"],
        "content_hash": original["content_hash"],
        "authority_state": "superseded",
        "relationship": "supersedes",
    }
