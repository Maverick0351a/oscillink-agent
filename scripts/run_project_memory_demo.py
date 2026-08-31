"""Run the deterministic local Project Memory continuity demonstration."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from time import monotonic
from typing import Annotated, Any, Literal

import anyio
from pydantic import BaseModel, ConfigDict, Field

from oscillink_agent.memory.obsidian import MemoryCategory, MemoryDomain
from oscillink_agent.memory.repository import MemoryAuthorityState, SQLiteMemoryRepository

DEFAULT_FIXTURE = (
    Path(__file__).parents[1]
    / "examples"
    / "project-memory-demo"
    / "project-fixture"
    / "scenario.json"
)


class DemoFixtureError(ValueError):
    """The public demo fixture violates a cross-record integrity rule."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DemoMemory(_StrictModel):
    key: Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    title: Annotated[str, Field(min_length=1, max_length=512)]
    content: Annotated[str, Field(min_length=1, max_length=4096)]
    category: MemoryCategory
    domains: tuple[MemoryDomain, ...]
    topics: tuple[Annotated[str, Field(min_length=1, max_length=128)], ...]
    source_ref: Annotated[str, Field(pattern=r"^doc_[0-9A-HJKMNP-TV-Z]{26}$")]


class DemoCorrection(_StrictModel):
    target_key: Annotated[str, Field(min_length=1, max_length=128)]
    content: Annotated[str, Field(min_length=1, max_length=4096)]
    reason: Annotated[str, Field(min_length=1, max_length=2048)]


class DemoFixture(_StrictModel):
    schema_version: Literal[1] = 1
    scenario_id: Annotated[str, Field(min_length=1, max_length=128)]
    memories: tuple[DemoMemory, ...]
    correction: DemoCorrection
    recall_query: Annotated[str, Field(min_length=1, max_length=4096)]
    token_budget: Annotated[int, Field(ge=1, le=32768)]


def _load_fixture(path: Path) -> tuple[DemoFixture, str]:
    fixture_bytes = path.read_bytes()
    fixture = DemoFixture.model_validate_json(fixture_bytes)
    keys = [memory.key for memory in fixture.memories]
    if len(keys) != len(set(keys)):
        raise DemoFixtureError("duplicate memory key")
    if fixture.correction.target_key not in keys:
        raise DemoFixtureError("correction target is absent from memories")
    digest = "sha256:" + hashlib.sha256(fixture_bytes).hexdigest()
    return fixture, digest


def _remember_requests(fixture: DemoFixture) -> list[dict[str, Any]]:
    return [
        {
            "schema_version": 1,
            "request_id": f"evt_01J000000000000000000000{index:02d}",
            "title": memory.title,
            "content": memory.content,
            "category": memory.category.value,
            "domains": [domain.value for domain in memory.domains],
            "topics": list(memory.topics),
            "source_refs": [memory.source_ref],
        }
        for index, memory in enumerate(fixture.memories, start=10)
    ]


