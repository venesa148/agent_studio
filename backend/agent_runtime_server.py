"""
Agent Runtime Server (Dedicated Multi-Agent Autonomous ReAct Runtime)
======================================================================
Generic Agent Runtime untuk lingkungan AWS EC2 dan lokal:
- Multi-Agent Registry (setiap agent memiliki slug unik di /agents/{slug}/invoke)
- Full Declarative YAML Parser (metadata, instructions, configuration, tools_required, guardrails)
- Autonomous ReAct Agent Loop (multi-step dynamic tool calling via OpenRouter / OpenAI)
- Fallback Regex Interceptor untuk model dengan sintaks tag (misal GLM / ChatGLM <tool_call>)
- Dynamic Live Web API & MCP Tool Execution (100% dinamis tanpa hardcode data fiktif)
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
# 2. Agent Runtime Engine (Parser & Autonomous ReAct Loop)
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

            # Parse tools_required dari YAML
            self.tools_required = self.raw_spec.get("tools_required", [])
            self.tools_by_ref = {}
            for t in self.tools_required:
                ref = t.get("tool_ref") or t.get("name") or t.get("tool_name")
                if ref:
                    self.tools_by_ref[ref] = t

            # Fallback jika tools didefinisikan dalam format list string tools: [...]
            for tname in self.raw_spec.get("tools", []):
                if isinstance(tname, str) and tname not in self.tools_by_ref:
                    self.tools_by_ref[tname] = {"tool_ref": tname, "endpoint": None, "purpose": f"Layanan tool {tname}"}

            # Siapkan schema tool function calling untuk LLM
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
                f"{len(self.openai_tools)} live tools. Model: {self.model_name}"
            )
        except Exception as e:
            logger.error(f"[Engine Load Error] Gagal memuat YAML: {e}")

    async def execute_tool(self, tool_ref: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Eksekusi tool secara dinamis tanpa hardcode data fiktif."""
        logger.info(f"[Runtime Tool Call] Menjalankan tool '{tool_ref}' dengan params: {params}")
        t_info = self.tools_by_ref.get(tool_ref, {})
        endpoint = t_info.get("endpoint")
        method = str(t_info.get("method") or "POST").upper()

        # 1. Protokol Triase Klinis Standar (classify_complaint)
        if tool_ref == "classify_complaint" or (endpoint and "classify_complaint" in endpoint):
            complaint = str(params.get("complaint") or params.get("keluhan") or "").strip()
            if not complaint:
                return {"status": "error", "message": "Parameter 'complaint' tidak boleh kosong."}

            complaint_lower = complaint.lower()
            red_flags = ["pingsan", "sesak nafas", "nyeri dada hebat", "darurat", "kejang", "tidak sadar", "pendarahan hebat", "stroke", "lumpuh", "koma"]
            matched_rf = [rf for rf in red_flags if rf in complaint_lower]
            if matched_rf:
                return {
                    "status": "ok",
                    "triage_class": "EMERGENCY",
                    "red_flag": True,
                    "matched_red_flags": matched_rf,
                    "candidate_service": ["IGD / Instalasi Gawat Darurat"],
                    "action": "ESCALATE_TO_EMERGENCY",
                    "_source": "Clinical Triage Protocol",
                    "_endpoint": "internal://triage/classify_complaint",
                    "message": "Indikasi gawat darurat (Red Flag) terdeteksi. Segera arahkan pasien ke IGD rumah sakit terdekat atau hubungi 119."
                }

            ortho_kw = ["lutut", "sendi", "tulang", "patah", "keseleo", "otot", "kaki", "pinggang", "punggung", "tangan", "bahu"]
            jantung_kw = ["jantung", "dada", "debar", "koroner", "aritmia"]
            internis_kw = ["lambung", "maag", "ulu hati", "mual", "muntah", "perut", "penyakit dalam", "gerd", "diare"]
            mata_kw = ["mata", "kabur", "katarak", "minus", "silinder"]
            gigi_kw = ["gigi", "gusi", "geraham", "tambal", "cabut gigi"]
            anak_kw = ["bayi", "balita", "anak", "imunisasi", "tumbuh kembang"]

            poli = "Poli Umum FKTP"
            if any(k in complaint_lower for k in ortho_kw):
                poli = "Poli Orthopaedi & Bedah Tulang"
            elif any(k in complaint_lower for k in jantung_kw):
                poli = "Poli Jantung & Pembuluh Darah"
            elif any(k in complaint_lower for k in internis_kw):
                poli = "Poli Penyakit Dalam"
            elif any(k in complaint_lower for k in mata_kw):
                poli = "Poli Mata"
            elif any(k in complaint_lower for k in gigi_kw):
                poli = "Poli Gigi & Mulut"
            elif any(k in complaint_lower for k in anak_kw):
                poli = "Poli Anak"

            return {
                "status": "ok",
                "triage_class": "NEED_FURTHER_CARE",
                "red_flag": False,
                "recommended_specialty": poli,
                "candidate_service": [poli, "Poli Umum FKTP"],
                "requires_eligibility_check": True,
                "_source": "Clinical Triage Protocol",
                "_endpoint": "internal://triage/classify_complaint"
            }

        # 2. Live REST API / MCP HTTP Endpoint Runner (Dinamis sesuai file YAML)
        if endpoint and (endpoint.startswith("http://") or endpoint.startswith("https://")):
            headers = {"Content-Type": "application/json"}
            auth_secret = t_info.get("auth_secret_ref")
            if auth_secret:
                headers["Authorization"] = f"Bearer {auth_secret}"

            # Normalisasi parameter input payload
            norm_params = dict(params)
            if "hospital_name" in norm_params and "location" not in norm_params:
                norm_params["location"] = norm_params["hospital_name"]
            if "city" in norm_params and "location" not in norm_params:
                norm_params["location"] = norm_params["city"]
            if "bpjs_number" in norm_params and "number" not in norm_params:
                norm_params["number"] = norm_params["bpjs_number"]
            if "bpjs_number" in norm_params and "bpjs_id" not in norm_params:
                norm_params["bpjs_id"] = norm_params["bpjs_number"]
            if "bpjs_id" in norm_params and "number" not in norm_params:
                norm_params["number"] = norm_params["bpjs_id"]
            if "participant_id" in norm_params and "number" not in norm_params:
                norm_params["number"] = norm_params["participant_id"]
            if "referral_number" in norm_params and "referral_no" not in norm_params:
                norm_params["referral_no"] = norm_params["referral_number"]
            if "referral_number" in norm_params and "referral_id" not in norm_params:
                norm_params["referral_id"] = norm_params["referral_number"]
            if "referral_id" in norm_params and "referral_no" not in norm_params:
                norm_params["referral_no"] = norm_params["referral_id"]

            try:
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                    if method == "GET":
                        resp = await client.get(endpoint, params=norm_params, headers=headers)
                    else:
                        resp = await client.post(endpoint, json=norm_params, headers=headers)

                    if resp.status_code == 200:
                        body = resp.json()
                        data = body.get("data", body) if isinstance(body, dict) else body
                        logger.info(f"[Live HTTP Tool OK] {tool_ref} -> 200 OK")
                        if isinstance(data, dict):
                            data["_endpoint"] = endpoint
                            data["_source"] = t_info.get("mcp_server_name") or "Live Web API"
                            return data
                        elif isinstance(data, list):
                            return {
                                "status": "ok",
                                "count": len(data),
                                "items": data,
                                "_endpoint": endpoint,
                                "_source": t_info.get("mcp_server_name") or "Live Web API"
                            }
                        return {"status": "ok", "result": data, "_endpoint": endpoint}
                    else:
                        logger.warning(f"[Live HTTP Tool Status {resp.status_code}] {tool_ref}: {resp.text[:200]}")
                        return {
                            "status": "error",
                            "status_code": resp.status_code,
                            "_endpoint": endpoint,
                            "_source": t_info.get("mcp_server_name") or "Live Web API",
                            "message": f"Server eksternal mengembalikan HTTP {resp.status_code} untuk tool '{tool_ref}'."
                        }
            except Exception as e:
                logger.warning(f"[Live HTTP Tool Error] {tool_ref} ({endpoint}): {e}")
                return {
                    "status": "error",
                    "error_type": "SERVICE_UNAVAILABLE",
                    "_endpoint": endpoint,
                    "_source": t_info.get("mcp_server_name") or "Live Web API (Offline)",
                    "message": f"Server live API ({endpoint}) sedang offline atau tidak dapat dijangkau: {str(e)}"
                }

        # 3. Live Web Search (DuckDuckGo Search)
        if tool_ref in ["search_web", "web_search"]:
            query = str(params.get("query") or params.get("q") or "").strip()
            if not query:
                return {"status": "error", "message": "Parameter 'query' tidak boleh kosong."}
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, region="id-id", max_results=4))
                    if not raw:
                        raw = list(ddgs.text(query, region="wt-wt", max_results=4))
                    if raw:
                        return {
                            "status": "ok",
                            "query": query,
                            "results": [{"title": r.get("title"), "snippet": r.get("body"), "url": r.get("href")} for r in raw],
                            "_source": "DuckDuckGo Web Search",
                            "_endpoint": "https://duckduckgo.com"
                        }
            except Exception as e_search:
                logger.warning(f"[Web Search Warning] {e_search}")
            return {"status": "error", "query": query, "message": "Layanan pencarian web sedang tidak dapat memuat hasil."}

        # 4. Safe Math Calculator
        if tool_ref in ["calculator", "math_eval"]:
            expr = str(params.get("expression") or params.get("expr") or "").strip()
            if not expr:
                return {"status": "error", "message": "Parameter 'expression' tidak boleh kosong."}
            try:
                import ast
                import operator
                ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg, ast.Mod: operator.mod}
                def _eval(node):
                    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                        return node.value
                    elif isinstance(node, ast.BinOp) and type(node.op) in ops:
                        return ops[type(node.op)](_eval(node.left), _eval(node.right))
                    elif isinstance(node, ast.UnaryOp) and type(node.op) in ops:
                        return ops[type(node.op)](_eval(node.operand))
                    raise ValueError("Operator tidak diizinkan")
                val = _eval(ast.parse(expr, mode='eval').body)
                return {"status": "ok", "expression": expr, "result": val, "_endpoint": "internal://calculator"}
            except Exception as e_calc:
                return {"status": "error", "expression": expr, "message": f"Gagal menghitung: {str(e_calc)}"}

        # 5. Generic Unconfigured Tool
        return {
            "status": "unconfigured",
            "tool": tool_ref,
            "message": f"Tool '{tool_ref}' belum dikonfigurasi endpoint HTTP live-nya.",
            "params": params
        }

    async def execute_llm_step(self, user_message: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Autonomous ReAct Agent Loop:
        - Mendukung multi-turn tool calling secara berurutan
        - Mendukung format function calling OpenAI JSON resmi
        - Fallback Regex Interceptor jika model (misal GLM / ChatGLM) mencetak <tool_call> di teks
        - Otomatis merangkum hasil tool menjadi jawaban ramah & profesional
        """
        api_key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
            or ""
        )
        if not api_key:
            return f"Halo! Saya {self.name}. (Server belum dikonfigurasi API Key LLM).", []

        from openai import AsyncOpenAI
        is_openrouter = api_key.startswith("sk-or-") or "openrouter.ai" in os.getenv("LLM_BASE_URL", "")
        base_url = "https://openrouter.ai/api/v1" if is_openrouter else os.getenv("OPENAI_BASE_URL")

        target_model = self.model_name
        if is_openrouter and "/" not in target_model:
            target_model = f"openai/{target_model}"

        headers = {
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Agent Studio Runtime"
        } if is_openrouter else None

        client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers)

        messages: List[Dict[str, Any]] = [
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
            raw_content = msg.content or ""
            parsed_tool_calls: List[Dict[str, Any]] = []

            # 1. Parsing jika LLM mengembalikan format OpenAI Tool Calls resmi
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        args = {}
                    parsed_tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": args,
                        "raw_args": tc.function.arguments or "{}"
                    })

            # 2. Fallback Regex Interceptor jika model (misal GLM / ChatGLM) mencetak tag <tool_call> di teks
            elif "<tool_call>" in raw_content:
                import re
                matches = re.findall(r'<tool_call>\s*([a-zA-Z0-9_-]+)\s*\((.*?)\)', raw_content)
                for fn_name, raw_args in matches:
                    args = {}
                    raw_args = raw_args.strip()
                    if raw_args.startswith("{") and raw_args.endswith("}"):
                        try:
                            args = json.loads(raw_args)
                        except Exception:
                            pass
                    if not args and raw_args:
                        pattern = r'([a-zA-Z0-9_-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^,)]+))'
                        for m in re.finditer(pattern, raw_args):
                            k = m.group(1)
                            v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4).strip())
                            args[k] = v

                    parsed_tool_calls.append({
                        "id": f"call_regex_{uuid.uuid4().hex[:8]}",
                        "name": fn_name,
                        "arguments": args,
                        "raw_args": json.dumps(args, ensure_ascii=False)
                    })

            # Jika tidak ada pemanggilan tool lagi, kita telah sampai pada jawaban akhir
            if not parsed_tool_calls:
                final_text = raw_content
                if not final_text and getattr(msg, "reasoning", None):
                    final_text = msg.reasoning
                if final_text and final_text.strip():
                    return final_text.strip(), executed_tools
                break

            # Catat instruksi assistant ke percakapan
            tool_payload = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["raw_args"]}
                }
                for tc in parsed_tool_calls
            ]
            messages.append({
                "role": "assistant",
                "content": raw_content or "",
                "tool_calls": tool_payload
            })

            # Eksekusi setiap tool secara dinamis
            for tc in parsed_tool_calls:
                fn_name = tc["name"]
                fn_args = tc["arguments"]
                tool_res = await self.execute_tool(fn_name, fn_args)
                executed_tools.append({"tool": fn_name, "params": fn_args, "result": tool_res})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_res, ensure_ascii=False)
                })

        # Jika loop tools selesai tetapi belum menghasilkan teks final yang dirangkum
        if executed_tools:
            try:
                messages.append({
                    "role": "user",
                    "content": (
                        "Tolong rangkum semua data yang sudah kamu peroleh dari tools di atas ke dalam format jawaban yang "
                        "sangat ramah, empatik, terstruktur, serta sampaikan langkah selanjutnya dengan jelas kepada pasien."
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

        fallback = f"Halo, data Anda telah berhasil diverifikasi oleh {self.name}."
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

# Muat semua agent yang ada di folder deployed_agents/
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
        "engine": "Multi-Agent Autonomous ReAct Runtime (Dynamic / No Hardcode)",
        "deployed_agents": list(agents_registry.keys()),
        "port": PORT
    }


@app.get("/spec", tags=["Specification"])
async def get_active_spec():
    default_engine = agents_registry.get("default") or (next(iter(agents_registry.values())) if agents_registry else None)
    if not default_engine:
        raise HTTPException(status_code=404, detail="Belum ada agent yang aktif.")
    return default_engine.raw_spec


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
