# Claude Desktop setup on macOS

Claude Desktop is the optional language model and Text-to-SQL client for this
project. The completed seven-analysis dashboard is already available from the
versioned registry and does not require Claude at runtime. Connect Claude when
you want to ask new natural-language questions or deliberately regenerate a
saved analysis. The project does not use an Anthropic API key or any other LLM
API.

## Prerequisites

- A current Claude Desktop installation.
- Docker Desktop with the `docker compose` command available.
- This project stored in a stable local directory.

Start the application stack before opening or restarting Claude Desktop:

```bash
cd <PROJECT_PATH>
docker compose up --build -d
docker compose ps
```

All five services should be running and healthy, and the populated dashboard
should be available at [http://localhost:8502](http://localhost:8502). Claude
starts an additional stdio MCP process inside the existing MCP container. That
process uses the same isolated Compose network, application environment, and
dashboard registry as the HTTP MCP service.

## Add the local MCP server

Claude Desktop's developer-defined MCP configuration on macOS is:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Quit Claude Desktop completely. Merge the following entry into the existing JSON file; do not overwrite other configured servers. Replace `<HOME_PATH>` with the absolute path to your home directory (for example, the output of `echo "$HOME"`).

```json
{
  "mcpServers": {
    "dataglot-school-assistant": {
      "command": "/Applications/Docker.app/Contents/Resources/bin/docker",
      "args": [
        "exec",
        "-i",
        "dataglot-mcp-school-assistant-mcp-1",
        "python",
        "-m",
        "school_mcp.server",
        "--transport",
        "stdio"
      ],
      "env": {
        "DOCKER_HOST": "unix://<HOME_PATH>/.docker/run/docker.sock"
      }
    }
  }
}
```

This command avoids asking Claude Desktop or a child shell to open a launcher under a macOS privacy-protected folder such as Documents. It also avoids relying on Claude Desktop's `PATH`. No project path, database password, or API key belongs in this configuration.

If Docker Desktop is installed somewhere other than `/Applications`, set `command` to the absolute path reported by `command -v docker` after resolving any symbolic link. The command must be executable by Claude Desktop.

The repository launcher remains available for terminal testing:

```bash
./scripts/run_mcp_claude.sh
```

It uses the same `docker exec -i` transport, but it is not the recommended Claude configuration when the repository is inside Documents because macOS may prevent Claude's helper process from opening the script.

## Confirm the connection

1. Fully quit and reopen Claude Desktop after saving the configuration.
2. Open a new conversation and inspect the available tools or integrations.
3. Confirm that `dataglot-school-assistant` appears and exposes tools including `get_data_context`, `list_tables`, and `execute_readonly_query`.
4. Use this first prompt:

   > Use the DataGlot School Assistant MCP tools to list the available tables and data sources. Call `get_data_context` first, and do not guess from prior knowledge.

5. Then ask:

   > Using the DataGlot School Assistant MCP tools, calculate how many students belong to each department. Generate one read-only federated SQL query, execute it through DataGlot, and show the SQL and result.

Successful automated tests confirm the direct Docker command and stdio protocol,
but the Claude Desktop user interface remains a host-specific manual verification
step. Connecting Claude is not required to view the seven included analyses.

## Troubleshooting

- Confirm the stack: `docker compose ps`.
- Check MCP and DataGlot logs: `docker compose logs --tail=200 mcp dataglot`.
- Run the launcher directly from Terminal: `./scripts/run_mcp_claude.sh`. Press Control-D to close its stdin.
- Claude Desktop MCP logs are under `~/Library/Logs/Claude`. Check `mcp.log` and the server-specific `mcp-server-dataglot-school-assistant.log` if present.
- Confirm the Docker Desktop CLI exists at the configured absolute path and the socket exists at `~/.docker/run/docker.sock`.
- If Claude reports `Operation not permitted` for a launcher under Documents, use the direct Docker configuration above. Changing the script's executable bit does not fix a macOS privacy denial when the script is already executable.
- If the MCP container name is missing, start the stack from the project directory with `docker compose up --build -d` and confirm `dataglot-mcp-school-assistant-mcp-1` is healthy.
- If source tables were changed after DataGlot started, restart DataGlot because DataGlot 0.5.2 snapshots source metadata: `docker compose restart dataglot mcp dashboard`.
- Ensure the JSON is valid and that `<HOME_PATH>` was replaced rather than left literally in the socket URL.

The MCP server writes protocol messages only to stdout and sends application logs to stderr so that Claude's stdio connection is not corrupted.

## Remove the integration

1. Fully quit Claude Desktop.
2. Remove only the `dataglot-school-assistant` object from `mcpServers` in `claude_desktop_config.json`.
3. Reopen Claude Desktop.
4. Optionally stop the project with `docker compose down` from the project directory.

References: [official MCP Python SDK host guide](https://py.sdk.modelcontextprotocol.io/get-started/real-host/) and [Anthropic's local MCP guidance](https://support.anthropic.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).
