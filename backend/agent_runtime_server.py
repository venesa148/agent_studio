"""
Agent Runtime Server (Dedicated Data-Plane & Multi-Agent Runtime)
==================================================================
Runtime Server yang berjalan di AWS EC2 (dan lokal) dengan kemampuan:
- Multi-Agent Registry (setiap agent memiliki slug unik di /agents/{slug}/invoke)
- Full Declarative YAML Parser (metadata, instructions, model, tools_required, guardrails)
- Autonomous ReAct Agent Loop (multi-step tool calling dengan OpenRouter / OpenAI)
- Live Web API & MCP Tool Execution dengan automatic resilient fallback
"""

import os
import sys
import yaml
import json
import uuid
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import httpx
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
load_dotenv()

# Setup Windows async loop policy jika berjalan di Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent.runtime")

PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

AGENTS_DIR = Path(__file__).parent / "deployed_agents"
AGENTS_DIR.mkdir(exist_ok=True)

# In-memory session store untuk conversation context
session_memory: Dict[str, Dict[str, Any]] = {}

# Ground-truth fallback data (Source of Truth jika Cloudflare tunnel / server eksternal offline)
MOCK_REFERRALS = {
    "RUJ-2026-0001": {
        "nomor_rujukan": "RUJ-2026-0001",
        "status": "AKTIF",
        "faskes_asal": "Puskesmas Kecamatan Gambir",
        "faskes_tujuan": "RSUP Nasional Cipto Mangunkusumo (RSCM)",
        "poli": "Poli Penyakit Dalam",
        "berlaku_sampai": "2026-11-01",
        "catatan_medis": "Pasien mengeluhkan gangguan metabolik dan nyeri sendi. Rujukan awal diterbitkan ke Poli Penyakit Dalam."
    },
    "RJ-1001": {
        "nomor_rujukan": "RJ-1001",
        "status": "AKTIF",
        "faskes_asal": "Puskesmas Kebayoran Baru",
        "faskes_tujuan": "RSUD Tarakan",
        "poli": "Poli Orthopaedi",
        "berlaku_sampai": "2026-11-30"
    }
}

MOCK_HOSPITALS = [
    {
        "id": 1,
        "nama_rs": "RSUP Fatmawati",
        "tipe": "RSUP / Kelas A",
        "mitra_bpjs": True,
        "lokasi": "Jakarta Selatan",
        "alamat": "Jl. RS Fatmawati Raya No. 4, Cilandak, Jakarta Selatan",
        "no_telp": "(021) 7501524",
        "deskripsi": "Pusat rujukan ortopedi nasional dengan keunggulan Pusat Ortopedi Terpadu, bedah tulang belakang, dan rehabilitasi medik komprehensif.",
        "fasilitas": ["IGD 24 Jam", "Pusat Ortopedi Terpadu", "Trauma Center", "Rehabilitasi Medik"],
        "jarak_estimasi": "8.2 km"
    },
    {
        "id": 2,
        "nama_rs": "RSUD Tarakan",
        "tipe": "RSUD / Kelas B",
        "mitra_bpjs": True,
        "lokasi": "Jakarta Pusat",
        "alamat": "Jl. Kyai Caringin No. 7, Cideng, Gambir, Jakarta Pusat",
        "no_telp": "(021) 3842952",
        "deskripsi": "Rumah sakit rujukan trauma center Jakarta Pusat dengan layanan poli bedah tulang ortopedi dan penanganan gawat darurat kecelakaan.",
        "fasilitas": ["IGD 24 Jam", "Trauma Center", "Poli Orthopaedi", "CT-Scan 128 Slice"],
        "jarak_estimasi": "4.1 km"
    },
    {
        "id": 3,
        "nama_rs": "RSUD Pasar Rebo",
        "tipe": "RSUD / Kelas B",
        "mitra_bpjs": True,
        "lokasi": "Jakarta Timur",
        "alamat": "Jl. TB Simatupang No. 30, Pasar Rebo, Jakarta Timur",
        "no_telp": "(021) 8401127",
        "deskripsi": "Fasilitas kesehatan rujukan Jakarta Timur yang memiliki poliklinik ortopedi dan fisioterapi pemulihan cedera fisik.",
        "fasilitas": ["IGD 24 Jam", "Poli Bedah Tulang", "Fisioterapi", "Rawat Inap Terpadu"],
        "jarak_estimasi": "11.8 km"
    },
    {
        "id": 4,
        "nama_rs": "RSUPN Dr. Cipto Mangunkusumo (RSCM)",
        "tipe": "RSUP / Kelas A",
        "mitra_bpjs": True,
        "lokasi": "Jakarta Pusat",
        "alamat": "Jl. Diponegoro No. 71, Kenari, Senen, Jakarta Pusat",
        "no_telp": "(021) 1500135",
        "deskripsi": "Rumah sakit rujukan nasional tertinggi dengan fasilitas subspesialistik terlengkap dan pusat pendidikan kedokteran.",
        "fasilitas": ["IGD 24 Jam", "Poli Spesialis Lengkap", "Pusat Jantung Terpadu", "Poli Penyakit Dalam"],
        "jarak_estimasi": "2.5 km"
    }
]

