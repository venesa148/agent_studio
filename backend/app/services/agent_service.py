from datetime import datetime
from typing import List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import AgentSpecModel
from app.schemas.agent import AgentSpecCreate, AgentSpecUpdate, AgentTestResponse


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
        from app.models.tool import ToolModel
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
        if settings.OPENAI_API_KEY:
            return AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0), agent.model or settings.OPENAI_DEFAULT_MODEL
        if settings.LLM_API_KEY:
            return AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL, max_retries=0), agent.model or settings.LLM_MODEL
        raise RuntimeError("LLM belum dikonfigurasi. Tambahkan OPENAI_API_KEY atau LLM_API_KEY untuk menjalankan test chat; tidak ada respons contoh yang ditampilkan.")

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
            f"Nama agent: {db_agent.name}\nTujuan: {db_agent.description or ''}\n"
            f"Instruksi: {db_agent.instructions or ''}\nTools yang dipilih dan terdaftar: {selected_tools}\n"
            f"MCP yang dipilih: {selected_mcp}\n"
            "Jangan mengaku telah memakai tool atau MCP kecuali eksekusi nyata tersedia. "
            "Jangan mengarang data atau hasil tool."
        )
        try:
            completion = await client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_message}, {"role": "user", "content": message_trimmed}],
            )
        except Exception as exc:
            if settings.LLM_API_KEY and settings.OPENAI_API_KEY:
                try:
                    fallback_client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL, max_retries=0)
                    fallback_model = settings.LLM_MODEL
                    completion = await fallback_client.chat.completions.create(
                        model=fallback_model,
                        messages=[{"role": "system", "content": system_message}, {"role": "user", "content": message_trimmed}],
                    )
                except Exception as fallback_exc:
                    raise RuntimeError(f"LLM gagal memproses pesan untuk agent '{db_agent.name}': {fallback_exc}") from fallback_exc
            else:
                raise RuntimeError(f"LLM gagal memproses pesan untuk agent '{db_agent.name}': {exc}") from exc

        response = completion.choices[0].message.content
        if not response:
            raise RuntimeError("LLM tidak mengembalikan respons. Tidak ada respons pengganti yang dibuat.")
        return AgentTestResponse(
            agent_id=db_agent.id, agent_name=db_agent.name, response=response,
            status="ok", trace_steps=[], timestamp=datetime.utcnow(),
        )
