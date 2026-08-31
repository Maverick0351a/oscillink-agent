"""Isolated MCP client worker for the Project Memory public demo."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _server_parameters(data_root: Path) -> StdioServerParameters:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = ""
    return StdioServerParameters(
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


async def _run(data_root: Path, calls: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    async with (
        stdio_client(_server_parameters(data_root)) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        for call in calls:
            tool_name = str(call["name"])
            arguments = dict(call["arguments"])
            result = await session.call_tool(tool_name, arguments)
            if result.is_error or result.structured_content is None:
                raise RuntimeError(f"demo tool call failed: {tool_name}")
            results.append(dict(result.structured_content))
    return {"client_process_id": os.getpid(), "results": results}


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read())
    data_root = Path(payload["data_root"])
    calls = list(payload["calls"])
    result = anyio.run(_run, data_root, calls)
    sys.stdout.write(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
