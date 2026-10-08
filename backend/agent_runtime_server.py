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
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import httpx
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
    slug: Optional[str] = None
    target_environment: Optional[str] = None


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
        self.system_prompt: str = ""
        self.nodes_by_id: Dict[str, Dict[str, Any]] = {}
        self.entry_node: str = ""
        self.tools_required: List[Dict[str, Any]] = []
        self.tools_by_ref: Dict[str, Dict[str, Any]] = {}
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

            # 1. Mendukung format standar baru (metadata block) dan format legacy
            metadata = self.raw_spec.get("metadata", {})
            self.agent_id = metadata.get("id") or self.raw_spec.get("agent_id", "default-agent-001")
            self.name = metadata.get("name") or self.raw_spec.get("name", "AI Assistant")
            self.version = metadata.get("version") or self.raw_spec.get("version", 1)
            self.status = metadata.get("status") or self.raw_spec.get("status", "active")
            self.description = metadata.get("description") or self.raw_spec.get("description", "")

            # 2. Parse system prompt / instructions secara dinamis dari spesifikasi YAML
            instructions = self.raw_spec.get("instructions")
            if isinstance(instructions, str) and instructions.strip():
                self.system_prompt = instructions.strip()
            elif isinstance(instructions, dict):
                self.system_prompt = instructions.get("system", "") or instructions.get("instruction", "")
            else:
                self.system_prompt = self.raw_spec.get("system_prompt", "")

            if not self.system_prompt:
                self.system_prompt = (
                    f"Kamu adalah {self.name}. Berikan respon yang informatif, profesional, "
                    "dan membantu sesuai dengan arahan peran Anda."
                )

            # 3. Parse flow graph
            flow = self.raw_spec.get("flow", {})
            self.entry_node = flow.get("entry_node", "")
            nodes = flow.get("nodes", [])
            self.nodes_by_id = {node["id"]: node for node in nodes if "id" in node}

            # Buat auto flow jika graph belum didefinisikan secara eksplisit
            if not self.nodes_by_id:
                self.entry_node = "main_step"
                self.nodes_by_id = {
                    "main_step": {
                        "id": "main_step",
                        "type": "llm_step",
                        "instruction": "Tanggapi pesan pengguna secara akurat sesuai dengan peran dan instruksi Anda.",
                        "next": "selesai"
                    },
                    "selesai": {"id": "selesai", "type": "end"}
                }

            # 4. Parse tools_required dan tools list
            self.tools_required = self.raw_spec.get("tools_required", [])
            self.tools_by_ref = {}
            for t in self.tools_required:
                ref = t.get("tool_ref") or t.get("name") or t.get("tool_name")
                if ref:
                    self.tools_by_ref[ref] = t
            for tname in self.raw_spec.get("tools", []):
                if isinstance(tname, str) and tname not in self.tools_by_ref:
                    self.tools_by_ref[tname] = {"tool_ref": tname, "endpoint": None, "connection_status": "unconfigured"}

            logger.info(
                f"[Agent Runtime] Berhasil memuat config: '{self.name}' "
                f"(ID: {self.agent_id}, v{self.version}) dengan {len(self.nodes_by_id)} node graph "
                f"dan {len(self.tools_by_ref)} registered tools."
            )
        except Exception as e:
            logger.error(f"Gagal memuat config YAML: {e}")
            self.status = "error_loading_config"

    def _fallback_spec(self) -> Dict[str, Any]:
        return {
            "spec_version": "v1.0",
            "metadata": {
                "id": "default-assistant-001",
                "name": "General AI Assistant",
                "version": 1,
                "status": "active",
                "description": "Asisten serbaguna yang siap memproses dan menjawab kebutuhan pengguna."
            },
            "configuration": {
                "model": "gpt-4o-mini"
            },
            "instructions": "Kamu adalah asisten AI yang cerdas, ramah, dan profesional. Bantu pengguna dengan solusi yang tepat.",
            "flow": {
                "entry_node": "main_step",
                "nodes": [
                    {
                        "id": "main_step",
                        "type": "llm_step",
                        "instruction": "Tanggapi pesan pengguna dengan jelas dan solutif.",
                        "next": "selesai"
                    },
                    {"id": "selesai", "type": "end"}
                ]
            }
        }

    async def execute_tool(self, tool_ref: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Eksekusi live HTTP call ke Web API / MCP Server atau internal tool berdasarkan spesifikasi YAML."""
        logger.info(f"[Runtime Tool Call] Menjalankan tool '{tool_ref}' dengan params: {params}")

        # 1. Cari spesifikasi tool dari YAML
        tool_info = self.tools_by_ref.get(tool_ref) or {}
        endpoint = tool_info.get("endpoint")
        method = str(tool_info.get("method") or "POST").upper()

        # Fallback dinamis jika endpoint belum terdefinisi di YAML tetapi ada server tunnel di env
        if not endpoint:
            api_base = (
                os.getenv("EXTERNAL_MOCK_API_URL")
                or os.getenv("CLOUDFLARE_TUNNEL_URL")
                or "https://fundamentals-mechanism-serious-paragraphs.trycloudflare.com"
            ).rstrip("/")

            bpjs_routes = {
                "check_bpjs": f"{api_base}/api/v1/mock-bpjs/check-bpjs",
                "get_participant_status": f"{api_base}/api/v1/mock-bpjs/check-bpjs",
                "get_referral_status": f"{api_base}/api/v1/mock-bpjs/referral-status",
                "search_hospital": f"{api_base}/api/v1/mock-bpjs/hospitals",
                "hospital_finder": f"{api_base}/api/v1/mock-bpjs/hospitals",
                "search_hospitals": f"{api_base}/api/v1/mock-bpjs/hospitals",
                "find_specialist": f"{api_base}/api/v1/mock-bpjs/specialists",
                "search_doctors": f"{api_base}/api/v1/mock-bpjs/specialists",
                "mcp_hospital_doctor_search": f"{api_base}/api/v1/mock-bpjs/specialists",
                "create_appointment": f"{api_base}/api/v1/mock-bpjs/appointments",
                "book_appointment": f"{api_base}/api/v1/mock-bpjs/appointments",
                "mcp_calendar_booking": f"{api_base}/api/v1/mock-bpjs/appointments",
            }
            if tool_ref in bpjs_routes:
                endpoint = bpjs_routes[tool_ref]

        # 2. Eksekusi jika endpoint adalah live URL HTTP/HTTPS
        if endpoint and (endpoint.startswith("http://") or endpoint.startswith("https://")):
            headers = {"Content-Type": "application/json"}
            auth_secret = tool_info.get("auth_secret_ref")
            if auth_secret:
                headers["Authorization"] = f"Bearer {auth_secret}"

            # Normalisasi parameter payload untuk API eksternal
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
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                    if method == "GET":
                        resp = await client.get(endpoint, params=norm_params, headers=headers)
                    else:
                        resp = await client.post(endpoint, json=norm_params, headers=headers)

                    if resp.status_code == 200:
                        try:
                            body = resp.json()
                            if isinstance(body, dict):
                                data = body.get("data", body)
                                if isinstance(data, dict):
                                    data["_endpoint"] = endpoint
                                    data["_source"] = tool_info.get("mcp_server_name") or "Live Web API"
                                    return data
                                elif isinstance(data, list):
                                    return {
                                        "status": "ok",
                                        "count": len(data),
                                        "items": data,
                                        "_endpoint": endpoint,
                                        "_source": tool_info.get("mcp_server_name") or "Live Web API"
                                    }
                                return {"status": "ok", "result": data, "_endpoint": endpoint}
                            elif isinstance(body, list):
                                return {
                                    "status": "ok",
                                    "count": len(body),
                                    "items": body,
                                    "_endpoint": endpoint,
                                    "_source": tool_info.get("mcp_server_name") or "Live Web API"
                                }
                            return {"status": "ok", "result": body, "_endpoint": endpoint}
                        except Exception:
                            return {"status": "ok", "text": resp.text, "_endpoint": endpoint}
                    else:
                        return {
                            "status": "error",
                            "status_code": resp.status_code,
                            "_endpoint": endpoint,
                            "_source": "Live Web API",
                            "message": f"Server eksternal mengembalikan HTTP {resp.status_code} untuk tool '{tool_ref}'."
                        }
            except Exception as e:
                logger.warning(f"[Live Tool Error] Request ke {endpoint} gagal: {e}")
                return {
                    "status": "error",
                    "error_type": "SERVICE_UNAVAILABLE",
                    "_endpoint": endpoint,
                    "_source": "Live Web API (Offline)",
                    "message": f"Server live API ({endpoint}) tidak dapat dihubungi: {str(e)}"
                }

        # 3. Tool Internal: Clinical Triage (classify_complaint)
        if tool_ref == "classify_complaint" or (endpoint and "classify_complaint" in endpoint):
            complaint = str(params.get("complaint") or params.get("keluhan") or "").strip()
            if not complaint:
                return {"status": "error", "message": "Parameter 'complaint' tidak boleh kosong."}

            complaint_lower = complaint.lower()
            red_flags = ["pingsan", "sesak nafas", "nyeri dada hebat", "darurat", "kejang", "tidak sadar", "pendarahan hebat", "stroke", "lumpuh", "koma"]
            matched_red_flags = [rf for rf in red_flags if rf in complaint_lower]
            if matched_red_flags:
                return {
                    "status": "ok",
                    "triage_class": "EMERGENCY",
                    "red_flag": True,
                    "matched_red_flags": matched_red_flags,
                    "candidate_service": ["IGD / Instalasi Gawat Darurat"],
                    "action": "ESCALATE_TO_EMERGENCY",
                    "_source": "Clinical Triage Protocol",
                    "_endpoint": "internal://triage/classify_complaint",
                    "message": "Terdeteksi indikasi gawat darurat (Red Flag). Alur booking dihentikan. Segera arahkan pasien ke IGD rumah sakit terdekat atau hubungi 119."
                }

            ortho_kw = ["lutut", "sendi", "tulang", "patah", "keseleo", "otot", "kaki", "pinggang", "punggung", "tangan", "bahu"]
            jantung_kw = ["jantung", "dada", "debar", "koroner", "aritmia"]
            mata_kw = ["mata", "kabur", "katarak", "minus", "silinder"]
            anak_kw = ["bayi", "balita", "anak", "imunisasi", "tumbuh kembang"]

            poli = "Poli Umum"
            if any(k in complaint_lower for k in ortho_kw):
                poli = "Poli Orthopaedi & Bedah Tulang"
            elif any(k in complaint_lower for k in jantung_kw):
                poli = "Poli Jantung & Pembuluh Darah"
            elif any(k in complaint_lower for k in mata_kw):
                poli = "Poli Mata"
            elif any(k in complaint_lower for k in anak_kw):
                poli = "Poli Anak"

            return {
                "status": "ok",
                "triage_class": "NON_EMERGENCY",
                "red_flag": False,
                "recommended_specialty": poli,
                "_source": "Clinical Triage Protocol",
                "_endpoint": "internal://triage/classify_complaint"
            }

        # 4. Tool Internal: Calculator
        if tool_ref in ["calculator", "math_eval"]:
            expr = str(params.get("expression") or params.get("expr") or "").strip()
            if not expr:
                return {"status": "error", "message": "Parameter 'expression' tidak boleh kosong."}
            try:
                import ast
                import operator
                ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
                def _eval(node):
                    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                        return node.value
                    elif isinstance(node, ast.BinOp) and type(node.op) in ops:
                        return ops[type(node.op)](_eval(node.left), _eval(node.right))
                    raise ValueError("Operator tidak diizinkan")
                parsed = ast.parse(expr, mode='eval')
                return {"status": "ok", "expression": expr, "result": _eval(parsed.body), "_endpoint": "internal://calc"}
            except Exception as e_c:
                return {"status": "error", "message": f"Gagal kalkulasi: {e_c}"}

        # 5. Tool Internal: Web Search
        if tool_ref == "search_web":
            query = str(params.get("query") or params.get("q") or "").strip()
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, region="id-id", max_results=3))
                if raw:
                    return {
                        "status": "ok",
                        "query": query,
                        "results": [{"title": r.get("title"), "snippet": r.get("body"), "url": r.get("href")} for r in raw],
                        "_source": "DuckDuckGo Web Search",
                        "_endpoint": "https://duckduckgo.com"
                    }
            except Exception:
                pass
            return {"status": "error", "query": query, "message": "Pencarian web tidak tersedia saat ini."}

        # 6. Fallback jika tool belum terkonfigurasi
        return {
            "status": "unconfigured",
            "tool": tool_ref,
            "message": f"Tool '{tool_ref}' belum dikonfigurasi endpoint live-nya di file YAML.",
            "params": params
        }

    async def execute_llm_step(
        self, instruction: str, system_prompt: str, user_message: str, context: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Memanggil LLM (Anthropic / OpenAI / OpenRouter) dengan dukungan dynamic tool calling."""
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")

        model_cfg = self.raw_spec.get("configuration", {}).get("model") or self.raw_spec.get("model", {})
        if isinstance(model_cfg, dict):
            model_name = model_cfg.get("name", "gpt-4o-mini")
            max_tokens = model_cfg.get("max_tokens", 1024)
        elif isinstance(model_cfg, str) and model_cfg:
            model_name = model_cfg
            max_tokens = 1024
        else:
            model_name = "gpt-4o-mini"
            max_tokens = 1024

        executed_tool_calls: List[Dict[str, Any]] = []

        # Siapkan tool schemas untuk OpenAI / OpenRouter function calling
        openai_tools = []
        for ref, t_info in self.tools_by_ref.items():
            schema = t_info.get("input_schema")
            if not isinstance(schema, dict) or "type" not in schema:
                schema = {"type": "object", "properties": {}}
            desc = t_info.get("purpose") or t_info.get("description") or f"Layanan tool {ref}"
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": ref,
                    "description": desc,
                    "parameters": schema
                }
            })

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
                claude_model = model_name if "claude" in model_name else "claude-3-5-sonnet-20241022"
                msg = await client.messages.create(
                    model=claude_model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt_full}]
                )
                return msg.content[0].text, executed_tool_calls
            except Exception as e:
                logger.warning(f"Gagal memanggil Anthropic ({e}), mencoba fallback...")

        # 2. Coba OpenAI / OpenRouter jika terkonfigurasi
        if openai_key and openai_key != "sk-...":
            try:
                from openai import AsyncOpenAI
                is_openrouter = openai_key.startswith("sk-or-")
                base_url = "https://openrouter.ai/api/v1" if is_openrouter else os.getenv("OPENAI_BASE_URL")

                target_model = model_name
                if is_openrouter and "/" not in target_model:
                    target_model = f"openai/{target_model}"

                client = AsyncOpenAI(api_key=openai_key, base_url=base_url)
                prompt_full = (
                    f"Instruksi langkah saat ini: {instruction}\n"
                    f"Konteks riwayat: {json.dumps(context, ensure_ascii=False)}\n"
                    f"Pesan pengguna: {user_message}"
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_full}
                ]

                call_args: Dict[str, Any] = {
                    "model": target_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.3
                }
                if openai_tools:
                    call_args["tools"] = openai_tools

                res = await client.chat.completions.create(**call_args)
                msg = res.choices[0].message

                # Jika LLM memutuskan memanggil tools
                if msg.tool_calls:
                    tool_calls_payload = []
                    for tc in msg.tool_calls:
                        tool_calls_payload.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}
                        })
                    messages.append({
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": tool_calls_payload
                    })

                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        try:
                            fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                        except Exception:
                            fn_args = {}
                        tool_res = await self.execute_tool(fn_name, fn_args)
                        executed_tool_calls.append({"tool": fn_name, "params": fn_args, "result": tool_res})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(tool_res, ensure_ascii=False)
                        })

                    # Panggil kembali LLM untuk merangkum hasil tool
                    second_res = await client.chat.completions.create(
                        model=target_model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=0.3
                    )
                    return second_res.choices[0].message.content or "", executed_tool_calls

                return msg.content or "", executed_tool_calls
            except Exception as e:
                logger.warning(f"Gagal memanggil OpenAI/OpenRouter ({e}), menggunakan runtime responder...")

        # 3. Fallback responder universal (jika offline)
        fallback_text = (
            f"Halo! Saya {self.name}. Pesan Anda: \"{user_message}\" telah berhasil diproses oleh runtime. "
            f"(Peran agen: {self.description or 'Asisten AI'}. "
            f"Langkah aktif: {instruction or 'Menanggapi kebutuhan pengguna'}.)"
        )
        return fallback_text, executed_tool_calls

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
                response="Batas maksimal percakapan untuk sesi ini telah tercapai demi alasan keamanan (Guardrail max_turns). Silakan mulai sesi percakapan baru.",
                current_node="blocked",
                status="blocked",
                turn_count=session["turn_count"]
            )

        # Guardrail check: disallowed behaviors
        disallowed = guardrails.get("disallowed_behaviors", [])
        system_prompt = self.system_prompt or "Kamu adalah asisten AI yang profesional dan bertindak sesuai panduan."
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
            response_text, step_tool_calls = await self.execute_llm_step(instruction, system_prompt, user_message, session["node_outputs"])
            executed_tools.extend(step_tool_calls)
            session["node_outputs"][curr_node_id] = response_text

            # Cek jika ada output classification
            if node.get("output_type") == "classification":
                branches = node.get("branches", {})
                lowered_resp = response_text.lower()
                next_node_id = list(branches.values())[0] if branches else "selesai"
                for key, target in branches.items():
                    if key.lower() in lowered_resp:
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
                f"Sistem telah menjalankan eksekusi tool '{tool_ref}': "
                f"{json.dumps(tool_res, ensure_ascii=False)}"
            )

        elif node_type == "end":
            response_text = f"Sesi interaksi dengan {self.name} telah selesai. Terima kasih!"
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

