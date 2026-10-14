import json
import logging
import os
import re
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
    async def _detect_and_ingest_url(db: AsyncSession, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Mendeteksi jika pengguna mencantumkan URL web referensi di dalam chat prompt.
        Jika terdeteksi dan bukan API endpoint, sistem otomatis mengambil kontennya secara aman (anti-SSRF)
        dan menyimpannya ke Knowledge Base (PostgreSQL).
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
                doc = await VectorService.ingest_document(
                    db=db,
                    title=doc_title,
                    source_type="url",
                    source_uri=detected_url,
                    text_content=scraped_text,
                )
                return {
                    "doc_id": doc.id,
                    "title": doc_title,
                    "uri": detected_url,
                    "type": "url",
                    "total_chunks": doc.total_chunks,
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
    async def build_agent_spec(
        db: AsyncSession, prompt: str, current_spec: Optional[AgentSpec] = None, history: Optional[List[Any]] = None
    ) -> BuilderChatResponse:
        prompt_trimmed = prompt.strip()
        if not prompt_trimmed:
            raise ValueError("Prompt tidak boleh kosong.")

        # Ambil daftar tools yang aktif 100% DINAMIS dari database
        db_tools_result = await db.execute(select(ToolModel).where(ToolModel.is_active == True))
        db_tools = db_tools_result.scalars().all()
        valid_db_tools = {t.name: (t.description or "") for t in db_tools}

        # Cek apakah ada URL yang bisa di-ingest otomatis ke Knowledge Base
        auto_knowledge_source = await BuilderService._detect_and_ingest_url(db, prompt_trimmed)

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
            model = settings.LLM_MODEL or settings.OPENAI_DEFAULT_MODEL or "z-ai/glm-5.3-flash"

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
                "4. ATURAN COMMIT: Set 'should_commit': true HANYA jika pengguna secara eksplisit meminta menyimpan ('simpan', 'commit', 'save').\n\n"
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
                completion = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2500,
                    timeout=65.0,
                )
                msg_obj = completion.choices[0].message
                content = msg_obj.content or ""

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
                        knowledge_list = parsed["spec"].get("knowledge_sources") or []

                    if auto_knowledge_source:
                        knowledge_list.append(auto_knowledge_source)
                        message += (
                            f"\n\n\U0001f4da **Knowledge Auto-Ingestion:** Tautan `{auto_knowledge_source['uri']}` "
                            f"berhasil ditelan ke dalam Knowledge Base ({auto_knowledge_source['total_chunks']} potongan teks)."
                        )

                    # Simpan tool baru (Tool Factory)
                    new_tools_raw = parsed.get("new_tools", [])
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
                        tools = [t for t in spec_data.get("tools", []) if t in valid_db_tools]
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
                                    model=(settings.LLM_MODEL or "z-ai/glm-5.3"),
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
                                id=current_spec.id if current_spec else None,
                                name=name,
                                description=description,
                                instructions=instructions,
                                tools=tools,
                                knowledge_sources=knowledge_list,
                                guardrails=guardrails_data,
                                model=(settings.LLM_MODEL or "z-ai/glm-5.3"),
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
        tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)
        knowledge_list = [auto_knowledge_source] if auto_knowledge_source else []

        instructions = (
            f"PERAN: Kamu adalah '{name}', asisten virtual profesional yang memandu pengguna secara ramah dan terstruktur.\n\n"
            f"SOP & ALUR KERJA:\n"
            f"1. Pahami kebutuhan pengguna, berikan jawaban to the point berdasarkan data resmi.\n"
            f"2. Gunakan tools yang tersedia secara akurat untuk memverifikasi atau mengambil data.\n"
            f"3. Dilarang mengarang informasi fiktif jika data tidak ditemukan.\n"
        )

        health_score = BuilderService._compute_health_score(
            name=name,
            instructions=instructions,
            tools=tools,
            has_knowledge=bool(knowledge_list),
        )

        draft_spec = AgentSpec(
            id=current_spec.id if current_spec else None,
            name=name,
            description=f"Asisten virtual ({name}) yang siap melayani operasional pengguna.",
            instructions=instructions,
            tools=tools,
            knowledge_sources=knowledge_list,
            model=(settings.LLM_MODEL or "z-ai/glm-5.3"),
            status="draft",
        )

        fallback_msg = (
            f"Draf awal untuk **{name}** telah siap dan langsung aktif di panel Test Chat sebelah kanan (Health Score: {health_score}%)! "
            "Anda dapat langsung mengujinya. Jika ingin menambahkan aturan SOP khusus, batas jam operasional, atau mengintegrasikan API web, beri tahu saya!"
        )

        if auto_knowledge_source:
            fallback_msg += f"\n\n\U0001f4da **Knowledge Ingestion:** Tautan `{auto_knowledge_source['uri']}` telah tersimpan ke dalam Knowledge Base."

        return BuilderChatResponse(
            id=draft_spec.id,
            message=fallback_msg,
            spec=draft_spec,
            is_draft=True,
            health_score=health_score,
        )
