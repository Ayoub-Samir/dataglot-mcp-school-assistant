from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg


class DataGlotQueryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class QuerySettings:
    default_max_rows: int = 200
    hard_max_rows: int = 1000
    timeout_seconds: int = 20


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def _sanitized_message(error: Exception) -> str:
    message = " ".join(str(error).split())
    message = re.sub(r"(?i)(password\s*[=:]\s*)\S+", r"\1[redacted]", message)
    message = re.sub(r"(?i)(mysql://[^:]+:)[^@]+@", r"\1[redacted]@", message)
    return message[:500] or "DataGlot rejected the query."


class DataGlotClient:
    """The only database client; it connects exclusively to DataGlot's PG-wire port."""

    def __init__(self, settings: QuerySettings | None = None) -> None:
        self.host = os.getenv("DATAGLOT_HOST", "dataglot")
        self.port = int(os.getenv("DATAGLOT_PORT", "5432"))
        self.database = os.getenv("DATAGLOT_DATABASE", "pg")
        self.user = os.getenv("DATAGLOT_USER", "mcp_client")
        self.settings = settings or QuerySettings(
            default_max_rows=int(os.getenv("MCP_MAX_ROWS", "200")),
            hard_max_rows=int(os.getenv("MCP_HARD_MAX_ROWS", "1000")),
            timeout_seconds=int(os.getenv("MCP_QUERY_TIMEOUT_SECONDS", "20")),
        )

    def _connect(self) -> psycopg.Connection[Any]:
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                return psycopg.connect(
                    host=self.host,
                    port=self.port,
                    dbname=self.database,
                    user=self.user,
                    connect_timeout=5,
                    autocommit=True,
                    prepare_threshold=None,
                )
            except psycopg.OperationalError as error:
                last_error = error
                if attempt < 4:
                    time.sleep(1)
        raise DataGlotQueryError(
            "dataglot_unavailable", "DataGlot is not available on its configured endpoint."
        ) from last_error

    def execute(self, sql: str, max_rows: int | None = None) -> dict[str, Any]:
        requested_limit = max_rows or self.settings.default_max_rows
        if requested_limit < 1 or requested_limit > self.settings.hard_max_rows:
            raise DataGlotQueryError(
                "invalid_row_limit",
                f"max_rows must be between 1 and {self.settings.hard_max_rows}.",
            )

        timed_out = threading.Event()
        with self._connect() as connection:
            def cancel_query() -> None:
                timed_out.set()
                try:
                    connection.cancel()
                except Exception:
                    pass

            timer = threading.Timer(self.settings.timeout_seconds, cancel_query)
            timer.daemon = True
            timer.start()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql, prepare=False)
                    if cursor.description is None:
                        raise DataGlotQueryError(
                            "non_query_result", "The statement did not return a read-only result set."
                        )
                    columns = [column.name for column in cursor.description]
                    fetched = cursor.fetchmany(requested_limit + 1)
            except DataGlotQueryError:
                raise
            except Exception as error:
                if timed_out.is_set():
                    raise DataGlotQueryError(
                        "query_timeout",
                        f"The query exceeded the {self.settings.timeout_seconds}-second timeout.",
                    ) from error
                raise DataGlotQueryError("query_failed", _sanitized_message(error)) from error
            finally:
                timer.cancel()

        truncated = len(fetched) > requested_limit
        visible_rows = fetched[:requested_limit]
        rows = [[_json_value(value) for value in row] for row in visible_rows]
        return {
            "ok": True,
            "columns": columns,
            "rows": rows,
            "returned_row_count": len(rows),
            "total_row_count": None if truncated else len(rows),
            "truncated": truncated,
            "row_limit": requested_limit,
        }

    def probe_table(self, qualified_name: str) -> dict[str, Any]:
        result = self.execute(
            f"SELECT * FROM {qualified_name} WHERE 1 = 0",
            max_rows=1,
        )
        return {
            "qualified_name": qualified_name,
            "visible_through_dataglot": True,
            "discovered_columns": result["columns"],
        }