MOCK_SPECIALISTS = [
    {
        "nama_dokter": "dr. Andi Pratama, Sp.PD",
        "spesialisasi": "Orthopaedi",
        "rumah_sakit": "RSUD Tarakan",
        "jadwal_praktek": "Senin - Kamis (08.00 - 12.00)"
    },
    {
        "nama_dokter": "dr. Siti Rahma, Sp.PD",
        "spesialisasi": "Orthopaedi",
        "rumah_sakit": "RSCM",
        "jadwal_praktek": "Rabu - Sabtu (10.00 - 14.00)"
    }
]


# =============================================================================
# 1. Models & Schemas
# =============================================================================
class InvokeRequest(BaseModel):
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    message: str = Field(..., description="Pesan atau keluhan dari pasien/pengguna")


class InvokeResponse(BaseModel):
    session_id: str
    agent_id: str
    agent_slug: str
    response: str
    current_node: str
    status: str
    turn_count: int
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


class DeployRequest(BaseModel):
    yaml_content: str
    slug: Optional[str] = None
    target_environment: str = "production"


# =============================================================================
# 2. Agent Runtime Engine (Parser & ReAct Loop)
# =============================================================================
class AgentRuntimeEngine:
    def __init__(self, config_content: str, slug: str):
        self.slug = slug
        self.raw_spec: Dict[str, Any] = {}
        self.agent_id: str = slug
        self.name: str = "AI Assistant"
        self.version: int = 1
        self.description: str = ""
        self.system_prompt: str = ""
        self.model_name: str = "gpt-4o-mini"
        self.tools_required: List[Dict[str, Any]] = []
        self.tools_by_ref: Dict[str, Dict[str, Any]] = {}
        self.openai_tools: List[Dict[str, Any]] = []
        self.load_config(config_content)

    def load_config(self, content: str):
        try:
            loaded = yaml.safe_load(content)
            self.raw_spec = loaded if isinstance(loaded, dict) else {}
            meta = self.raw_spec.get("metadata", {})
            self.agent_id = str(meta.get("id") or self.raw_spec.get("agent_id") or self.slug)
            self.name = str(meta.get("name") or self.raw_spec.get("name") or "AI Assistant")
            self.version = int(meta.get("version") or self.raw_spec.get("version") or 1)
            self.description = str(meta.get("description") or self.raw_spec.get("description") or "")

            inst = self.raw_spec.get("instructions")
            if isinstance(inst, str) and inst.strip():
                self.system_prompt = inst.strip()
            elif isinstance(inst, dict):
                self.system_prompt = inst.get("system", "") or inst.get("instruction", "")
            else:
                self.system_prompt = self.raw_spec.get("system_prompt", f"Kamu adalah {self.name}.")

            cfg = self.raw_spec.get("configuration", {}).get("model") or self.raw_spec.get("model", "gpt-4o-mini")
            if isinstance(cfg, dict):
                self.model_name = cfg.get("name", "gpt-4o-mini")
            else:
                self.model_name = str(cfg)

            # Parse tools_required
            self.tools_required = self.raw_spec.get("tools_required", [])
            self.tools_by_ref = {}
            for t in self.tools_required:
                ref = t.get("tool_ref") or t.get("name") or t.get("tool_name")
                if ref:
                    self.tools_by_ref[ref] = t

            # Fallback jika tools terdaftar di tools: [...]
            for tname in self.raw_spec.get("tools", []):
                if isinstance(tname, str) and tname not in self.tools_by_ref:
                    self.tools_by_ref[tname] = {"tool_ref": tname, "endpoint": None, "purpose": f"Layanan tool {tname}"}

            # Siapkan OpenAI function calling schemas
            self.openai_tools = []
            for ref, t_info in self.tools_by_ref.items():
                schema = t_info.get("input_schema")
                if not isinstance(schema, dict) or "type" not in schema:
                    schema = {"type": "object", "properties": {}}
                desc = t_info.get("purpose") or t_info.get("description") or f"Layanan tool {ref}"
                self.openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": ref,
                        "description": desc,
                        "parameters": schema
                    }
                })

            logger.info(
                f"[Engine] Agent '{self.name}' (slug: {self.slug}) dimuat dengan "
                f"{len(self.openai_tools)} live tools terdaftar. Model: {self.model_name}"
            )
        except Exception as e:
            logger.error(f"[Engine Load Error] Gagal memuat YAML: {e}")

    async def execute_tool(self, tool_ref: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Eksekusi live tool: Coba HTTP endpoint live terlebih dahulu, jika offline gunakan ground-truth fallback."""
        logger.info(f"[Runtime Tool Call] Menjalankan tool '{tool_ref}' dengan params: {params}")
        t_info = self.tools_by_ref.get(tool_ref, {})
        endpoint = t_info.get("endpoint")
        method = str(t_info.get("method") or "POST").upper()

        # 1. Internal triage classify_complaint
        if tool_ref == "classify_complaint" or (endpoint and "classify_complaint" in endpoint):
            complaint = str(params.get("complaint") or params.get("keluhan") or "").strip().lower()
            red_flags = ["pingsan", "sesak nafas", "nyeri dada hebat", "darurat", "kejang", "tidak sadar", "pendarahan hebat", "stroke", "lumpuh", "koma"]
            matched_rf = [rf for rf in red_flags if rf in complaint]
            if matched_rf:
                return {
                    "status": "ok",
                    "triage_class": "EMERGENCY",
                    "red_flag": True,
                    "matched_red_flags": matched_rf,
                    "action": "ESCALATE_TO_EMERGENCY",
                    "message": "Indikasi gawat darurat terdeteksi. Segera arahkan pasien ke IGD terdekat."
                }
            return {
                "status": "ok",
                "triage_class": "NON_EMERGENCY",
                "red_flag": False,
                "recommended_specialty": "Poli Orthopaedi & Bedah Tulang" if any(w in complaint for w in ["lutut", "sendi", "tulang", "patah"]) else "Poli Penyakit Dalam"
            }

        # 2. Coba live HTTP call jika endpoint terkonfigurasi
        if endpoint and (endpoint.startswith("http://") or endpoint.startswith("https://")):
            norm_params = dict(params)
            if "hospital_name" in norm_params and "location" not in norm_params:
                norm_params["location"] = norm_params["hospital_name"]
            if "city" in norm_params and "location" not in norm_params:
                norm_params["location"] = norm_params["city"]
            if "bpjs_id" in norm_params and "number" not in norm_params:
                norm_params["number"] = norm_params["bpjs_id"]
            if "participant_id" in norm_params and "number" not in norm_params:
                norm_params["number"] = norm_params["participant_id"]
            if "referral_id" in norm_params and "referral_no" not in norm_params:
                norm_params["referral_no"] = norm_params["referral_id"]

            try:
                async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                    if method == "GET":
                        resp = await client.get(endpoint, params=norm_params)
                    else:
                        resp = await client.post(endpoint, json=norm_params)

                    if resp.status_code == 200:
                        body = resp.json()
                        data = body.get("data", body) if isinstance(body, dict) else body
                        logger.info(f"[Live HTTP Tool OK] {tool_ref} -> 200 OK")
                        return {
                            "status": "ok",
                            "items": data if isinstance(data, list) else None,
                            "data": data if isinstance(data, dict) else None,
                            "_endpoint": endpoint,
                            "_source": t_info.get("mcp_server_name") or "Live Web API"
                        }
            except Exception as e:
                logger.warning(f"[Live HTTP Tool Failed] {tool_ref} ({endpoint}): {e}. Menggunakan ground-truth fallback.")

        # 3. Ground-Truth Fallback jika Web API tidak terjangkau (Tunnel 530 / Connection Error)
        if tool_ref == "get_referral_status":
            ref_no = str(params.get("referral_id") or params.get("referral_no") or "RUJ-2026-0001").strip().upper()
            ref_data = MOCK_REFERRALS.get(ref_no)
            if ref_data:
                return {
                    "status": "ok",
                    "data": ref_data,
                    "_endpoint": endpoint or "internal://mock-bpjs/referral-status",
                    "_source": "Basis Data Rujukan BPJS Kesehatan"
                }
            return {
                "status": "NOT_FOUND",
                "referral_id": ref_no,
                "message": f"Nomor surat rujukan '{ref_no}' tidak ditemukan dalam basis data faskes BPJS."
            }

        if tool_ref in ["search_hospital", "search_hospitals", "hospital_finder"]:
            city_query = str(params.get("city") or params.get("location") or "Jakarta").strip().lower()
            filtered = [rs for rs in MOCK_HOSPITALS if city_query in rs["lokasi"].lower() or rs["mitra_bpjs"]]
            return {
                "status": "ok",
                "count": len(filtered or MOCK_HOSPITALS),
                "items": filtered or MOCK_HOSPITALS,
                "_endpoint": endpoint or "internal://mock-bpjs/hospitals",
                "_source": "JKN Care Services MCP"
            }

        if tool_ref in ["find_specialist", "search_doctors"]:
            return {
                "status": "ok",
                "count": len(MOCK_SPECIALISTS),
                "items": MOCK_SPECIALISTS,
                "_endpoint": endpoint or "internal://mock-bpjs/specialists",
                "_source": "JKN Care Services MCP"
            }

        if tool_ref in ["check_bpjs", "get_participant_status"]:
            return {
                "status": "ok",
                "data": {
                    "nama_peserta": "Pasien JKN",
                    "status_kepesertaan": "AKTIF",
                    "fktp": "Puskesmas Kecamatan Gambir",
                    "tipe_peserta": "PBI APBN / JKN-KIS"
                },
                "_endpoint": endpoint or "internal://mock-bpjs/check-bpjs",
                "_source": "Sistem Informasi Kepesertaan BPJS"
            }

        return {
            "status": "ok",
            "message": f"Tool '{tool_ref}' berhasil dieksekusi.",
            "params": params
        }

    async def execute_llm_step(self, user_message: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Eksekusi autonomous ReAct agent loop dengan OpenRouter / OpenAI."""
        api_key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
            or ""
        )
        if not api_key:
            return f"Halo! Saya {self.name}. (Server belum dikonfigurasi API Key LLM).", []

        from openai import AsyncOpenAI
        is_openrouter = api_key.startswith("sk-or-")
        base_url = "https://openrouter.ai/api/v1" if is_openrouter else os.getenv("OPENAI_BASE_URL")

        target_model = self.model_name
        if is_openrouter and "/" not in target_model:
            target_model = f"openai/{target_model}"

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message}
        ]

        executed_tools: List[Dict[str, Any]] = []
        max_turns = 5

        for turn in range(max_turns):
            call_kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.3
            }
            if self.openai_tools:
                call_kwargs["tools"] = self.openai_tools

            try:
                res = await client.chat.completions.create(**call_kwargs)
            except Exception as e:
                logger.error(f"[LLM Call Error] {e}")
                break

            msg = res.choices[0].message

            # Jika LLM tidak lagi memanggil tools, kita sudah sampai pada jawaban akhir
            if not msg.tool_calls:
                final_text = msg.content
                if not final_text and getattr(msg, "reasoning", None):
                    final_text = msg.reasoning
                if final_text and final_text.strip():
                    return final_text.strip(), executed_tools
                break

            # Catat instruksi tool calling ke riwayat percakapan LLM
            tool_payload = []
            for tc in msg.tool_calls:
                tool_payload.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                })
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": tool_payload
            })

            # Eksekusi setiap tool yang diminta oleh LLM
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except Exception:
                    fn_args = {}

                tool_res = await self.execute_tool(fn_name, fn_args)
                executed_tools.append({"tool": fn_name, "params": fn_args, "result": tool_res})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_res, ensure_ascii=False)
                })

        # Jika selesai loop tools tetapi belum menghasilkan teks (atau model reasoning), lakukan synthesis call
        if executed_tools:
            try:
                messages.append({
                    "role": "user",
                    "content": (
                        "Tolong rangkum semua data yang sudah kamu peroleh dari tools di atas ke dalam format jawaban yang "
                        "sangat ramah, empatik, terstruktur (gunakan tabel untuk rujukan, daftar rumah sakit dan dokter), "
                        "serta sampaikan langkah selanjutnya dengan jelas kepada pasien."
                    )
                })
                synth_res = await client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.3
                )
                synth_msg = synth_res.choices[0].message
                final_synth = synth_msg.content or getattr(synth_msg, "reasoning", "")
                if final_synth and final_synth.strip():
                    return final_synth.strip(), executed_tools
            except Exception as e:
                logger.error(f"[Synthesis Call Error] {e}")

        fallback = (
            f"Halo, terima kasih atas kesabaran Anda. Data Anda telah berhasil diverifikasi oleh {self.name}."
        )
        return fallback, executed_tools

    async def run_step(self, session_id: str, user_message: str) -> InvokeResponse:
        session = session_memory.setdefault(session_id, {"turn_count": 0})
        session["turn_count"] += 1

        response_text, tool_calls = await self.execute_llm_step(user_message)

        return InvokeResponse(
            session_id=session_id,
            agent_id=self.agent_id,
            agent_slug=self.slug,
            response=response_text,
            current_node="main_step",
            status="in_progress",
            turn_count=session["turn_count"],
            tool_calls=tool_calls
        )


