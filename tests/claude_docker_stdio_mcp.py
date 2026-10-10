"""Verify Claude's script-free Docker stdio command with the official MCP client."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters


DOCKER_BIN = os.getenv(
    "DOCKER_BIN", "/Applications/Docker.app/Contents/Resources/bin/docker"
)
MCP_CONTAINER_NAME = os.getenv(
    "MCP_CONTAINER_NAME", "dataglot-mcp-school-assistant-mcp-1"
)


def unpack(result: Any) -> dict[str, Any]:
    structured = result.structured_content
    if isinstance(structured, dict):
        if set(structured) == {"result"} and isinstance(structured["result"], dict):
            return structured["result"]
        return structured
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    raise AssertionError("Tool result did not contain a structured object")


async def main() -> None:
    docker_host = os.getenv(
        "DOCKER_HOST", f"unix://{Path.home() / '.docker/run/docker.sock'}"
    )
    parameters = StdioServerParameters(
        command=DOCKER_BIN,
        args=[
            "exec",
            "-i",
            MCP_CONTAINER_NAME,
            "python",
            "-m",
            "school_mcp.server",
            "--transport",
            "stdio",
        ],
        env={"DOCKER_HOST": docker_host},
    )

    async with Client(parameters) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        assert "get_data_context" in names
        assert "execute_readonly_query" in names

        result = unpack(
            await client.call_tool(
                "execute_readonly_query",
                {
                    "sql": (
                        "SELECT s.student_id, c.course_name "
                        "FROM pg.public.students AS s "
                        "JOIN mysql.school.grades AS g "
                        "ON s.student_id = g.student_id "
                        "JOIN mysql.school.courses AS c "
                        "ON g.course_id = c.course_id "
                        "ORDER BY s.student_id, c.course_id LIMIT 3"
                    ),
                    "max_rows": 3,
                },
            )
        )
        assert result["ok"]
        assert result["returned_row_count"] == 3
        assert set(result["referenced_tables"]) == {
            "pg.public.students",
            "mysql.school.grades",
            "mysql.school.courses",
        }

    print(
        json.dumps(
            {
                "initialized": True,
                "tools": sorted(names),
                "federated_query": {
                    "returned_row_count": result["returned_row_count"],
                    "referenced_tables": result["referenced_tables"],
                    "rows": result["rows"],
                },
            },
            indent=2,
        )
    )
    print("Claude Docker stdio MCP check passed")


if __name__ == "__main__":
    asyncio.run(main())
