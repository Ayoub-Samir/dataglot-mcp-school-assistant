from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st
from mcp import Client

from analysis_results import (
    AnalysisResultState,
    classify_analysis_result,
    unavailable_presentation,
)


st.set_page_config(
    page_title="DataGlot MCP School Assistant",
    page_icon="🎓",
    layout="wide",
)

MCP_URL = os.getenv("MCP_URL", "http://mcp:8000/mcp")
ANALYSIS_IDS = (
    "overview",
    "department_performance",
    "grade_distribution",
    "courses_needing_attention",
    "course_performance",
    "at_risk_students",
    "top_students",
)


def _structured_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        if set(structured) == {"result"} and isinstance(structured["result"], dict):
            return structured["result"]
        return structured
    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if text:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    raise RuntimeError("The MCP tool returned no structured object.")


async def _load_from_mcp() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    async with Client(MCP_URL) as client:
        listing = _structured_result(await client.call_tool("list_dashboard_analyses", {}))
        registered = {
            analysis["analysis_id"]: analysis
            for analysis in listing.get("analyses", [])
        }
        results: dict[str, dict[str, Any]] = {}
        for analysis_id in ANALYSIS_IDS:
            if analysis_id in registered:
                results[analysis_id] = _structured_result(
                    await client.call_tool(
                        "execute_dashboard_analysis",
                        {"analysis_id": analysis_id, "max_rows": 1000},
                    )
                )
        return listing, results


@st.cache_data(ttl=30, show_spinner=False)
def load_dashboard_data() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    return asyncio.run(_load_from_mcp())


def frame_for(
    results: dict[str, dict[str, Any]], analysis_id: str
) -> tuple[pd.DataFrame | None, AnalysisResultState]:
    state = classify_analysis_result(results.get(analysis_id))
    if state.status != "ready" or state.result is None:
        return None, state
    return (
        pd.DataFrame(state.result["rows"], columns=state.result["columns"]),
        state,
    )


def render_unavailable(state: AnalysisResultState) -> bool:
    presentation = unavailable_presentation(state)
    if presentation is None:
        return False
    severity, message = presentation
    if severity == "error":
        st.error(message)
    else:
        st.info(message)
    return True


def display_table(frame: pd.DataFrame, labels: dict[str, str], height: int | str = "auto") -> None:
    st.dataframe(
        frame.rename(columns=labels),
        hide_index=True,
        width="stretch",
        height=height,
    )


st.title("School Management Dashboard")
st.caption(
    "Claude-generated analytical SQL is registered through MCP and executed through "
    "DataGlot across PostgreSQL and MySQL. This application connects only to MCP."
)