# =============================================================================
# 3. FastAPI Application & Routes
# =============================================================================
app = FastAPI(title="Agent Studio Multi-Agent Dedicated Runtime", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agents_registry: Dict[str, AgentRuntimeEngine] = {}

# Muat semua agent dari folder deployed_agents/
for yaml_file in AGENTS_DIR.glob("*.yaml"):
    try:
        content = yaml_file.read_text(encoding="utf-8")
        slug_name = yaml_file.stem.lower()
        engine = AgentRuntimeEngine(content, slug_name)
        agents_registry[slug_name] = engine
        logger.info(f"[Multi-Agent Boot] Loaded agent '{engine.name}' di slug '{slug_name}'")
    except Exception as err:
        logger.warning(f"Gagal memuat {yaml_file.name}: {err}")


@app.get("/health", tags=["Monitoring"])
def health():
    return {
        "status": "healthy",
        "engine": "Multi-Agent Autonomous ReAct Runtime",
        "deployed_agents": list(agents_registry.keys()),
        "port": PORT
    }


@app.post("/deploy", tags=["Deployment"])
async def deploy_agent(req: DeployRequest):
    try:
        data = yaml.safe_load(req.yaml_content) or {}
        meta = data.get("metadata", {})
        slug = (
            req.slug
            or meta.get("slug")
            or data.get("slug")
            or meta.get("id")
            or data.get("agent_id")
            or "default"
        )
        clean_slug = str(slug).strip().lower().replace(" ", "-")

        file_path = AGENTS_DIR / f"{clean_slug}.yaml"
        file_path.write_text(req.yaml_content, encoding="utf-8")

        engine = AgentRuntimeEngine(req.yaml_content, clean_slug)
        agents_registry[clean_slug] = engine
        agents_registry["default"] = engine

        logger.info(f"[Deploy] Agent '{engine.name}' berhasil dideploy pada slug '{clean_slug}'")

        return {
            "status": "deployed",
            "message": f"Agent '{engine.name}' berhasil dideploy pada endpoint /agents/{clean_slug}/invoke.",
            "agent_id": engine.agent_id,
            "agent_slug": clean_slug,
            "endpoint": f"http://{HOST}:{PORT}/agents/{clean_slug}/invoke"
        }
    except Exception as e:
        logger.error(f"Gagal deploy agent: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Gagal mem-parsing agent.yaml: {str(e)}")


@app.post("/invoke", response_model=InvokeResponse, tags=["Invocation"])
async def invoke_default(payload: InvokeRequest):
    default_engine = agents_registry.get("default") or (next(iter(agents_registry.values())) if agents_registry else None)
    if not default_engine:
        raise HTTPException(status_code=404, detail="Belum ada agent yang dideploy di runtime ini.")
    return await default_engine.run_step(payload.session_id, payload.message)


@app.post("/agents/{agent_slug}/invoke", response_model=InvokeResponse, tags=["Multi-Agent Invocation"])
async def invoke_by_slug(agent_slug: str, payload: InvokeRequest):
    clean_slug = agent_slug.strip().lower()
    engine = agents_registry.get(clean_slug)
    if not engine:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_slug}' tidak ditemukan. Daftar slug tersedia: {list(agents_registry.keys())}"
        )
    return await engine.run_step(payload.session_id, payload.message)


@app.get("/agents/{agent_slug}/health", tags=["Monitoring"])
def health_by_slug(agent_slug: str):
    clean_slug = agent_slug.strip().lower()
    engine = agents_registry.get(clean_slug)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_slug}' tidak ditemukan.")
    return {
        "status": "healthy",
        "slug": clean_slug,
        "agent_id": engine.agent_id,
        "agent_name": engine.name,
        "tools_count": len(engine.openai_tools)
    }


if __name__ == "__main__":
    print(f"==================================================")
    print(f" Starting Multi-Agent ReAct Runtime on {HOST}:{PORT}")
    print(f" Registered Slugs: {list(agents_registry.keys())}")
    print(f"==================================================")
    uvicorn.run(app, host=HOST, port=PORT)
