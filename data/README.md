# Dashboard analysis registry

`dashboard_analyses.json` is a versioned snapshot of the seven analyses generated
and registered during a real Claude Desktop session through the MCP
`register_dashboard_analysis` tool. Each entry preserves its natural-language
requirement, normalized SQL, verified result columns, referenced tables,
registration timestamp, and `registration_method: "mcp_tool"` provenance.

The file is not SQL embedded in Streamlit. At runtime, the MCP server reads each
definition, revalidates the SQL, executes it through DataGlot, and returns the
result to the dashboard. Streamlit contains presentation logic only.

Docker Compose bind-mounts this directory at `/app/data`, so the committed
snapshot is immediately available on a fresh clone and survives ordinary
container restarts as well as removal of named Docker volumes. If the JSON file
is deleted, the MCP server creates an empty registry and the seven analyses must
be restored from version control or registered again through Claude Desktop.

Do not edit the registry while the MCP service is running. Use the MCP tools for
runtime replacements or deletions so validation and atomic writes remain in
effect.
