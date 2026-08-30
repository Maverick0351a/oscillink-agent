from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from oscillink_agent.agent_runtime.tools import FileReadToolRequest
from oscillink_agent.providers.base import (
    FinalResponseResult,
    ProviderResult,
    ToolRequestResult,
)


def test_provider_result_is_exactly_final_response_or_one_file_read_request() -> None:
    adapter = TypeAdapter(ProviderResult)

    final = adapter.validate_python(
        {"kind": "final_response", "answer": "Bounded final answer."},
        strict=True,
    )
    tool = adapter.validate_python(
        {
            "kind": "tool_request",
            "request": {
                "schema_version": 1,
                "operation": "file.read",
                "scope_id": "repo_oscillink_agent",
                "target": "docs/build-plan.md",
                "max_bytes": 65_536,
            },
        },
        strict=True,
    )

    assert isinstance(final, FinalResponseResult)
    assert final.answer == "Bounded final answer."
    assert isinstance(tool, ToolRequestResult)
    assert tool.request == FileReadToolRequest(
        schema_version=1,
        operation="file.read",
        scope_id="repo_oscillink_agent",
        target="docs/build-plan.md",
        max_bytes=65_536,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "schema_version": 1,
            "operation": "shell.exec",
            "scope_id": "repo_oscillink_agent",
            "target": "README.md",
            "max_bytes": 1024,
        },
        {
            "schema_version": 1,
            "operation": "file.read",
            "scope_id": "repo_oscillink_agent",
            "target": "../secrets.txt",
            "max_bytes": 1024,
        },
        {
            "schema_version": 1,
            "operation": "file.read",
            "scope_id": "repo_oscillink_agent",
            "target": "C:/Windows/System32/config/SAM",
            "max_bytes": 1024,
        },
        {
            "schema_version": 1,
            "operation": "file.read",
            "scope_id": "repo_oscillink_agent",
            "target": "README.md",
            "max_bytes": 1_048_577,
        },
        {
            "schema_version": 1,
            "operation": "file.read",
            "scope_id": "repo_oscillink_agent",
            "target": "README.md",
            "max_bytes": 1024,
            "grant_id": "grt_01J00000000000000000000000",
        },
    ],
)
def test_file_read_request_rejects_unknown_unportable_oversized_or_grant_fields(
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        FileReadToolRequest.model_validate(payload, strict=True)


def test_provider_result_rejects_ambiguous_or_extra_shapes() -> None:
    adapter = TypeAdapter(ProviderResult)

    for malformed in (
        {"kind": "final_response", "answer": "answer", "request": {}},
        {"kind": "tool_request", "request": [], "answer": "fabricated"},
        {"kind": "tool_request", "request": [{}, {}]},
        {"kind": "unknown", "answer": "answer"},
    ):
        with pytest.raises(ValidationError):
            adapter.validate_python(malformed, strict=True)
