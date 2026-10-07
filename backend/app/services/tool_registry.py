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
            city_raw = params.get("city", "Jakarta")
            city_norm = str(city_raw).lower().strip()

            hospitals_database = {
                "pusat": [
                    {"name": "RSUP Nasional Cipto Mangunkusumo (RSCM)", "type": "Tipe A", "bpjs": True, "emergency_24h": True, "address": "Jl. Diponegoro No. 71, Jakarta Pusat"},
                    {"name": "RSUD Tarakan", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "poli": ["Jantung", "Mata", "Bedah"], "address": "Jl. Kyai Caringin, Gambir, Jakarta Pusat"},
                    {"name": "RS PGI Cikini", "type": "Tipe B", "bpjs": True, "emergency_24h": False, "poli": ["Penyakit Dalam", "Ginjal"], "address": "Jl. Raden Saleh No. 40, Jakarta Pusat"}
                ],
                "selatan": [
                    {"name": "RSUP Fatmawati", "type": "Tipe A", "bpjs": True, "emergency_24h": True, "inpatient_quota": 14, "address": "Jl. RS Fatmawati, Cilandak, Jakarta Selatan"},
                    {"name": "RSUD Pasar Minggu", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "poli": ["Anak", "Kebidanan"], "address": "Jl. TB Simatupang No. 1, Jakarta Selatan"},
                    {"name": "RS Siloam Hospitals TB Simatupang", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "poli": ["Jantung", "Saraf"], "address": "Jl. RA Kartini No. 8, Jakarta Selatan"}
                ],
                "barat": [
                    {"name": "RSUD Cengkareng", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "address": "Jl. Bumi Cengkareng Indah, Jakarta Barat"},
                    {"name": "RS Pelni", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "poli": ["Jantung", "Paru"], "address": "Jl. Aipda KS Tubun No. 92, Jakarta Barat"}
                ],
                "timur": [
                    {"name": "RSUP Persahabatan", "type": "Tipe A", "bpjs": True, "emergency_24h": True, "poli": ["Respirasi", "Paru"], "address": "Jl. Persahabatan Raya, Rawamangun, Jakarta Timur"},
                    {"name": "RSUD Pasar Rebo", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "address": "Jl. TB Simatupang No. 30, Jakarta Timur"}
                ],
                "utara": [
                    {"name": "RSUD Koja", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "address": "Jl. Deli No. 4, Tanjung Priok, Jakarta Utara"},
                    {"name": "RS Pelabuhan Jakarta", "type": "Tipe C", "bpjs": True, "emergency_24h": True, "address": "Jl. Kramat Jaya, Koja, Jakarta Utara"}
                ],
                "surabaya": [
                    {"name": "RSUD Dr. Soetomo", "type": "Tipe A", "bpjs": True, "emergency_24h": True, "address": "Jl. Mayjen Prof. Dr. Moestopo No. 6-8, Surabaya"},
                    {"name": "RS Universitas Airlangga (RSUA)", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "address": "Kampus C Unair, Mulyorejo, Surabaya"}
                ],
                "bandung": [
                    {"name": "RSUP Dr. Hasan Sadikin (RSHS)", "type": "Tipe A", "bpjs": True, "emergency_24h": True, "address": "Jl. Pasteur No. 38, Bandung"},
                    {"name": "RSUD Kota Bandung", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "address": "Jl. Rumah Sakit No. 22, Ujung Berung, Bandung"}
                ]
            }

            # Filter data rumah sakit sesuai daerah yang diminta
            matched_hospitals = None
            for key, h_list in hospitals_database.items():
                if key in city_norm or (key == "selatan" and ("jaksel" in city_norm or "jak sel" in city_norm)) or (key == "pusat" and ("jakpus" in city_norm or "jak pus" in city_norm)) or (key == "barat" and ("jakbar" in city_norm or "jak bar" in city_norm)) or (key == "timur" and ("jaktim" in city_norm or "jak tim" in city_norm)) or (key == "utara" and ("jakut" in city_norm or "jak ut" in city_norm)):
                    matched_hospitals = h_list
                    break

            if not matched_hospitals:
                # Default fallback jika hanya disebut 'Jakarta' umum
                if "jakarta" in city_norm:
                    matched_hospitals = [
                        {"name": "RSUP Nasional Cipto Mangunkusumo", "type": "Tipe A", "bpjs": True, "emergency_24h": True, "region": "Jakarta Pusat"},
                        {"name": "RSUP Fatmawati", "type": "Tipe A", "bpjs": True, "emergency_24h": True, "region": "Jakarta Selatan"},
                        {"name": "RSUD Tarakan", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "region": "Jakarta Pusat"}
                    ]
                else:
                    matched_hospitals = [
                        {"name": f"RSUD {city_raw.title()}", "type": "Tipe B", "bpjs": True, "emergency_24h": True, "address": f"Jl. Kesehatan Utama No. 1, {city_raw.title()}"},
                        {"name": f"RS Harapan Sehat {city_raw.title()}", "type": "Tipe C", "bpjs": True, "emergency_24h": True, "address": f"Jl. Merdeka No. 45, {city_raw.title()}"}
                    ]

            return {
                "city": city_raw,
                "count": len(matched_hospitals),
                "hospitals": matched_hospitals
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

