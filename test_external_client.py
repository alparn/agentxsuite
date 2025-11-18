#!/usr/bin/env python3
"""
Test script for external AI client integration with AgentxSuite MCP Fabric.
Usage: python test_external_client.py YOUR_TOKEN_HERE
"""
import sys
import httpx

MCP_FABRIC_URL = "http://localhost:8090"

def test_mcp_integration(token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("🧪 Testing MCP Fabric Integration\n")
    
    # Test 1: Get Manifest
    print("1. Getting Manifest...")
    try:
        response = httpx.get(f"{MCP_FABRIC_URL}/.well-known/mcp/manifest.json", headers=headers)
        print(f"   ✓ Status: {response.status_code}")
        print(f"   Manifest: {response.json().get('name', 'N/A')}\n")
    except Exception as e:
        print(f"   ✗ Error: {e}\n")
    
    # Test 2: List Tools
    print("2. Listing Available Tools...")
    try:
        response = httpx.get(f"{MCP_FABRIC_URL}/.well-known/mcp/tools", headers=headers)
        tools = response.json()
        print(f"   ✓ Found {len(tools)} tools")
        for tool in tools[:3]:
            print(f"     - {tool.get('name', 'N/A')}")
        print()
    except Exception as e:
        print(f"   ✗ Error: {e}\n")
    
    # Test 3: Run Tool
    print("3. Running Tool (agentxsuite_list_agents)...")
    try:
        response = httpx.post(
            f"{MCP_FABRIC_URL}/.well-known/mcp/run",
            headers=headers,
            json={"name": "agentxsuite_list_agents", "arguments": {}}
        )
        result = response.json()
        print(f"   ✓ Status: {response.status_code}")
        print(f"   IsError: {result.get('isError', False)}")
        if result.get('content'):
            print(f"   Content: {result['content'][0].get('text', 'N/A')[:100]}...")
        print()
    except Exception as e:
        print(f"   ✗ Error: {e}\n")
    
    print("✅ Integration test complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_external_client.py YOUR_TOKEN_HERE")
        sys.exit(1)
    
    token = sys.argv[1]
    test_mcp_integration(token)
