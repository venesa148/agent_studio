"""
Agent Runtime Server (Dedicated Data-Plane Harness)
====================================================
Program ini adalah Generic Agent Runtime yang didesain untuk berjalan di server AWS EC2.
Server ini membaca file deklaratif `agent.yaml`, mem-booting Graph State-Machine in-memory,
menghubungkan LLM & Tools, dan mengekspos endpoint live:
  - GET  /health   -> Cek kesehatan runtime & agent yang sedang aktif
  - GET  /spec     -> Detail spesifikasi agent yang sedang dimuat
  - POST /deploy   -> Menerima pembaruan agent.yaml baru dari Agent Studio
  - POST /invoke   -> Endpoint utama untuk menerima pesan pasien dari chatbot / sistem luar
"""

import os
import sys
import yaml
import json
import uuid
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# Setup Windows async loop policy jika berjalan di Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent.runtime")

CONFIG_PATH = Path(__file__).parent / "agent.yaml"
PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")
RUNTIME_AUTH_TOKEN = os.getenv("RUNTIME_AUTH_TOKEN", "agent_studio_live_token_2026")

# In-memory session store untuk conversation context
session_memory: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# 1. Models & Schemas
# =============================================================================
class InvokeRequest(BaseModel):
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    message: str = Field(..., description="Pesan atau keluhan dari pasien/pengguna")


class InvokeResponse(BaseModel):
    session_id: str
    agent_id: str
    response: str
    current_node: str
    status: str  # in_progress | completed | blocked
    turn_count: int
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


class DeployRequest(BaseModel):
    yaml_content: str
    api_key: Optional[str] = None


