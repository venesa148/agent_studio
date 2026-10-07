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
        return cleaned[:255].title() if cleaned else "Custom AI Assistant"

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
            tools_info = ", ".join([f"{k} ({v})" for k,v in valid_db_tools.items()])
            current_spec_json = current_spec.model_dump_json() if current_spec else "None"
            system_msg = (
                "Anda adalah 'Agent Builder', asisten ahli untuk membuat dan merancang AI Agent. "
                "Diskusikan kebutuhan pengguna, kumpulkan informasi, dan rancang spesifikasi agent.\n\n"
                "Kewajiban utama: Anda HARUS SELALU membalas dalam format JSON di dalam blok markdown ```json ... ```:\n"
                "{\n"
                '  "message": "Pesan Anda ke pengguna (bahasa Indonesia, misal bertanya klarifikasi atau infokan bahwa spesifikasi telah dibuat)",\n'
                '  "spec_updated": true atau false (true jika Anda membuat/mengubah spesifikasi agent),\n'
                '  "spec": {\n'
                '    "name": "Nama Agent",\n'
                '    "description": "Deskripsi Agent",\n'
                '    "instructions": "System prompt lengkap untuk agent tersebut (peran, tugas, perilaku)",\n'
                '    "tools": ["tool_a", "tool_b"]\n'
                '  }\n'
                "}\n\n"
                "Aturan:\n"
                "1. 'message' adalah balasan teks normal yang akan dibaca pengguna.\n"
                "2. Jika pengguna belum jelas, set 'spec_updated': false dan tanyakan detailnya di 'message'.\n"
                "3. Jika Anda siap membuat/mengupdate agent, set 'spec_updated': true.\n"
                f"4. Tool yang tersedia HANYA: {tools_info}.\n"
                "5. 'tools' di dalam spec HANYA boleh berisi nama-nama tool dari daftar di atas. Jika tidak ada yang relevan, kosongkan [].\n"
                f"6. Spesifikasi agent yang sedang aktif (jika ada): {current_spec_json}\n"
            )
            
            messages = [{"role": "system", "content": system_msg}]
            if history:
                for h in history:
                    messages.append({"role": h.role if hasattr(h, 'role') else h.get('role', 'user'), "content": h.content if hasattr(h, 'content') else h.get('content', '')})
            
            messages.append({"role": "user", "content": prompt_trimmed})
            
            try:
                completion = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2
                )
                content = completion.choices[0].message.content or ""
                match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
                if not match:
                    match = re.search(r"({.*})", content, re.DOTALL)
                    
                if match:
                    parsed = json.loads(match.group(1))
                    message = parsed.get("message", "Saya telah memproses permintaan Anda.")
                    spec_updated = parsed.get("spec_updated", False)
                    
                    if spec_updated and "spec" in parsed:
                        spec_data = parsed["spec"]
                        name = spec_data.get("name", "Custom Agent")
                        description = spec_data.get("description", "")
                        instructions = spec_data.get("instructions", "")
                        tools = [t for t in spec_data.get("tools", []) if t in valid_db_tools]
                        
                        db_agent = None
                        if current_spec and current_spec.id:
                            # Update existing
                            result = await db.execute(select(AgentSpecModel).where(AgentSpecModel.id == current_spec.id))
                            db_agent = result.scalar_one_or_none()
                        
                        if db_agent:
                            db_agent.name = name
                            db_agent.description = description
                            db_agent.instructions = instructions
                            db_agent.tools = tools
                        else:
                            db_agent = AgentSpecModel(
                                name=name, description=description, instructions=instructions,
                                model=(settings.LLM_MODEL or "z-ai/glm-5.3"), tools=tools, mcp_servers=[], harness="default-safe-v1", status="active"
                            )
                            db.add(db_agent)
                            
                        await db.commit()
                        await db.refresh(db_agent)
                        try:
                            from app.services.agent_service import AgentService
                            await AgentService.export_agent_yaml(db, db_agent.id, save_to_disk=True)
                        except Exception as e_yaml:
                            print(f"Warning auto-export yaml: {e_yaml}")
                        spec_response = AgentSpecResponse.model_validate(db_agent)
                        return BuilderChatResponse(id=db_agent.id, message=message, spec=spec_response)
                    else:
                        return BuilderChatResponse(message=message)
                        
            except Exception as e:
                print(f"LLM Builder Error: {e}")
                # Fallback ke logic lama
                pass

        # Fallback Logic (Naive)
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
            
            result = await db.execute(select(AgentSpecModel).where(AgentSpecModel.id == current_spec.id))
            db_agent = result.scalar_one_or_none()
            if db_agent:
                db_agent.name = name
                db_agent.description = description
                db_agent.instructions = instructions
                db_agent.tools = tools
                await db.commit()
                await db.refresh(db_agent)
            else:
                db_agent = AgentSpecModel(name=name, description=description, instructions=instructions, model=agent_model, tools=tools, mcp_servers=mcp_servers, harness=harness, status=status)
                db.add(db_agent)
                await db.commit()
                await db.refresh(db_agent)
        else:
            name = BuilderService._agent_name(prompt_trimmed)
            description = f"Agent untuk: {prompt_trimmed}"
            instructions = f"Peran dan tujuan agent ini berasal dari permintaan pengguna: {prompt_trimmed}\n\nJawab sesuai peran tersebut."
            tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)
            db_agent = AgentSpecModel(name=name, description=description, instructions=instructions, model=(settings.LLM_MODEL or "z-ai/glm-5.3"), tools=tools, mcp_servers=[], harness="default-safe-v1", status="active")
            db.add(db_agent)
            await db.commit()
            await db.refresh(db_agent)

        spec_response = AgentSpecResponse.model_validate(db_agent)
        return BuilderChatResponse(
            id=db_agent.id,
            message=f"Agent '{db_agent.name}' dibuat/diupdate dari permintaan Anda.",
            spec=spec_response,
        )
