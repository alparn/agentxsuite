"""
stdio MCP Adapter - Native stdio protocol support for AgentxSuite.

This adapter enables AgentxSuite to communicate directly with MCP clients
(like Claude Desktop) via stdin/stdout, eliminating the need for external bridges.

Usage:
    python -m mcp_fabric.stdio_adapter --token <JWT_TOKEN>

Protocol:
    - Input: Newline-delimited JSON-RPC messages via stdin
    - Output: Newline-delimited JSON-RPC responses via stdout
    - Logging: All logs go to stderr (never stdout)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

import django

# Initialize Django before imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from asgiref.sync import sync_to_async

from apps.agents.models import Agent
from apps.tenants.models import Environment, Organization
from mcp_fabric.deps import get_validated_token
from mcp_fabric.jsonrpc import MCPJsonRpcContext, MCPJsonRpcHandler, normalize_mcp_tool_name

# Configure logging to stderr only
logging.basicConfig(
    level=logging.INFO if os.getenv("DEBUG") else logging.WARNING,
    format="[%(levelname)s] %(message)s",
    stream=sys.stderr,  # CRITICAL: All logs to stderr, never stdout
)
logger = logging.getLogger(__name__)


class StdioMCPAdapter:
    """
    stdio MCP Adapter for AgentxSuite.
    
    Implements the MCP protocol over stdin/stdout for direct integration
    with Claude Desktop and other stdio-based MCP clients.
    """

    def __init__(self, token: str):
        """
        Initialize adapter with JWT token.
        
        Args:
            token: JWT token containing org_id, env_id, and agent_id claims
        """
        self.token = token
        self.org: Organization | None = None
        self.env: Environment | None = None
        self.agent: Agent | None = None
        self.token_claims: dict[str, Any] | None = None
        self.handler: MCPJsonRpcHandler | None = None
        self.initialized = False

    async def start(self):
        """
        Main event loop: read JSON-RPC from stdin, write responses to stdout.
        
        This is the entry point for the stdio adapter.
        """
        try:
            # Validate token and extract org/env/agent
            await self._validate_and_setup()
            
            logger.info(
                f"stdio Adapter started for org={self.org.name}, env={self.env.name}, agent={self.agent.name if self.agent else 'auto'}"
            )
            
            # Read from stdin line by line
            loop = asyncio.get_event_loop()
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            
            # Process messages
            while True:
                try:
                    line_bytes = await reader.readline()
                    if not line_bytes:
                        # EOF reached
                        logger.info("stdin closed, exiting")
                        break
                    
                    line = line_bytes.decode("utf-8").strip()
                    if not line:
                        continue
                    
                    message = json.loads(line)
                    logger.debug(f"Received message: {message.get('method', 'unknown')}")
                    
                    response = await self.handle_message(message)
                    if response:
                        self._write_response(response)
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    continue
                    
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)

    async def _validate_and_setup(self):
        """Validate token and setup org/env/agent from claims."""
        try:
            # Validate token with required scopes
            self.token_claims = get_validated_token(
                self.token,
                required_scopes=["mcp:tools"],  # Minimum scope for tool access
            )
            
            org_id = self.token_claims.get("org_id")
            env_id = self.token_claims.get("env_id")
            agent_id = self.token_claims.get("agent_id")
            
            if not org_id or not env_id:
                raise ValueError("Token missing org_id or env_id claims")
            
            # Get organization
            self.org = await sync_to_async(Organization.objects.filter(id=org_id).first)()
            if not self.org:
                raise ValueError(f"Organization {org_id} not found")
            
            # Get environment
            self.env = await sync_to_async(
                Environment.objects.filter(
                    id=env_id,
                    organization=self.org
                ).first
            )()
            if not self.env:
                raise ValueError(f"Environment {env_id} not found or not in organization {org_id}")
            
            # Get agent (optional - can auto-select)
            if agent_id:
                self.agent = await sync_to_async(
                    Agent.objects.filter(
                        id=agent_id,
                        organization=self.org,
                        environment=self.env,
                        enabled=True,
                    ).first
                )()
                if not self.agent:
                    logger.warning(f"Agent {agent_id} not found, will auto-select")
            
            logger.info(f"Validated token for org={self.org.name}, env={self.env.name}")
            self.handler = self._build_handler()
            
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            raise

    def _build_handler(self) -> MCPJsonRpcHandler:
        """Build the shared JSON-RPC handler for this stdio session."""
        if not self.org or not self.env or self.token_claims is None:
            raise ValueError("Organization/Environment not set")

        resolved_agent_id = str(self.agent.id) if self.agent else self.token_claims.get("agent_id")
        self.token_claims["_resolved_agent_id"] = resolved_agent_id
        self.token_claims["_client_ip"] = None
        self.token_claims["_jti"] = self.token_claims.get("_jti") or self.token_claims.get("jti")

        return MCPJsonRpcHandler(
            MCPJsonRpcContext(
                organization=self.org,
                environment=self.env,
                agent=self.agent,
                token_claims=self.token_claims,
                server_name="agentxsuite",
            )
        )

    def _get_handler(self) -> MCPJsonRpcHandler:
        """Return the shared JSON-RPC handler, creating it for test-initialized adapters."""
        if self.handler is None:
            self.handler = self._build_handler()
        return self.handler

    async def handle_message(self, message: dict) -> dict | None:
        """
        Route JSON-RPC message to the shared transport-independent handler.
        
        Args:
            message: JSON-RPC message
            
        Returns:
            JSON-RPC response or None (for notifications)
        """
        response = await self._get_handler().handle_message(message)
        self.initialized = self._get_handler().initialized
        return response

    async def handle_initialize(self, message: dict) -> dict:
        """
        Handle MCP initialize request via the shared JSON-RPC handler.
        
        Returns server capabilities and protocol version.
        """
        response = await self._get_handler().handle_initialize(message)
        self.initialized = self._get_handler().initialized
        return response

    async def handle_tools_list(self, message: dict) -> dict:
        """
        Handle tools/list request via the shared JSON-RPC handler.
        
        Returns all enabled tools for the org/env.
        """
        return await self._get_handler().handle_tools_list(message)

    async def handle_tool_call(self, message: dict) -> dict:
        """
        Handle tools/call request via the shared JSON-RPC handler.
        
        Executes a tool via AgentxSuite's run service with full security pipeline.
        """
        return await self._get_handler().handle_tool_call(message)

    async def handle_resources_list(self, message: dict) -> dict:
        """
        Handle resources/list request.
        
        Returns empty list for now (Phase 3).
        """
        return self._get_handler()._success_response(message.get("id"), {"resources": []})

    async def handle_prompts_list(self, message: dict) -> dict:
        """
        Handle prompts/list request.
        
        Returns empty list for now (Phase 3).
        """
        return self._get_handler()._success_response(message.get("id"), {"prompts": []})

    def _normalize_tool_name(self, name: str) -> str:
        """
        Normalize tool name to match MCP spec: ^[a-zA-Z0-9_-]{1,64}$
        
        Args:
            name: Original tool name
            
        Returns:
            Normalized tool name
        """
        return normalize_mcp_tool_name(name)

    def _write_response(self, response: dict):
        """
        Write JSON-RPC response to stdout.
        
        CRITICAL: This is the ONLY place we write to stdout.
        Each response must be on its own line (newline-delimited JSON).
        
        Args:
            response: JSON-RPC response dictionary
        """
        json_str = json.dumps(response)
        sys.stdout.write(json_str + "\n")
        sys.stdout.flush()
        logger.debug(f"Sent response for id={response.get('id')}")

    def _error_response(
        self,
        msg_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> dict:
        """
        Create JSON-RPC error response.
        
        Args:
            msg_id: Message ID from request
            code: Error code
            message: Error message
            data: Optional additional error data
            
        Returns:
            JSON-RPC error response
        """
        return self._get_handler()._error_response(msg_id, code, message, data)


async def main():
    """Main entry point for stdio adapter."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AgentxSuite stdio MCP Adapter"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="JWT token with org_id, env_id, and agent_id claims",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    adapter = StdioMCPAdapter(token=args.token)
    await adapter.start()


if __name__ == "__main__":
    asyncio.run(main())

