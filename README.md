# DataGlot MCP School Assistant

A natural-language analytics system that exposes federated PostgreSQL and MySQL data through DataGlot and MCP, enabling Claude Desktop to perform Text-to-SQL over distributed data sources and register reusable school-management analytics.

Claude Desktop is the language model. This project does not call an OpenAI, Anthropic, or other LLM API and requires no model API key.

## Architecture

Dynamic conversational analytics:

```text
User -> Claude Desktop -> MCP (stdio) -> MCP server -> DataGlot
                                                     |-> PostgreSQL
                                                     \-> MySQL
```

Registered dashboard analytics:

```text
Claude-generated SQL -> MCP validation/registration -> JSON registry
Streamlit -> MCP (Streamable HTTP) -> saved validated SQL -> DataGlot -> both sources
```

The MCP server has one query connection: DataGlot's PostgreSQL-wire endpoint. It never connects directly to either source. Streamlit has no database driver or SQL and communicates only with the MCP service.

## Data model

- PostgreSQL 17: `pg.public.departments` (5 rows), `pg.public.students` (1,000 rows).
- MySQL 8.4: `mysql.school.courses` (40 rows), `mysql.school.grades` (6,000 rows).
- `grades.student_id` relates to PostgreSQL students; `courses.department_id` relates to PostgreSQL departments.
- Final score: `0.40 * midterm_score + 0.60 * final_exam_score`.
- Pass threshold: final score at least `60`.

The committed sample data is deterministic with seed `20260924` and contains Fall and Spring records for academic year 2024-2025.

## Completed dashboard

The repository includes the completed seven-analysis registry at
[`data/dashboard_analyses.json`](data/dashboard_analyses.json). These definitions
were generated and registered through a real Claude Desktop MCP Text-to-SQL
session; they are not SQL embedded in Streamlit. Each saved entry retains its
requirement, normalized SQL, verification metadata, source tables, timestamp,
and `registration_method: "mcp_tool"` provenance. See
[`data/README.md`](data/README.md) for the registry lifecycle.

On startup, Streamlit asks MCP to execute the saved definitions. MCP revalidates
each query and sends it through DataGlot, so the completed dashboard is available
without connecting Claude Desktop or calling any LLM API.

## MCP tools

- `get_data_context`: schema, business semantics, relationships, SQL rules, contracts, and live DataGlot visibility.
- `list_tables`: permitted tables, sources, columns, and live visibility.
- `describe_table`: semantic and live metadata for one permitted table.
- `execute_readonly_query`: generic, validated analytical SQL execution.
- `register_dashboard_analysis`: validates, executes, contract-checks, and atomically saves generated SQL.
- `list_dashboard_analyses`: saved definitions and missing required contracts.
- `execute_dashboard_analysis`: revalidates and runs a saved definition.
- `delete_dashboard_analysis`: removes a definition without modifying source data.

The same server definition is exposed over stdio for Claude Desktop and Streamable HTTP for the dashboard and automated tests.

## SQL safety

The query path applies defense in depth:

- SQLGlot parses exactly one PostgreSQL-compatible statement.
- Only SELECT and read-only WITH queries are accepted.
- Nested write/control nodes, comments, multi-statements, locks, and dangerous functions are rejected.
- Every source table must use an allowlisted three-part name.
- Returned rows default to 200 and have a hard maximum of 1,000.
- A 20-second cancellation timer is applied on a best-effort basis through the PG-wire driver.
- Errors are bounded and scrubbed before tool responses.
- DataGlot source credentials belong to SELECT-only PostgreSQL and MySQL users.

This is a local analytical safety model, not a claim of production-grade sandboxing. The SQL parser is not the sole boundary; source permissions remain read-only even if validation were bypassed.

## Start

Docker Desktop or Docker Engine with Compose v2 is the only application-stack prerequisite.

```bash
git clone https://github.com/Ayoub-Samir/dataglot-mcp-school-assistant.git
cd dataglot-mcp-school-assistant
docker compose up --build
```

Open the populated dashboard at [http://localhost:8502](http://localhost:8502).
The committed registry supplies all seven analyses on a fresh clone.

Default loopback-only host ports:

| Service | Port |
|---|---:|
| PostgreSQL | 5435 |
| MySQL | 3309 |
| DataGlot PG-wire | 15433 |
| MCP Streamable HTTP | 18000 |
| Streamlit | 8502 |

The defaults intentionally differ from the related standalone dashboard project, and Compose uses the isolated project name `dataglot-mcp-school-assistant`.

## Optional Claude Desktop integration

The dashboard does not require Claude Desktop at runtime. Connect it when you
want to ask arbitrary natural-language questions, inspect generated SQL, or
replace a saved analysis through the MCP workflow. Follow
[docs/CLAUDE_DESKTOP_SETUP.md](docs/CLAUDE_DESKTOP_SETUP.md). On macOS, the
recommended configuration invokes Docker Desktop directly and starts the stdio
MCP process with `docker exec -i`, avoiding launcher access through
privacy-protected project folders. `scripts/run_mcp_claude.sh` provides the same
transport for terminal testing and keeps logs off protocol stdout.

The included registry already contains:

- Overview KPIs
- Department Performance
- Grade Distribution
- Courses Needing Attention
- Full Course Performance
- At-Risk Students
- Top Students

Claude generates new SQL for conversational questions at conversation time.
The optional workflow in
[docs/DASHBOARD_BOOTSTRAP_WITH_CLAUDE.md](docs/DASHBOARD_BOOTSTRAP_WITH_CLAUDE.md)
documents how the saved definitions were produced and how to regenerate them if
desired. Dashboard SQL is generated once, validated and saved through MCP, and
then reused by Streamlit without another model call.

## Tests

Run the parser/safety suite:

```bash
docker compose run --rm --no-deps --entrypoint pytest mcp -q tests/test_sql_safety.py
```

With the stack healthy, run the live MCP test:

```bash
docker compose exec -T mcp python tests/integration_mcp.py
```

The live integration test is read-only with respect to the completed registry.
It verifies all seven saved analyses, federation, result limits, and rejection of
unsafe SQL without replacing or deleting registered definitions.

Clean-start validation removes only this project's containers, network, and database volumes:

```bash
docker compose down -v --remove-orphans
docker compose up --build -d
docker compose ps
```

## Stop and reset

Stop while retaining data and registered analyses:

```bash
docker compose down
```

Resetting with `down -v` removes PostgreSQL and MySQL named volumes. The
deterministic initialization scripts recreate their data on the next start. The
dashboard registry is a bind-mounted, versioned project file under `data/`, not a
Docker volume, so it survives both normal restarts and named-volume removal.
Delete or replace analyses through MCP rather than editing the registry while
services are running.

## Limitations

- Claude Desktop configuration is optional, host-specific, and must be completed locally before conversational Text-to-SQL tools can be used from Claude.
- The dashboard currently renders registered whole-dataset analyses; department and semester parameterized filters are not exposed. This avoids implying that an unsafe or ineffective filter exists.
- DataGlot 0.5.2 snapshots source metadata when catalogs start. Restart DataGlot after adding source tables.
- Query cancellation depends on DataGlot's PG-wire cancellation behavior and is therefore best-effort; result-size bounding is enforced independently.
- The Streamable HTTP MCP endpoint has no application-level authentication. Compose binds it to `127.0.0.1` for local use; do not expose it to an untrusted network without an appropriate authenticated security layer.
- Local development credentials are visible in Compose and are not suitable for production.

The project uses pinned MCP Python SDK `2.2.0` and DataGlot `0.5.2` at the tested image digest. No Claude configuration, API key, token, or `.env` file is included.