# =============================================================================
# 2. Agent Runtime Engine (Parser & State Machine)
# =============================================================================
class AgentRuntimeEngine:
    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.raw_spec: Dict[str, Any] = {}
        self.agent_id: str = "unknown"
        self.name: str = "Unknown Agent"
        self.status: str = "initializing"
        self.version: int = 1
        self.nodes_by_id: Dict[str, Dict[str, Any]] = {}
        self.entry_node: str = ""
        self.load_config()

    def load_config(self, content: Optional[str] = None):
        try:
            if content:
                data = yaml.safe_load(content)
            elif self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                logger.warning(f"File {self.config_file} tidak ditemukan. Menggunakan template default.")
                data = self._fallback_spec()

            self.raw_spec = data or {}
            self.agent_id = self.raw_spec.get("agent_id", "bpjs-triase-rs-001")
            self.name = self.raw_spec.get("name", "Agent Triase BPJS RS")
            self.version = self.raw_spec.get("version", 1)
            self.status = "active"

            # Parse flow graph
            flow = self.raw_spec.get("flow", {})
            self.entry_node = flow.get("entry_node", "")
            nodes = flow.get("nodes", [])
            self.nodes_by_id = {node["id"]: node for node in nodes if "id" in node}

            logger.info(
                f"[Agent Runtime] Berhasil memuat config: '{self.name}' "
                f"(ID: {self.agent_id}, v{self.version}) dengan {len(self.nodes_by_id)} node graph."
            )
        except Exception as e:
            logger.error(f"Gagal memuat config YAML: {e}")
            self.status = "error_loading_config"

    def _fallback_spec(self) -> Dict[str, Any]:
        return {
            "agent_id": "default-agent-001",
            "name": "Default Assistant",
            "version": 1,
            "status": "active",
            "system_prompt": "Anda adalah asisten medis yang ramah.",
            "flow": {
                "entry_node": "terima_keluhan",
                "nodes": [
                    {
                        "id": "terima_keluhan",
                        "type": "llm_step",
                        "instruction": "Tanggapi keluhan pengguna dengan empati.",
                        "next": "selesai"
                    },
                    {"id": "selesai", "type": "end"}
                ]
            }
        }

    async def execute_llm_step(self, instruction: str, system_prompt: str, user_message: str, context: Dict[str, Any]) -> str:
        """Memanggil LLM (Anthropic / OpenAI) atau fallback jika key belum disetel."""
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")

        # 1. Coba Anthropic jika terkonfigurasi
        if anthropic_key and anthropic_key != "sk-ant-...":
            try:
                import anthropic
                client = anthropic.AsyncAnthropic(api_key=anthropic_key)
                prompt_full = (
                    f"Instruksi langkah saat ini: {instruction}\n"
                    f"Konteks riwayat: {json.dumps(context, ensure_ascii=False)}\n"
                    f"Pesan pengguna: {user_message}"
                )
                msg = await client.messages.create(
                    model=self.raw_spec.get("model", {}).get("name", "claude-sonnet-4-5"),
                    max_tokens=self.raw_spec.get("model", {}).get("max_tokens", 1024),
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt_full}]
                )
                return msg.content[0].text
            except Exception as e:
                logger.warning(f"Gagal memanggil Anthropic ({e}), mencoba fallback...")

        # 2. Coba OpenAI / OpenRouter jika terkonfigurasi
        if openai_key and openai_key != "sk-...":
            try:
                from openai import AsyncOpenAI
                is_openrouter = openai_key.startswith("sk-or-")
                base_url = "https://openrouter.ai/api/v1" if is_openrouter else os.getenv("OPENAI_BASE_URL")
                model_name = "openai/gpt-4o-mini" if is_openrouter else "gpt-4o-mini"

                client = AsyncOpenAI(api_key=openai_key, base_url=base_url)
                prompt_full = (
                    f"Instruksi langkah saat ini: {instruction}\n"
                    f"Konteks riwayat: {json.dumps(context, ensure_ascii=False)}\n"
                    f"Pesan pengguna: {user_message}"
                )
                res = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_full}
                    ]
                )
                return res.choices[0].message.content or ""
            except Exception as e:
                logger.warning(f"Gagal memanggil OpenAI/OpenRouter ({e}), menggunakan runtime responder...")

        # 3. Fallback deterministic generator untuk pengujian triase BPJS tanpa API Key
        lowered = user_message.lower()
        if "pusing" in lowered or "demam" in lowered or "batuk" in lowered:
            return (
                "Terima kasih telah menyampaikan keluhan Anda. Saya mencatat Anda mengalami gejala "
                f"'{user_message}'. Untuk memastikan penanganan yang tepat, apakah gejala ini sudah berlangsung "
                "lebih dari 3 hari, atau disertai sesak napas / demam tinggi?"
            )
        elif "darurat" in lowered or "sesak" in lowered or "parah" in lowered or "sakit sekali" in lowered:
            return (
                "Berdasarkan keluhan yang Anda rasakan, kondisi ini memerlukan pemeriksaan langsung oleh dokter spesialis. "
                "Saya sedang memeriksa jadwal dokter dan fasilitas IGD/Poli terdekat untuk Anda."
            )
        else:
            return (
                f"Halo! Saya {self.name}. Keluhan Anda: \"{user_message}\" telah kami terima. "
                "Bisa diceritakan lebih detail bagian tubuh mana yang dirasakan sakit dan sudah berapa lama?"
            )

    async def execute_tool(self, tool_ref: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Eksekusi panggilan tool MCP / API internal"""
        logger.info(f"[Runtime Tool Call] Menjalankan tool '{tool_ref}' dengan params: {params}")
        if tool_ref == "mcp_hospital_doctor_search":
            return {
                "dokter_id": "DOK-402",
                "nama_dokter": "dr. Budi Santoso, Sp.PD (Spesialis Penyakit Dalam)",
                "jadwal": "Senin - Kamis, 09:00 - 14:00 WIB",
                "rumah_sakit": "RSUD Tarakan (Rekanan BPJS Kesehatan)"
            }
        elif tool_ref == "mcp_calendar_booking":
            return {
                "booking_id": f"BK-{uuid.uuid4().hex[:6].upper()}",
                "status": "confirmed",
                "antrian_no": "A-14",
                "estimasi_jam": "10:30 WIB"
            }
        return {"status": "success", "result": f"Tool '{tool_ref}' dieksekusi dengan baik."}

    async def run_step(self, session_id: str, user_message: str) -> InvokeResponse:
        # Guardrail check: max turns
        guardrails = self.raw_spec.get("guardrails", {})
        max_turns = guardrails.get("max_turns", 15)

        if session_id not in session_memory:
            session_memory[session_id] = {
                "turn_count": 0,
                "current_node": self.entry_node,
                "history": [],
                "node_outputs": {}
            }

        session = session_memory[session_id]
        session["turn_count"] += 1

        if session["turn_count"] > max_turns:
            return InvokeResponse(
                session_id=session_id,
                agent_id=self.agent_id,
                response="Batas maksimal percakapan untuk sesi ini telah tercapai demi alasan keamanan (Guardrail max_turns). Silakan hubungi langsung pusat informasi rumah sakit.",
                current_node="blocked",
                status="blocked",
                turn_count=session["turn_count"]
            )

        # Guardrail check: disallowed behaviors
        disallowed = guardrails.get("disallowed_behaviors", [])
        system_prompt = self.raw_spec.get("system_prompt", "Kamu adalah asisten triase rumah sakit.")
        if disallowed:
            system_prompt += f"\nBATASAN KEAMANAN: Jangan melakukan hal-hal berikut: {'; '.join(disallowed)}."

        curr_node_id = session["current_node"]
        node = self.nodes_by_id.get(curr_node_id, self.nodes_by_id.get(self.entry_node))
        if not node:
            return InvokeResponse(
                session_id=session_id,
                agent_id=self.agent_id,
                response="Node eksekusi tidak ditemukan dalam flow graph.",
                current_node="unknown",
                status="completed",
                turn_count=session["turn_count"]
            )

        executed_tools = []
        node_type = node.get("type", "llm_step")

        # Logika eksekusi node
        if node_type == "llm_step":
            instruction = node.get("instruction", "")
            response_text = await self.execute_llm_step(instruction, system_prompt, user_message, session["node_outputs"])
            session["node_outputs"][curr_node_id] = response_text

            # Cek jika ada output classification
            if node.get("output_type") == "classification":
                branches = node.get("branches", {})
                lowered_resp = response_text.lower()
                next_node_id = branches.get("ringan", "beri_saran_mandiri")
                for key, target in branches.items():
                    if key in lowered_resp:
                        next_node_id = target
                        break
                session["current_node"] = next_node_id
            else:
                session["current_node"] = node.get("next", "selesai")

        elif node_type == "tool_call":
            tool_ref = node.get("tool_ref", "")
            input_mapping = node.get("input_mapping", {})
            params = {}
            for k, v in input_mapping.items():
                if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                    ref_key = v.strip("{}").split(".")[0]
                    params[k] = session["node_outputs"].get(ref_key, user_message)
                else:
                    params[k] = v

            tool_res = await self.execute_tool(tool_ref, params)
            executed_tools.append({"tool": tool_ref, "params": params, "result": tool_res})
            session["node_outputs"][curr_node_id] = tool_res
            session["current_node"] = node.get("next", "selesai")

            response_text = (
                f"Sistem telah menjalankan verifikasi jadwal dokter melalui tool {tool_ref}: "
                f"{json.dumps(tool_res, ensure_ascii=False)}"
            )

        elif node_type == "end":
            response_text = "Sesi konsultasi triase telah selesai. Semoga lekas sembuh!"
            session["current_node"] = "selesai"
        else:
            response_text = f"Memproses langkah {curr_node_id}..."
            session["current_node"] = node.get("next", "selesai")

        # Cek jika node berikutnya adalah end
        status = "completed" if session["current_node"] == "selesai" else "in_progress"

        return InvokeResponse(
            session_id=session_id,
            agent_id=self.agent_id,
            response=response_text,
            current_node=session["current_node"],
            status=status,
            turn_count=session["turn_count"],
            tool_calls=executed_tools
        )


# =============================================================================
# 3. FastAPI Web Application
# =============================================================================
app = FastAPI(
    title="Agent Runtime Harness",
    description="Dedicated server runtime executing agent.yaml graph for deployed agents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = AgentRuntimeEngine(CONFIG_PATH)


@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Health check endpoint untuk load balancer / monitoring di AWS"""
    return {
        "status": "healthy",
        "runtime": "Agent Studio Dedicated Runtime",
        "agent_id": engine.agent_id,
        "agent_name": engine.name,
        "version": engine.version,
        "agent_status": engine.status,
        "nodes_loaded": len(engine.nodes_by_id)
    }


@app.get("/spec", tags=["Specification"])
async def get_active_spec():
    """Mengembalikan spesifikasi aktif yang sedang dijalankan"""
    return engine.raw_spec


@app.post("/deploy", tags=["Deployment"])
async def deploy_agent_config(payload: DeployRequest):
    """
    Menerima deploy konfigurasi agent.yaml baru dari Agent Studio.
    Dipanggil saat user mengklik tombol 'Publish Agent' di studio.
    """
    try:
        engine.load_config(content=payload.yaml_content)
        # Tulis ke file config lokal agar persisten saat restart
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(payload.yaml_content)

        return {
            "status": "deployed",
            "message": f"Agent '{engine.name}' (v{engine.version}) berhasil dideploy ke server runtime.",
            "agent_id": engine.agent_id,
            "endpoint": f"http://{HOST}:{PORT}/invoke"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal mem-parsing file agent.yaml: {str(e)}")


@app.post("/invoke", response_model=InvokeResponse, tags=["Invocation"])
async def invoke_agent(payload: InvokeRequest):
    """
    Endpoint utama bagi pengguna / chatbot rumah sakit eksternal untuk berbicara dengan agent (default).
    """
    try:
        return await engine.run_step(payload.session_id, payload.message)
    except Exception as e:
        logger.error(f"Error saat mengeksekusi invoke: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Runtime error: {str(e)}")


@app.post("/agents/{agent_slug}/invoke", response_model=InvokeResponse, tags=["Multi-Agent Invocation"])
async def invoke_agent_by_slug(agent_slug: str, payload: InvokeRequest):
    """
    Multi-Agent Endpoint: Memanggil agent spesifik berdasarkan slug/identitas uniknya.
    """
    try:
        logger.info(f"[Multi-Agent Runtime] Menerima request untuk agent slug: '{agent_slug}'")
        return await engine.run_step(payload.session_id, payload.message)
    except Exception as e:
        logger.error(f"Error saat mengeksekusi invoke [{agent_slug}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Runtime error: {str(e)}")


@app.get("/agents/{agent_slug}/health", tags=["Monitoring"])
async def health_check_by_slug(agent_slug: str):
    """Health check spesifik untuk agent berdasarkan slug"""
    return {
        "status": "healthy",
        "slug": agent_slug,
        "runtime": "Agent Studio Dedicated Runtime",
        "agent_id": engine.agent_id,
        "agent_name": engine.name,
        "version": engine.version,
        "nodes_loaded": len(engine.nodes_by_id)
    }


# =============================================================================
# 4. Entrypoint Runner
# =============================================================================
if __name__ == "__main__":
    print(f"==================================================")
    print(f" Starting Agent Runtime Harness on {HOST}:{PORT}")
    print(f" Active Agent : {engine.name} ({engine.agent_id})")
    print(f" Spec Version : v{engine.version}")
    print(f" Public Invoke: http://{HOST}:{PORT}/invoke")
    print(f" Health Check : http://{HOST}:{PORT}/health")
    print(f"==================================================")
    uvicorn.run("agent_runtime_server:app", host=HOST, port=PORT, reload=False)
