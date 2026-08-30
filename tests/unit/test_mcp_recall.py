import json
from hashlib import sha256
from pathlib import Path

from oscillink_agent.integrations.mcp.server import (
    create_read_only_server,
    execute_read_only_tool,
    list_read_only_tools,
)
from oscillink_agent.memory.obsidian import (
    IndexedObsidianNote,
    MemoryCategory,
    MemoryDomain,
)
from oscillink_agent.memory.repository import (
    MemoryAuthorityState,
    ProductMemoryRecord,
    SQLiteMemoryRepository,
)


def _create_memory(
    repository: SQLiteMemoryRepository,
    *,
    title: str,
    content: str,
    topics: tuple[str, ...] = ("deployment",),
) -> ProductMemoryRecord:
    return repository.create_native(
        title=title,
        content=content,
        category=MemoryCategory.GOVERNANCE,
        domains=(MemoryDomain.SOFTWARE,),
        topics=topics,
        content_hash="sha256:" + sha256(content.encode()).hexdigest(),
    )


def _review(
    repository: SQLiteMemoryRepository,
    record: ProductMemoryRecord,
    decision: MemoryAuthorityState,
    sequence: int,
    *,
    replacement: ProductMemoryRecord | None = None,
) -> None:
    repository.review(
        record.id,
        decision=decision,
        event_id=f"evt_01J000000000000000000000{sequence:X}",
        idempotency_key=f"test-review-{sequence}",
        replacement_record_id=None if replacement is None else replacement.id,
    )


def test_read_only_server_lists_only_recall_and_explain_with_strict_schemas(
    tmp_path: Path,
) -> None:
    server = create_read_only_server(tmp_path / "workspace")
    result = list_read_only_tools()

    assert server.server_info.name == "oscillink-project-memory"
    assert server.get_request_handler("tools/list") is not None
    assert server.get_request_handler("tools/call") is not None
    assert [tool.name for tool in result.tools] == ["recall", "explain"]
    for tool in result.tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.idempotent_hint is True
        assert tool.annotations.open_world_hint is False
        assert tool.input_schema["additionalProperties"] is False
        assert "workspace_id" not in tool.input_schema.get("properties", {})
        assert tool.output_schema is not None
        encoded_output_schema = json.dumps(tool.output_schema, sort_keys=True)
        assert "raw_exception" not in encoded_output_schema
        assert "host_path" not in encoded_output_schema


def test_recall_returns_typed_unavailable_for_an_empty_workspace(tmp_path: Path) -> None:
    result = execute_read_only_tool(
        tmp_path / "workspace",
        "recall",
        {
            "schema_version": 1,
            "request_id": "evt_01J00000000000000000000000",
            "query": "deployment approach",
            "token_budget": 2048,
        },
    )

    assert result.model_dump(mode="json") == {
        "schema_version": 1,
        "state": "unavailable",
        "operation": "recall",
        "reason": "empty_workspace",
        "retryable": False,
    }


def test_recall_returns_only_current_approved_memory_with_deterministic_evidence(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "workspace"
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        superseded = _create_memory(
            repository,
            title="Old deployment approach",
            content="Deploy immediately after a local test.",
        )
        current = _create_memory(
            repository,
            title="Current deployment approach",
            content="Deploy only after immutable verification.",
        )
        candidate = _create_memory(
            repository,
            title="Candidate deployment approach",
            content="Deploy without verification.",
        )
        rejected = _create_memory(
            repository,
            title="Rejected deployment approach",
            content="Deploy from an unreviewed workspace.",
        )
        unmatched = _create_memory(
            repository,
            title="Editor preference",
            content="Use concise commit messages.",
            topics=(),
        )
        _review(repository, superseded, MemoryAuthorityState.APPROVED, 1)
        _review(repository, current, MemoryAuthorityState.APPROVED, 2)
        _review(repository, rejected, MemoryAuthorityState.REJECTED, 3)
        _review(repository, unmatched, MemoryAuthorityState.APPROVED, 4)
        _review(
            repository,
            superseded,
            MemoryAuthorityState.SUPERSEDED,
            5,
            replacement=current,
        )
    finally:
        repository.close()

    arguments = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000000",
        "query": "deployment approach",
        "token_budget": 2048,
    }
    first = execute_read_only_tool(data_root, "recall", arguments)
    second = execute_read_only_tool(data_root, "recall", arguments)

    assert first.model_dump_json() == second.model_dump_json()
    assert first.state == "available"
    payload = first.model_dump(mode="json")
    assert [record["record_id"] for record in payload["records"]] == [current.id]
    assert payload["records"][0]["content_hash"] == current.content_hash
    assert payload["records"][0]["content_treatment"] == "untrusted_data"
    assert payload["context_manifest"]["exclusion_summary"] == {
        "not_approved_count": 2,
        "missing_source_count": 0,
        "superseded_count": 1,
        "conflict_count": 0,
    }
    assert payload["context_manifest"]["omissions"] == [
        {
            "record_id": unmatched.id,
            "content_hash": unmatched.content_hash,
            "reason": "no_query_match",
            "retrieval_rank": None,
            "retrieval_score": None,
        }
    ]
    assert candidate.content not in first.model_dump_json()
    assert rejected.content not in first.model_dump_json()
    assert superseded.content not in first.model_dump_json()

    bounded = execute_read_only_tool(
        data_root,
        "recall",
        {**arguments, "token_budget": 2},
    ).model_dump(mode="json")
    assert bounded["records"] == []
    assert bounded["context_manifest"]["total_token_count"] == 0
    assert bounded["context_manifest"]["omissions"][0]["record_id"] == current.id
    assert bounded["context_manifest"]["omissions"][0]["reason"] == "token_budget"


