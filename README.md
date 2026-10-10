# DataGlot MCP School Assistant

An AI-powered conversational Text-to-SQL system that lets users ask Claude
Desktop questions about school data federated across PostgreSQL and MySQL.
Claude generates analytical SQL dynamically, the custom MCP server validates and
executes it through DataGlot, and Claude presents the result to the user.

The project has two main parts:

1. **Claude-powered conversational Text-to-SQL:** users ask natural-language
   questions and receive answers produced from live federated queries.
2. **School Management Dashboard:** Streamlit visualizes seven analytical queries
   originally generated, validated, and registered through the same Claude → MCP
   workflow.

Claude Desktop provides the language model interface. The project does not call
an OpenAI, Anthropic, or other LLM API and requires no model API key.

## Architecture and core workflows

### 1. Claude-powered conversational Text-to-SQL

Claude Desktop handles interactive natural-language analytics. It uses the MCP
tools to inspect the available schema and business rules, generate SQL for the
user's question, execute the query through DataGlot, and explain the result.

```text
User question -> Claude Desktop (generates SQL) -> MCP server
              -> DataGlot -> PostgreSQL/MySQL
PostgreSQL/MySQL -> DataGlot -> MCP server -> Claude response
```

For example, a user can ask Claude:

> Which department has the lowest average final score, and how many students
> belong to that department?

For this request, Claude reads the schema and business rules exposed by MCP,
writes a read-only federated query, and sends it through MCP and DataGlot. It
then returns the result with the SQL it used. The query is generated for the
question rather than selected from a fixed list.

### 2. Registered School Management Dashboard

Claude also generated and registered seven reusable management analyses through
MCP. The Streamlit dashboard executes those saved definitions through the same
query path:

```text
Claude-generated SQL -> MCP validation and registration -> JSON registry
JSON registry -> Streamlit Dashboard -> MCP -> DataGlot -> PostgreSQL/MySQL
PostgreSQL/MySQL -> DataGlot -> MCP -> Streamlit charts and tables
```

The dashboard can run without Claude Desktop because the verified definitions
are already registered. It displays those seven registered analyses; it does not
automatically visualize arbitrary one-off questions asked during a Claude
conversation. A new analysis appears in the dashboard only when it is explicitly
validated and registered through the MCP dashboard workflow.

The MCP server connects only to DataGlot's PostgreSQL-wire endpoint, never
directly to either source. Streamlit has no database driver or embedded
analytical SQL and communicates only with the MCP service.

## Data model

- PostgreSQL 17: `pg.public.departments` (5 rows), `pg.public.students` (1,000 rows).
- MySQL 8.4: `mysql.school.courses` (40 rows), `mysql.school.grades` (6,000 rows).
- `grades.student_id` relates to PostgreSQL students; `courses.department_id` relates to PostgreSQL departments.
- Final score: `0.40 * midterm_score + 0.60 * final_exam_score`.
- Pass threshold: final score at least `60`.

The committed sample data is deterministic with seed `20260924` and contains Fall and Spring records for academic year 2024-2025.

## Registered dashboard analyses

The repository includes the seven-analysis registry at
[`data/dashboard_analyses.json`](data/dashboard_analyses.json). Claude Desktop
generated and registered these definitions through MCP during a Text-to-SQL
session; Streamlit does not embed them. Each saved entry retains its requirement,
normalized SQL, verification metadata, source tables, timestamp, and
`registration_method: "mcp_tool"` provenance. See
[`data/README.md`](data/README.md) for the registry lifecycle.

On startup, Streamlit asks MCP to execute the saved definitions. MCP revalidates
each query and sends it through DataGlot, so the dashboard works without a live
Claude Desktop connection or an LLM API call.

The dashboard contains:

- Overview KPIs
- Department Performance
- Grade Distribution
- Courses Needing Attention
- Full Course Performance
- At-Risk Students
- Top Students

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

The query path uses several safeguards:

- SQLGlot parses exactly one PostgreSQL-compatible statement.
- Only SELECT and read-only WITH queries are accepted.
- Nested write/control nodes, comments, multi-statements, locks, and dangerous functions are rejected.
- Every source table must use an allowlisted three-part name.
- Returned rows default to 200 and have a hard maximum of 1,000.
- A 20-second cancellation timer is applied on a best-effort basis through the PG-wire driver.
- Errors are bounded and scrubbed before tool responses.
- DataGlot source credentials belong to SELECT-only PostgreSQL and MySQL users.

These controls are intended for local analytical use, not as a production
sandbox. The SQL parser is not the only boundary: source permissions remain
read-only even if validation is bypassed.

## Start

You only need Docker Desktop or Docker Engine with Compose v2.

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

Compose uses the project name `dataglot-mcp-school-assistant` to keep its
containers, network, and volumes isolated from other Compose projects.

## Claude Desktop — AI Text-to-SQL Integration

Claude Desktop is required for interactive conversational Text-to-SQL. Connect
it to ask arbitrary natural-language questions, inspect generated SQL, or
register or replace a saved dashboard analysis. The dashboard continues to work
without Claude Desktop because its seven queries are already registered.

For setup instructions, see
[docs/CLAUDE_DESKTOP_SETUP.md](docs/CLAUDE_DESKTOP_SETUP.md). On macOS, the
recommended configuration invokes Docker Desktop directly and starts the stdio
MCP process with `docker exec -i`, avoiding launcher access through
privacy-protected project folders. `scripts/run_mcp_claude.sh` provides the same
transport for terminal testing and keeps logs off protocol stdout.

Claude generates SQL for each conversational request. One-off results are
returned in the Claude conversation and are not
automatically added to the dashboard. The separate registration workflow in
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

The live integration test does not modify the registry. It verifies all seven
saved analyses, federation, result limits, and rejection of unsafe SQL without
replacing or deleting registered definitions.

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

- Claude Desktop configuration is host-specific. It is required for interactive conversational Text-to-SQL but not for viewing the already-registered dashboard analyses.
- The dashboard renders registered whole-dataset analyses; department and semester filters are not implemented.
- DataGlot 0.5.2 snapshots source metadata when catalogs start. Restart DataGlot after adding source tables.
- Query cancellation depends on DataGlot's PG-wire cancellation behavior and is best-effort; result-size limits are enforced separately.
- The Streamable HTTP MCP endpoint has no application-level authentication. Compose binds it to `127.0.0.1` for local use; do not expose it to an untrusted network without adding authentication and TLS.
- Local development credentials are visible in Compose and are not suitable for production.

The project uses pinned MCP Python SDK `2.2.0` and DataGlot `0.5.2` at the tested image digest. No Claude configuration, API key, token, or `.env` file is included.
