"""MCP (Model Context Protocol) server exposing altr's document skills.

Run with `altr mcp`; requires the optional dependency:

    pip install "altr-oss[mcp]"

Any MCP client (Claude Desktop, Claude Code, Cursor, ...) then gets the same
seven tools the agent loop uses: create/read/edit for docx, xlsx, and pptx.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .tools import dispatch, get_tool_specs

try:
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError as e:  # pragma: no cover - exercised via CLI message
    raise ImportError(
        'the MCP server needs the optional dependency: pip install "altr-oss[mcp]"'
    ) from e


def build_server(out_dir: str | Path, templates: dict[str, Path] | None = None) -> Server:
    server = Server("altr")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(name=name, description=description, inputSchema=schema)
            for name, description, schema in get_tool_specs()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        outcome = dispatch(name, arguments, out_dir, templates)
        return [types.TextContent(type="text", text=json.dumps(outcome))]

    return server


async def _serve(out_dir: str | Path, templates: dict[str, Path] | None) -> None:
    server = build_server(out_dir, templates)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def serve(out_dir: str | Path, templates: dict[str, Path] | None = None) -> None:
    """Blocking entry point: serve MCP over stdio until the client hangs up."""
    asyncio.run(_serve(out_dir, templates))
