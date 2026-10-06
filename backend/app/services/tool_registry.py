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
        elif tool_entry and tool_entry.source_type == "builtin":
            output = await ToolRegistryService._execute_builtin_tool(tool_name, params)
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
    async def _execute_builtin_tool(tool_name: str, params: Dict[str, Any]) -> Any:
        if tool_name == "get_referral_status":
            ref_id = params.get("referral_id", "RJ-001")
            return {
                "referral_id": ref_id,
                "status": "Aktif" if ref_id != "RJ-9999" else "Tidak Ditemukan",
                "valid_until": "2026-12-31",
                "destination_hospital": "RS Cipto Mangunkusumo",
                "poli": "Spesialis Penyakit Dalam"
            }
        elif tool_name in ["search_hospital", "hospital_finder"]:
            city = params.get("city", "Jakarta")
            return {
                "city": city,
                "count": 3,
                "hospitals": [
                    {"name": "RS Cipto Mangunkusumo", "type": "Tipe A", "bpjs": True, "emergency_24h": True},
                    {"name": "RSUD Tarakan", "type": "Tipe B", "bpjs": True, "poli": ["Jantung", "Mata"]},
                    {"name": "RS Fatmawati", "type": "Tipe A", "bpjs": True, "inpatient_quota": 14}
                ]
            }
        elif tool_name == "find_specialist":
            specialty = params.get("specialty", "Penyakit Dalam")
            city = params.get("city", "Jakarta")
            return {
                "specialty": specialty,
                "city": city,
                "doctors": [
                    {"name": "dr. Budi Santoso, Sp.PD", "hospital": "RS Cipto Mangunkusumo", "schedule": "Senin-Kamis 09:00"},
                    {"name": "dr. Siti Rahma, Sp.PD", "hospital": "RS Fatmawati", "schedule": "Selasa-Jumat 13:00"}
                ]
            }
        elif tool_name == "check_bpjs":
            bpjs_id = params.get("bpjs_id") or params.get("hospital_id", "000123456789")
            return {
                "card_number": bpjs_id,
                "status": "AKTIF",
                "faskes_1": "Puskesmas Gambir",
                "class": "Kelas 1"
            }
        elif tool_name == "search_web":
            query = params.get("query", "")
            return {
                "query": query,
                "results": [
                    {"title": f"Hasil pencarian untuk: {query}", "snippet": f"Informasi terkini mengenai {query}."}
                ]
            }
        return {"status": "ok", "tool": tool_name, "params": params}

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

