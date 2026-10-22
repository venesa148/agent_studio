import json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from openai import AsyncOpenAI
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models.agent import AgentSpecModel
from app.models.tool import ToolModel
from app.models.mcp import MCPServerModel
from app.schemas.agent import AgentSpec, AgentSpecResponse, BuilderChatResponse
from app.services.rag.ingestion import fetch_url_content, validate_url_safety, SSRFValidationError
from app.services.rag.vector_service import VectorService

logger = logging.getLogger("builder_service")


class BuilderService:
    """
    Meta-Architect Builder Agent:
    Menganalisis kebutuhan pengguna dalam bahasa alami, mengklasifikasikan kebutuhan ke dalam
    4 Arketipe Sumber Daya (Knowledge RAG, Generic REST API, Local DB, MCP Catalog),
    menghasilkan draf AGENT.YAML fungsional di Turn 1 (Turn-1 Ready),
    serta memberikan panduan proaktif dan perhitungan skor kesiapan (Health Score).
    """

    @staticmethod
    def _agent_name(prompt: str) -> str:
        cleaned = prompt.strip().rstrip(".!?")

        # 1. Deteksi pola eksplisit: "bernama [Nama Agent]" atau "nama [Nama Agent]"
        named_match = re.search(
            r"(?:bernama|nama(?:nya)?|called|named)\s+[\"\'\`]?([A-Za-z0-9\s/_-]+?)[\"\'\`]?(?:\s+(?:untuk|yang|guna|agar|dengan|sebagai)|\.|\,|$)",
            cleaned,
            re.IGNORECASE,
        )
        if named_match:
            candidate = named_match.group(1).strip()
            if candidate and len(candidate.split()) <= 6:
                name = candidate.title()
                for acr in ["AI", "API", "IT", "CS", "HR", "CRM", "ERP", "SOP", "URL", "JSON", "REST", "SQL", "BPJS"]:
                    name = re.sub(rf"\b{acr.capitalize()}\b", acr, name)
                return name

        lowered = cleaned.lower()

        # 2. Token-based check: jika prompt hanya berisi salam / filler words
        intent_and_filler_words = {
            "halo", "hai", "hi", "hei", "hey", "hallo", "selamat", "pagi", "siang", "sore", "malam",
            "saya", "aku", "kami", "kita", "gue", "gw",
            "ingin", "mau", "pengen", "hendak", "akan",
            "membuat", "buat", "buatkan", "bikin", "bikinin", "ciptakan", "create", "build", "make",
            "tolong", "bantu", "bisa", "coba", "mohon", "tolonglah",
            "ai", "agent", "agen", "bot", "asisten", "assistant",
            "dong", "deh", "ya", "yah", "nih", "lah", "kan", "pun", "saja", "aja", "sebuah", "suatu", "satu", "dulu",
        }
        words = re.findall(r"[a-zA-Z0-9]+", lowered)
        non_filler = [w for w in words if w not in intent_and_filler_words]
        if not non_filler:
            return "Asisten AI Serbaguna"

        # 3. Bersihkan prefix instruksi umum jika ada domain substantif di belakangnya
        clean_regex = (
            r"^(?:halo|hai|hi|hei|selamat\s+(?:pagi|siang|sore|malam))?[,\s]*"
            r"(?:saya|aku|kami)?\s*(?:ingin|mau|pengen|coba)?\s*(?:halo|hai)?[,\s]*"
            r"(?:tolong\s+)?(?:buatkan|membuat|bikin|buat|ciptakan|create)\s+"
            r"(?:aku\s+|saya\s+)?(?:agent\s+|agen\s+|ai\s+|bot\s+|asisten\s+)?"
            r"(?:asisten\s+)?"
        )
        cleaned = re.sub(clean_regex, "", cleaned, flags=re.IGNORECASE).strip()

        # Potong klausul penjelas
        split_match = re.split(r"\s+(?:untuk|yang|guna|agar|sebagai)\s+", cleaned, flags=re.IGNORECASE)
        if split_match and len(split_match[0].strip()) > 0:
            cleaned = split_match[0].strip()

        if not cleaned or cleaned.lower() in ("ai", "agent", "agen", "bot", "asisten", "asisten ai"):
            return "Asisten AI Serbaguna"

        name = cleaned[:50].strip().title()
        if not name.lower().startswith("asisten") and not name.lower().startswith("agent") and not name.lower().startswith("bot"):
            name = f"Asisten {name}"

        for acr in ["AI", "API", "IT", "CS", "HR", "CRM", "ERP", "SOP", "URL", "JSON", "REST", "SQL", "BPJS"]:
            name = re.sub(rf"\b{acr.capitalize()}\b", acr, name)
        return name

    @staticmethod
    def _compute_health_score(
        name: str,
        instructions: str,
        tools: List[str],
        has_knowledge: bool = False,
        has_guardrails: bool = False,
    ) -> int:
        """
        Menghitung skor kesiapan agen (Agent Readiness Health Score 0-100%):
        - Nama & Identitas Jelas: 25%
        - SOP & Instruksi Operasional Terstruktur (panjang >= 60 karakter): 25%
        - Tools / Integrasi Aktif (Katalog / HTTP): 25%
        - Knowledge Base (RAG) atau Batasan Keamanan (Guardrails): 25%
        """
        score = 0
        if name and name != "Asisten AI Serbaguna":
            score += 25
        elif name:
            score += 15

        if instructions and len(instructions.strip()) >= 60:
            score += 25
        elif instructions:
            score += 15

        if tools and len(tools) > 0:
            score += 25

        if has_knowledge or has_guardrails:
            score += 25

        return min(max(score, 25), 100)

    @staticmethod
    async def _detect_and_ingest_url(db: AsyncSession, prompt: str, agent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Mendeteksi jika pengguna mencantumkan URL web referensi di dalam chat prompt.
        Jika terdeteksi dan bukan API endpoint, sistem otomatis mengambil kontennya secara aman (anti-SSRF)
        dan menyimpannya ke Knowledge Base (PostgreSQL) ditautkan ke agent_id.
        """
        url_match = re.search(r"https?://[^\s,()<>'\"]+", prompt)
        if not url_match:
            return None

        detected_url = url_match.group(0).rstrip(".,;")
        # Jika URL mengindikasikan API endpoint murni, biarkan ditangani oleh Tool Factory
        if "/api/" in detected_url.lower() or detected_url.lower().endswith((".json", ".xml")):
            return None

        try:
            validate_url_safety(detected_url)
            scraped_text = await fetch_url_content(detected_url, timeout_sec=8.0)
            if scraped_text and len(scraped_text.strip()) > 30:
                doc_title = f"Web: {detected_url[:35]}"
                # Jika agent_id adalah draft yang belum ada di tabel agent_specs, set None agar lolos foreign key FK
                db_agent_id = agent_id if (agent_id and not str(agent_id).startswith("draft_")) else None
                doc = await VectorService.ingest_document(
                    db=db,
                    title=doc_title,
                    source_type="url",
                    source_uri=detected_url,
                    text_content=scraped_text,
                    agent_id=db_agent_id,
                )
                return {
                    "doc_id": doc.id,
                    "title": doc_title,
                    "uri": detected_url,
                    "type": "url",
                    "total_chunks": doc.total_chunks,
                    "agent_id": agent_id,
                }
        except Exception as exc:
            logger.warning(f"URL auto-ingestion dilewati untuk '{detected_url}': {exc}")

        return None

    @staticmethod
    async def _select_tools_from_db(db: AsyncSession, prompt: str) -> List[str]:
        """Ambil tools yang aktif HANYA dari database (tabel tools)."""
        result = await db.execute(select(ToolModel).where(ToolModel.is_active == True))
        db_tools = list(result.scalars().all())
        if not db_tools:
            return []

        available_tool_names = {t.name for t in db_tools}
        prompt_lower = prompt.lower()

        # Heuristik pencocokan semantik & kata kunci terhadap katalog tools
        selected = []
        prompt_words = set(re.findall(r"\w+", prompt_lower))
        for tool in db_tools:
            t_name = tool.name.lower()
            t_desc = (tool.description or "").lower()
            name_words = set(re.findall(r"\w+", t_name))
            desc_words = {w for w in re.findall(r"\w+", t_desc) if len(w) >= 4}

            if (prompt_words & name_words) or (prompt_words & desc_words):
                if tool.name not in selected:
                    selected.append(tool.name)

        return [t for t in selected if t in available_tool_names]

    @staticmethod
    def _extract_dynamic_tools_from_text(prompt: str, detected_url: Optional[str] = None, target_agent_id: str = "") -> List[Dict[str, Any]]:
        """
        Mengekstrak dan mensintesis tools secara dinamis dari intent pengguna dan URL web (jika ada).
        100% domain-agnostik tanpa hardcode spesifik perusahaan.
        """
        tools: List[Dict[str, Any]] = []
        p_lower = prompt.lower()
        base_url = detected_url.rstrip("/") if detected_url else ""

        action_patterns = [
            (r"\b(?:reservasi|booking|pesan|book)\s+([a-zA-Z0-9_-]+)", "write", "melakukan pemesanan/reservasi", "reservasi"),
            (r"\b(?:cek|check|lacak|tracking|status)\s+([a-zA-Z0-9_-]+)", "read", "memeriksa atau melacak status", "cek_status"),
            (r"\b(?:cari|search|lihat|katalog|daftar|menu)\s+([a-zA-Z0-9_-]+)", "read", "mencari atau melihat katalog", "cari"),
            (r"\b(?:batal|cancel|batalkan)\s+([a-zA-Z0-9_-]+)", "write", "membatalkan transaksi atau pesanan", "batalkan"),
            (r"\b(?:kirim|submit|buat|create)\s+([a-zA-Z0-9_-]+)", "write", "membuat atau mengirim data baru", "buat"),
        ]

        found_actions = set()
        stop_nouns = {"dan", "untuk", "yang", "pada", "di", "ke", "dari", "website", "web", "ini", "itu", "agen", "agent", "bot", "asisten", "assistant", "ai"}

        for pattern, effect, desc_action, prefix in action_patterns:
            matches = re.findall(pattern, p_lower)
            for target_noun in matches:
                target_noun = target_noun.strip()
                if not target_noun or target_noun in stop_nouns or len(target_noun) < 3:
                    continue

                tool_name = f"{prefix}_{target_noun}"
                tool_name = re.sub(r"[^a-zA-Z0-9_]", "_", tool_name).strip("_")

                if tool_name in found_actions:
                    continue
                found_actions.add(tool_name)

                if effect == "write":
                    input_schema = {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Nama pemesan/pengguna"},
                            "contact": {"type": "string", "description": "Nomor kontak / WhatsApp"},
                            "details": {"type": "string", "description": f"Detail informasi {target_noun}"},
                        },
                        "required": ["name"]
                    }
                else:
                    input_schema = {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": f"ID, kode, atau kata kunci pencarian {target_noun}"},
                        },
                        "required": ["query"]
                    }

                endpoint_url = f"{base_url}/api/{target_noun}s" if base_url else f"{{api_base}}/api/{tool_name}"
                method = "POST" if effect == "write" else "GET"

                tools.append({
                    "name": tool_name,
                    "description": f"Tool dinamis untuk {desc_action} {target_noun} secara terintegrasi.",
                    "input_schema": input_schema,
                    "implementation": {
                        "type": "http",
                        "url": endpoint_url,
                        "method": method
                    },
                    "effect": effect,
                    "status": "draft",
                    "used_by": target_agent_id
                })

        # Jika pengguna menyebut 'customer service' atau 'cs' atau 'layanan pelanggan'
        if any(w in p_lower for w in ["customer service", "cs", "layanan pelanggan", "bantuan"]) and not any("status" in t["name"] or "support" in t["name"] for t in tools):
            tools.append({
                "name": "inquiry_customer_service",
                "description": "Tool untuk memeriksa status tiket atau mengirim eskalasi pertanyaan layanan pelanggan.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Topik pertanyaan atau keluhan"},
                        "user_id": {"type": "string", "description": "ID pelanggan atau kontak"}
                    },
                    "required": ["subject"]
                },
                "implementation": {
                    "type": "http",
                    "url": f"{base_url}/api/support" if base_url else "{api_base}/api/support",
                    "method": "POST"
                },
                "effect": "read",
                "status": "draft",
                "used_by": target_agent_id
            })

        return tools

    @staticmethod
    async def build_agent_spec(
        db: AsyncSession, prompt: str, current_spec: Optional[AgentSpec] = None, history: Optional[List[Any]] = None
    ) -> BuilderChatResponse:
        prompt_trimmed = prompt.strip()
        if not prompt_trimmed:
            raise ValueError("Prompt tidak boleh kosong.")

        # Tentukan ID target agent (pertahankan jika sudah ada, atau buat draft ID baru)
        target_agent_id = (
            current_spec.id if current_spec and current_spec.id else f"draft_{int(time.time() * 1000)}"
        )

        # Ambil daftar tools yang aktif 100% DINAMIS dari database
        db_tools_result = await db.execute(select(ToolModel).where(ToolModel.is_active == True))
        db_tools = db_tools_result.scalars().all()
        valid_db_tools = {t.name: (t.description or "") for t in db_tools}

        # Cek apakah ada URL yang bisa di-ingest otomatis ke Knowledge Base
        auto_knowledge_source = await BuilderService._detect_and_ingest_url(db, prompt_trimmed, agent_id=target_agent_id)

        client = None
        model = None
        api_key = settings.LLM_API_KEY or settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
        if api_key:
            headers = {}
            if "openrouter.ai" in (settings.LLM_BASE_URL or ""):
                headers = {
                    "HTTP-Referer": "https://agentstudio.ai",
                    "X-Title": "Agent Studio",
                }
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.LLM_BASE_URL if ("openrouter.ai" in (settings.LLM_BASE_URL or "") or "googleapis.com" in (settings.LLM_BASE_URL or "")) else None,
                default_headers=headers,
                max_retries=1,
            )
            model = settings.LLM_MODEL or settings.OPENAI_DEFAULT_MODEL or "openrouter/free"

        if client and model:
            tools_info_list = []
            for t in db_tools:
                src_label = f"[{t.source_type.upper()}]" if t.source_type else "[TOOL]"
                tools_info_list.append(f"{t.name} ({src_label}: {t.description or 'No description'})")
            tools_info = "\n".join([f"- {item}" for item in tools_info_list]) if tools_info_list else "Belum ada tools aktif di database."
            current_spec_json = current_spec.model_dump_json() if current_spec else "Belum ada spesifikasi awal."

            system_msg = (
                "Anda adalah 'AI Agent Architect & Meta-Builder' di Agent Studio (terinspirasi dari Sierra & Cohere).\n"
                "Tugas Anda: Menerjemahkan kebutuhan pengguna menjadi arsitektur AI Agent lengkap, profesional, dan siap diuji.\n\n"
                "4 ARKETIPE SUMBER DAYA (RESOURCE ARCHETYPES):\n"
                "Pahami perbedaan 4 jenis kebutuhan pengguna secara presisi:\n"
                "1. ARKETIPE 1: KNOWLEDGE / DOKUMEN (RAG)\n"
                "   - Jika pengguna menyebutkan dokumen, file PDF, katalog produk, SOP teks, atau URL web informasi (contoh: https://kopikamu.com).\n"
                "   - JANGAN membuat custom code tool untuk membaca PDF! Masukkan referensi ke 'knowledge_sources' dan instruksikan agent untuk merujuk ke knowledge base.\n"
                "2. ARKETIPE 2: REST API ACTIONS (GENERIC HTTP TOOLS)\n"
                "   - Jika pengguna ingin agent melakukan aksi aktif ke internet (contoh: booking meja, cek resi, create tiket, fetch endpoint API).\n"
                "   - Buatkan tool baru di array 'new_tools' dengan format: {name, description, input_schema, implementation: {type: 'http', url: '...', method: 'POST'|'GET'}, effect: 'write'|'read'}.\n"
                "3. ARKETIPE 3: DATABASE LOKAL (LOCAL DB CONNECTOR)\n"
                "   - Jika pengguna ingin agent membaca tabel database internal (MySQL/Postgres/SQLite) milik mereka.\n"
                "   - Buatkan spesifikasi tool di 'new_tools' dengan {name, description, input_schema, implementation: {type: 'local_db'}, effect: 'read'}.\n"
                "4. ARKETIPE 4: TOOLS KATALOG / MCP\n"
                f"   - Pilih nama tool yang cocok dari daftar database aktif saat ini:\n{tools_info}\n\n"
                "PRINSIP UTAMA:\n"
                "1. TURN-1 READY: Langsung hasilkan draf agent yang lengkap dan berfungsi di putaran pertama.\n"
                "2. ANTI-AMNESIA: Pada putaran revisi, pertahankan nama, konteks, SOP lama, dan perbarui hanya bagian yang diminta.\n"
                "3. PROAKTIF & DINAMIS: Jelaskan apa yang telah dirancang, beri tahu bahwa bot sudah aktif di panel kanan (Test Chat), dan usulkan 1-2 ide perbaikan domain spesifik.\n"
                "4. ATURAN COMMIT: Set 'should_commit': true HANYA jika pengguna secara eksplisit meminta menyimpan ('simpan', 'commit', 'save').\n"
                "5. EFISIENSI TOKEN: Tuliskan instruksi dan respons secara padat, jelas, dan ringkas (maksimal 200 kata) agar JSON lengkap dan valid.\n\n"
                "FORMAT BALASAN (Wajib JSON valid di dalam blok ```json ... ```):\n"
                "{\n"
                '  "message": "Konfirmasi ramah apa yang baru dirancang + ajakan tes di panel kanan + saran fitur lanjutan",\n'
                '  "spec_updated": true,\n'
                '  "should_commit": false,\n'
                '  "spec": {\n'
                '    "name": "Nama Agent",\n'
                '    "description": "Tugas utama agent",\n'
                '    "instructions": "System prompt lengkap (Peran, SOP terstruktur, Batasan Keamanan)",\n'
                '    "tools": ["nama_tool_katalog"],\n'
                '    "knowledge_sources": [],\n'
                '    "guardrails": {"require_confirmation_for": ["nama_tool_mutasi"]}\n'
                '  },\n'
                '  "new_tools": []\n'
                "}\n\n"
                f"Spesifikasi saat ini: {current_spec_json}\n"
            )

            messages = [{"role": "system", "content": system_msg}]
            if history:
                recent_history = history[-4:] if len(history) > 4 else history
                for h in recent_history:
                    content_str = h.content if hasattr(h, "role") else (h.get("content", "") if isinstance(h, dict) else str(h))
                    if content_str and len(content_str) > 500:
                        content_str = content_str[:500] + "..."
                    role_str = h.role if hasattr(h, "role") else (h.get("role", "user") if isinstance(h, dict) else "user")
                    messages.append({"role": role_str, "content": content_str or ""})

            messages.append({"role": "user", "content": prompt_trimmed})

            try:
                builder_max_tokens = getattr(settings, "BUILDER_MAX_TOKENS", 1500)
                try:
                    completion = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=builder_max_tokens,
                        timeout=65.0,
                    )
                except Exception as call_err:
                    fallback_model = getattr(settings, "LLM_FALLBACK_MODEL", "openrouter/free")
                    if ("402" in str(call_err) or "credits" in str(call_err).lower() or "fewer max_tokens" in str(call_err).lower()) and model != fallback_model:
                        logger.warning(f"[BuilderService] Model {model} gagal (402/kredit). Otomatis fallback ke '{fallback_model}'...")
                        completion = await client.chat.completions.create(
                            model=fallback_model,
                            messages=messages,
                            temperature=0.2,
                            max_tokens=builder_max_tokens,
                            timeout=65.0,
                        )
                    else:
                        raise call_err

                msg_obj = completion.choices[0].message
                content = msg_obj.content or ""
                if not content.strip() and hasattr(msg_obj, "reasoning") and msg_obj.reasoning:
                    content = msg_obj.reasoning

                parsed = None
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if match:
                    try:
                        parsed = json.loads(match.group(1).strip(), strict=False)
                    except Exception:
                        pass

                if not parsed:
                    first_brace = content.find("{")
                    last_brace = content.rfind("}")
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        try:
                            parsed = json.loads(content[first_brace : last_brace + 1].strip(), strict=False)
                        except Exception:
                            pass

                if parsed and isinstance(parsed, dict):
                    message = parsed.get("message", "Draf spesifikasi agen telah diperbarui.")
                    spec_updated = parsed.get("spec_updated", True)
                    should_commit = parsed.get("should_commit", False)

                    # Jika auto URL ingestion berhasil, tambahkan info ke pesan dan spec
                    knowledge_list = []
                    if "spec" in parsed and isinstance(parsed["spec"], dict):
                        raw_k = parsed["spec"].get("knowledge_sources") or []
                        if isinstance(raw_k, list):
                            for item in raw_k:
                                if isinstance(item, dict):
                                    knowledge_list.append(item)
                                elif isinstance(item, str) and item.strip():
                                    knowledge_list.append({"uri": item.strip(), "source": f"Web: {item.strip()[:30]}"})

                    if auto_knowledge_source:
                        knowledge_list.append(auto_knowledge_source)
                        message += (
                            f"\n\n\U0001f4da **Knowledge Auto-Ingestion:** Tautan `{auto_knowledge_source['uri']}` "
                            f"berhasil ditelan ke dalam Knowledge Base ({auto_knowledge_source['total_chunks']} potongan teks)."
                        )

                    # Simpan tool baru (Tool Factory)
                    new_tools_raw = parsed.get("new_tools", [])
                    if not isinstance(new_tools_raw, list):
                        new_tools_raw = []

                    # Cek juga jika LLM menaruh definisi tool baru di dalam spec.tools
                    spec_data_temp = parsed.get("spec", {}) if isinstance(parsed.get("spec"), dict) else {}
                    raw_spec_tools = spec_data_temp.get("tools", [])
                    if isinstance(raw_spec_tools, list):
                        for item in raw_spec_tools:
                            if isinstance(item, dict):
                                t_name = (item.get("name") or "").strip().lower()
                                if t_name and not any(isinstance(x, dict) and (x.get("name") or "").strip().lower() == t_name for x in new_tools_raw):
                                    new_tools_raw.append({
                                        "name": t_name,
                                        "description": item.get("description", f"Tool {t_name}"),
                                        "input_schema": item.get("input_schema") or item.get("parameters") or {"type": "object", "properties": {}},
                                        "implementation": item.get("implementation") or {"type": "http"},
                                        "effect": item.get("effect", "read"),
                                        "status": "published" if should_commit else "draft",
                                        "used_by": target_agent_id
                                    })

                    if new_tools_raw and isinstance(new_tools_raw, list):
                        for nt in new_tools_raw:
                            if not isinstance(nt, dict):
                                continue
                            nt_name = (nt.get("name") or "").strip().lower()
                            if not nt_name:
                                continue
                            nt_desc = nt.get("description", f"Tool {nt_name}")
                            nt_schema = nt.get("input_schema") or {"type": "object", "properties": {}}
                            nt_impl = nt.get("implementation", {})
                            nt_effect = nt.get("effect", "read")
                            nt_status = "published" if should_commit else nt.get("status", "draft")

                            t_check = await db.execute(select(ToolModel).where(ToolModel.name == nt_name))
                            existing_t = t_check.scalar_one_or_none()
                            if existing_t:
                                existing_t.description = nt_desc
                                existing_t.input_schema = nt_schema
                                existing_t.implementation = nt_impl
                                existing_t.effect = nt_effect
                                existing_t.status = nt_status
                                existing_t.source_type = nt_impl.get("type", "http")
                                if existing_t.used_by and target_agent_id not in existing_t.used_by and existing_t.used_by != "All agents":
                                    existing_t.used_by = f"{existing_t.used_by}, {target_agent_id}"
                                elif not existing_t.used_by:
                                    existing_t.used_by = target_agent_id
                            else:
                                new_t = ToolModel(
                                    id=str(uuid.uuid4()),
                                    name=nt_name,
                                    description=nt_desc,
                                    input_schema=nt_schema,
                                    implementation=nt_impl,
                                    effect=nt_effect,
                                    status=nt_status,
                                    source_type=nt_impl.get("type", "http"),
                                    used_by=target_agent_id,
                                    is_active=True,
                                )
                                db.add(new_t)
                            valid_db_tools[nt_name] = nt_desc
                        await db.flush()

                    if spec_updated and "spec" in parsed:
                        spec_data = parsed["spec"]
                        name = spec_data.get("name", "Custom Agent")
                        description = spec_data.get("description", "")
                        instructions = spec_data.get("instructions", "")

                        # Normalisasi tools: dukung baik list string maupun list dict
                        raw_tools = spec_data.get("tools", [])
                        extracted_tool_names = []
                        if isinstance(raw_tools, list):
                            for item in raw_tools:
                                if isinstance(item, dict):
                                    t_name = (item.get("name") or "").strip().lower()
                                    if t_name:
                                        extracted_tool_names.append(t_name)
                                elif isinstance(item, str) and item.strip():
                                    extracted_tool_names.append(item.strip().lower())

                        for nt in new_tools_raw:
                            if isinstance(nt, dict):
                                nt_name = (nt.get("name") or "").strip().lower()
                                if nt_name and nt_name not in extracted_tool_names:
                                    extracted_tool_names.append(nt_name)

                        # AUTO-REGISTER: Setiap tool yang diusulkan oleh LLM tapi belum ada di valid_db_tools,
                        # simpan secara dinamis ke database berdasarkan ID agent mini (target_agent_id)!
                        for t_name in extracted_tool_names:
                            if t_name not in valid_db_tools:
                                t_check = await db.execute(select(ToolModel).where(ToolModel.name == t_name))
                                existing_t = t_check.scalar_one_or_none()
                                if existing_t:
                                    if existing_t.used_by and target_agent_id not in existing_t.used_by and existing_t.used_by != "All agents":
                                        existing_t.used_by = f"{existing_t.used_by}, {target_agent_id}"
                                    elif not existing_t.used_by:
                                        existing_t.used_by = target_agent_id
                                    valid_db_tools[t_name] = existing_t.description or f"Tool {t_name}"
                                else:
                                    is_mutation = any(w in t_name for w in ["reserve", "book", "order", "create", "update", "delete", "post", "bayar", "pesan", "simpan", "cancel"])
                                    new_t = ToolModel(
                                        id=str(uuid.uuid4()),
                                        name=t_name,
                                        description=f"Tool dinamis untuk agen: {name}",
                                        input_schema={"type": "object", "properties": {}},
                                        implementation={"type": "http"},
                                        effect="write" if is_mutation else "read",
                                        status="published" if should_commit else "draft",
                                        source_type="http",
                                        used_by=target_agent_id,
                                        is_active=True,
                                    )
                                    db.add(new_t)
                                    valid_db_tools[t_name] = new_t.description
                                    if not any(isinstance(x, dict) and (x.get("name") or "").strip().lower() == t_name for x in new_tools_raw):
                                        new_tools_raw.append({
                                            "name": t_name,
                                            "description": new_t.description,
                                            "input_schema": new_t.input_schema,
                                            "implementation": new_t.implementation,
                                            "effect": new_t.effect,
                                            "status": new_t.status,
                                            "used_by": target_agent_id,
                                        })
                        await db.flush()

                        # Seluruh tool yang di-extract pasti valid dan tersimpan di DB
                        tools = [t for t in extracted_tool_names if isinstance(t, str) and t in valid_db_tools]
                        guardrails_data = spec_data.get("guardrails")

                        health_score = BuilderService._compute_health_score(
                            name=name,
                            instructions=instructions,
                            tools=tools,
                            has_knowledge=bool(knowledge_list),
                            has_guardrails=bool(guardrails_data),
                        )

                        if should_commit:
                            db_agent = None
                            if current_spec and current_spec.id:
                                result = await db.execute(select(AgentSpecModel).where(AgentSpecModel.id == current_spec.id))
                                db_agent = result.scalar_one_or_none()

                            if db_agent:
                                db_agent.name = name
                                db_agent.description = description
                                db_agent.instructions = instructions
                                db_agent.tools = tools
                                db_agent.knowledge_sources = knowledge_list
                                db_agent.guardrails = guardrails_data
                            else:
                                db_agent = AgentSpecModel(
                                    name=name,
                                    description=description,
                                    instructions=instructions,
                                    model=(parsed.get("spec", {}).get("model") or settings.LLM_MODEL or "cohere/north-mini-code:free"),
                                    tools=tools,
                                    knowledge_sources=knowledge_list,
                                    guardrails=guardrails_data,
                                    harness="default-safe-v1",
                                    status="active",
                                )
                                db.add(db_agent)

                            await db.commit()
                            await db.refresh(db_agent)
                            spec_response = AgentSpec.model_validate(db_agent)
                            return BuilderChatResponse(
                                id=db_agent.id,
                                message=message,
                                spec=spec_response,
                                is_draft=False,
                                new_tools=new_tools_raw,
                                health_score=health_score,
                            )
                        else:
                            draft_spec = AgentSpec(
                                id=target_agent_id,
                                name=name,
                                description=description,
                                instructions=instructions,
                                tools=tools,
                                knowledge_sources=knowledge_list,
                                guardrails=guardrails_data,
                                model=(parsed.get("spec", {}).get("model") or settings.LLM_MODEL or "cohere/north-mini-code:free"),
                                harness="default-safe-v1",
                                status="draft",
                            )
                            return BuilderChatResponse(
                                id=draft_spec.id,
                                message=message,
                                spec=draft_spec,
                                is_draft=True,
                                new_tools=new_tools_raw,
                                health_score=health_score,
                            )

            except Exception as e:
                logger.warning(f"[BuilderService] Panggilan LLM builder gagal, beralih ke deterministik fallback: {e}")

        # =========================================================================
        # DETERMINISTIC FALLBACK LOGIC (Turn-1 Ready Offline/Local)
        # =========================================================================
        name = BuilderService._agent_name(prompt_trimmed)

        detected_url = auto_knowledge_source.get("uri") if auto_knowledge_source else None
        if not detected_url:
            u_match = re.search(r"https?://[^\s,()<>'\"]+", prompt_trimmed)
            if u_match:
                detected_url = u_match.group(0).rstrip(".,;")

        dynamic_tools = BuilderService._extract_dynamic_tools_from_text(
            prompt=prompt_trimmed,
            detected_url=detected_url,
            target_agent_id=target_agent_id,
        )

        tools: List[str] = []
        new_tools_raw: List[Dict[str, Any]] = []

        if dynamic_tools:
            for dt in dynamic_tools:
                dt_name = dt["name"]
                t_check = await db.execute(select(ToolModel).where(ToolModel.name == dt_name))
                existing_t = t_check.scalar_one_or_none()
                if existing_t:
                    existing_t.description = dt.get("description", existing_t.description)
                    existing_t.input_schema = dt.get("input_schema", existing_t.input_schema)
                    existing_t.implementation = dt.get("implementation", existing_t.implementation)
                    existing_t.effect = dt.get("effect", existing_t.effect)
                    if existing_t.used_by and target_agent_id not in existing_t.used_by and existing_t.used_by != "All agents":
                        existing_t.used_by = f"{existing_t.used_by}, {target_agent_id}"
                    elif not existing_t.used_by:
                        existing_t.used_by = target_agent_id
                    tools.append(dt_name)
                    new_tools_raw.append(dt)
                else:
                    new_t = ToolModel(
                        id=str(uuid.uuid4()),
                        name=dt_name,
                        description=dt.get("description", f"Tool {dt_name}"),
                        input_schema=dt.get("input_schema") or {"type": "object", "properties": {}},
                        implementation=dt.get("implementation") or {"type": "http"},
                        effect=dt.get("effect", "read"),
                        status="draft",
                        source_type="http",
                        used_by=target_agent_id,
                        is_active=True,
                    )
                    db.add(new_t)
                    tools.append(dt_name)
                    new_tools_raw.append(dt)
            await db.flush()
        else:
            tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)

        knowledge_list = [auto_knowledge_source] if auto_knowledge_source else []

        instructions = (
            f"PERAN: Kamu adalah '{name}', asisten virtual profesional yang memandu pengguna secara ramah dan terstruktur.\n\n"
            f"SOP & ALUR KERJA:\n"
            f"1. Pahami kebutuhan pengguna, berikan jawaban to the point berdasarkan data resmi.\n"
            f"2. Gunakan tools yang tersedia ({', '.join(tools) if tools else 'tidak ada tools tambahan'}) secara akurat untuk memverifikasi atau mengambil data.\n"
            f"3. Dilarang mengarang informasi fiktif jika data tidak ditemukan.\n"
        )

        health_score = BuilderService._compute_health_score(
            name=name,
            instructions=instructions,
            tools=tools,
            has_knowledge=bool(knowledge_list),
        )

        draft_spec = AgentSpec(
            id=target_agent_id,
            name=name,
            description=f"Asisten virtual ({name}) yang siap melayani operasional pengguna.",
            instructions=instructions,
            tools=tools,
            knowledge_sources=knowledge_list,
            model=(settings.LLM_MODEL or "cohere/north-mini-code:free"),
            status="draft",
        )

        tools_desc = ""
        if tools:
            tools_desc = f"\n\n🛠️ **Tools Terintegrasi ({len(tools)}):** Agen ini telah dilengkapi dengan tools khusus: " + ", ".join([f"`{t}`" for t in tools]) + "."

        fallback_msg = (
            f"Draf awal untuk **{name}** telah siap dan langsung aktif di panel Test Chat sebelah kanan (Health Score: {health_score}%)! "
            "Anda dapat langsung mengujinya."
            f"{tools_desc}"
        )

        if auto_knowledge_source:
            fallback_msg += f"\n\n📚 **Knowledge Ingestion:** Tautan `{auto_knowledge_source['uri']}` telah tersimpan ke dalam Knowledge Base."

        return BuilderChatResponse(
            id=draft_spec.id,
            message=fallback_msg,
            spec=draft_spec,
            is_draft=True,
            new_tools=new_tools_raw if new_tools_raw else None,
            health_score=health_score,
        )
