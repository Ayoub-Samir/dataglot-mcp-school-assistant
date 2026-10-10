from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class SemanticModelError(ValueError):
    """Raised when the semantic model is incomplete or inconsistent."""


class SemanticModel:
    def __init__(self, path: Path) -> None:
        self.path = path
        with path.open(encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        if not isinstance(loaded, dict):
            raise SemanticModelError("The semantic model must be a YAML object.")
        self._model: dict[str, Any] = loaded
        self._tables = self._index_tables()
        if not self._tables:
            raise SemanticModelError("The semantic model does not define any tables.")

    def _index_tables(self) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for catalog_name, catalog in self._model.get("catalogs", {}).items():
            schema_name = catalog.get("schema")
            for table_name, table in catalog.get("tables", {}).items():
                qualified_name = table.get(
                    "qualified_name", f"{catalog_name}.{schema_name}.{table_name}"
                )
                entry = deepcopy(table)
                entry.update(
                    {
                        "catalog": catalog_name,
                        "schema": schema_name,
                        "table": table_name,
                        "qualified_name": qualified_name,
                        "source": catalog.get("source"),
                    }
                )
                indexed[qualified_name.lower()] = entry
        return indexed

    @property
    def allowed_tables(self) -> frozenset[str]:
        return frozenset(self._tables)

    def table_definitions(self) -> list[dict[str, Any]]:
        return [deepcopy(self._tables[name]) for name in sorted(self._tables)]

    def describe_table(self, catalog: str, schema: str, table: str) -> dict[str, Any]:
        qualified_name = f"{catalog}.{schema}.{table}".lower()
        try:
            definition = deepcopy(self._tables[qualified_name])
        except KeyError as error:
            raise SemanticModelError(
                f"Table '{qualified_name}' is not in the permitted semantic model."
            ) from error
        definition["relationships"] = [
            deepcopy(relationship)
            for relationship in self._model.get("relationships", [])
            if relationship.get("from", "").lower().startswith(qualified_name + ".")
            or relationship.get("to", "").lower().startswith(qualified_name + ".")
        ]
        return definition

    def dashboard_contract(self, analysis_id: str) -> dict[str, Any]:
        contracts = self._model.get("dashboard_contracts", {})
        try:
            return deepcopy(contracts[analysis_id])
        except KeyError as error:
            allowed = ", ".join(sorted(contracts))
            raise SemanticModelError(
                f"Unknown dashboard analysis ID '{analysis_id}'. Allowed IDs: {allowed}."
            ) from error

    def dashboard_contracts(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._model.get("dashboard_contracts", {}))

    def public_context(self) -> dict[str, Any]:
        return deepcopy(self._model)

