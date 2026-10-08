import json
import re
from typing import Any, List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import AgentSpecModel
from app.models.tool import ToolModel
from app.schemas.agent import AgentSpec, AgentSpecResponse, BuilderChatResponse


class BuilderService:
    """Creates a persisted agent specification from the user's own request."""

    @staticmethod
    def _agent_name(prompt: str) -> str:
        cleaned = prompt.strip().rstrip(".!?")
        lowered = cleaned.lower()
        prefixes = (
            "buatkan aku agent ", "buatkan saya agent ", "buatkan agent ",
            "buat agent ", "create an agent ", "create agent ",
            "buatkan ", "buat ", "create "
        )
        for prefix in prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        if not cleaned:
            return "Custom AI Assistant"
        name = cleaned[:255].title()
        for acr in ["BPJS", "CS", "AI", "API", "IT", "RS", "IGD", "FKTP"]:
            name = re.sub(rf"\b{acr.capitalize()}\b", acr, name)
        return name

    @staticmethod
    async def _select_tools_from_db(db: AsyncSession, prompt: str) -> List[str]:
        """
        Ambil tools yang aktif HANYA dari database (tabel tools).
        Tidak menggunakan daftar tools yang pre-defined/hardcoded.
        """
        result = await db.execute(select(ToolModel).where(ToolModel.is_active == True))
        db_tools = list(result.scalars().all())
        if not db_tools:
            return []

        available_tool_names = {t.name for t in db_tools}
        prompt_lower = prompt.lower()

        # 1. Coba gunakan LLM jika API Key tersedia untuk seleksi semantik dari database
        client = None
        model = None
        if settings.OPENAI_API_KEY:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
            model = settings.OPENAI_DEFAULT_MODEL
        elif settings.LLM_API_KEY:
            client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL, max_retries=0)
            model = settings.LLM_MODEL

        if client and model:
            try:
                tools_desc = "\n".join(
                    [f"- {t.name}: {t.description or 'No description'}" for t in db_tools]
                )
                system_msg = (
                    "Anda adalah asisten arsitektur agent. Pilih tools yang relevan dari daftar tools database berikut:\n"
                    f"{tools_desc}\n\n"
                    "Aturan KETAT:\n"
                    "1. Kembalikan HANYA JSON array string berisi nama tool yang dipilih, contoh: [\"tool_a\", \"tool_b\"].\n"
                    "2. JANGAN PERNAH mengembalikan nama tool di luar daftar database di atas.\n"
                    "3. Jika tidak ada tool yang relevan dengan instruksi pengguna, kembalikan []."
                )
                completion = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": f"Kebutuhan agent: {prompt}"}
                    ],
                    temperature=0.0
                )
                content = completion.choices[0].message.content or ""
                # Parse JSON array dari response
                match = re.search(r"\[.*?\]", content, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list):
                        valid_selected = [t for t in parsed if t in available_tool_names]
                        return valid_selected
            except Exception:
                pass

        # 2. Heuristik pencocokan semantik & kata kunci terhadap katalog tools (100% DINAMIS, TANPA HARDCODE)
        selected = []
        prompt_words = set(re.findall(r"\w+", prompt_lower))
        for tool in db_tools:
            t_name = tool.name.lower()
            t_desc = (tool.description or "").lower()
            name_words = set(re.findall(r"\w+", t_name))
            desc_words = {w for w in re.findall(r"\w+", t_desc) if len(w) >= 4}

            # Cocokkan token kata dari prompt pengguna dengan nama tool atau deskripsinya di DB
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
        
        client = None
        model = None
        if settings.OPENAI_API_KEY:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
            model = settings.OPENAI_DEFAULT_MODEL
        elif settings.LLM_API_KEY:
            client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL, max_retries=0)
            model = settings.LLM_MODEL

        if client and model:
            tools_info_list = []
            for t in db_tools:
                src_label = f"[{t.source_type.upper()}]" if t.source_type else "[TOOL]"
                tools_info_list.append(f"{t.name} ({src_label}: {t.description or 'No description'})")
            tools_info = "\n".join([f"- {item}" for item in tools_info_list]) if tools_info_list else "Belum ada tools aktif di database."
            current_spec_json = current_spec.model_dump_json() if current_spec else "Belum ada spesifikasi awal."
            
            system_msg = (
                "Anda adalah 'Agent Builder', asisten konsultan dan arsitek AI kelas dunia yang bertugas merancang AI Agent baru bersama pengguna secara interaktif (Conversational Co-pilot).\n\n"
                "PANDUAN INTERAKSI KONSULTATIF (MULTI-TURN):\n"
                "1. EKSPLORASI & TANYA KLARIFIKASI (Jika Permintaan Singkat/Umum):\n"
                "   - Jika pengguna baru menyebut ide umum (contoh: 'mau bikin agent makan', 'buat agent klinik', 'bikin bot travel'), JANGAN langsung mengunci dan menyelesaikan spesifikasi.\n"
                "   - Sambut dengan ramah di 'message', lalu ajukan 1–2 pertanyaan pemantik yang terarah (contoh: apa tujuan utamanya, fitur apa saja yang diharapkan, target penggunanya siapa).\n"
                "   - Rancang draf awal nama & fungsi di objek 'spec' agar pengguna melihat gambaran visualnya, namun jelaskan di 'message' bahwa ini draf awal dan tanyakan konfirmasi mereka.\n\n"
                "2. GALI BATASAN & PREFERENSI (Guardrails):\n"
                "   - Tanyakan apakah ada aturan khusus (misal: gaya bahasa santai/formal, batasan privasi, pantangan medis, pantangan topik).\n\n"
                "3. PILIH TOOLS DARI DATABASE KATALOG (100% DINAMIS & CERDAS):\n"
                f"   - Tool yang aktif di database saat ini:\n{tools_info}\n"
                "   - Panduan kecocokan kebutuhan:\n"
                "     * Butuh info web/berita/referensi riil online -> 'search_web'\n"
                "     * Butuh hitungan matematika presisi -> 'calculator'\n"
                "     * Butuh request REST API eksternal -> 'api_fetch'\n"
                "     * Butuh waktu/tanggal/jam server saat ini -> 'system_time'\n"
                "     * Butuh info spek sistem/runtime OS -> 'system_diagnostics'\n"
                "     * Butuh konversi nilai kurs uang asing ke IDR -> 'currency_converter'\n"
                "     * Butuh data rumah sakit / rujukan kesehatan -> 'search_hospital', 'get_referral_status'\n"
                "   - Pilih HANYA nama tool yang benar-benar ada di daftar di atas. Jika tidak ada yang relevan, kosongkan []. DILARANG MENGARANG NAMA TOOL.\n"
                "   - Dalam 'instructions' (system prompt agent), sertakan instruksi jelas bagaimana agen harus memanfaatkan tool-tool tersebut secara jujur tanpa halusinasi.\n\n"
                "4. DRAF PREVIEW & REVISI BERKELANJUTAN:\n"
                "   - Setiap kali pengguna memberikan detail baru atau meminta revisi (contoh: 'tambahkan estimasi waktu', 'ganti namanya'), perbarui isi 'spec'.\n"
                "   - Di 'message', jelaskan poin-poin yang baru Anda perbarui dan tanyakan apakah ada hal lain yang ingin disesuaikan.\n\n"
                "5. KAPAN HARUS COMMIT KE DATABASE ('should_commit'):\n"
                "   - Set 'should_commit': true HANYA jika pengguna secara eksplisit berkata 'oke simpan', 'sudah pas', 'buatkan sekarang', 'apply', atau 'save'.\n"
                "   - Jika pengguna masih berdiskusi, bertanya, atau memberikan detail, selalu set 'should_commit': false.\n\n"
                "FORMAT BALASAN MUTLAK (Harus berupa JSON valid di dalam blok ```json ... ```):\n"
                "{\n"
                '  "message": "Kalimat percakapan Anda dalam Bahasa Indonesia yang ramah, profesional, dan interaktif.",\n'
                '  "spec_updated": true,\n'
                '  "should_commit": false,\n'
                '  "spec": {\n'
                '    "name": "Nama Agent",\n'
                '    "description": "Deskripsi singkat fungsi agen",\n'
                '    "instructions": "System prompt lengkap (Peran, SOP, Gaya Bahasa, Batasan Keamanan, dan Aturan Penggunaan Tool)",\n'
                '    "tools": ["nama_tool_1"]\n'
                '  }\n'
                "}\n\n"
                f"Spesifikasi saat ini (jika ada): {current_spec_json}\n"
            )
            
            messages = [{"role": "system", "content": system_msg}]
            if history:
                for h in history:
                    messages.append({
                        "role": h.role if hasattr(h, 'role') else h.get('role', 'user'),
                        "content": h.content if hasattr(h, 'content') else h.get('content', '')
                    })
            
            messages.append({"role": "user", "content": prompt_trimmed})
            
            try:
                completion = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3
                )
                content = completion.choices[0].message.content or ""
                match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
                if not match:
                    match = re.search(r"({.*})", content, re.DOTALL)
                    
                if match:
                    raw_json = match.group(1).strip()
                    try:
                        parsed = json.loads(raw_json, strict=False)
                    except json.JSONDecodeError:
                        cleaned_json = re.sub(r'\\(?![/u"bfnrt])', r'\\\\', raw_json)
                        parsed = json.loads(cleaned_json, strict=False)
                    message = parsed.get("message", "Saya telah memproses permintaan Anda.")
                    spec_updated = parsed.get("spec_updated", False)
                    should_commit = parsed.get("should_commit", False)
                    
                    if spec_updated and "spec" in parsed:
                        spec_data = parsed["spec"]
                        name = spec_data.get("name", "Custom Agent")
                        description = spec_data.get("description", "")
                        instructions = spec_data.get("instructions", "")
                        tools = [t for t in spec_data.get("tools", []) if t in valid_db_tools]
                        
                        mcp_servers: List[str] = []
                        if tools:
                            t_query = await db.execute(
                                select(ToolModel.mcp_server_id).where(
                                    ToolModel.name.in_(tools),
                                    ToolModel.mcp_server_id.isnot(None)
                                )
                            )
                            mcp_servers = list(set([r[0] for r in t_query.fetchall() if r[0]]))

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
                                db_agent.mcp_servers = mcp_servers
                            else:
                                db_agent = AgentSpecModel(
                                    name=name, description=description, instructions=instructions,
                                    model=(settings.LLM_MODEL or "z-ai/glm-5.3"), tools=tools, mcp_servers=mcp_servers, harness="default-safe-v1", status="active"
                                )
                                db.add(db_agent)
                                
                            await db.commit()
                            await db.refresh(db_agent)
                            try:
                                from app.services.agent_service import AgentService
                                await AgentService.export_agent_yaml(db, db_agent.id, save_to_disk=True)
                            except Exception as e_yaml:
                                print(f"Warning auto-export yaml: {e_yaml}")
                            spec_response = AgentSpec.model_validate(db_agent)
                            return BuilderChatResponse(id=db_agent.id, message=message, spec=spec_response, is_draft=False)
                        else:
                            # In-memory Draft Spec (Belum di-commit ke DB agar user bisa review & revisi)
                            draft_spec = AgentSpec(
                                id=current_spec.id if current_spec else None,
                                name=name,
                                description=description,
                                instructions=instructions,
                                tools=tools,
                                model=(settings.LLM_MODEL or "z-ai/glm-5.3"),
                                mcp_servers=mcp_servers,
                                harness="default-safe-v1",
                                status="draft"
                            )
                            return BuilderChatResponse(id=draft_spec.id, message=message, spec=draft_spec, is_draft=True)
                    else:
                        return BuilderChatResponse(message=message, is_draft=True)
                        
            except Exception as e:
                print(f"LLM Builder Error: {e}")
                pass

        # Fallback Logic (Naive jika LLM offline)
        if current_spec and current_spec.id:
            name = current_spec.name
            description = current_spec.description or f"Agent untuk: {prompt_trimmed}"
            instructions = "\n\n".join(
                part for part in [current_spec.instructions or "", prompt_trimmed] if part
            )
            existing_tools = [t for t in (current_spec.tools or []) if t in valid_db_tools]
            new_selected_tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)
            merged_tools = list(dict.fromkeys(existing_tools + new_selected_tools))
            tools = merged_tools
            mcp_servers = current_spec.mcp_servers
            agent_model, harness, status = current_spec.model, current_spec.harness, current_spec.status
            
            draft_spec = AgentSpec(
                id=current_spec.id,
                name=name,
                description=description,
                instructions=instructions,
                tools=tools,
                model=agent_model,
                mcp_servers=mcp_servers,
                harness=harness,
                status=status
            )
            return BuilderChatResponse(id=current_spec.id, message=f"Draf instruksi diperbarui: {prompt_trimmed}", spec=draft_spec, is_draft=True)
        else:
            name = BuilderService._agent_name(prompt_trimmed)
            description = f"Agent untuk: {prompt_trimmed}"
            instructions = f"Peran dan tujuan agent ini berasal dari permintaan pengguna: {prompt_trimmed}\n\nJawab sesuai peran tersebut."
            tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)
            mcp_servers = []
            if tools:
                t_query = await db.execute(
                    select(ToolModel.mcp_server_id).where(
                        ToolModel.name.in_(tools),
                        ToolModel.mcp_server_id.isnot(None)
                    )
                )
                mcp_servers = list(set([r[0] for r in t_query.fetchall() if r[0]]))

            draft_spec = AgentSpec(
                name=name,
                description=description,
                instructions=instructions,
                model=(settings.LLM_MODEL or "z-ai/glm-5.3"),
                tools=tools,
                mcp_servers=mcp_servers,
                harness="default-safe-v1",
                status="draft"
            )
            return BuilderChatResponse(
                message=f"Draf awal untuk '{name}' telah disiapkan. Apakah ada yang ingin ditambahkan?",
                spec=draft_spec,
                is_draft=True
            )
