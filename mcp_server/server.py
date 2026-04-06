"""MCP Server for Multi-Agent Market Research Platform.

Exposes research platform capabilities as MCP tools for AI agents.
Communicates with the FastAPI backend via localhost HTTP.

Usage:
    python mcp_server/server.py
"""

import json
import os
import sys
import logging

from mcp.server.fastmcp import FastMCP
import httpx

# Configure logging to stderr (stdout reserved for MCP JSON-RPC)
logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp-market-research")

BASE_URL = os.environ.get("MARKET_RESEARCH_URL", "http://localhost:8000")

mcp = FastMCP(name="market-research")


async def _call_api(
    method: str,
    path: str,
    params: dict = None,
    json_body: dict = None,
    timeout: float = 30,
) -> str:
    """Call the FastAPI backend and return JSON string."""
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                method, url, params=params, json=json_body, timeout=timeout,
            )
            data = resp.json()
            return json.dumps(data, indent=2, default=str)
        except httpx.TimeoutException:
            return json.dumps({"error": True, "message": f"Request timed out after {timeout}s"})
        except httpx.ConnectError:
            return json.dumps({
                "error": True,
                "message": f"Cannot connect to research platform. Is the server running on {BASE_URL}? Start with: python run.py",
            })
        except Exception as e:
            return json.dumps({"error": True, "message": f"Request failed: {str(e)}"})


# Import and register tools from submodules
from mcp_server.tools.analysis import register_tools as register_analysis_tools
from mcp_server.tools.actions import register_tools as register_action_tools
from mcp_server.tools.data import register_tools as register_data_tools

register_analysis_tools(mcp, _call_api)
register_action_tools(mcp, _call_api)
register_data_tools(mcp, _call_api)


if __name__ == "__main__":
    mcp.run(transport="stdio")
