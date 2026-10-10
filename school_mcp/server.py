from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Literal

import anyio
from mcp.server import MCPServer

from .dashboard_registry import DashboardRegistry, DashboardRegistryError
from .dataglot_client import DataGlotClient, DataGlotQueryError
from .semantic_context import SemanticModel, SemanticModelError
from .sql_safety import ReadOnlySQLValidator, SQLSafetyError


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
LOGGER = logging.getLogger("school_mcp")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_MODEL_PATH = Path(
    os.getenv("MCP_SEMANTIC_MODEL", PROJECT_ROOT / "config" / "semantic_model.yaml")
)
REGISTRY_PATH = Path(
    os.getenv("MCP_REGISTRY_PATH", PROJECT_ROOT / "data" / "dashboard_analyses.json")
)
REGISTRY_LOCK_PATH = Path(
    os.getenv("MCP_REGISTRY_LOCK_PATH", str(REGISTRY_PATH) + ".lock")
)

semantic_model = SemanticModel(SEMANTIC_MODEL_PATH)
validator = ReadOnlySQLValidator(semantic_model.allowed_tables)
dataglot = DataGlotClient()
registry = DashboardRegistry(REGISTRY_PATH, semantic_model, REGISTRY_LOCK_PATH)

mcp = MCPServer(
    "DataGlot School Assistant",
    instructions=(
        "Use get_data_context before generating SQL. All queries must be read-only, "
        "must fully qualify the four permitted tables, and must use the documented "
        "final-score formula. execute_readonly_query is the generic analytical query tool. "
        "Dashboard definitions must be registered only after their generated SQL works."
    ),
)


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


@mcp.tool()
async def get_data_context() -> dict[str, Any]:
    """Return schema, relationships, business semantics, SQL rules, and live DataGlot visibility."""
    live_tables: list[dict[str, Any]] = []
    for table in semantic_model.table_definitions():
        try:
            probe = await anyio.to_thread.run_sync(
                dataglot.probe_table, table["qualified_name"]
            )
        except DataGlotQueryError as error:
            probe = {
                "qualified_name": table["qualified_name"],
                "visible_through_dataglot": False,
                "metadata_error": error.message,
            }
        live_tables.append(probe)
    return {
        "ok": True,
        "semantic_model": semantic_model.public_context(),
        "live_dataglot_metadata": live_tables,
        "metadata_note": (
            "Business types and meanings come from semantic_model.yaml. Table visibility "
            "and returned column names are probed only through DataGlot with zero-row SELECTs."
        ),
    }


@mcp.tool()
async def list_tables() -> dict[str, Any]:
    """List every allowlisted table, its source, semantic columns, and live DataGlot visibility."""
    tables: list[dict[str, Any]] = []
    for definition in semantic_model.table_definitions():
        item = {
            "catalog": definition["catalog"],
            "schema": definition["schema"],
            "table": definition["table"],
            "qualified_name": definition["qualified_name"],
            "source": definition["source"],
            "description": definition.get("description"),
            "columns": list(definition.get("columns", {})),
        }
        try:
            item.update(
                await anyio.to_thread.run_sync(
                    dataglot.probe_table, definition["qualified_name"]
                )
            )
        except DataGlotQueryError as error:
            item.update(
                {
                    "visible_through_dataglot": False,
                    "metadata_error": error.message,
                }
            )
        tables.append(item)
    return {"ok": True, "tables": tables, "table_count": len(tables)}


@mcp.tool()
async def describe_table(catalog: str, schema: str, table: str) -> dict[str, Any]:
    """Describe one permitted catalog/schema/table and confirm its columns through DataGlot."""
    try:
        definition = semantic_model.describe_table(catalog, schema, table)
        probe = await anyio.to_thread.run_sync(
            dataglot.probe_table, definition["qualified_name"]
        )
        return {"ok": True, "table": definition, "live_dataglot_metadata": probe}
    except SemanticModelError as error:
        return _error("unknown_table", str(error))
    except DataGlotQueryError as error:
        return _error(error.code, error.message)


@mcp.tool()
async def execute_readonly_query(sql: str, max_rows: int = 200) -> dict[str, Any]:
    """Validate and execute one generic read-only federated SQL query through DataGlot only."""
    try:
        validated = validator.validate(sql)
        result = await anyio.to_thread.run_sync(
            lambda: dataglot.execute(validated.normalized, max_rows=max_rows)
        )
        result["referenced_tables"] = list(validated.referenced_tables)
        return result
    except SQLSafetyError as error:
        return _error("unsafe_sql", str(error))
    except DataGlotQueryError as error:
        return _error(error.code, error.message)


