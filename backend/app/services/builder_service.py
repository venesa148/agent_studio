from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentSpecModel
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
    async def build_agent_spec(
        db: AsyncSession, prompt: str, current_spec: Optional[AgentSpec] = None
    ) -> BuilderChatResponse:
        prompt_trimmed = prompt.strip()
        if not prompt_trimmed:
            raise ValueError("Prompt tidak boleh kosong.")

        if current_spec and current_spec.id:
            name = current_spec.name
            description = current_spec.description or f"Agent untuk: {prompt_trimmed}"
            instructions = "\n\n".join(
                part for part in [current_spec.instructions or "", prompt_trimmed] if part
            )
            tools, mcp_servers = current_spec.tools, current_spec.mcp_servers
            model, harness, status = current_spec.model, current_spec.harness, current_spec.status
        else:
            name = BuilderService._agent_name(prompt_trimmed)
            description = f"Agent untuk: {prompt_trimmed}"
            instructions = (
                f"Peran dan tujuan agent ini berasal dari permintaan pengguna: {prompt_trimmed}\n\n"
                "Jawab sesuai peran tersebut. Jika informasi atau kemampuan yang diperlukan "
                "tidak tersedia, jelaskan keterbatasannya tanpa mengarang hasil."
            )
            tools = ["search_hospital"] if "bpjs" in prompt_trimmed.lower() else []
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