with st.sidebar:
    st.header("Text-to-SQL status")
    st.caption(
        "Dashboard analyses appear after Claude Desktop generates and registers them "
        "through the DataGlot MCP tools."
    )
    if st.button("Refresh analyses", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Final score = 40% midterm + 60% final exam. Pass threshold: 60.")

try:
    with st.spinner("Loading registered analyses through MCP..."):
        listing, results = load_dashboard_data()
except Exception as error:
    st.error("The dashboard could not communicate with the MCP service.")
    st.code(str(error))
    st.stop()

registered_count = int(listing.get("registered_count", 0))
st.caption(f"Registered dashboard analyses: {registered_count} of {len(ANALYSIS_IDS)}")

overview, overview_state = frame_for(results, "overview")
if overview_state.status != "ready":
    st.subheader("Overview KPIs")
    render_unavailable(overview_state)
else:
    assert overview is not None
    row = overview.iloc[0]
    kpi_columns = st.columns(4)
    kpi_columns[0].metric("Total Students", f"{int(row['total_students']):,}")
    kpi_columns[1].metric("Total Courses", f"{int(row['total_courses']):,}")
    kpi_columns[2].metric("Average Final Score", f"{float(row['average_final_score']):.2f}")
    kpi_columns[3].metric("Pass Rate", f"{float(row['pass_percentage']):.2f}%")
    st.caption(f"Based on {int(row['total_grade_records']):,} grade records.")

st.divider()
left, right = st.columns(2)
chart_height = 300
table_height = 245

with left:
    st.subheader("Department Performance")
    department, department_state = frame_for(results, "department_performance")
    if render_unavailable(department_state):
        pass
    else:
        assert department is not None
        order = (
            department.sort_values("average_final_score", ascending=False)["department_name"]
            .astype(str)
            .tolist()
        )
        chart = (
            alt.Chart(department)
            .mark_bar()
            .encode(
                x=alt.X(
                    "average_final_score:Q",
                    title="Average final score",
                    scale=alt.Scale(domain=[0, 100]),
                ),
                y=alt.Y(
                    "department_name:N",
                    title=None,
                    sort=order,
                    axis=alt.Axis(labelLimit=0, labelPadding=8),
                ),
                tooltip=[
                    alt.Tooltip("department_name:N", title="Department"),
                    alt.Tooltip("average_final_score:Q", title="Average score", format=".2f"),
                    alt.Tooltip("pass_percentage:Q", title="Pass %", format=".2f"),
                ],
            )
            .properties(height=chart_height)
        )
        st.altair_chart(chart, width="stretch", theme="streamlit")
        display_table(
            department,
            {
                "department_name": "Department",
                "student_count": "Students",
                "grade_count": "Grades",
                "average_final_score": "Average Score",
                "pass_percentage": "Pass %",
                "fail_percentage": "Fail %",
            },
            height=table_height,
        )

with right:
    st.subheader("Grade Distribution")
    distribution, distribution_state = frame_for(results, "grade_distribution")
    if render_unavailable(distribution_state):
        pass
    else:
        assert distribution is not None
        display_bands = {
            "60-69": "60–69",
            "70-79": "70–79",
            "80-89": "80–89",
            "90-100": "90–100",
        }
        distribution = distribution.copy()
        distribution["grade_band"] = distribution["grade_band"].replace(display_bands)
        chart = (
            alt.Chart(distribution)
            .mark_bar()
            .encode(
                x=alt.X(
                    "grade_band:N",
                    title="Final-score band",
                    sort=alt.EncodingSortField(
                        field="sort_order", op="min", order="ascending"
                    ),
                ),
                y=alt.Y("grade_count:Q", title="Grade records"),
                tooltip=[
                    alt.Tooltip("grade_band:N", title="Score band"),
                    alt.Tooltip("grade_count:Q", title="Grades", format=","),
                    alt.Tooltip("percentage:Q", title="Percentage", format=".2f"),
                ],
            )
            .properties(height=chart_height)
        )
        st.altair_chart(chart, width="stretch", theme="streamlit")
        distribution = distribution.sort_values("sort_order")
        display_table(
            distribution.drop(columns=["sort_order"]),
            {
                "grade_band": "Score Band",
                "grade_count": "Grades",
                "percentage": "Percentage",
            },
            height=table_height,
        )

st.divider()
st.subheader("Courses Needing Attention")
attention, attention_state = frame_for(results, "courses_needing_attention")
if render_unavailable(attention_state):
    pass
else:
    assert attention is not None
    attention = attention.sort_values("average_final_score", ascending=True)
    attention_chart = (
        alt.Chart(attention)
        .mark_bar()
        .encode(
            x=alt.X("average_final_score:Q", title="Average final score"),
            y=alt.Y(
                "course_name:N",
                title=None,
                sort=attention["course_name"].tolist(),
                axis=alt.Axis(labelLimit=0, labelPadding=8),
            ),
            tooltip=[
                alt.Tooltip("course_name:N", title="Course"),
                alt.Tooltip("average_final_score:Q", title="Average score", format=".2f"),
                alt.Tooltip("pass_percentage:Q", title="Pass %", format=".2f"),
            ],
        )
        .properties(height=360)
    )
    st.altair_chart(attention_chart, width="stretch", theme="streamlit")

st.markdown("**Full course performance**")
course, course_state = frame_for(results, "course_performance")
if render_unavailable(course_state):
    pass
else:
    assert course is not None
    display_table(
        course,
        {
            "course_id": "Course ID",
            "course_name": "Course",
            "course_department": "Course Department",
            "student_count": "Students",
            "average_final_score": "Average Score",
            "pass_percentage": "Pass %",
        },
    )

st.divider()
st.subheader("At-Risk Students")
st.caption("Students with at least one course score below 60, ordered by risk.")
at_risk, at_risk_state = frame_for(results, "at_risk_students")
if render_unavailable(at_risk_state):
    pass
else:
    assert at_risk is not None
    display_table(
        at_risk,
        {
            "student_id": "Student ID",
            "student_name": "Student",
            "department_name": "Department",
            "average_final_score": "Average Score",
            "failing_courses": "Failing Courses",
        },
    )

st.divider()
st.subheader("Top Students")
st.caption("Students ordered by average final score across their grade records.")
top, top_state = frame_for(results, "top_students")
if render_unavailable(top_state):
    pass
else:
    assert top is not None
    display_table(
        top,
        {
            "student_id": "Student ID",
            "student_name": "Student",
            "department_name": "Department",
            "average_final_score": "Average Score",
        },
    )
