"""
Claude Agent SDK implementation.

This module implements the actual Claude agent that interacts with AgentxSuite.
"""

import logging
from typing import Any

from anthropic import Anthropic

from .agent_registry import AgentxSuiteToolRegistry
from .tool_handlers import AgentxSuiteToolHandlers, ToolExecutionError

logger = logging.getLogger(__name__)


class AgentxSuiteClaudeAgent:
    """
    Claude agent implementation for AgentxSuite.

    This agent bridges Claude's hosted Agent SDK with AgentxSuite's
    internal tool execution and orchestration infrastructure.
    """

    def __init__(
        self,
        api_key: str,
        organization_id: str,
        environment_id: str,
        auth_token: str,
        model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize the Claude agent.

        Args:
            api_key: Anthropic API key for Claude
            organization_id: AgentxSuite organization ID
            environment_id: AgentxSuite environment ID
            auth_token: Authentication token for AgentxSuite API
            model: Claude model to use (default: claude-sonnet-4)
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.organization_id = organization_id
        self.environment_id = environment_id

        # Initialize tool registry and handlers
        self.registry = AgentxSuiteToolRegistry()
        self.handlers = AgentxSuiteToolHandlers(organization_id, environment_id, auth_token)

        logger.info(
            f"Initialized Claude agent for org={organization_id}, env={environment_id}, model={model}"
        )

    async def execute_conversation(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a conversation with Claude, handling tool calls automatically.

        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens for response
            system_prompt: Optional system prompt override

        Returns:
            Dictionary containing response and execution metadata
        """
        try:
            # Get tool definitions from registry
            tools = self.registry.get_tools()

            # Build request parameters
            request_params = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": messages,
                "tools": tools,
            }

            if system_prompt:
                request_params["system"] = system_prompt

            # Initial API call
            response = self.client.messages.create(**request_params)

            # Track tool calls for logging
            tool_calls_made = []

            # Handle tool calls iteratively
            while response.stop_reason == "tool_use":
                # Process tool calls from response
                tool_results = []

                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input
                        tool_use_id = content_block.id

                        logger.info(f"Claude requested tool: {tool_name} with input: {tool_input}")

                        try:
                            # Execute tool via handlers
                            result = await self.handlers.handle_tool_call(tool_name, tool_input)

                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": str(result),
                                }
                            )

                            tool_calls_made.append(
                                {"tool": tool_name, "input": tool_input, "success": True}
                            )

                        except ToolExecutionError as e:
                            logger.error(f"Tool execution failed for {tool_name}: {e}")

                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": f"Error: {str(e)}",
                                    "is_error": True,
                                }
                            )

                            tool_calls_made.append(
                                {"tool": tool_name, "input": tool_input, "success": False, "error": str(e)}
                            )

                # Add tool results to messages and continue conversation
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                # Continue conversation with tool results
                response = self.client.messages.create(
                    model=self.model, max_tokens=max_tokens, messages=messages, tools=tools
                )

            # Extract final response text
            response_text = ""
            for content_block in response.content:
                if hasattr(content_block, "text"):
                    response_text += content_block.text

            return {
                "success": True,
                "response": response_text,
                "stop_reason": response.stop_reason,
                "tool_calls": tool_calls_made,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_calls": tool_calls_made if "tool_calls_made" in locals() else [],
            }

    async def execute_single_message(
        self, message: str, system_prompt: str | None = None
    ) -> dict[str, Any]:
        """
        Execute a single message with Claude.

        Args:
            message: User message
            system_prompt: Optional system prompt

        Returns:
            Response dictionary
        """
        messages = [{"role": "user", "content": message}]
        return await self.execute_conversation(messages, system_prompt=system_prompt)

    def get_available_tools(self) -> list[dict[str, Any]]:
        """
        Get list of available tools.

        Returns:
            List of tool definitions
        """
        return self.registry.get_tools()

