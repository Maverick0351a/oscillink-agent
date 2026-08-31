import os
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.repository import MemoryAuthorityState, SQLiteMemoryRepository


async def _exercise_stdio_server(data_root: Path) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = ""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "oscillink_agent.integrations.mcp.cli",
            "--data-root",
            str(data_root),
        ],
        cwd=Path.cwd(),
        env=environment,
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        initialized = await session.initialize()
        tools = await session.list_tools()
        called = await session.call_tool(
            "recall",
            {
                "schema_version": 1,
                "request_id": "evt_01J00000000000000000000009",
                "query": "deployment verification",
                "token_budget": 2048,
            },
        )
        remembered = await session.call_tool(
            "remember",
            {
                "schema_version": 1,
                "request_id": "evt_01J0000000000000000000000M",
                "title": "Context policy",
                "content": "Use only approved project memory in model context.",
                "category": "governance",
                "domains": ["software"],
                "topics": ["context"],
                "source_refs": ["doc_01J00000000000000000000004"],
            },
        )
        return {
            "server_name": initialized.server_info.name,
            "tools": [tool.name for tool in tools.tools],
            "is_error": called.is_error,
            "structured": called.structured_content,
            "remember_error": remembered.is_error,
            "remembered": remembered.structured_content,
        }


def test_stdio_mcp_client_reads_approved_memory_and_creates_candidate_writes(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "workspace"
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        content = "Deploy only after immutable verification."
        record = repository.create_native(
            title="Deployment verification",
            content=content,
            category=MemoryCategory.GOVERNANCE,
            domains=(MemoryDomain.SOFTWARE,),
            topics=("deployment", "verification"),
            content_hash="sha256:" + sha256(content.encode()).hexdigest(),
        )
        repository.review(
            record.id,
            decision=MemoryAuthorityState.APPROVED,
            event_id="evt_01J00000000000000000000008",
            idempotency_key="stdio-integration-approve",
        )
    finally:
        repository.close()

    result = anyio.run(_exercise_stdio_server, data_root)

    assert result["server_name"] == "oscillink-project-memory"
    assert result["tools"] == ["remember", "recall", "correct", "explain"]
    assert result["is_error"] is False
    structured = result["structured"]
    assert structured is not None
    assert structured["state"] == "available"
    assert structured["records"] == [
        {
            "record_id": record.id,
            "content_hash": record.content_hash,
            "title": "Deployment verification",
            "content": "Deploy only after immutable verification.",
            "source_refs": [record.id],
            "content_treatment": "untrusted_data",
        }
    ]
    assert result["remember_error"] is False
    remembered = result["remembered"]
    assert remembered is not None
    assert remembered["state"] == "candidate"
    assert remembered["operation"] == "remember"
    assert remembered["approval_required"] is True

    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        candidate = repository.get(remembered["record_id"])
    finally:
        repository.close()
    assert candidate is not None
    assert candidate.authority_state is MemoryAuthorityState.CANDIDATE
