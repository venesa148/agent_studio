import logging
import os
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.mcp import MCPServerModel
from app.models.tool import ToolModel
from app.services.executors.http_executor import GenericHttpExecutor
from app.services.executors.native_executor import NativePythonExecutor
from app.services.mcp_client import MCPClientService

logger = logging.getLogger("tool_registry")

# Deklarasi skema default untuk katalog showcase tools
# Seluruh pemanggilan dieksekusi secara generik & dinamis oleh GenericHttpExecutor
CATALOG_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "get_referral_status": {
        "type": "http",
        "method": "POST",
        "url": "{api_base}/api/v1/mock-bpjs/referral-status",
        "param_mapping": {"referral_id": "referral_no"},
        "source_label": "External Service API",
        "timeout_ms": 6000,
    },
    "search_hospital": {
        "type": "http",
        "method": "POST",
        "url": "{api_base}/api/v1/mock-bpjs/hospitals",
        "param_mapping": {"city": "location"},
        "source_label": "External Hospital API",
        "timeout_ms": 6000,
    },
    "search_hospitals": {
        "type": "http",
        "method": "POST",
        "url": "{api_base}/api/v1/mock-bpjs/hospitals",
        "param_mapping": {"city": "location"},
        "source_label": "External Hospital API",
        "timeout_ms": 6000,
    },
    "hospital_finder": {
        "type": "http",
        "method": "POST",
        "url": "{api_base}/api/v1/mock-bpjs/hospitals",
        "param_mapping": {"city": "location"},
        "source_label": "External Hospital API",
        "timeout_ms": 6000,
    },
    "check_bpjs": {
        "type": "http",
        "method": "POST",
        "url": "{api_base}/api/v1/mock-bpjs/check-bpjs",
        "param_mapping": {"participant_id": "number", "bpjs_id": "number", "hospital_id": "number"},
        "source_label": "External Hospital API",
        "timeout_ms": 6000,
    },
    "get_participant_status": {
        "type": "http",
        "method": "POST",
        "url": "{api_base}/api/v1/mock-bpjs/check-bpjs",
        "param_mapping": {"participant_id": "number", "bpjs_id": "number", "hospital_id": "number"},
        "source_label": "External Hospital API",
        "timeout_ms": 6000,
    },
    "create_appointment": {
        "type": "http",
        "method": "POST",
        "url": "{api_base}/api/bookings",
        "source_label": "Live Web API Appointment",
        "timeout_ms": 6000,
    },
    "get_appointment": {
        "type": "http",
        "method": "GET",
        "url": "{api_base}/api/bookings/{booking_id}",
        "param_mapping": {"id": "booking_id", "booking_code": "booking_id"},
        "source_label": "Live Web API Appointment",
        "timeout_ms": 6000,
    },
    "find_specialist": {
        "type": "http",
        "method": "GET",
        "url": "{api_base}/api/doctors/availability",
        "source_label": "External Hospital API",
        "timeout_ms": 6000,
    },
    "search_doctors": {
        "type": "http",
        "method": "GET",
        "url": "{api_base}/api/doctors/availability",
        "source_label": "External Hospital API",
        "timeout_ms": 6000,
    },
}


