"""Streamlit smoke checks against the live MCP service."""

from __future__ import annotations

import argparse

from streamlit.testing.v1 import AppTest


def main(expect_overview: bool) -> None:
    app = AppTest.from_file("/app/app.py").run(timeout=30)
    assert not app.exception, app.exception
    assert not app.error, app.error
    assert app.title[0].value == "School Management Dashboard"
    if expect_overview:
        values = [metric.value for metric in app.metric]
        assert values == ["1,000", "40", "70.49", "75.08%"], values
        assert not any(
            "not yet been generated" in message.value for message in app.info
        ), app.info
    else:
        assert len(app.metric) == 0
        assert any("not yet been generated" in message.value for message in app.info)
    print("Streamlit smoke check passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-overview", action="store_true")
    args = parser.parse_args()
    main(args.expect_overview)
