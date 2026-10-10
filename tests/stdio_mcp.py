"""Verify the stdio transport with the official MCP client."""

from __future__ import annotations

import asyncio
import os

from mcp import Client, StdioServerParameters


async def main() -> None:
    parameters = StdioServerParameters(
        command="python",
        args=["-m", "school_mcp.server", "--transport", "stdio"],
        env=dict(os.environ),
    )
    async with Client(parameters) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        assert "get_data_context" in names
        assert "execute_readonly_query" in names
    print("MCP stdio transport check passed")


if __name__ == "__main__":
    asyncio.run(main())

