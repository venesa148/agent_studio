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
        import os
        from app.core.config import settings

        api_base = getattr(settings, "EXTERNAL_MOCK_API_URL", None) or os.getenv("EXTERNAL_MOCK_API_URL", "https://sisters-given-cloud-nerve.trycloudflare.com")
        api_base = api_base.rstrip("/")

        # 1. get_referral_status
        if tool_name == "get_referral_status":
            ref_id = str(params.get("referral_id") or params.get("referral_no") or "RUJ-2026-0001").strip()
            
            # Skenario Harness: jika referral 9999, return NOT_FOUND untuk memicu eskalasi
            if "9999" in ref_id:
                return {
                    "referral_no": ref_id,
                    "status": "NOT_FOUND",
                    "message": f"Surat rujukan dengan nomor {ref_id} tidak ditemukan dalam basis data faskes BPJS Kesehatan."
                }
            
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    target_url = f"{api_base}/api/v1/mock-bpjs/referral-status"
                    resp = await client.post(target_url, json={"referral_no": ref_id})
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        res_dict = data if isinstance(data, dict) else resp.json()
                        if isinstance(res_dict, dict):
                            res_dict["_endpoint"] = target_url
                            res_dict["_source"] = "Live Cloudflare Web API Teman (MySQL)"
                        return res_dict
            except Exception as e:
                print(f"[Remote API Warning] referral-status fallback: {e}")

            return {
                "referral_id": ref_id,
                "status": "Aktif",
                "valid_until": "2026-12-31",
                "destination_hospital": "RSUPN Dr. Cipto Mangunkusumo",
                "poli": "Spesialis Penyakit Dalam"
            }

        # 2. search_hospital / hospital_finder
        elif tool_name in ["search_hospital", "hospital_finder"]:
            city_raw = str(params.get("city") or params.get("location") or "Jakarta").strip()
            
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    target_url = f"{api_base}/api/v1/mock-bpjs/hospitals"
                    resp = await client.post(target_url, json={"location": city_raw})
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        if data:
                            return {
                                "city": city_raw,
                                "source": "API Web Teman (MySQL 40 RS)",
                                "_endpoint": target_url,
                                "_source": "Live Cloudflare Web API Teman (MySQL)",
                                "count": len(data),
                                "hospitals": data
                            }
            except Exception as e:
                print(f"[Remote API Warning] hospitals fallback: {e}")

            # Fallback jika remote API offline
            return {
                "city": city_raw,
                "source": "Lokal Fallback",
                "count": 3,
                "hospitals": [
                    {"name": "RSUPN Dr. Cipto Mangunkusumo (RSCM)", "tipe": "RSUP / Kelas A", "mitra_bpjs": True, "kota": "Jakarta Pusat"},
                    {"name": "RSUD Tarakan", "tipe": "RSUD / Kelas B", "mitra_bpjs": True, "kota": "Jakarta Pusat"},
                    {"name": "RSUP Fatmawati", "tipe": "RSUP / Kelas A", "mitra_bpjs": True, "kota": "Jakarta Selatan"}
                ]
            }

        # 3. find_specialist
        elif tool_name == "find_specialist":
            specialty = str(params.get("specialty") or "Jantung").strip()
            city = str(params.get("city") or params.get("location") or "Jakarta").strip()
            
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    target_url = f"{api_base}/api/v1/mock-bpjs/specialists"
                    resp = await client.post(target_url, json={"specialty": specialty, "location": city})
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        if data:
                            return {
                                "specialty": specialty,
                                "city": city,
                                "source": "API Web Teman",
                                "_endpoint": target_url,
                                "_source": "Live Cloudflare Web API Teman (MySQL)",
                                "doctors": data
                            }
            except Exception as e:
                print(f"[Remote API Warning] specialists fallback: {e}")

            return {
                "specialty": specialty,
                "city": city,
                "doctors": [
                    {"nama_dokter": "dr. Andi Pratama, Sp.PD", "spesialisasi": specialty, "rumah_sakit": "RSUD Tarakan", "jadwal_praktek": "Senin - Kamis (08.00 - 12.00)"},
                    {"nama_dokter": "dr. Siti Rahma, Sp.PD", "spesialisasi": specialty, "rumah_sakit": "RSCM", "jadwal_praktek": "Rabu - Sabtu (10.00 - 14.00)"}
                ]
            }

        # 4. check_bpjs
        elif tool_name == "check_bpjs":
            bpjs_id = str(params.get("bpjs_id") or params.get("number") or params.get("hospital_id") or "1234567890123456").strip()
            
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(f"{api_base}/api/v1/mock-bpjs/check-bpjs", json={"number": bpjs_id})
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        if data:
                            return data
            except Exception as e:
                print(f"[Remote API Warning] check-bpjs fallback: {e}")

            return {
                "nik_atau_kartu": bpjs_id,
                "nama": "Budi Santoso",
                "status_kepesertaan": "AKTIF",
                "kelas_rawat": "Kelas 1",
                "faskes_tingkat_1": "Puskesmas Kecamatan Gambir",
                "eligibility": "Berhak mendapatkan pelayanan rawat jalan & inap"
            }

        # 5. search_web
        elif tool_name == "search_web":
            query = str(params.get("query") or "aturan rujukan BPJS").strip()
            
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(f"{api_base}/api/v1/mock-bpjs/search-web", json={"query": query})
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        if data:
                            return data
            except Exception as e:
                print(f"[Remote API Warning] search-web fallback: {e}")

            return {
                "query": query,
                "results": [
                    {"title": "Aturan Rujukan Faskes BPJS Kesehatan", "snippet": "Pelayanan kesehatan tingkat lanjutan harus melalui rujukan berjenjang dari FKTP kecuali kondisi gawat darurat."}
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

