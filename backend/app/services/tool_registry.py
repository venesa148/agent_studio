from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any, Optional
import time
import httpx
from app.models.tool import ToolModel
from app.models.mcp import MCPServerModel
from app.services.mcp_client import MCPClientService

class ToolRegistryService:

    @staticmethod
    async def get_all_tools(db: AsyncSession) -> List[ToolModel]:
        result = await db.execute(select(ToolModel).order_by(ToolModel.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def execute_tool(db: AsyncSession, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mengeksekusi tool berdasarkan registrasi di catalog (baik built-in maupun MCP tool).
        """
        start_time = time.time()
        
        # Cari info tool dari database
        result = await db.execute(select(ToolModel).where(ToolModel.name == tool_name))
        tool_entry = result.scalar_one_or_none()

        output: Any = None

        if not tool_entry or not tool_entry.is_active:
            raise ValueError(f"Tool '{tool_name}' tidak terdaftar atau tidak aktif.")
        if tool_entry.source_type == "mcp" and tool_entry.mcp_server_id:
            # Ambil detail MCP Server
            mcp_result = await db.execute(select(MCPServerModel).where(MCPServerModel.id == tool_entry.mcp_server_id))
            mcp_server = mcp_result.scalar_one_or_none()
            if not mcp_server:
                raise ValueError(f"MCP server untuk tool '{tool_name}' tidak ditemukan.")
            server_url = mcp_server.url
            output = await MCPClientService.call_tool(server_url, tool_name, params)
        elif tool_entry and tool_entry.source_type == "openapi":
            output = await ToolRegistryService._execute_openapi_tool(tool_entry, params)
        else:
            raise ValueError(f"Tool '{tool_name}' tidak memiliki executor yang didukung.")

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "name": tool_name,
            "params": params,
            "result": output,
            "duration_ms": duration_ms
        }

    @staticmethod
    async def _execute_openapi_tool(tool_entry: ToolModel, params: Dict[str, Any]) -> Any:
        schema = tool_entry.input_schema or {}
        config = schema.get("x-openapi", {})
        if not config.get("server_url") or not config.get("path"):
            return {"status": "error", "message": "OpenAPI tool configuration is incomplete."}
        locations = config.get("parameter_locations", {})
        path = config["path"]
        query, body = {}, None
        for name, value in params.items():
            location = locations.get(name, "query")
            if location == "path":
                path = path.replace("{" + name + "}", str(value))
            elif location == "body":
                body = value
            elif location == "header":
                continue  # credentials stay out of the registry and need a future vault integration
            else:
                query[name] = value
        base = config["server_url"].rstrip("/")
        url = base + path if path.startswith("/") else base + "/" + path
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(config.get("method", "GET"), url, params=query, json=body)
                response.raise_for_status()
                return response.json() if response.content else {"status": "success"}
        except (httpx.HTTPError, ValueError) as exc:
            return {"status": "error", "message": f"OpenAPI request failed: {exc}"}