async def _call_tools(
    data_root: Path,
    calls: Sequence[tuple[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], int]:
    payload = {
        "data_root": str(data_root),
        "calls": [
            {"name": tool_name, "arguments": arguments}
            for tool_name, arguments in calls
        ],
    }
    worker = Path(__file__).with_name("project_memory_demo_client.py")
    completed = await anyio.run_process(
        [sys.executable, str(worker)],
        input=json.dumps(payload).encode("utf-8"),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("isolated demo client failed")
    response = json.loads(completed.stdout)
    return list(response["results"]), int(response["client_process_id"])


def _review(
    data_root: Path,
    *,
    record_id: str,
    decision: MemoryAuthorityState,
    sequence: int,
    replacement_record_id: str | None = None,
) -> None:
    repository = SQLiteMemoryRepository(data_root / "memory.sqlite3")
    try:
        repository.review(
            record_id,
            decision=decision,
            event_id=f"evt_01J000000000000000000000{sequence:02d}",
            idempotency_key=f"project-memory-demo-review-{sequence}",
            replacement_record_id=replacement_record_id,
        )
    finally:
        repository.close()


async def run_demo(
    data_root: Path,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> dict[str, Any]:
    """Run two fresh agent sessions around an externally governed correction."""

    started = monotonic()
    fixture, fixture_hash = _load_fixture(fixture_path)
    data_root.mkdir(parents=True, exist_ok=True)
    remember_requests = _remember_requests(fixture)
    remembered, agent_a_process_id = await _call_tools(
        data_root,
        [("remember", request) for request in remember_requests],
    )
    for sequence, result in enumerate(remembered, start=20):
        _review(
            data_root,
            record_id=str(result["record_id"]),
            decision=MemoryAuthorityState.APPROVED,
            sequence=sequence,
        )

    target_index = next(
        index
        for index, memory in enumerate(fixture.memories)
        if memory.key == fixture.correction.target_key
    )
    old = remembered[target_index]
    correction_request = {
        **remember_requests[target_index],
        "request_id": (
            f"evt_01J000000000000000000000{10 + len(remember_requests):02d}"
        ),
        "content": fixture.correction.content,
        "source_refs": [old["record_id"]],
        "target_record_id": old["record_id"],
        "expected_content_hash": old["content_hash"],
        "reason": fixture.correction.reason,
    }
    correction_results, governance_process_id = await _call_tools(
        data_root,
        [("correct", correction_request)],
    )
    correction = correction_results[0]
    replacement_id = str(correction["replacement_record_id"])
    _review(
        data_root,
        record_id=replacement_id,
        decision=MemoryAuthorityState.APPROVED,
        sequence=20 + len(remembered),
    )
    _review(
        data_root,
        record_id=str(old["record_id"]),
        decision=MemoryAuthorityState.SUPERSEDED,
        sequence=21 + len(remembered),
        replacement_record_id=replacement_id,
    )

    agent_b_results, agent_b_process_id = await _call_tools(
        data_root,
        [
            (
                "recall",
                {
                    "schema_version": 1,
                    "request_id": "evt_01J00000000000000000000015",
                    "query": fixture.recall_query,
                    "token_budget": fixture.token_budget,
                },
            ),
            (
                "explain",
                {
                    "schema_version": 1,
                    "request_id": "evt_01J00000000000000000000016",
                    "record_id": replacement_id,
                    "content_hash": correction["replacement_content_hash"],
                },
            ),
        ],
    )
    recalled, explained = agent_b_results
    records = sorted(recalled["records"], key=lambda record: str(record["title"]))
    replacement = next(record for record in records if record["record_id"] == replacement_id)
    prior_revision = next(
        entry
        for entry in explained["lineage"]
        if entry["record_id"] == old["record_id"]
    )
    return {
        "schema_version": 1,
        "fixture_hash": fixture_hash,
        "transport": "stdio",
        "protocol_client": "official-python-mcp-sdk",
        "account_required": False,
        "transcript_replayed": False,
        "client_sessions": [
            {
                "name": "agent-a",
                "client_process_id": agent_a_process_id,
                "fresh_server_process": True,
            },
            {
                "name": "agent-b",
                "client_process_id": agent_b_process_id,
                "fresh_server_process": True,
            },
        ],
        "governance_session": {
            "purpose": "propose-correction-after-compaction",
            "client_process_id": governance_process_id,
            "fresh_server_process": True,
        },
        "learned_record_count": len(remembered),
        "agent_b": {
            "current_titles": [record["title"] for record in records],
            "current_contents": [record["content"] for record in records],
            "context_manifest": recalled["context_manifest"],
            "lineage": {
                "old_authority_state": prior_revision["authority_state"],
                "old_content": fixture.memories[target_index].content,
                "replacement_content": replacement["content"],
                "relationship": prior_revision["relationship"],
            },
        },
        "elapsed_seconds": monotonic() - started,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    import anyio

    arguments = _parser().parse_args(argv)
    report = anyio.run(run_demo, arguments.data_root, arguments.fixture)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
