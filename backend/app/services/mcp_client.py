import httpx
from httpx_sse import aconnect_sse
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("mcp_client")

class MCPClientService:
    """
    Client MCP berbasis Transport SSE over HTTP.
    Mengirim request JSON-RPC ke MCP Server untuk 'tools/list' dan 'tools/call'.
    """

    @staticmethod
    async def discover_tools(server_url: str) -> List[Dict[str, Any]]:
        """
        Terhubung ke server MCP via SSE untuk mengambil daftar tools yang tersedia (tools/list).
        Jika SSE server belum aktif / unreachable, mengembalikan fallback tools discovery default.
        """
        logger.info(f"Connecting to MCP Server via SSE: {server_url}")
        
        # Format payload standar Model Context Protocol JSON-RPC
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Cobalah melayangkan SSE HTTP connection
                response = await client.post(server_url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data and "tools" in data["result"]:
                        return data["result"]["tools"]
        except Exception as e:
            raise RuntimeError(f"Tidak dapat mengambil tools dari MCP server '{server_url}': {e}") from e
        raise RuntimeError(f"MCP server '{server_url}' tidak mengembalikan respons tools/list yang valid.")

    @staticmethod
    async def call_tool(server_url: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Memanggil tool pada MCP Server via JSON-RPC tools/call.
        """
        logger.info(f"Invoking tool '{tool_name}' on MCP server {server_url} with args: {arguments}")
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(server_url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        return data["result"]
        except Exception as e:
            raise RuntimeError(f"MCP tool '{tool_name}' gagal dieksekusi: {e}") from e
        raise RuntimeError(f"MCP tool '{tool_name}' tidak mengembalikan hasil yang valid.")
