import json
import re
from typing import List, Optional

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
        if "bpjs" in lowered:
            return "BPJS Customer Service Agent"
        if lowered.startswith("buat agent penulisan") or "artikel" in lowered:
            return "Custom AI Assistant"
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

        # 2. Heuristik pencocokan kata kunci terhadap katalog tools yang ada di database
        selected = []
        for tool in db_tools:
            t_name = tool.name.lower()
            t_desc = (tool.description or "").lower()

            matched = False
            if t_name in ["search_hospital", "hospital_finder"]:
                if any(w in prompt_lower for w in ["rs", "rumah sakit", "hospital", "faskes", "bpjs"]):
                    matched = True
            elif t_name == "get_referral_status":
                if any(w in prompt_lower for w in ["rujukan", "referral"]):
                    matched = True
            elif t_name == "find_specialist":
                if any(w in prompt_lower for w in ["spesialis", "dokter", "jadwal", "specialist"]):
                    matched = True
            elif t_name == "check_bpjs":
                if any(w in prompt_lower for w in ["bpjs", "kepesertaan", "kartu", "iuran"]):
                    matched = True
            elif t_name == "search_web":
                if any(w in prompt_lower for w in ["web", "internet", "berita", "google", "search", "cari"]):
                    matched = True
            else:
                # Cek kemunculan nama tool atau kata kunci deskripsi dalam prompt
                name_clean = t_name.replace("_", " ")
                if name_clean in prompt_lower:
                    matched = True
                else:
                    keywords = [w for w in t_desc.split() if len(w) >= 5]
                    if any(kw in prompt_lower for kw in keywords):
                        matched = True

            if matched and tool.name not in selected:
                selected.append(tool.name)

        return [t for t in selected if t in available_tool_names]

    @staticmethod
    async def build_agent_spec(
        db: AsyncSession, prompt: str, current_spec: Optional[AgentSpec] = None
    ) -> BuilderChatResponse:
        prompt_trimmed = prompt.strip()
        if not prompt_trimmed:
            raise ValueError("Prompt tidak boleh kosong.")

        # Ambil tools aktif langsung dari database
        db_tools_result = await db.execute(select(ToolModel).where(ToolModel.is_active == True))
        valid_db_tools = {t.name for t in db_tools_result.scalars().all()}

        if current_spec and current_spec.id:
            name = current_spec.name
            description = current_spec.description or f"Agent untuk: {prompt_trimmed}"
            instructions = "\n\n".join(
                part for part in [current_spec.instructions or "", prompt_trimmed] if part
            )
            # Filter tools yang sudah ada agar hanya menggunakan tool yang terdaftar di database
            existing_tools = [t for t in (current_spec.tools or []) if t in valid_db_tools]
            new_selected_tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)
            # Gabungkan tools tanpa duplikat
            merged_tools = list(dict.fromkeys(existing_tools + new_selected_tools))
            tools = merged_tools
            mcp_servers = current_spec.mcp_servers
            model, harness, status = current_spec.model, current_spec.harness, current_spec.status
        else:
            name = BuilderService._agent_name(prompt_trimmed)
            description = f"Agent untuk: {prompt_trimmed}"
            instructions = (
                f"Peran dan tujuan agent ini berasal dari permintaan pengguna: {prompt_trimmed}\n\n"
                "Jawab sesuai peran tersebut. Jika informasi atau kemampuan yang diperlukan "
                "tidak tersedia, jelaskan keterbatasannya tanpa mengarang hasil."
            )
            # Ambil tools murni dari database sesuai prompt pengguna
            tools = await BuilderService._select_tools_from_db(db, prompt_trimmed)
            mcp_servers = []
            model, harness, status = "gpt-4o-mini", "default-safe-v1", "active"

        db_agent = AgentSpecModel(
            name=name, description=description, instructions=instructions, model=model,
            tools=tools, mcp_servers=mcp_servers, harness=harness, status=status,
        )
        db.add(db_agent)
        await db.commit()
        await db.refresh(db_agent)
        spec_response = AgentSpecResponse.model_validate(db_agent)
        return BuilderChatResponse(
            id=db_agent.id,
            message=f"Agent '{db_agent.name}' dibuat dari permintaan Anda dan disimpan ke database.",
            spec=spec_response,
        )
