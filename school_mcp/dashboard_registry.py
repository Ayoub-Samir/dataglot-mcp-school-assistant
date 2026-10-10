from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

from .semantic_context import SemanticModel


ANALYSIS_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class DashboardRegistryError(ValueError):
    """Raised when a dashboard definition violates the registry contract."""


class DashboardRegistry:
    def __init__(
        self,
        path: Path,
        semantic_model: SemanticModel,
        lock_path: Path | None = None,
    ) -> None:
        self.path = path
        self.semantic_model = semantic_model
        resolved_lock_path = lock_path or Path(str(path) + ".lock")
        resolved_lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(resolved_lock_path, timeout=10)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_unlocked({"version": 1, "analyses": []})

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DashboardRegistryError("The dashboard registry cannot be read.") from error
        if payload.get("version") != 1 or not isinstance(payload.get("analyses"), list):
            raise DashboardRegistryError("The dashboard registry has an unsupported format.")
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            payload = self._read_unlocked()
        return sorted(
            payload["analyses"],
            key=lambda item: (item.get("display_order", 999), item["analysis_id"]),
        )

    def get(self, analysis_id: str) -> dict[str, Any]:
        for analysis in self.list():
            if analysis["analysis_id"] == analysis_id:
                return analysis
        raise DashboardRegistryError(
            f"Dashboard analysis '{analysis_id}' has not been registered."
        )

    def register(
        self,
        *,
        analysis_id: str,
        title: str,
        requirement: str,
        sql: str,
        visualization: str,
        result_columns: list[str],
        referenced_tables: tuple[str, ...],
        display_order: int | None,
    ) -> dict[str, Any]:
        if not ANALYSIS_ID_PATTERN.fullmatch(analysis_id):
            raise DashboardRegistryError(
                "analysis_id must be lower snake_case and 2-64 characters long."
            )
        contract = self.semantic_model.dashboard_contract(analysis_id)
        required_columns = contract["required_columns"]
        missing = [column for column in required_columns if column not in result_columns]
        if missing:
            raise DashboardRegistryError(
                "The verified query result is missing required columns: " + ", ".join(missing)
            )
        if visualization != contract["visualization"]:
            raise DashboardRegistryError(
                f"Analysis '{analysis_id}' requires visualization '{contract['visualization']}'."
            )
        if not title.strip() or len(title) > 120:
            raise DashboardRegistryError("title must contain 1-120 characters.")
        if not requirement.strip() or len(requirement) > 1000:
            raise DashboardRegistryError("requirement must contain 1-1000 characters.")

        definition = {
            "analysis_id": analysis_id,
            "title": title.strip(),
            "requirement": requirement.strip(),
            "sql": sql,
            "visualization": visualization,
            "required_columns": required_columns,
            "result_columns": result_columns,
            "referenced_tables": list(referenced_tables),
            "display_order": display_order
            if display_order is not None
            else contract["display_order"],
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "registration_method": "mcp_tool",
        }

        with self.lock:
            payload = self._read_unlocked()
            payload["analyses"] = [
                item
                for item in payload["analyses"]
                if item["analysis_id"] != analysis_id
            ]
            payload["analyses"].append(definition)
            self._write_unlocked(payload)
        return definition

    def delete(self, analysis_id: str) -> bool:
        with self.lock:
            payload = self._read_unlocked()
            retained = [
                item
                for item in payload["analyses"]
                if item["analysis_id"] != analysis_id
            ]
            deleted = len(retained) != len(payload["analyses"])
            if deleted:
                payload["analyses"] = retained
                self._write_unlocked(payload)
        return deleted
