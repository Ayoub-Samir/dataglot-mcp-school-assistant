# Dashboard analysis registry

`dashboard_analyses.json` is a versioned snapshot of the seven analyses generated
and registered in Claude Desktop through the MCP
`register_dashboard_analysis` tool. Each entry preserves its natural-language
requirement, normalized SQL, verified result columns, referenced tables,
registration timestamp, and `registration_method: "mcp_tool"` provenance.

Streamlit does not contain copies of these queries. At runtime, the MCP server
reads each definition, revalidates the SQL, executes it through DataGlot, and
returns the result to the dashboard. Streamlit contains presentation logic only.

Docker Compose bind-mounts this directory at `/app/data`, so the committed
snapshot is available on a fresh clone and survives container restarts and the
removal of named Docker volumes. If the JSON file is deleted, the MCP server
creates an empty registry; restore the seven analyses from version control or
register them again through Claude Desktop.

Do not edit the registry while the MCP service is running. Use the MCP tools for
replacements and deletions so that validation and atomic writes remain in effect.
