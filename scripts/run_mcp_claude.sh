#!/bin/sh
set -eu

if [ -n "${DOCKER_BIN:-}" ] && [ -x "$DOCKER_BIN" ]; then
  :
elif command -v docker >/dev/null 2>&1; then
  DOCKER_BIN=$(command -v docker)
elif [ -x /usr/local/bin/docker ]; then
  DOCKER_BIN=/usr/local/bin/docker
elif [ -x /opt/homebrew/bin/docker ]; then
  DOCKER_BIN=/opt/homebrew/bin/docker
elif [ -x "${HOME}/.docker/bin/docker" ]; then
  DOCKER_BIN="${HOME}/.docker/bin/docker"
else
  echo "Docker CLI was not found. Start Docker Desktop and set DOCKER_BIN if needed." >&2
  exit 127
fi

MCP_CONTAINER_NAME=${MCP_CONTAINER_NAME:-dataglot-mcp-school-assistant-mcp-1}

if [ "$("$DOCKER_BIN" inspect --format '{{.State.Running}}' "$MCP_CONTAINER_NAME" 2>/dev/null || true)" != "true" ]; then
  echo "MCP container '$MCP_CONTAINER_NAME' is not running. Start the stack with docker compose up --build -d." >&2
  exit 1
fi

exec "$DOCKER_BIN" exec -i "$MCP_CONTAINER_NAME" \
  python -m school_mcp.server --transport stdio
