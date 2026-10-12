import os
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import re

from openai import AsyncOpenAI
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.builder_engine import execute_http, check_guardrails
from app.models.agent import AgentSpecModel
from app.models.chat import ConversationModel, MessageModel
from app.models.tool import ToolModel
from app.models.mcp import MCPServerModel
from app.schemas.agent import AgentSpecCreate, AgentSpecUpdate, AgentTestResponse
from app.services.tool_registry import ToolRegistryService

DEFAULT_BUILTIN_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "search_web": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Kata kunci pencarian web secara real-time"
            }
        },
        "required": ["query"]
    },
    "calculator": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Ekspresi matematika yang ingin dihitung, contoh: '25 * 4', '150000 * 0.11', '(12 + 8) / 2'"
            }
        },
        "required": ["expression"]
    },
    "api_fetch": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL endpoint REST API publik yang ingin di-request"
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST"],
                "description": "HTTP method yang digunakan (GET atau POST)",
                "default": "GET"
            }
        },
        "required": ["url"]
    }
}


def _clean_reasoning(text: str) -> str:
    """Membersihkan monolog batin / Chain-of-Thought (Inggris maupun Indonesia) dari respons LLM."""
    if not text:
        return ""

    # 1. Bersihkan tag XML seperti <thought>...</thought> atau <think>...</think>
    text = re.sub(r"<(thought|think)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

    # 2. Periksa paragraf di awal yang berisi refleksi/analisis pertanyaan
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return text.strip()

    reasoning_indicators = [
        "we need", "i need", "i must", "i should", "i will", "user wrote", "user asks",
        "user is asking", "the user", "user said", "context:", "so answer:",
        "pengguna bertanya", "user menanyakan", "saya harus", "saya perlu", "saya akan",
        "analisis:", "proses berpikir:", "tujuan respon:"
    ]

    while len(paragraphs) > 1:
        first_p_lower = paragraphs[0].lower()
        if any(ind in first_p_lower for ind in reasoning_indicators):
            paragraphs.pop(0)
        else:
            break

    result = "\n\n".join(paragraphs).strip()
    return result if result else text.strip()


class AgentService:
    @staticmethod
    async def get_all_agents(db: AsyncSession) -> List[AgentSpecModel]:
        result = await db.execute(select(AgentSpecModel).order_by(AgentSpecModel.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_agent_by_id(db: AsyncSession, agent_id: str) -> Optional[AgentSpecModel]:
        result = await db.execute(select(AgentSpecModel).where(AgentSpecModel.id == agent_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def filter_registered_tools(db: AsyncSession, tools: Optional[List[str]]) -> List[str]:
        if not tools:
            return []
        result = await db.execute(select(ToolModel.name).where(ToolModel.is_active == True))
        active_tool_names = set(result.scalars().all())
        return [t for t in tools if t in active_tool_names]

    @staticmethod
    async def create_agent(db: AsyncSession, payload: AgentSpecCreate) -> AgentSpecModel:
        data = payload.model_dump()
        if "tools" in data and data["tools"]:
            data["tools"] = await AgentService.filter_registered_tools(db, data["tools"])
        db_agent = AgentSpecModel(**data)
        db.add(db_agent)
        await db.commit()
        await db.refresh(db_agent)
        return db_agent

    @staticmethod
    async def update_agent(db: AsyncSession, agent_id: str, payload: AgentSpecUpdate) -> Optional[AgentSpecModel]:
        db_agent = await AgentService.get_agent_by_id(db, agent_id)
        if not db_agent:
            return None
        data = payload.model_dump(exclude_unset=True)
        if "tools" in data and data["tools"] is not None:
            data["tools"] = await AgentService.filter_registered_tools(db, data["tools"])
        for key, value in data.items():
            setattr(db_agent, key, value)
        await db.commit()
        await db.refresh(db_agent)
        return db_agent

    @staticmethod
    async def delete_agent(db: AsyncSession, agent_id: str) -> bool:
        db_agent = await AgentService.get_agent_by_id(db, agent_id)
        if not db_agent:
            return False
        await db.delete(db_agent)
        await db.commit()
        return True

    @staticmethod
    def _client_and_model(agent: AgentSpecModel) -> tuple[AsyncOpenAI, str]:
        # Prioritaskan API Key OpenRouter / LLM
        api_key = settings.LLM_API_KEY or settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("API Key LLM belum dikonfigurasi. Silakan paste OPENROUTER_API_KEY atau LLM_API_KEY di file .env backend.")

        # Tentukan nama model (default ke settings.LLM_MODEL)
        model = settings.LLM_MODEL or "z-ai/glm-5.3-flash"
        if agent.model and agent.model not in ["gpt-4o-mini", "default", "z-ai/glm-5.3", "gemini-flash-lite-latest", "gemini-flash-latest"]:
            if "googleapis.com" in settings.LLM_BASE_URL and "gemini" in agent.model:
                model = agent.model
            elif "openrouter.ai" in settings.LLM_BASE_URL and ("z-ai" in agent.model or "glm" in agent.model):
                model = agent.model

        # Header dan penyesuaian khusus jika menggunakan OpenRouter
        if "openrouter.ai" in settings.LLM_BASE_URL:
            if model in ["glm-5.3", "glm-5.3-flash"]:
                model = f"z-ai/{model}"

            headers = {
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Agent Studio",
            }
            return AsyncOpenAI(
                api_key=api_key,
                base_url=settings.LLM_BASE_URL,
                default_headers=headers,
                max_retries=1
            ), model

        return AsyncOpenAI(api_key=api_key, base_url=settings.LLM_BASE_URL, max_retries=1), model

    @staticmethod
    async def get_agent_history(db: AsyncSession, agent_id: str) -> List[dict]:
        """Mengambil seluruh riwayat pesan untuk agent ini dari database."""
        conv_title = f"test_session_{agent_id}"
        conv_res = await db.execute(
            select(ConversationModel)
            .where(ConversationModel.title == conv_title)
            .order_by(ConversationModel.created_at.desc())
        )
        conversation = conv_res.scalars().first()
        if not conversation:
            return []
        msg_res = await db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation.id)
            .order_by(MessageModel.created_at)
        )
        messages = msg_res.scalars().all()
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "status": "blocked" if "Harness Guardrails" in (m.content or "") else ("escalated" if "TIDAK DITEMUKAN" in (m.content or "") or "ESCALATED" in (m.content or "") else "ok"),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

    @staticmethod
    async def clear_agent_history(db: AsyncSession, agent_id: str) -> bool:
        """Menghapus sesi riwayat percakapan agent ini untuk memulai percakapan baru."""
        conv_title = f"test_session_{agent_id}"
        conv_res = await db.execute(
            select(ConversationModel).where(ConversationModel.title == conv_title)
        )
        conversations = conv_res.scalars().all()
        if conversations:
            for conv in conversations:
                await db.execute(delete(MessageModel).where(MessageModel.conversation_id == conv.id))
                await db.delete(conv)
            await db.commit()
            return True
        return False

    @staticmethod
    async def test_agent(db: AsyncSession, agent_id: str, message: str) -> AgentTestResponse:
        message_trimmed = message.strip()
        if not message_trimmed:
            raise ValueError("Pesan chat tidak boleh kosong.")
        db_agent = await AgentService.get_agent_by_id(db, agent_id)
        if not db_agent:
            raise ValueError(f"Agent dengan ID '{agent_id}' tidak ditemukan di database.")

        client, model = AgentService._client_and_model(db_agent)
        selected_tools = ", ".join(db_agent.tools or []) or "tidak ada"
        selected_mcp = ", ".join(db_agent.mcp_servers or []) or "tidak ada"
        system_message = (
            f"Nama agent: {db_agent.name}\n"
            f"Tujuan: {db_agent.description or ''}\n"
            f"Instruksi: {db_agent.instructions or ''}\n"
            f"Tools yang terdaftar untuk agent ini: {selected_tools}\n"
            f"MCP yang terdaftar: {selected_mcp}\n\n"
            "ATURAN MUTLAK:\n"
            "1. Berikan HANYA jawaban akhir langsung kepada pengguna dalam Bahasa Indonesia yang ramah dan alami.\n"
            "2. DILARANG KERAS menampilkan proses berpikir, monolog batin, analisis pertanyaan, atau teks acak dalam bahasa apapun.\n"
            "3. Selalu perhatikan dan ingat seluruh konteks percakapan sebelumnya secara utuh.\n"
            "4. Jika pengguna menanyakan data yang memerlukan tools yang terdaftar, GUNAKAN tool yang tersedia dan jangan mengarang data!\n"
            "5. Jika hasil tool mengindikasikan status error atau layanan tidak dapat dihubungi, jelaskan dengan jujur kepada pengguna bahwa sistem/server sumber data sedang mengalami gangguan atau offline, dan jangan membuat data fiktif!"
        )

        # ======================================================================
        # RESOLUSI TOOLS SECARA DINAMIS (LEVEL 2: DYNAMIC FUNCTION CALLING SCHEMA)
        # ======================================================================
        openai_tools = None
        if db_agent.tools and len(db_agent.tools) > 0:
            tool_res = await db.execute(
                select(ToolModel).where(
                    ToolModel.name.in_(db_agent.tools),
                    ToolModel.is_active == True,
                    or_(ToolModel.status == "published", ToolModel.status.is_(None))
                )
            )
            active_tools = tool_res.scalars().all()
            if active_tools:
                openai_tools = []
                for t in active_tools:
                    schema = t.input_schema or DEFAULT_BUILTIN_SCHEMAS.get(t.name) or {"type": "object", "properties": {}}
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description or f"Fungsi alat untuk {t.name}",
                            "parameters": schema
                        }
                    })

        # ======================================================================
        # LEVEL 3: AGENT HARNESS - PRE-CHECK GUARDRAIL (SECURITY & ANTI-LEAK)
        # ======================================================================
        sensitive_keywords = [
            "password", "kata sandi", "secret", "api key", "apikey",
            "token rahasia", "kredensial", "credential", "database password",
            "connection string", "drop table", "select * from users", "bypass guardrail"
        ]
        msg_lower = message_trimmed.lower()
        matched_sensitive = [kw for kw in sensitive_keywords if kw in msg_lower]

        if matched_sensitive:
            # Setup working memory conversation
            conv_title = f"test_session_{agent_id}"
            conv_res = await db.execute(
                select(ConversationModel)
                .where(ConversationModel.title == conv_title)
                .order_by(ConversationModel.created_at.desc())
            )
            conversation = conv_res.scalars().first()
            if not conversation:
                conversation = ConversationModel(user_id=agent_id, title=conv_title)
                db.add(conversation)
                await db.flush()

            # Rekam pesan user
            user_msg_db = MessageModel(
                conversation_id=conversation.id,
                role="user",
                content=message_trimmed
            )
            db.add(user_msg_db)

            blocked_response = (
                "\U0001f6e1\ufe0f **Permintaan Ditolak oleh Sistem Pengaman (Harness Guardrails)**\n\n"
                "Pesan Anda terdeteksi mengandung permintaan terhadap data sensitif, kredensial internal, "
                "atau kata kunci rahasia yang melanggar kebijakan keamanan sistem. "
                "Untuk menjaga privasi dan keamanan data, permintaan ini tidak dapat diproses."
            )
            assistant_msg_db = MessageModel(
                conversation_id=conversation.id,
                role="assistant",
                content=blocked_response
            )
            db.add(assistant_msg_db)
            await db.commit()

            trace_steps = [{
                "step": 1,
                "step_no": 1,
                "title": "Harness Pre-Check: Security Block",
                "type": "harness_guardrail",
                "tool_name": "pre_check_guardrail",
                "params": {"detected_patterns": matched_sensitive, "input_sample": message_trimmed[:60]},
                "result": {"status": "blocked", "action": "BLOCKED_PRE_LLM", "reason": "Sensitive keyword violation"},
                "detail": f"Pesan diblokir oleh Harness Pre-Check sebelum mencapai LLM demi keamanan (terdeteksi: {', '.join(matched_sensitive)})",
                "duration_ms": 1,
                "status": "error"
            }]

            return AgentTestResponse(
                agent_id=db_agent.id,
                agent_name=db_agent.name,
                response=blocked_response,
                status="blocked",
                trace_steps=trace_steps,
                timestamp=datetime.utcnow(),
            )

        # ======================================================================
        # LEVEL 1: WORKING MEMORY & DATABASE PERSISTENCE
        # ======================================================================
        conv_title = f"test_session_{agent_id}"
        conv_res = await db.execute(
            select(ConversationModel)
            .where(ConversationModel.title == conv_title)
            .order_by(ConversationModel.created_at.desc())
        )
        conversation = conv_res.scalars().first()
        if not conversation:
            conversation = ConversationModel(user_id=agent_id, title=conv_title)
            db.add(conversation)
            await db.flush()

        user_msg_db = MessageModel(
            conversation_id=conversation.id,
            role="user",
            content=message_trimmed
        )
        db.add(user_msg_db)
        await db.flush()

        history_res = await db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation.id)
            .order_by(MessageModel.created_at)
        )
        history_messages = history_res.scalars().all()

        # Sliding Window Memory: Batasi 8 pesan terakhir agar respon LLM tetap ringan dan tidak lag
        recent_messages = history_messages[-8:] if len(history_messages) > 8 else history_messages

        messages_for_llm: List[Dict[str, Any]] = [{"role": "system", "content": system_message}]
        for m in recent_messages:
            messages_for_llm.append({"role": m.role, "content": m.content})

        # ======================================================================
        # LEVEL 2: DYNAMIC TOOL CALLING EXECUTION LOOP (MAKSIMAL 6 ITERASI)
        # ======================================================================
        raw_response = ""
        trace_steps: List[Dict[str, Any]] = []
        max_iterations = 6

        for iteration in range(max_iterations):
            call_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages_for_llm,
                "temperature": 0.7,
                "max_tokens": 2500,
            }
            if openai_tools:
                call_kwargs["tools"] = openai_tools

            try:
                completion = await client.chat.completions.create(**call_kwargs)
            except Exception as exc:
                raise RuntimeError(f"LLM gagal memproses pesan untuk agent '{db_agent.name}': {exc}") from exc

            choice = completion.choices[0]
            msg = choice.message

            # Cek apakah LLM meminta tool calls (baik via struktur tool_calls resmi maupun tag <tool_call> GLM)
            active_tool_calls = list(msg.tool_calls or [])
            if not active_tool_calls and "<tool_call>" in (msg.content or ""):
                import re
                raw_c = msg.content or ""
                t_matches = re.findall(r'<tool_call>\s*([a-zA-Z0-9_-]+)\s*\((.*?)\)', raw_c)
                for fn_n, raw_a in t_matches:
                    p_args = {}
                    raw_a = raw_a.strip()
                    if raw_a.startswith("{") and raw_a.endswith("}"):
                        try:
                            p_args = json.loads(raw_a)
                        except Exception:
                            pass
                    if not p_args and raw_a:
                        pat = r'([a-zA-Z0-9_-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^,)]+))'
                        for m in re.finditer(pat, raw_a):
                            k = m.group(1)
                            v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4).strip())
                            p_args[k] = v

                    class MockFunction:
                        def __init__(self, name, args):
                            self.name = name
                            self.arguments = json.dumps(args, ensure_ascii=False)

                    class MockToolCall:
                        def __init__(self, name, args):
                            self.id = f"call_regex_{uuid.uuid4().hex[:8]}"
                            self.function = MockFunction(name, args)

                    active_tool_calls.append(MockToolCall(fn_n, p_args))

            # Jika LLM tidak meminta pemanggilan tool, kita sudah mendapatkan jawaban akhir!
            if not active_tool_calls:
                raw_response = msg.content or ""
                break

            # Jika LLM meminta pemanggilan tool (Function Calling)
            if hasattr(msg, "model_dump") and msg.tool_calls:
                messages_for_llm.append(msg.model_dump(exclude_none=True))
            else:
                tool_calls_payload = []
                for tc in active_tool_calls:
                    tc_dict = {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}"
                        }
                    }
                    if hasattr(tc, "extra_content") and tc.extra_content:
                        tc_dict["extra_content"] = tc.extra_content
                    tool_calls_payload.append(tc_dict)

                messages_for_llm.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": tool_calls_payload
                })

            # Eksekusi setiap tool yang diminta oleh LLM secara dinamis
            for tc in active_tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except Exception:
                    fn_args = {}

                try:
                    # Cek apakah tool memiliki konfigurasi deklaratif dari builder_engine (Tool Factory)
                    t_spec_res = await db.execute(select(ToolModel).where(ToolModel.name == fn_name))
                    t_spec_obj = t_spec_res.scalar_one_or_none()
                    
                    if t_spec_obj and t_spec_obj.implementation and t_spec_obj.implementation.get("type") == "http":
                        # Jalankan via Safe Egress HTTP Executor (builder_agent_core)
                        t_http_spec = {
                            "name": t_spec_obj.name,
                            "description": t_spec_obj.description or "",
                            "input_schema": t_spec_obj.input_schema or {},
                            "implementation": t_spec_obj.implementation,
                            "effect": t_spec_obj.effect or "read"
                        }
                        allowed_hosts = ["*.trycloudflare.com", "trycloudflare.com", "localhost", "127.0.0.1", "*"]
                        start_time = time.time()
                        exec_res = execute_http(t_http_spec, fn_args, vault={}, allowed_hosts=allowed_hosts)
                        duration_ms = int((time.time() - start_time) * 1000)
                        
                        if exec_res.get("ok"):
                            tool_result = exec_res.get("data", exec_res)
                            if isinstance(tool_result, dict):
                                tool_result["_endpoint"] = t_spec_obj.implementation.get("url")
                                tool_result["_source"] = "Declarative HTTP Executor (Core Engine)"
                        else:
                            tool_result = {"status": "error", "message": f"Eksekusi HTTP tool gagal: {exec_res.get('error')}"}
                    else:
                        # Fallback ke built-in / live API registry
                        tool_exec = await ToolRegistryService.execute_tool(db, fn_name, fn_args)
                        tool_result = tool_exec.get("result", tool_exec)
                        duration_ms = tool_exec.get("duration_ms", 0)
                except Exception as err:
                    tool_result = {"status": "error", "message": f"Eksekusi tool '{fn_name}' gagal: {str(err)}"}
                    duration_ms = 0

                # Deteksi target endpoint live API / deklaratif
                endpoint_url = None
                if isinstance(tool_result, dict) and tool_result.get("_endpoint"):
                    endpoint_url = tool_result.get("_endpoint")
                elif t_spec_obj and t_spec_obj.implementation and isinstance(t_spec_obj.implementation, dict):
                    endpoint_url = t_spec_obj.implementation.get("url")

                source_name = "Local Service"
                if isinstance(tool_result, dict):
                    if tool_result.get("_source"):
                        source_name = tool_result.get("_source")
                    elif endpoint_url:
                        source_name = "External Service API"

                is_tool_error = False
                if isinstance(tool_result, dict):
                    if tool_result.get("status") in ["error", "ERROR"] or tool_result.get("error"):
                        is_tool_error = True

                # Rekam ke trace steps untuk observabilitas UI
                trace_steps.append({
                    "step": len(trace_steps) + 1,
                    "step_no": len(trace_steps) + 1,
                    "title": f"Call Tool: {fn_name}",
                    "type": "tool_calling",
                    "tool_name": fn_name,
                    "endpoint": endpoint_url or f"internal://tools/{fn_name}",
                    "source": source_name,
                    "params": fn_args,
                    "result": tool_result,
                    "detail": f"{fn_name}({json.dumps(fn_args, ensure_ascii=False)})",
                    "duration_ms": duration_ms,
                    "status": "error" if is_tool_error else "ok"
                })

                # Masukkan hasil tool kembali ke konteks LLM
                messages_for_llm.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })

        # ======================================================================
        # LEVEL 3: AGENT HARNESS - POST-CHECK & ESCALATION GUARDRAILS
        # ======================================================================
        final_status = "ok"
        escalation_reasons = []

        # 1. Periksa apakah salah satu hasil eksekusi tool mengindikasikan status NOT_FOUND / gagal
        for step in trace_steps:
            res = step.get("result")
            if isinstance(res, dict):
                st = str(res.get("status", "")).lower()
                if "tidak ditemukan" in st or "not_found" in st:
                    escalation_reasons.append(f"Hasil tool '{step.get('tool_name')}' tidak ditemukan dalam database")
                elif st == "error" or res.get("error"):
                    escalation_reasons.append(f"Tool '{step.get('tool_name')}' mengalami kegagalan eksekusi")

        # 2. Periksa apakah pengguna meminta eskalasi ke staf manusia (secara fleksibel)
        import re
        escalation_pattern = r"(bicara|hubung|kontak|eskalasi|bantuan).*(manusia|petugas|operator|staf)|operator|staf manusia|customer service"
        if re.search(escalation_pattern, msg_lower):
            escalation_reasons.append("Pengguna meminta terhubung langsung dengan petugas/staf manusia")

        if escalation_reasons:
            final_status = "escalated"
            escalation_dest = f"Tim Dukungan Layanan ({db_agent.name}) / Operator Manusia"

            trace_steps.append({
                "step": len(trace_steps) + 1,
                "step_no": len(trace_steps) + 1,
                "title": "Harness Post-Check: Escalation to Human",
                "type": "harness_escalation",
                "tool_name": "post_check_escalation",
                "params": {"triggers": escalation_reasons},
                "result": {
                    "action": "ESCALATED",
                    "destination": escalation_dest,
                    "reason": "; ".join(escalation_reasons)
                },
                "detail": f"Kasus dialihkan ke antrean petugas manusia oleh Harness Post-Check: {'; '.join(escalation_reasons)}",
                "duration_ms": 1,
                "status": "ok"
            })

        # Bersihkan jawaban akhir dari monolog internal
        response_clean = _clean_reasoning(raw_response)
        if not response_clean:
            response_clean = raw_response.strip() or "Maaf, saya tidak dapat merangkum data saat ini."

        # Simpan pesan balasan asisten ke database
        assistant_msg_db = MessageModel(
            conversation_id=conversation.id,
            role="assistant",
            content=response_clean
        )
        db.add(assistant_msg_db)
        await db.commit()

        return AgentTestResponse(
            agent_id=db_agent.id,
            agent_name=db_agent.name,
            response=response_clean,
            status=final_status,
            trace_steps=trace_steps,
            timestamp=datetime.utcnow(),
        )

    @staticmethod
    async def export_agent_yaml(db: AsyncSession, agent_id: str, save_to_disk: bool = True) -> Optional[Dict[str, Any]]:
        """Mengekspor spesifikasi Agent ke format deklaratif .YAML standar dengan tools_required dan endpoint live terintegrasi."""
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            return None

        slug = re.sub(r"[^a-z0-9]+", "_", (agent.name or "agent").lower()).strip("_")

        # 1. Resolusi dinamis endpoint dan server MCP dari database
        mcp_res = await db.execute(select(MCPServerModel))
        all_mcps = mcp_res.scalars().all()
        mcp_by_id = {m.id: m for m in all_mcps}

        # Cari base URL terbaik untuk live API (Cloudflare tunnel / mock API)
        active_api_base = None
        for m in all_mcps:
            if m.url and not m.url.endswith("/local-server") and m.status == "connected":
                active_api_base = m.url.rstrip("/")
                break
        if not active_api_base:
            active_api_base = (getattr(settings, "EXTERNAL_MOCK_API_URL", None) or os.getenv("EXTERNAL_MOCK_API_URL", "")).rstrip("/")

        # 2. Ambil semua tools yang tercatat di agent
        tools_list = agent.tools or []
        tools_res = await db.execute(select(ToolModel).where(ToolModel.name.in_(tools_list)))
        db_tools_map = {t.name: t for t in tools_res.scalars().all()}

        # Utilitas bawaan umum
        builtin_general_defs: Dict[str, Dict[str, Any]] = {
            "search_web": {
                "path": "https://duckduckgo.com",
                "method": "GET",
                "purpose": "Pencarian web real-time untuk informasi publik",
                "source_type": "builtin"
            },
            "calculator": {
                "path": "internal://calc/eval",
                "method": "INTERNAL",
                "purpose": "Evaluasi perhitungan matematika dan kalkulasi angka",
                "source_type": "builtin"
            },
        }

        tools_required_list = []
        for tname in tools_list:
            t_obj = db_tools_map.get(tname)
            
            # Resolusi sumber MCP Server jika terikat
            mcp_srv = None
            if t_obj and t_obj.mcp_server_id:
                mcp_srv = mcp_by_id.get(t_obj.mcp_server_id)

            endpoint = None
            method = "POST"
            conn_status = "unconfigured"
            source_type = t_obj.source_type if t_obj else "custom"
            purpose = (t_obj.description if t_obj and t_obj.description else None) or f"Layanan tool {tname}"
            mcp_name = mcp_srv.name if mcp_srv else None

            # Prioritas 1: Tool deklaratif dari Tool Factory (implementation.type == 'http')
            if t_obj and t_obj.implementation and isinstance(t_obj.implementation, dict):
                impl = t_obj.implementation
                endpoint = impl.get("url")
                method = impl.get("method", "GET")
                source_type = impl.get("type", "http")
                conn_status = "connected" if endpoint else "unconfigured"
            
            # Prioritas 2: Built-in general utility
            elif tname in builtin_general_defs:
                b_def = builtin_general_defs[tname]
                endpoint = b_def.get("path")
                method = b_def.get("method", "GET")
                source_type = b_def.get("source_type", "builtin")
                purpose = b_def.get("purpose", purpose)
                conn_status = "connected"
            
            # Prioritas 3: MCP Server
            elif mcp_srv and mcp_srv.url:
                endpoint = f"{mcp_srv.url.rstrip('/')}/tools/{tname}"
                method = "POST"
                source_type = "mcp"
                conn_status = "connected"
            
            # Prioritas 4: Fallback OpenAPI / config in schema
            elif t_obj and t_obj.input_schema:
                schema_cfg = t_obj.input_schema.get("x-api-config", {}) or t_obj.input_schema.get("x-openapi", {})
                b_url = schema_cfg.get("base_url") or schema_cfg.get("server_url")
                if b_url:
                    endpoint = f"{b_url.rstrip('/')}/{tname}"
                    conn_status = "connected"

            # Ambil input schema
            schema = (t_obj.input_schema if t_obj and t_obj.input_schema else None) or DEFAULT_BUILTIN_SCHEMAS.get(tname, {"type": "object", "properties": {}})

            tools_required_list.append({
                "tool_ref": tname,
                "tool_name": t_obj.name if t_obj else tname,
                "purpose": purpose,
                "source_type": source_type,
                "mcp_server_name": mcp_name,
                "endpoint": endpoint,
                "method": method,
                "connection_status": conn_status,
                "auth_secret_ref": None,
                "input_schema": schema
            })

        spec_dict = {
            "spec_version": "v1.0",
            "metadata": {
                "id": agent.id,
                "name": agent.name,
                "slug": slug,
                "description": agent.description or "",
                "status": agent.status or "active",
                "created_at": agent.created_at.isoformat() if agent.created_at else None,
                "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            },
            "configuration": {
                "model": agent.model if agent.model and agent.model != "gpt-4o-mini" else (settings.LLM_MODEL or "z-ai/glm-5.3"),
                "harness": agent.harness or "default-safe-v1",
            },
            "tools": agent.tools or [],
            "mcp_servers": agent.mcp_servers or [],
            "instructions": agent.instructions or "",
            "flow": {
                "entry_node": "main_step",
                "nodes": [
                    {
                        "id": "main_step",
                        "type": "llm_step",
                        "instruction": "Tanggapi dan bantu kebutuhan pengguna dengan memanfaatkan tools yang relevan secara akurat sesuai instruksi.",
                        "next": "selesai"
                    },
                    {"id": "selesai", "type": "end"}
                ]
            },
            "tools_required": tools_required_list,
            "guardrails": {
                "max_turns": 15,
                "strict_grounding": True,
                "disallowed_behaviors": [
                    "memberi diagnosis pasti tanpa dokter",
                    "merekomendasikan obat atau dosis spesifik",
                    "mengabaikan keluhan yang mengindikasikan kondisi darurat"
                ]
            }
        }

        import yaml
        class IndentedDumper(yaml.Dumper):
            pass
        def represent_str(dumper, data):
            if "\n" in data:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)
        IndentedDumper.add_representer(str, represent_str)

        yaml_content = yaml.dump(spec_dict, Dumper=IndentedDumper, sort_keys=False, allow_unicode=True)
        filename = f"{slug}.yaml"
        saved_paths = []

        if save_to_disk:
            import os
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

            # 1. agents/{filename}
            agents_dir = os.path.join(root_dir, "agents")
            os.makedirs(agents_dir, exist_ok=True)
            file_path = os.path.join(agents_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            saved_paths.append(file_path)

            # 2. frontend/agent-project/agents/{filename}
            project_agents_dir = os.path.join(root_dir, "frontend", "agent-project", "agents")
            os.makedirs(project_agents_dir, exist_ok=True)
            fp2 = os.path.join(project_agents_dir, filename)
            with open(fp2, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            saved_paths.append(fp2)

            # 3. backend/{filename}
            fp3 = os.path.join(backend_dir, filename)
            with open(fp3, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            saved_paths.append(fp3)

            # 4. backend/deployed_agents/{filename}
            deployed_dir = os.path.join(backend_dir, "deployed_agents")
            os.makedirs(deployed_dir, exist_ok=True)
            fp4 = os.path.join(deployed_dir, filename)
            with open(fp4, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            saved_paths.append(fp4)

        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "filename": filename,
            "yaml": yaml_content,
            "saved_paths": saved_paths
        }