def test_explain_reports_exact_supersession_lineage_and_missing_revision(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "workspace"
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        old = _create_memory(
            repository,
            title="Old deployment approach",
            content="Deploy after a local test.",
        )
        replacement = _create_memory(
            repository,
            title="Current deployment approach",
            content="Deploy after immutable verification.",
        )
        _review(repository, old, MemoryAuthorityState.APPROVED, 1)
        _review(repository, replacement, MemoryAuthorityState.APPROVED, 2)
        _review(
            repository,
            old,
            MemoryAuthorityState.SUPERSEDED,
            3,
            replacement=replacement,
        )
    finally:
        repository.close()

    arguments = {
        "schema_version": 1,
        "request_id": "evt_01J00000000000000000000006",
        "record_id": old.id,
        "content_hash": old.content_hash,
    }
    result = execute_read_only_tool(data_root, "explain", arguments)

    assert result.model_dump(mode="json") == {
        "schema_version": 1,
        "state": "available",
        "operation": "explain",
        "request_id": arguments["request_id"],
        "record_id": old.id,
        "content_hash": old.content_hash,
        "authority_state": "superseded",
        "reasons": ["superseded"],
        "lineage": [
            {
                "record_id": old.id,
                "content_hash": old.content_hash,
                "authority_state": "superseded",
                "relationship": "requested",
            },
            {
                "record_id": replacement.id,
                "content_hash": replacement.content_hash,
                "authority_state": "approved",
                "relationship": "superseded_by",
            },
        ],
    }

    selected = execute_read_only_tool(
        data_root,
        "explain",
        {
            **arguments,
            "record_id": replacement.id,
            "content_hash": replacement.content_hash,
        },
    ).model_dump(mode="json")
    assert selected["authority_state"] == "approved"
    assert selected["reasons"] == ["selected"]
    assert selected["lineage"][0]["relationship"] == "requested"

    missing = execute_read_only_tool(
        data_root,
        "explain",
        {**arguments, "content_hash": "sha256:" + "f" * 64},
    )
    assert missing.model_dump(mode="json") == {
        "schema_version": 1,
        "state": "unavailable",
        "operation": "explain",
        "reason": "revision_not_found",
        "retryable": False,
    }


def test_explain_marks_an_exact_stored_revision_stale_after_source_revision(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "workspace"
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")

    def note(content: str) -> IndexedObsidianNote:
        return IndexedObsidianNote(
            id="doc_01J00000000000000000000000",
            source_path="Projects/Oscillink.md",
            title="Oscillink deployment",
            content=content,
            frontmatter_type="project",
            source_status=None,
            category=MemoryCategory.PROJECT,
            domains=(MemoryDomain.SOFTWARE,),
            topics=("deployment",),
            wikilinks=(),
            classification_basis=("frontmatter",),
            content_hash="sha256:" + sha256(content.encode()).hexdigest(),
        )

    try:
        original = note("Deploy after local verification.")
        first = repository.sync_obsidian(
            source_key="primary-vault",
            notes=(original,),
            event_id="evt_01J0000000000000000000000A",
            idempotency_key="stale-sync-one",
            snapshot_hash="sha256:" + "a" * 64,
            issue_count=0,
        ).records[0]
        _review(repository, first, MemoryAuthorityState.APPROVED, 11)
        revised = note("Deploy only after immutable verification.")
        second = repository.sync_obsidian(
            source_key="primary-vault",
            notes=(revised,),
            event_id="evt_01J0000000000000000000000B",
            idempotency_key="stale-sync-two",
            snapshot_hash="sha256:" + "b" * 64,
            issue_count=0,
        ).records[0]
    finally:
        repository.close()

    assert first.id == second.id
    result = execute_read_only_tool(
        data_root,
        "explain",
        {
            "schema_version": 1,
            "request_id": "evt_01J0000000000000000000000C",
            "record_id": first.id,
            "content_hash": first.content_hash,
        },
    ).model_dump(mode="json")

    assert result["state"] == "available"
    assert result["record_id"] == first.id
    assert result["content_hash"] == first.content_hash
    assert result["reasons"] == ["stale_revision"]
    assert result["lineage"][0]["relationship"] == "requested"
