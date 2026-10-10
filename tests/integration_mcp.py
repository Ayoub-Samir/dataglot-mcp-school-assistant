"""Non-destructive live MCP integration checks against the completed registry."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp import Client


MCP_URL = os.getenv("MCP_TEST_URL", "http://127.0.0.1:8000/mcp")

ANALYSIS_IDS = (
    "overview",
    "department_performance",
    "grade_distribution",
    "courses_needing_attention",
    "course_performance",
    "at_risk_students",
    "top_students",
)

EXPECTED_ROW_COUNTS = {
    "overview": 1,
    "department_performance": 5,
    "grade_distribution": 5,
    "courses_needing_attention": 12,
    "course_performance": 40,
    "at_risk_students": 50,
    "top_students": 50,
}


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


async def call(client: Client, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return unpack(await client.call_tool(name, arguments))


async def run() -> None:
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        expected_tools = {
            "get_data_context",
            "list_tables",
            "describe_table",
            "execute_readonly_query",
            "register_dashboard_analysis",
            "list_dashboard_analyses",
            "execute_dashboard_analysis",
            "delete_dashboard_analysis",
        }
        assert expected_tools <= names, names

        listing = await call(
            client, "list_dashboard_analyses", {"include_sql": True}
        )
        assert listing["ok"]
        assert listing["registered_count"] == 7
        assert listing["missing_analysis_ids"] == []
        assert tuple(item["analysis_id"] for item in listing["analyses"]) == ANALYSIS_IDS
        assert all(
            item["registration_method"] == "mcp_tool"
            for item in listing["analyses"]
        )

        context = await call(client, "get_data_context", {})
        assert context["ok"]
        assert all(
            table["visible_through_dataglot"]
            for table in context["live_dataglot_metadata"]
        )

        tables = await call(client, "list_tables", {})
        assert tables["ok"] and tables["table_count"] == 4

        described = await call(
            client,
            "describe_table",
            {"catalog": "pg", "schema": "public", "table": "students"},
        )
        assert described["ok"]
        assert "student_id" in described["live_dataglot_metadata"]["discovered_columns"]

        counts = await call(
            client,
            "execute_readonly_query",
            {
                "sql": (
                    "SELECT "
                    "(SELECT COUNT(*) FROM pg.public.departments) AS departments, "
                    "(SELECT COUNT(*) FROM pg.public.students) AS students, "
                    "(SELECT COUNT(*) FROM mysql.school.courses) AS courses, "
                    "(SELECT COUNT(*) FROM mysql.school.grades) AS grades"
                ),
                "max_rows": 5,
            },
        )
        assert counts["ok"] and counts["rows"][0] == [5, 1000, 40, 6000]

        federated = await call(
            client,
            "execute_readonly_query",
            {
                "sql": (
                    "SELECT s.student_id, c.course_name "
                    "FROM pg.public.students AS s "
                    "JOIN mysql.school.grades AS g ON s.student_id = g.student_id "
                    "JOIN mysql.school.courses AS c ON g.course_id = c.course_id "
                    "ORDER BY s.student_id, c.course_id LIMIT 10"
                ),
                "max_rows": 20,
            },
        )
        assert federated["ok"] and federated["returned_row_count"] == 10
        assert set(federated["referenced_tables"]) == {
            "pg.public.students",
            "mysql.school.grades",
            "mysql.school.courses",
        }

        cte = await call(
            client,
            "execute_readonly_query",
            {
                "sql": (
                    "WITH scored AS (SELECT 0.4 * midterm_score + 0.6 * final_exam_score AS score "
                    "FROM mysql.school.grades) SELECT ROUND(AVG(score), 2) AS average_score FROM scored"
                )
            },
        )
        assert cte["ok"] and abs(float(cte["rows"][0][0]) - 70.49) < 0.01

        limited = await call(
            client,
            "execute_readonly_query",
            {"sql": "SELECT student_id FROM pg.public.students ORDER BY student_id", "max_rows": 3},
        )
        assert limited["ok"]
        assert limited["returned_row_count"] == 3
        assert limited["truncated"] is True
        assert limited["total_row_count"] is None

        destructive_statements = [
            "INSERT INTO pg.public.students (student_id) VALUES (2001)",
            "UPDATE pg.public.students SET status = 'active'",
            "DELETE FROM mysql.school.grades",
            "DROP TABLE pg.public.students",
            "CREATE TABLE pg.public.nope (id int)",
            "SELECT 1; SELECT 2",
            "WITH changed AS (DELETE FROM mysql.school.grades RETURNING grade_id) SELECT * FROM changed",
            "SELECT pg_sleep(10)",
        ]
        for sql in destructive_statements:
            rejected = await call(client, "execute_readonly_query", {"sql": sql})
            assert not rejected["ok"] and rejected["error"]["code"] == "unsafe_sql"

        invalid = await call(
            client, "execute_readonly_query", {"sql": "SELECT FROM pg.public.students"}
        )
        assert not invalid["ok"]
        assert "password" not in json.dumps(invalid).lower()

        unsafe_registration = await call(
            client,
            "register_dashboard_analysis",
            {
                "analysis_id": "overview",
                "title": "Unsafe fixture",
                "requirement": "This should be rejected.",
                "sql": "DELETE FROM mysql.school.grades",
                "visualization": "kpi",
            },
        )
        assert not unsafe_registration["ok"]

        executions: dict[str, dict[str, Any]] = {}
        for analysis_id in ANALYSIS_IDS:
            executed = await call(
                client,
                "execute_dashboard_analysis",
                {"analysis_id": analysis_id, "max_rows": 1000},
            )
            assert executed["ok"], (analysis_id, executed)
            assert executed["returned_row_count"] == EXPECTED_ROW_COUNTS[analysis_id]
            assert not executed["truncated"]
            executions[analysis_id] = executed

        overview = executions["overview"]
        row = dict(zip(overview["columns"], overview["rows"][0], strict=True))
        assert row["total_students"] == 1000
        assert row["total_courses"] == 40
        assert row["total_grade_records"] == 6000
        assert abs(float(row["average_final_score"]) - 70.49) < 0.01
        assert abs(float(row["pass_percentage"]) - 75.08) < 0.01

        distribution = executions["grade_distribution"]
        assert [row[0] for row in distribution["rows"]] == [
            "Below 60",
            "60-69",
            "70-79",
            "80-89",
            "90-100",
        ]
        assert [row[3] for row in distribution["rows"]] == [1, 2, 3, 4, 5]

        attention = executions["courses_needing_attention"]
        course_performance = executions["course_performance"]
        assert attention["rows"] == course_performance["rows"][:12]


if __name__ == "__main__":
    asyncio.run(run())
    print("MCP integration checks passed")
