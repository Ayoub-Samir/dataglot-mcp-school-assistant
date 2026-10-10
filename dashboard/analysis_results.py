from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


EMPTY_MESSAGE = "This analysis has not yet been generated through the Text-to-SQL workflow."


@dataclass(frozen=True)
class AnalysisResultState:
    status: Literal["missing", "error", "empty", "ready"]
    result: Mapping[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


def classify_analysis_result(result: Any) -> AnalysisResultState:
    """Classify one MCP result without treating execution failures as missing analyses."""
    if result is None:
        return AnalysisResultState(status="missing")
    if not isinstance(result, Mapping):
        return AnalysisResultState(
            status="error",
            error_code="invalid_mcp_response",
            error_message="The MCP service returned an invalid analysis response.",
        )
    if result.get("ok") is not True:
        error = result.get("error")
        if not isinstance(error, Mapping):
            error = {}
        return AnalysisResultState(
            status="error",
            result=result,
            error_code=str(error.get("code") or "analysis_execution_failed"),
            error_message=str(
                error.get("message")
                or "The registered analysis could not be executed."
            ),
        )

    columns = result.get("columns")
    rows = result.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return AnalysisResultState(
            status="error",
            result=result,
            error_code="invalid_mcp_response",
            error_message="The MCP service returned an invalid analysis result shape.",
        )
    if not rows:
        return AnalysisResultState(status="empty", result=result)
    return AnalysisResultState(status="ready", result=result)


def unavailable_presentation(
    state: AnalysisResultState,
) -> tuple[Literal["info", "error"], str] | None:
    """Return the correct UI severity and message for a non-renderable result."""
    if state.status == "ready":
        return None
    if state.status == "missing":
        return "info", EMPTY_MESSAGE
    if state.status == "empty":
        return "info", "This registered analysis executed successfully but returned no rows."
    return (
        "error",
        "Registered analysis execution failed "
        f"({state.error_code}): {state.error_message}",
    )