# Folder untuk menyimpan file konfigurasi per agent
AGENTS_DIR = Path(__file__).parent / "deployed_agents"
AGENTS_DIR.mkdir(exist_ok=True)

# Multi-Agent in-memory registry: slug -> AgentRuntimeEngine
agents_registry: Dict[str, AgentRuntimeEngine] = {}

# Muat file konfigurasi default awal jika ada
if CONFIG_PATH.exists():
    try:
        default_engine = AgentRuntimeEngine(CONFIG_PATH)
        agents_registry["default"] = default_engine
        default_slug = getattr(default_engine, "slug", None) or default_engine.agent_id.lower()
        agents_registry[default_slug] = default_engine
    except Exception as e:
        logger.warning(f"Gagal memuat default agent.yaml: {e}")

# Muat seluruh agent yang pernah dideploy sebelumnya di deployed_agents/
for yaml_file in AGENTS_DIR.glob("*.yaml"):
    try:
        loaded_engine = AgentRuntimeEngine(yaml_file)
        agent_slug = yaml_file.stem.lower()
        agents_registry[agent_slug] = loaded_engine
        logger.info(f"[Multi-Agent Registry] Pre-loaded agent '{loaded_engine.name}' di slug '{agent_slug}'.")
    except Exception as err:
        logger.warning(f"Gagal pre-load {yaml_file.name}: {err}")


