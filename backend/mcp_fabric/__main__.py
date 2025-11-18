"""
Entry point for running mcp_fabric.stdio_adapter as a module.

Usage:
    python -m mcp_fabric.stdio_adapter --token <JWT_TOKEN>
"""
import asyncio
from mcp_fabric.stdio_adapter import main

if __name__ == "__main__":
    asyncio.run(main())

