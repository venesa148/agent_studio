from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import verify_api_key
from app.schemas.agent import (
    BuilderChatRequest, 
    BuilderChatResponse, 
    AgentSpecResponse, 
    AgentSpec,
    AgentSpecCreate,
    AgentSpecUpdate
)
from app.services.builder_service import BuilderService
from app.services.agent_service import AgentService

router = APIRouter(prefix="/builder", tags=["Agent Builder"], dependencies=[Depends(verify_api_key)])

@router.post("/chat", response_model=BuilderChatResponse)
async def builder_chat(payload: BuilderChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint untuk menyusun spesifikasi Agent berbasis bahasa alami dari pengguna
    dan menyimpannya secara otomatis ke database.
    """
    try:
        return await BuilderService.build_agent_spec(db, payload.prompt, payload.current_spec, payload.history)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal membuat Agent: {str(e)}")

@router.post("/save", response_model=AgentSpecResponse)
async def builder_save(payload: AgentSpec, db: AsyncSession = Depends(get_db)):
    """
    Menyimpan atau memperbarui Spesifikasi Agent ke database.
    """
    try:
        # Auto-resolve mcp_servers from tools if not provided
        mcp_servers = payload.mcp_servers or []
        if payload.tools and not mcp_servers:
            from app.models.tool import ToolModel
            from sqlalchemy import select
            t_query = await db.execute(
                select(ToolModel.mcp_server_id).where(
                    ToolModel.name.in_(payload.tools),
                    ToolModel.mcp_server_id.isnot(None)
                )
            )
            mcp_servers = list(set([r[0] for r in t_query.fetchall() if r[0]]))

        if payload.id:
            db_agent = await AgentService.update_agent(db, payload.id, AgentSpecUpdate(
                name=payload.name,
                description=payload.description,
                instructions=payload.instructions,
                model=payload.model,
                tools=payload.tools,
                mcp_servers=mcp_servers,
                harness=payload.harness,
                status=payload.status
            ))
            if not db_agent:
                # If ID passed wasn't found in DB, create new
                create_payload = AgentSpecCreate(
                    name=payload.name,
                    description=payload.description,
                    instructions=payload.instructions,
                    model=payload.model,
                    tools=payload.tools,
                    mcp_servers=mcp_servers,
                    harness=payload.harness,
                    status=payload.status
                )
                db_agent = await AgentService.create_agent(db, create_payload)
        else:
            create_payload = AgentSpecCreate(
                name=payload.name,
                description=payload.description,
                instructions=payload.instructions,
                model=payload.model,
                tools=payload.tools,
                mcp_servers=mcp_servers,
                harness=payload.harness,
                status=payload.status
            )
            db_agent = await AgentService.create_agent(db, create_payload)

        try:
            await AgentService.export_agent_yaml(db, db_agent.id, save_to_disk=True)
        except Exception as e_yaml:
            print(f'Warning auto-export yaml: {e_yaml}')
        return AgentSpecResponse.model_validate(db_agent)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal menyimpan Agent: {str(e)}")

from pydantic import BaseModel
import json
from sqlalchemy import select
from app.models.chat import ConversationModel, MessageModel

class BuilderHistorySaveRequest(BaseModel):
    messages: list[dict]

@router.get("/history/{agent_id}")
async def get_builder_history(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Mengambil riwayat percakapan pembuatan agent (builder chat)."""
    conv_title = f"builder_session_{agent_id}"
    conv_res = await db.execute(select(ConversationModel).where(ConversationModel.title == conv_title))
    conversation = conv_res.scalar_one_or_none()
    if not conversation:
        return []
    msg_res = await db.execute(select(MessageModel).where(MessageModel.conversation_id == conversation.id).order_by(MessageModel.created_at))
    messages = msg_res.scalars().all()
    out = []
    for m in messages:
        try:
            data = json.loads(m.content)
            out.append(data)
        except Exception:
            out.append({
                "id": m.id,
                "sender": m.role,
                "text": m.content,
                "time": m.created_at.isoformat() if m.created_at else None
            })
    return out

@router.post("/history/{agent_id}")
async def save_builder_history(agent_id: str, payload: BuilderHistorySaveRequest, db: AsyncSession = Depends(get_db)):
    """Menyimpan riwayat percakapan pembuatan agent (builder chat)."""
    conv_title = f"builder_session_{agent_id}"
    conv_res = await db.execute(select(ConversationModel).where(ConversationModel.title == conv_title))
    conversation = conv_res.scalar_one_or_none()
    
    if conversation:
        await db.delete(conversation)
        await db.flush()
        
    conversation = ConversationModel(user_id=agent_id, title=conv_title)
    db.add(conversation)
    await db.flush()
    
    for msg in payload.messages:
        db.add(MessageModel(
            conversation_id=conversation.id,
            role=msg.get("sender", "user"),
            content=json.dumps(msg)
        ))
    
    await db.commit()
    return {"status": "ok"}
