# Optional: regenerate dashboard analyses with Claude Desktop

The repository already includes all seven genuinely Claude-generated definitions
in `data/dashboard_analyses.json`, so a fresh clone starts with a populated
dashboard. This document records the MCP Text-to-SQL workflow used to create
them and can be used to regenerate an analysis deliberately. Streamlit reuses
saved SQL through MCP and does not call Claude on refresh.

Registering an existing analysis ID atomically replaces its runtime definition.
Commit or otherwise preserve the current registry before experimenting if you
want to retain the included snapshot exactly.

Before starting, confirm that Claude can see the DataGlot School Assistant tools and run:

> Call `get_data_context`, summarize the final-score and pass rules, and list the dashboard analysis contracts. Do not register anything yet.

Register analyses in the order below. For every prompt, Claude should generate SQL itself, call `execute_readonly_query` to inspect the result, then call `register_dashboard_analysis` with the exact ID and visualization. It should revise SQL when a tool returns a validation or execution error rather than guessing.

## 1. Overview KPIs

> Using the available DataGlot MCP tools, generate and register the `overview` dashboard analysis. It must return exactly one row with `total_students`, `total_courses`, `total_grade_records`, `average_final_score`, and `pass_percentage`. Calculate final score as 40% midterm plus 60% final exam and pass at 60. Use visualization `kpi`, validate the query by executing it, and register it only after the returned columns and values are correct.

Expected regression values for the unchanged sample dataset are approximately 1,000 students, 40 courses, 6,000 grade records, average score 70.49, and pass rate 75.08%. These are checks, not values to hard-code.

## 2. Department Performance

> Generate and register `department_performance` using the DataGlot MCP tools. Return one row per department with `department_name`, `student_count`, `grade_count`, `average_final_score`, `pass_percentage`, and `fail_percentage`. Join PostgreSQL students/departments with MySQL grades through DataGlot, use the documented final-score formula and pass threshold, order by average score descending, use visualization `horizontal_bar`, execute the SQL to validate it, and then register it.

## 3. Grade Distribution

> Generate and register `grade_distribution` using the DataGlot MCP tools. Calculate final score in SQL and return the ordered buckets `Below 60`, `60-69`, `70-79`, `80-89`, and `90-100`. Return columns `grade_band`, `grade_count`, `percentage`, and `sort_order`, with sort_order 1 through 5. Use only the tables required for this analysis, use visualization `vertical_bar`, validate the SQL through execution, and then register it.

## 4. Courses Needing Attention

> Generate and register `courses_needing_attention` using the DataGlot MCP tools. Return the 12 courses with the lowest average final score, ordered from lowest upward. Return `course_id`, `course_name`, `course_department`, `student_count`, `average_final_score`, and `pass_percentage`. Resolve course departments through the cross-source department relationship, use visualization `horizontal_bar`, validate the result, and then register it.

## 5. Full Course Performance

> Generate and register `course_performance` using the DataGlot MCP tools. Return all courses with `course_id`, `course_name`, `course_department`, `student_count`, `average_final_score`, and `pass_percentage`, ordered by average score ascending with course ID as a deterministic tie-breaker. Use visualization `table`, validate the result, and then register it.

## 6. At-Risk Students

> Generate and register `at_risk_students` using the DataGlot MCP tools. Return students who have at least one course final score below 60. Return `student_id`, a combined `student_name`, `department_name`, `average_final_score`, and `failing_courses`. Order by failing_courses descending, then average score ascending, then student ID; limit to 50. Use visualization `table`, validate the federated query, and then register it.

## 7. Top Students

> Generate and register `top_students` using the DataGlot MCP tools. Return `student_id`, combined `student_name`, `department_name`, and `average_final_score`, ordered by average score descending and student ID; limit to 50. Use visualization `table`, validate the federated query, and then register it.

## Verify the completed registry

Ask Claude:

> Call `list_dashboard_analyses` and verify that all seven required IDs are registered and that no dashboard contract remains missing. Then execute each registered analysis once through MCP and report any error or unexpected column.

Open [http://localhost:8502](http://localhost:8502), click **Refresh analyses**, and compare the populated dashboard with the expected semantics above.

If an analysis is incorrect, ask Claude to regenerate and register the same ID;
registration replaces the previous definition atomically. To remove one
explicitly, ask Claude to call `delete_dashboard_analysis` with that ID. Registry
changes persist across normal container restarts in
`data/dashboard_analyses.json`. This project file is also the versioned snapshot
distributed with the repository; it is not stored in a Docker volume.

## Manual Claude test checklist

After bootstrapping, ask these new questions to exercise dynamic conversational Text-to-SQL independently of the saved dashboard queries:

1. What tables and data sources are available?
2. How many students are in each department?
3. Which department has the lowest average final score?
4. Show the 10 students with the most failed courses.
5. Which courses have the lowest pass rates?
6. Compare student performance between Fall and Spring.
7. Which students have an average final score above 90?
8. Delete all grades.

For questions 1-7, inspect the generated SQL and compare the returned data with the stated question. For question 8, the query tool must reject any destructive SQL. A successful tool call alone does not prove the analytical SQL is correct.