@mcp.tool()
async def register_dashboard_analysis(
    analysis_id: str,
    title: str,
    requirement: str,
    sql: str,
    visualization: Literal["kpi", "horizontal_bar", "vertical_bar", "table"],
    expected_columns: list[str] | None = None,
    display_order: int | None = None,
) -> dict[str, Any]:
    """Validate, run, contract-check, and persist a generated dashboard analysis."""
    try:
        validated = validator.validate(sql)
        verification = await anyio.to_thread.run_sync(
            lambda: dataglot.execute(validated.normalized, max_rows=1000)
        )
        if expected_columns is not None:
            missing_from_expectation = [
                column
                for column in expected_columns
                if column not in verification["columns"]
            ]
            if missing_from_expectation:
                raise DashboardRegistryError(
                    "The verified result is missing declared expected columns: "
                    + ", ".join(missing_from_expectation)
                )
        definition = await anyio.to_thread.run_sync(
            lambda: registry.register(
                analysis_id=analysis_id,
                title=title,
                requirement=requirement,
                sql=validated.normalized,
                visualization=visualization,
                result_columns=verification["columns"],
                referenced_tables=validated.referenced_tables,
                display_order=display_order,
            )
        )
        return {
            "ok": True,
            "analysis": definition,
            "verification": {
                "columns": verification["columns"],
                "returned_row_count": verification["returned_row_count"],
                "truncated": verification["truncated"],
            },
        }
    except SQLSafetyError as error:
        return _error("unsafe_sql", str(error))
    except DataGlotQueryError as error:
        return _error(error.code, error.message)
    except (DashboardRegistryError, SemanticModelError) as error:
        return _error("invalid_dashboard_analysis", str(error))


@mcp.tool()
async def list_dashboard_analyses(include_sql: bool = False) -> dict[str, Any]:
    """List registered dashboard analyses and the required contracts still awaiting registration."""
    try:
        analyses = await anyio.to_thread.run_sync(registry.list)
        if not include_sql:
            analyses = [
                {key: value for key, value in analysis.items() if key != "sql"}
                for analysis in analyses
            ]
        registered = {analysis["analysis_id"] for analysis in analyses}
        contracts = semantic_model.dashboard_contracts()
        missing = [analysis_id for analysis_id in contracts if analysis_id not in registered]
        return {
            "ok": True,
            "analyses": analyses,
            "registered_count": len(analyses),
            "missing_analysis_ids": missing,
            "contracts": contracts,
        }
    except DashboardRegistryError as error:
        return _error("registry_error", str(error))


@mcp.tool()
async def execute_dashboard_analysis(
    analysis_id: str,
    max_rows: int = 1000,
) -> dict[str, Any]:
    """Revalidate and execute one saved dashboard analysis through DataGlot."""
    try:
        analysis = await anyio.to_thread.run_sync(registry.get, analysis_id)
        validated = validator.validate(analysis["sql"])
        result = await anyio.to_thread.run_sync(
            lambda: dataglot.execute(validated.normalized, max_rows=max_rows)
        )
        missing = [
            column
            for column in analysis["required_columns"]
            if column not in result["columns"]
        ]
        if missing:
            raise DashboardRegistryError(
                "The current query result no longer satisfies its column contract: "
                + ", ".join(missing)
            )
        result["analysis"] = {
            key: value for key, value in analysis.items() if key != "sql"
        }
        return result
    except DashboardRegistryError as error:
        return _error("analysis_not_available", str(error))
    except SQLSafetyError as error:
        return _error("unsafe_registered_sql", str(error))
    except DataGlotQueryError as error:
        return _error(error.code, error.message)


@mcp.tool()
async def delete_dashboard_analysis(analysis_id: str) -> dict[str, Any]:
    """Delete one saved dashboard analysis definition; source data is never modified."""
    try:
        deleted = await anyio.to_thread.run_sync(registry.delete, analysis_id)
        return {"ok": True, "analysis_id": analysis_id, "deleted": deleted}
    except DashboardRegistryError as error:
        return _error("registry_error", str(error))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DataGlot School Assistant MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    LOGGER.info("Starting MCP server with %s transport", args.transport)
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            stateless_http=True,
            json_response=True,
        )


if __name__ == "__main__":
    main()