@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Health check endpoint untuk load balancer / monitoring di AWS"""
    return {
        "status": "healthy",
        "engine": "OpenRouter & Multi-Agent Dynamic Runtime",
        "deployed_agents_count": len(agents_registry),
        "active_slugs": list(agents_registry.keys()),
        "port": PORT
    }


@app.get("/spec", tags=["Specification"])
async def get_active_spec():
    """Mengembalikan spesifikasi aktif default yang sedang dijalankan"""
    default_engine = agents_registry.get("default") or (next(iter(agents_registry.values())) if agents_registry else None)
    if not default_engine:
        raise HTTPException(status_code=404, detail="Belum ada agent yang aktif.")
    return default_engine.raw_spec


@app.post("/deploy", tags=["Deployment"])
async def deploy_agent_config(payload: DeployRequest):
    """
    Menerima deploy konfigurasi agent.yaml baru dari Agent Studio.
    Menyimpan secara persisten per slug dan mendaftarkannya ke registry aktif.
    """
    try:
        data = yaml.safe_load(payload.yaml_content) or {}
        metadata = data.get("metadata", {})
        slug = (
            getattr(payload, "slug", None)
            or metadata.get("slug")
            or data.get("slug")
            or metadata.get("id")
            or data.get("agent_id")
            or "default"
        )
        clean_slug = str(slug).strip().lower().replace(" ", "-")

        # Simpan persisten ke deployed_agents/{slug}.yaml
        agent_file = AGENTS_DIR / f"{clean_slug}.yaml"
        agent_file.write_text(payload.yaml_content, encoding="utf-8")

        # Buat instance engine baru khusus untuk agent ini
        new_engine = AgentRuntimeEngine(agent_file)
        agents_registry[clean_slug] = new_engine
        agents_registry["default"] = new_engine

        logger.info(f"[Multi-Agent Deploy] Berhasil mendaftarkan agent '{new_engine.name}' pada slug '{clean_slug}'.")

        return {
            "status": "deployed",
            "message": f"Agent '{new_engine.name}' (v{new_engine.version}) berhasil dideploy pada endpoint /agents/{clean_slug}/invoke.",
            "agent_id": new_engine.agent_id,
            "agent_slug": clean_slug,
            "endpoint": f"http://{HOST}:{PORT}/agents/{clean_slug}/invoke"
        }
    except Exception as e:
        logger.error(f"Gagal deploy agent: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Gagal mem-parsing file agent.yaml: {str(e)}")


@app.post("/invoke", response_model=InvokeResponse, tags=["Invocation"])
async def invoke_agent(payload: InvokeRequest):
    """
    Endpoint pemanggilan agent default yang sedang aktif.
    """
    default_engine = agents_registry.get("default") or (next(iter(agents_registry.values())) if agents_registry else None)
    if not default_engine:
        raise HTTPException(status_code=404, detail="Belum ada agent yang dideploy di runtime ini.")
    try:
        return await default_engine.run_step(payload.session_id, payload.message)
    except Exception as e:
        logger.error(f"Error saat mengeksekusi invoke: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Runtime error: {str(e)}")


@app.post("/agents/{agent_slug}/invoke", response_model=InvokeResponse, tags=["Multi-Agent Invocation"])
async def invoke_agent_by_slug(agent_slug: str, payload: InvokeRequest):
    """
    Multi-Agent Endpoint: Memanggil agent spesifik berdasarkan slug uniknya.
    Jika slug belum dideploy, mengembalikan HTTP 404 (tidak merespons secara sembarangan).
    """
    clean_slug = agent_slug.strip().lower()
    target_engine = agents_registry.get(clean_slug)

    if not target_engine:
        active_list = [s for s in agents_registry.keys() if s != "default"]
        raise HTTPException(
            status_code=404,
            detail=(
                f"Agent dengan slug '{agent_slug}' tidak ditemukan atau belum dideploy di server runtime ini. "
                f"Slug yang tersedia saat ini: {active_list}"
            )
        )

    try:
        logger.info(f"[Multi-Agent Runtime] Mengeksekusi permintaan untuk agent '{target_engine.name}' (slug: {clean_slug})")
        resp = await target_engine.run_step(payload.session_id, payload.message)
        return resp
    except Exception as e:
        logger.error(f"Error saat mengeksekusi invoke [{agent_slug}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Runtime error: {str(e)}")


@app.get("/agents/{agent_slug}/health", tags=["Monitoring"])
async def health_check_by_slug(agent_slug: str):
    """Health check spesifik untuk agent berdasarkan slug"""
    clean_slug = agent_slug.strip().lower()
    target_engine = agents_registry.get(clean_slug)
    if not target_engine:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_slug}' tidak ditemukan.")

    return {
        "status": "healthy",
        "slug": clean_slug,
        "runtime": "Agent Studio Dedicated Runtime",
        "agent_id": target_engine.agent_id,
        "agent_name": target_engine.name,
        "version": target_engine.version,
        "nodes_loaded": len(target_engine.nodes_by_id)
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
