import json
import os
import re
import uuid
from typing import Any, List, Optional
from urllib.parse import urlparse

from openai import AsyncOpenAI
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.builder_engine import (
    Ledger,
    coverage_check,
    next_questions,
    validate_spec,
    execute_http,
    check_url,
    Blocked
)
from app.models.agent import AgentSpecModel
from app.models.tool import ToolModel
from app.models.mcp import MCPServerModel
from app.schemas.agent import AgentSpec, AgentSpecResponse, BuilderChatResponse


class BuilderService:
    """Creates a persisted agent specification from the user's own request."""

    @staticmethod
    def _agent_name(prompt: str) -> str:
        cleaned = prompt.strip().rstrip(".!?")
        
        # 1. Deteksi pola eksplisit: "bernama [Nama Agent]" atau "nama [Nama Agent]"
        named_match = re.search(
            r"(?:bernama|nama(?:nya)?|called|named)\s+[\"\'\`]?([A-Za-z0-9\s/_-]+?)[\"\'\`]?(?:\s+(?:untuk|yang|guna|agar|dengan|sebagai)|\.|\,|$)",
            cleaned,
            re.IGNORECASE
        )
        if named_match:
            candidate = named_match.group(1).strip()
            if candidate and len(candidate.split()) <= 6:
                name = candidate.title()
                for acr in ["AI", "API", "IT", "CS", "HR", "CRM", "ERP", "SOP", "URL", "JSON", "REST", "SQL", "BPJS"]:
                    name = re.sub(rf"\b{acr.capitalize()}\b", acr, name)
                return name

        lowered = cleaned.lower()
        prefixes = (
            "ubah nama agent menjadi ", "ubah nama agen menjadi ", "ubah nama menjadi ",
            "ganti nama agent menjadi ", "ganti nama agen menjadi ", "ganti nama menjadi ",
            "rename agent to ", "rename to ",
            "buatkan aku agent asisten ", "buatkan saya agent asisten ", "buatkan agent asisten ",
            "buatkan aku agent ", "buatkan saya agent ", "buatkan agent ",
            "buat agent asisten ", "buat agent ", "create an agent ", "create agent ",
            "buatkan asisten ", "buatkan ", "buat ", "create "
        )
        for prefix in prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break

        # Potong jika masih ada klausul penjelas seperti "untuk...", "guna..."
        split_match = re.split(r"\s+(?:untuk|yang|guna|agar|sebagai)\s+", cleaned, flags=re.IGNORECASE)
        if split_match and len(split_match[0].strip()) > 0:
            cleaned = split_match[0].strip()

        if not cleaned:
            return "Custom AI Assistant"
        name = cleaned[:60].title()
        for acr in ["AI", "API", "IT", "CS", "HR", "CRM", "ERP", "SOP", "URL", "JSON", "REST", "SQL", "BPJS"]:
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
                    max_tokens=256,
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

        # Deteksi otomatis apakah pengguna memberikan URL / endpoint baru dalam percakapan
        found_urls = re.findall(r"https?://[^\s'\"<>]+", prompt_trimmed)
        if found_urls:
            raw_url = found_urls[0].rstrip("/")
            parsed_u = urlparse(raw_url)
            new_base_url = f"{parsed_u.scheme}://{parsed_u.netloc}"
            
            # 1. Update in-memory settings langsung
            settings.EXTERNAL_MOCK_API_URL = new_base_url
            
            # 2. Update file .env di disk secara aman agar tidak tertinggal
            try:
                env_paths = [".env", "backend/.env", "../backend/.env"]
                for ep in env_paths:
                    if os.path.exists(ep):
                        with open(ep, "r", encoding="utf-8") as f_env:
                            env_content = f_env.read()
                        if "EXTERNAL_MOCK_API_URL=" in env_content:
                            new_env_content = re.sub(
                                r"EXTERNAL_MOCK_API_URL=[^\r\n]*",
                                f"EXTERNAL_MOCK_API_URL={new_base_url}",
                                env_content
                            )
                            with open(ep, "w", encoding="utf-8") as f_env:
                                f_env.write(new_env_content)
            except Exception as e_env:
                print(f"[Warning] Gagal update .env: {e_env}")

            # 3. Update semua tools HTTP di database agar mengarah ke base URL baru
            try:
                tools_to_update = await db.execute(
                    select(ToolModel).where(
                        or_(
                            ToolModel.source_type == "http",
                            ToolModel.implementation.isnot(None)
                        )
                    )
                )
                for t in tools_to_update.scalars().all():
                    if t.implementation and isinstance(t.implementation, dict):
                        old_url = t.implementation.get("url", "")
                        old_parsed = urlparse(old_url)
                        if old_parsed.netloc:
                            updated_url = f"{new_base_url}{old_parsed.path}"
                            if old_parsed.query:
                                updated_url += f"?{old_parsed.query}"
                            new_impl = dict(t.implementation)
                            new_impl["url"] = updated_url
                            t.implementation = new_impl
                            flag_modified(t, "implementation")
                    elif t.source_type == "http":
                        endpoint_path = f"/api/v1/{t.name.replace('_', '-')}"
                        t.implementation = {
                            "type": "http",
                            "url": f"{new_base_url}{endpoint_path}",
                            "method": "GET"
                        }
                        flag_modified(t, "implementation")
                
                # 4. Update mcp_servers jika ada yang menunjuk ke URL mock/trycloudflare lama
                mcp_to_update = await db.execute(select(MCPServerModel))
                for m in mcp_to_update.scalars().all():
                    if m.url and ("trycloudflare.com" in m.url or "mock" in m.url):
                        m.url = f"{new_base_url}/"
                
                await db.commit()
            except Exception as e_db:
                print(f"[Warning] Gagal update tools dengan URL baru: {e_db}")

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
                "Anda adalah 'AI Agent Architect & Co-Pilot' di Agent Studio (seperti GPT Builder di OpenAI atau Coze).\n"
                "Tugas Anda: Membantu pengguna merancang, menyempurnakan, dan menguji agent AI secara interaktif, kolaboratif, dan proaktif.\n\n"
                "PRINSIP UTAMA:\n"
                "1. GENERATIF & SIAP UJI DI TURN 1 (TURN-1 READY):\n"
                "   - Begitu pengguna menyampaikan ide atau kebutuhan pertama kali, LANGSUNG buatkan draf agent yang lengkap dan berfungsi di blok 'spec' (nama, deskripsi, instruksi SOP lengkap, dan tools relevan).\n"
                "   - Dilarang keras menolak membuat agent atau menunda pembuatan dengan interogasi panjang.\n\n"
                "2. PROAKTIF & INTERAKTIF SECARA DINAMIS (BUKAN TEMPLATE):\n"
                "   - Di bidang 'message', sampaikan respons ramah dan cerdas dengan 3 elemen:\n"
                "     a. Konfirmasi ringkas: jelaskan apa yang baru saja dirancang/disesuaikan.\n"
                "     b. Ajak uji coba langsung: beri tahu pengguna bahwa draf agent sudah aktif dan siap dicoba di panel uji sebelah kanan (Test Chat).\n"
                "     c. Saran proaktif kontekstual: berikan 1-2 ide atau pertanyaan spesifik yang sangat relevan dengan industri/domain agent tersebut (contoh: untuk toko online, sarankan aturan retur barang atau jam operasional; untuk helpdesk IT, sarankan eskalasi tiket kritis; untuk asisten riset, sarankan format sitasi).\n"
                "     HINDARI pertanyaan generik yang membosankan seperti 'mau tambahkan hal ini lagi?'. Selalu sebutkan fitur/aspek nyata yang spesifik untuk domain tersebut!\n\n"
                "3. PERBAIKAN INKREMENTAL (ANTI-AMNESIA):\n"
                "   - Jika pengguna meminta revisi pada draf yang sudah ada ('current_spec'), JANGAN menghapus aturan atau instruksi yang sudah dibuat sebelumnya!\n"
                "   - Lakukan patch/penyempurnaan secara cerdas: pertahankan nama, konteks domain, SOP, dan tools yang sudah ada, lalu perbarui hanya bagian yang diminta (misal: gaya bicara lebih santai, tambahan larangan tertentu, format respons).\n\n"
                "4. PEMILIHAN & PERANCANGAN TOOL:\n"
                "   A. Tool Katalog Database:\n"
                f"      Daftar tool aktif saat ini:\n{tools_info}\n"
                "      Pilih nama tool yang cocok dan masukkan ke 'spec.tools'.\n"
                "   B. Tool Factory (Endpoint Baru):\n"
                "      Jika pengguna memberikan URL / endpoint API (contoh: https://.../api/...), buatkan draf tool baru di array 'new_tools' (name, description, input_schema, implementation: {type: 'http', url: '...', method: 'GET'|'POST'}, effect, status: 'draft').\n\n"
                "5. ATURAN COMMIT ('should_commit'):\n"
                "   - Set 'should_commit': true HANYA jika pengguna secara eksplisit meminta menyimpan ('simpan', 'terapkan ke database', 'save', 'commit').\n"
                "   - Jika masih eksplorasi, tanya jawab, atau revisi, set 'should_commit': false.\n\n"
                "FORMAT BALASAN (Wajib JSON valid di dalam blok ```json ... ```):\n"
                "{\n"
                '  "message": "Kalimat percakapan ramah & proaktif: konfirmasi pembuatan + ajakan tes di panel kanan + saran spesifik dinamis sesuai domain",\n'
                '  "spec_updated": true,\n'
                '  "should_commit": false,\n'
                '  "spec": {\n'
                '    "name": "Nama Agent",\n'
                '    "description": "Tugas utama agent",\n'
                '    "instructions": "System prompt lengkap (Peran, SOP, Gaya Bicara, Fallback saat data kosong, Batasan Keamanan)",\n'
                '    "tools": ["nama_tool"]\n'
                '  },\n'
                '  "new_tools": [],\n'
                '  "coverage": {\n'
                '    "C1": "terisi",\n'
                '    "C2": "terisi",\n'
                '    "C3": "kosong",\n'
                '    "C4": "kosong",\n'
                '    "C5": "terisi",\n'
                '    "C6": "terisi",\n'
                '    "C7": "terisi",\n'
                '    "C8": "kosong",\n'
                '    "C9": "kosong",\n'
                '    "C10": "kosong",\n'
                '    "C11": "kosong",\n'
                '    "C12": "kosong"\n'
                '  }\n'
                "}\n\n"
                f"Spesifikasi saat ini: {current_spec_json}\n"
            )
            
            messages = [{"role": "system", "content": system_msg}]
            if history:
                # Batasi hanya 4 pesan riwayat terakhir agar payload ringan dan latensi rendah
                recent_history = history[-4:] if len(history) > 4 else history
                for h in recent_history:
                    content_str = h.content if hasattr(h, 'role') else (h.get('content', '') if isinstance(h, dict) else str(h))
                    if content_str and len(content_str) > 500:
                        content_str = content_str[:500] + "..."
                    role_str = h.role if hasattr(h, 'role') else (h.get('role', 'user') if isinstance(h, dict) else 'user')
                    messages.append({
                        "role": role_str,
                        "content": content_str or ""
                    })
            
            messages.append({"role": "user", "content": prompt_trimmed})
            
            try:
                completion = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2500,
                    timeout=35.0
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
                    
                    # Tool Factory: Simpan draf tool baru yang dirancang oleh LLM
                    new_tools_raw = parsed.get("new_tools", [])
                    if new_tools_raw and isinstance(new_tools_raw, list):
                        allowed_hosts = ["*.trycloudflare.com", "trycloudflare.com", "localhost", "127.0.0.1", "api.github.com", "*.supabase.co", "*"]
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
                                existing_t.source_type = "http"
                            else:
                                new_t = ToolModel(
                                    id=str(uuid.uuid4()),
                                    name=nt_name,
                                    description=nt_desc,
                                    input_schema=nt_schema,
                                    implementation=nt_impl,
                                    effect=nt_effect,
                                    status=nt_status,
                                    source_type="http",
                                    is_active=True
                                )
                                db.add(new_t)
                            valid_db_tools[nt_name] = nt_desc
                        await db.flush()
                    
                    # Kalkulasi Coverage Checklist (12 Poin Wajib SKILL.md)
                    raw_cov = parsed.get("coverage", {}) if isinstance(parsed.get("coverage"), dict) else {}
                    cov_items = {}
                    satisfied_count = 0
                    for i in range(1, 13):
                        key = f"C{i}"
                        status_val = raw_cov.get(key, "kosong")
                        cov_items[key] = status_val
                        if status_val in ("terisi", "tidak_berlaku", "diserahkan"):
                            satisfied_count += 1

                    cov_percent = round((satisfied_count / 12) * 100)
                    coverage_data = {
                        "satisfied": satisfied_count,
                        "total": 12,
                        "percent": cov_percent,
                        "can_build": True,
                        "items": cov_items
                    }

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
                            return BuilderChatResponse(id=db_agent.id, message=message, spec=spec_response, is_draft=False, new_tools=new_tools_raw, coverage=coverage_data)
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
                            return BuilderChatResponse(id=draft_spec.id, message=message, spec=draft_spec, is_draft=True, new_tools=new_tools_raw, coverage=coverage_data)
                    else:
                        return BuilderChatResponse(message=message, is_draft=True, new_tools=new_tools_raw, coverage=coverage_data)
                        
            except Exception as e:
                print(f"LLM Builder Error: {e}")
                pass

        # Fallback Logic (jika LLM offline/timeout/error)
        if current_spec:
            name = current_spec.name
            description = current_spec.description
            instructions = current_spec.instructions
            tools = [t for t in (current_spec.tools or []) if t in valid_db_tools]
            mcp_servers = current_spec.mcp_servers or []
            
            # Cek apakah pengguna bermaksud mengubah nama agent
            rename_match = re.search(
                r"(?:ubah|ganti|rename)\s+(?:nama\s+)?(?:agent|agen)?\s*(?:menjadi|ke|to|jadi)\s+[:\"']?(.+?)[\"']?$",
                prompt_trimmed,
                re.IGNORECASE
            )
            if rename_match:
                raw_name = rename_match.group(1).strip()
                name = BuilderService._agent_name(raw_name)
                message_text = f"Nama agent berhasil diperbarui menjadi **{name}**."
            else:
                instructions = "\n\n".join(
                    part for part in [instructions or "", prompt_trimmed] if part
                )
                new_selected_tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)
                tools = list(dict.fromkeys(tools + new_selected_tools))
                message_text = f"Rancangan spesifikasi dan alur kerja untuk **{name}** telah diperbarui sesuai instruksi Anda."
            
            draft_spec = AgentSpec(
                id=current_spec.id,
                name=name,
                description=description,
                instructions=instructions,
                tools=tools,
                model=current_spec.model or (settings.LLM_MODEL or "z-ai/glm-5.3"),
                mcp_servers=mcp_servers,
                harness=current_spec.harness or "default-safe-v1",
                status=current_spec.status or "draft"
            )
            return BuilderChatResponse(
                id=current_spec.id, 
                message=message_text, 
                spec=draft_spec, 
                is_draft=True
            )
        else:
            name = BuilderService._agent_name(prompt_trimmed)
            desc_match = re.search(r'(?:untuk|guna|tugasnya|bertugas)\s+(.+)$', prompt_trimmed, re.IGNORECASE)
            if desc_match:
                clean_action = desc_match.group(1).strip().rstrip('.!?')
                description = f"Asisten virtual ({name}) yang bertugas {clean_action}."
                clean_goal = clean_action
            else:
                cleaned_goal = re.sub(r'^(?:buatkan|bikin|buat|create)\s+(?:agent\s+)?(?:asisten\s+)?(?:bernama\s+[^\s]+\s+)?', '', prompt_trimmed, flags=re.IGNORECASE).strip()
                description = f"Asisten virtual ({name}) untuk {cleaned_goal}."
                clean_goal = cleaned_goal

            tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)
            
            tool_rules = "\n".join([f"- Gunakan '{t}' sesuai kebutuhan alur pemeriksaan/layanan." for t in tools]) if tools else "- Gunakan tool yang tersedia untuk membantu pengguna."
            
            instructions = (
                f"PERAN: Kamu adalah '{name}', asisten virtual profesional yang memandu pengguna secara ramah, solutif, dan terstruktur.\n\n"
                f"TUJUAN UTAMA:\n"
                f"{clean_goal}\n\n"
                f"SOP & ALUR KERJA:\n"
                f"1. Sambut pengguna dengan ramah, dengarkan dan pahami kebutuhan atau pertanyaan yang disampaikan.\n"
                f"2. Gunakan tools yang tersedia secara bertahap dan akurat untuk memverifikasi atau mengambil data pendukung.\n"
                f"3. Berikan jawaban yang jelas, to the point, dan panduan langkah selanjutnya yang solutif.\n\n"
                f"BATASAN KEAMANAN & ETIKA:\n"
                f"- Jaga kerahasiaan data privasi dan etika interaksi profesional.\n"
                f"- Dilarang mengarang informasi fiktif. Jika data tidak tersedia atau layanan sistem sedang offline, sampaikan dengan jujur.\n\n"
                f"ATURAN PENGGUNAAN TOOL:\n"
                f"{tool_rules}"
            )
            
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
                message=f"Draf awal untuk **{name}** telah siap! Anda bisa langsung mencobanya di panel uji (Test Chat) di sebelah kanan. Apakah ingin menambahkan aturan khusus, gaya bahasa tertentu, atau mengintegrasikan tool baru?",
                spec=draft_spec,
                is_draft=True
            )
