"""Regression checks for dashboard MCP-result classification."""

from analysis_results import classify_analysis_result, unavailable_presentation


def main() -> None:
    missing = classify_analysis_result(None)
    assert missing.status == "missing"
    assert unavailable_presentation(missing) == (
        "info",
        "This analysis has not yet been generated through the Text-to-SQL workflow.",
    )

    failure = classify_analysis_result(
        {
            "ok": False,
            "error": {
                "code": "dataglot_unavailable",
                "message": "DataGlot is not available on its configured endpoint.",
            },
        }
    )
    failure_presentation = unavailable_presentation(failure)
    assert failure.status == "error"
    assert failure_presentation is not None
    assert failure_presentation[0] == "error"
    assert "dataglot_unavailable" in failure_presentation[1]
    assert "not yet been generated" not in failure_presentation[1]

    empty = classify_analysis_result({"ok": True, "columns": ["value"], "rows": []})
    assert empty.status == "empty"
    assert unavailable_presentation(empty)[0] == "info"

    ready = classify_analysis_result(
        {"ok": True, "columns": ["value"], "rows": [[1]]}
    )
    assert ready.status == "ready"
    assert unavailable_presentation(ready) is None

    print("Dashboard response-state regression checks passed")


if __name__ == "__main__":
    main()
