from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class SQLSafetyError(ValueError):
    """Raised when SQL does not satisfy the read-only policy."""


@dataclass(frozen=True)
class ValidatedSQL:
    original: str
    normalized: str
    referenced_tables: tuple[str, ...]


FORBIDDEN_NODE_KEYS = frozenset(
    {
        "alter",
        "analyze",
        "attach",
        "cache",
        "call",
        "command",
        "commit",
        "copy",
        "create",
        "delete",
        "detach",
        "drop",
        "grant",
        "insert",
        "into",
        "load_data",
        "lock",
        "merge",
        "pragma",
        "refresh",
        "replace",
        "revoke",
        "rollback",
        "set",
        "transaction",
        "truncate",
        "uncache",
        "update",
        "use",
    }
)

DANGEROUS_FUNCTIONS = frozenset(
    {
        "benchmark",
        "current_setting",
        "dblink",
        "dblink_connect",
        "dblink_exec",
        "load_file",
        "lo_export",
        "lo_import",
        "pg_cancel_backend",
        "pg_ls_dir",
        "pg_read_binary_file",
        "pg_read_file",
        "pg_sleep",
        "pg_stat_file",
        "pg_terminate_backend",
        "query_to_xml",
        "set_config",
        "sleep",
        "sys_eval",
        "sys_exec",
    }
)


class ReadOnlySQLValidator:
    def __init__(self, allowed_tables: frozenset[str]) -> None:
        self.allowed_tables = frozenset(name.lower() for name in allowed_tables)

    def validate(self, sql: str) -> ValidatedSQL:
        if not isinstance(sql, str) or not sql.strip():
            raise SQLSafetyError("SQL must be a non-empty string.")
        if len(sql) > 50_000:
            raise SQLSafetyError("SQL exceeds the 50,000-character safety limit.")
        if any(marker in sql for marker in ("--", "/*", "*/")):
            raise SQLSafetyError("SQL comments are not accepted by the query tool.")

        try:
            statements = [
                statement
                for statement in sqlglot.parse(sql, read="postgres")
                if statement is not None
            ]
        except ParseError as error:
            raise SQLSafetyError("SQL could not be parsed as PostgreSQL-compatible SQL.") from error

        if len(statements) != 1:
            raise SQLSafetyError("Exactly one SQL statement is required.")

        statement = statements[0]
        if statement.key not in {"select", "union", "intersect", "except"}:
            raise SQLSafetyError("Only SELECT or read-only WITH queries are allowed.")

        for node in statement.walk():
            if node.key in FORBIDDEN_NODE_KEYS:
                raise SQLSafetyError(f"Forbidden SQL construct detected: {node.key.upper()}.")

        cte_names = {
            cte.alias_or_name.lower()
            for cte in statement.find_all(exp.CTE)
            if cte.alias_or_name
        }
        referenced_tables: set[str] = set()
        for table in statement.find_all(exp.Table):
            catalog = table.catalog
            schema = table.db
            name = table.name
            if not catalog and not schema and name.lower() in cte_names:
                continue
            if not catalog or not schema:
                raise SQLSafetyError(
                    f"Table '{name}' must use a full catalog.schema.table qualification."
                )
            qualified_name = f"{catalog}.{schema}.{name}".lower()
            if qualified_name not in self.allowed_tables:
                raise SQLSafetyError(
                    f"Table '{qualified_name}' is outside the permitted dataset."
                )
            referenced_tables.add(qualified_name)

        for function in statement.find_all(exp.Func):
            function_name = (
                function.name
                if isinstance(function, exp.Anonymous)
                else function.sql_name()
            ).lower()
            if function_name in DANGEROUS_FUNCTIONS or function_name.startswith("dblink"):
                raise SQLSafetyError(
                    f"Function '{function_name}' is not allowed by the read-only policy."
                )

        normalized = statement.sql(dialect="postgres", pretty=False)
        return ValidatedSQL(
            original=sql,
            normalized=normalized,
            referenced_tables=tuple(sorted(referenced_tables)),
        )
