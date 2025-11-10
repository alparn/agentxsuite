#!/usr/bin/env bash
set -euo pipefail

# Script to start Mock MCP Server and MCP Fabric for local testing

echo "Starting local test servers..."

# 1) Mock MCP Server
echo "Starting Mock MCP Server on :8091"
cd "$(dirname "$0")/.."
uvicorn dev.mock_mcp_server:app --reload --port 8091 &
MOCK_PID=$!

# 2) MCP Fabric
echo "Starting MCP Fabric on :8090"
uvicorn mcp_fabric.main:app --reload --port 8090 &
FABRIC_PID=$!

echo ""
echo "Servers started:"
echo "  - Mock MCP Server: PID $MOCK_PID (http://127.0.0.1:8091)"
echo "  - MCP Fabric: PID $FABRIC_PID (http://127.0.0.1:8090)"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for both processes
wait

