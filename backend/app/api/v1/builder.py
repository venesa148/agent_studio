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
