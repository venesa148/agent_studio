from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.security import verify_api_key
from app.schemas.agent import (
    AgentSpecResponse,
    AgentSpecCreate,
    AgentSpecUpdate,
    AgentTestRequest,
    AgentTestResponse
)
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["Agent Management & Testing"], dependencies=[Depends(verify_api_key)])

@router.get("", response_model=List[AgentSpecResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    """
    Mengambil daftar seluruh Agent yang tersimpan di database.
    """
    agents = await AgentService.get_all_agents(db)
    return [AgentSpecResponse.model_validate(a) for a in agents]

@router.get("/{agent_id}", response_model=AgentSpecResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """
    Mengambil detail Agent berdasarkan ID dari database.
    """
    agent = await AgentService.get_agent_by_id(db, agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent dengan ID '{agent_id}' tidak ditemukan.")
    return AgentSpecResponse.model_validate(agent)

@router.post("", response_model=AgentSpecResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: AgentSpecCreate, db: AsyncSession = Depends(get_db)):
    """
    Membuat Agent baru dan menyimpannya ke database.
    """
    db_agent = await AgentService.create_agent(db, payload)
    return AgentSpecResponse.model_validate(db_agent)

@router.put("/{agent_id}", response_model=AgentSpecResponse)
async def update_agent(agent_id: str, payload: AgentSpecUpdate, db: AsyncSession = Depends(get_db)):
    """
    Perbarui data Agent yang ada di database.
    """
    updated = await AgentService.update_agent(db, agent_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent dengan ID '{agent_id}' tidak ditemukan.")
    return AgentSpecResponse.model_validate(updated)

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """
    Hapus Agent dari database berdasarkan ID.
    """
    success = await AgentService.delete_agent(db, agent_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent dengan ID '{agent_id}' tidak ditemukan.")
    return None

@router.get("/{agent_id}/history")
async def get_agent_history(agent_id: str, db: AsyncSession = Depends(get_db)):
    """
    Mengambil seluruh riwayat pesan percakapan (working memory) untuk Agent ini dari database.
    """
    return await AgentService.get_agent_history(db, agent_id)

@router.delete("/{agent_id}/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_agent_history(agent_id: str, db: AsyncSession = Depends(get_db)):
    """
    Mereset atau membersihkan riwayat percakapan Agent ini di database.
    """
    await AgentService.clear_agent_history(db, agent_id)
    return None

@router.post("/chat", response_model=AgentTestResponse)
async def agent_chat_test(payload: AgentTestRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint pengujian Agent di panel kanan (Test Chat).
    Menerima agent_id + message, mengambil Agent dari database, dan memproses respons deterministik.
    """
    try:
        return await AgentService.test_agent(db, payload.agent_id, payload.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal memproses pesan agent: {str(e)}")

@router.get("/{agent_id}/export-yaml")
async def export_agent_yaml(agent_id: str, download: bool = False, db: AsyncSession = Depends(get_db)):
    """
    Mengekspor spesifikasi Agent ke format deklaratif .YAML.
    """
    res = await AgentService.export_agent_yaml(db, agent_id, save_to_disk=True)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent dengan ID '{agent_id}' tidak ditemukan.")

    if download:
        from fastapi.responses import Response
        filename = res["filename"]
        return Response(
            content=res["yaml"],
            media_type="application/x-yaml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    return res
