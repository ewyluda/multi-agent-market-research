"""Tests for MCP server tool definitions."""


def test_server_imports():
    from mcp_server.server import mcp as mcp_server
    assert mcp_server is not None
    assert mcp_server.name == "market-research"


def test_tool_count():
    from mcp_server.server import mcp as mcp_server
    tools = mcp_server._tool_manager._tools
    assert len(tools) >= 30, f"Expected 30+ tools, got {len(tools)}"
