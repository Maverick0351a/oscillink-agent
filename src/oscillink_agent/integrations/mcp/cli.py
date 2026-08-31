"""Command-line entry point for the local Project Memory MCP stdio server."""

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

from mcp.server.stdio import stdio_server

from oscillink_agent.integrations.mcp.server import create_project_memory_server


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oscillink-project-memory",
        description="Serve governed Oscillink Project Memory over local MCP stdio.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="Oscillink workspace data directory containing memory.sqlite3.",
    )
    return parser


async def _serve(data_root: Path) -> None:
    server = create_project_memory_server(data_root)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bounded local stdio server until its client disconnects."""

    args = _parser().parse_args(argv)
    asyncio.run(_serve(args.data_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
