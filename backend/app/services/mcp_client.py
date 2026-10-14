"""
Formal Model Context Protocol (MCP) Client Service:
Mengimplementasikan spesifikasi formal MCP Protocol JSON-RPC 2.0 (2024-11-05):
1. Handshake & Capability Negotiation ('initialize')
2. Liveness Check ('ping')
3. Dynamic Tool Discovery ('tools/list') dengan normalisasi skema input
4. Tool Invocation ('tools/call') dengan parsing content multi-part & pemetaan error standar.
100% Dinamis dan Domain-Agnostik.
"""

import httpx
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("mcp_client")

MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {
    "name": "agent-studio-orchestrator",
    "version": "1.0.0"
}


class MCPProtocolError(Exception):
    """Exception khusus untuk error spesifikasi JSON-RPC 2.0 MCP."""
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        super().__init__(f"MCP Error [{code}]: {message}")
        self.code = code
        self.message = message
        self.data = data


class MCPClientService:
    @staticmethod
    async def initialize(server_url: str, timeout: float = 6.0) -> Dict[str, Any]:
        """
        Melakukan formal JSON-RPC 2.0 Handshake ('initialize') ke MCP Server.
        Menegosiasikan capabilities dan memverifikasi kesesuaian protokol.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {},
                    "prompts": {}
                },
                "clientInfo": CLIENT_INFO
            }
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(server_url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if "error" in data:
                        err = data["error"]
                        raise MCPProtocolError(err.get("code", -32603), err.get("message", "Handshake failed"))
                    result = data.get("result", {})
                    return {
                        "status": "connected",
                        "protocol_version": result.get("protocolVersion", MCP_PROTOCOL_VERSION),
                        "server_info": result.get("serverInfo", {}),
                        "capabilities": result.get("capabilities", {}),
                        "server_url": server_url
                    }
                else:
                    raise RuntimeError(f"Server mengembalikan HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"MCP Handshake ke {server_url} gagal: {e}")
            raise RuntimeError(f"Gagal inisialisasi koneksi MCP ke '{server_url}': {str(e)}") from e

    @staticmethod
    async def ping(server_url: str, timeout: float = 3.0) -> bool:
        """Memeriksa liveness server MCP melalui metode ping JSON-RPC."""
        payload = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "ping",
            "params": {}
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(server_url, json=payload)
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def discover_tools(server_url: str, timeout: float = 8.0) -> List[Dict[str, Any]]:
        """
        Mengambil daftar tools dari MCP Server via JSON-RPC 'tools/list'.
        Melakukan normalisasi skema (mengubah inputSchema MCP menjadi dictionary siap pakai).
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(server_url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if "error" in data:
                        err = data["error"]
                        raise MCPProtocolError(err.get("code", -32603), err.get("message", "tools/list failed"))

                    raw_tools = data.get("result", {}).get("tools", [])
                    normalized = []
                    for t in raw_tools:
                        tool_item = {
                            "name": t.get("name"),
                            "description": t.get("description", ""),
                            "input_schema": t.get("inputSchema") or t.get("input_schema") or {"type": "object", "properties": {}},
                            "source_type": "mcp",
                            "effect": t.get("effect", "read")
                        }
                        normalized.append(tool_item)
                    return normalized
                else:
                    raise RuntimeError(f"HTTP {resp.status_code} saat discover_tools: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Gagal mengambil tools dari MCP server '{server_url}': {e}")
            raise RuntimeError(f"Tidak dapat mengambil tools dari MCP server '{server_url}': {e}") from e

    @staticmethod
    async def call_tool(server_url: str, tool_name: str, arguments: Dict[str, Any], timeout: float = 12.0) -> Dict[str, Any]:
        """
        Mengeksekusi pemanggilan tool via JSON-RPC 'tools/call'.
        Mendukung parsing multi-content (text, data, embedded) dan standard error mapping.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(server_url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()

                    # Cek apakah ada JSON-RPC error
                    if "error" in data:
                        err = data["error"]
                        code = err.get("code", -32603)
                        msg = err.get("message", "Unknown MCP execution error")
                        logger.warning(f"MCP Server error saat eksekusi '{tool_name}': {msg} (code={code})")
                        return {
                            "status": "error",
                            "error_type": "MCP_PROTOCOL_ERROR",
                            "code": code,
                            "message": msg,
                            "_source": f"MCP: {server_url}",
                            "_endpoint": server_url
                        }

                    # Cek result
                    res = data.get("result", {})
                    # Parsing Model Context Protocol content blocks
                    if isinstance(res, dict) and "content" in res and isinstance(res["content"], list):
                        text_blocks = [
                            c.get("text", "") for c in res["content"]
                            if isinstance(c, dict) and c.get("type") == "text"
                        ]
                        output_text = "\n".join(text_blocks)
                        return {
                            "status": "ok",
                            "output": output_text,
                            "data": res.get("data", {}),
                            "raw_content": res["content"],
                            "_source": f"MCP: {server_url}",
                            "_endpoint": server_url
                        }

                    if isinstance(res, dict):
                        res.setdefault("status", "ok")
                        res["_source"] = f"MCP: {server_url}"
                        res["_endpoint"] = server_url
                        return res

                    return {
                        "status": "ok",
                        "result": res,
                        "_source": f"MCP: {server_url}",
                        "_endpoint": server_url
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Server MCP mengembalikan status HTTP {resp.status_code}",
                        "_source": f"MCP: {server_url}",
                        "_endpoint": server_url
                    }
        except httpx.TimeoutException:
            return {
                "status": "error",
                "message": f"Timeout {timeout}s saat memanggil MCP tool '{tool_name}' di {server_url}",
                "_source": f"MCP: {server_url}",
                "_endpoint": server_url
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Gagal memanggil MCP tool '{tool_name}': {str(e)}",
                "_source": f"MCP: {server_url}",
                "_endpoint": server_url
            }