class ToolRegistryService:
    """
    Unified Tool Broker:
    Pintu gerbang tunggal eksekusi seluruh tools di Agent Studio.
    Merutekan eksekusi secara dinamis ke:
    1. GenericHttpExecutor (Semua REST API tools buatan builder maupun katalog)
    2. NativePythonExecutor (Algoritma deterministik lokal Python: kalkulator, triase, web search)
    3. MCPClientService (Tools eksternal Model Context Protocol)
    """

    @staticmethod
    async def get_all_tools(db: AsyncSession) -> List[ToolModel]:
        result = await db.execute(select(ToolModel).order_by(ToolModel.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def resolve_api_base(db: AsyncSession, tool_entry: Optional[ToolModel] = None) -> str:
        """
        Resolusi dinamis api_base tanpa hardcoding:
        1. Cek konfigurasi x-api-config atau x-openapi dari input_schema tool
        2. Cek mcp_server_id dari tool_entry
        3. Cek server MCP eksternal yang aktif/terhubung di database
        4. Fallback ke settings.EXTERNAL_MOCK_API_URL / environment variable
        """
        api_base: Optional[str] = None

        if tool_entry and tool_entry.input_schema:
            api_base = (
                tool_entry.input_schema.get("x-api-config", {}).get("base_url")
                or tool_entry.input_schema.get("x-openapi", {}).get("server_url")
                or tool_entry.input_schema.get("base_url")
            )

        if not api_base and tool_entry and tool_entry.mcp_server_id:
            mcp_res = await db.execute(select(MCPServerModel).where(MCPServerModel.id == tool_entry.mcp_server_id))
            mcp_srv = mcp_res.scalar_one_or_none()
            if mcp_srv and mcp_srv.url and not mcp_srv.url.endswith("/local-server"):
                api_base = mcp_srv.url

        if not api_base:
            ext_mcp_res = await db.execute(
                select(MCPServerModel).where(
                    MCPServerModel.status == "connected",
                    MCPServerModel.url.notlike("%/local-server%"),
                    MCPServerModel.url.notlike("%localhost:8080%"),
                ).order_by(MCPServerModel.updated_at.desc())
            )
            ext_srv = ext_mcp_res.scalars().first()
            if ext_srv and ext_srv.url:
                api_base = ext_srv.url

        if not api_base:
            api_base = (
                getattr(settings, "EXTERNAL_MOCK_API_URL", None)
                or os.getenv("EXTERNAL_MOCK_API_URL", "")
            )

        return str(api_base or "").rstrip("/")

    @staticmethod
    async def execute_tool(db: AsyncSession, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mengeksekusi tool secara dinamis berdasarkan metadata registrasi di database.
        """
        start_time = time.time()

        # 1. Cari registrasi tool di database
        result = await db.execute(select(ToolModel).where(ToolModel.name == tool_name))
        tool_entry = result.scalar_one_or_none()

        output: Any = None

        # 2. Penanganan Tool Khusus: api_fetch / http_request (Generic Dynamic REST Invoker)
        if tool_name in ("api_fetch", "http_request"):
            url = str(params.get("url") or "").strip()
            method = str(params.get("method") or "GET").upper()
            dynamic_impl = {
                "type": "http",
                "method": method,
                "url": url,
                "headers": params.get("headers") or {},
                "timeout_ms": 10000,
            }
            body_payload = params.get("body")
            exec_params = body_payload if isinstance(body_payload, dict) else params
            output = await GenericHttpExecutor.execute(dynamic_impl, exec_params, source_label=f"REST API ({method})")

        # 3. Prioritas A: Tool dengan konfigurasi deklaratif eksplisit (Tool Factory buatan Builder)
        elif tool_entry and tool_entry.implementation and tool_entry.implementation.get("type") == "http":
            api_base = await ToolRegistryService.resolve_api_base(db, tool_entry)
            output = await GenericHttpExecutor.execute(
                tool_entry.implementation,
                params,
                api_base=api_base,
                source_label=f"Declarative HTTP Tool ({tool_name})",
            )

        # 4. Prioritas B: Native Python Function (Kalkulator, Triase, Web Search)
        elif NativePythonExecutor.can_handle(tool_name):
            output = await NativePythonExecutor.execute(tool_name, params)

        # 5. Prioritas C: MCP Tool Server (JSON-RPC)
        elif tool_entry and tool_entry.source_type == "mcp" and tool_entry.mcp_server_id:
            mcp_result = await db.execute(select(MCPServerModel).where(MCPServerModel.id == tool_entry.mcp_server_id))
            mcp_server = mcp_result.scalar_one_or_none()
            if not mcp_server:
                raise ValueError(f"MCP server untuk tool '{tool_name}' tidak ditemukan.")
            try:
                output = await MCPClientService.call_tool(mcp_server.url, tool_name, params)
            except Exception:
                # Fallback ke catalog schema jika server MCP offline
                if tool_name in CATALOG_TOOL_SCHEMAS:
                    api_base = await ToolRegistryService.resolve_api_base(db, tool_entry)
                    output = await GenericHttpExecutor.execute(
                        CATALOG_TOOL_SCHEMAS[tool_name],
                        params,
                        api_base=api_base,
                    )
                else:
                    raise

        # 6. Prioritas D: OpenAPI Spec Tool
        elif tool_entry and tool_entry.source_type == "openapi":
            schema = tool_entry.input_schema or {}
            config = schema.get("x-openapi", {})
            server_url = (config.get("server_url") or "").rstrip("/")
            path = config.get("path") or ""
            method = (config.get("method") or "GET").upper()
            full_url = f"{server_url}{path}"
            openapi_impl = {
                "type": "http",
                "method": method,
                "url": full_url,
                "timeout_ms": 15000,
            }
            output = await GenericHttpExecutor.execute(
                openapi_impl, params, source_label=f"OpenAPI ({tool_entry.name})"
            )

        # 7. Prioritas E: Catalog Tool Schema (Katalog umum BPJS/Faskes yang dieksekusi secara generik)
        elif tool_name in CATALOG_TOOL_SCHEMAS:
            api_base = await ToolRegistryService.resolve_api_base(db, tool_entry)
            output = await GenericHttpExecutor.execute(
                CATALOG_TOOL_SCHEMAS[tool_name],
                params,
                api_base=api_base,
            )

        else:
            if not tool_entry:
                raise ValueError(f"Tool '{tool_name}' tidak terdaftar dalam registry.")
            raise ValueError(f"Tool '{tool_name}' tidak memiliki eksekutor yang valid.")

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "name": tool_name,
            "params": params,
            "result": output,
            "duration_ms": duration_ms,
        }
