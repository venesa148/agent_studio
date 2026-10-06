from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.db import get_db
from app.core.security import verify_api_key
from app.schemas.tool import ToolResponse, ToolRegisterRequest, OpenAPIImportRequest
from app.models.tool import ToolModel
from app.services.tool_registry import ToolRegistryService
from sqlalchemy.future import select
from app.services.openapi_importer import OpenAPIImporter

router = APIRouter(prefix="/tools", tags=["Tools Registry"], dependencies=[Depends(verify_api_key)])

@router.get("", response_model=List[ToolResponse])
async def list_tools(db: AsyncSession = Depends(get_db)):
    """
    Mengambil daftar seluruh tools yang terdaftar pada registry allowlist.
    """
    tools = await ToolRegistryService.get_all_tools(db)
    return [
        ToolResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            source=t.source_type,
            auth=t.auth_custody or "none",
            health=t.health_status,
            usedBy=t.used_by or "All agents",
            input_schema=t.input_schema,
            mcp_server_id=t.mcp_server_id,
            created_at=t.created_at
        )
        for t in tools
    ]

@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def register_tool(payload: ToolRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Mendaftarkan custom/built-in tool ke registry catalog.
    """
    existing = await db.execute(select(ToolModel).where(ToolModel.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Tool with name '{payload.name}' already exists.")

    new_tool = ToolModel(
        name=payload.name,
        description=payload.description,
        source_type=payload.source_type,
        input_schema=payload.input_schema,
        auth_custody="none",
        health_status="healthy",
        used_by="All agents"
    )
    db.add(new_tool)
    await db.commit()
    await db.refresh(new_tool)

    return ToolResponse(
        id=new_tool.id,
        name=new_tool.name,
        description=new_tool.description,
        source=new_tool.source_type,
        auth=new_tool.auth_custody,
        health=new_tool.health_status,
        usedBy=new_tool.used_by,
        input_schema=new_tool.input_schema,
        mcp_server_id=new_tool.mcp_server_id,
        created_at=new_tool.created_at,
        is_active=new_tool.is_active
    )


@router.post("/import-openapi", response_model=List[ToolResponse], status_code=status.HTTP_201_CREATED)
async def import_openapi_tools(payload: OpenAPIImportRequest, db: AsyncSession = Depends(get_db)):
    """Import every callable operation in an OpenAPI JSON document into the allowlist."""
    operations = await OpenAPIImporter.fetch_operations(str(payload.spec_url), payload.name_prefix or "")
    names = [operation["name"] for operation in operations]
    existing_result = await db.execute(select(ToolModel.name).where(ToolModel.name.in_(names)))
    existing_names = set(existing_result.scalars().all())
    created = []
    for operation in operations:
        if operation["name"] in existing_names:
            continue
        tool = ToolModel(
            name=operation["name"], description=operation["description"], source_type="openapi",
            input_schema=operation["input_schema"], auth_custody="none", health_status="healthy", used_by="All agents",
        )
        db.add(tool)
        created.append(tool)
    if not created:
        raise HTTPException(status_code=409, detail="All discovered operations already exist in the registry.")
    await db.commit()
    for tool in created:
        await db.refresh(tool)
    return [ToolResponse(id=t.id, name=t.name, description=t.description, source=t.source_type,
                         auth=t.auth_custody or "none", health=t.health_status, usedBy=t.used_by or "All agents",
                         input_schema=t.input_schema, mcp_server_id=t.mcp_server_id, created_at=t.created_at,
                         is_active=t.is_active) for t in created]

from app.schemas.tool import ToolUpdateRequest

@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: str, db: AsyncSession = Depends(get_db)):
    """
    Mengambil detail satu tool berdasarkan ID.
    """
    result = await db.execute(select(ToolModel).where(ToolModel.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool with ID '{tool_id}' not found.")
    
    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        source=tool.source_type,
        auth=tool.auth_custody or "none",
        health=tool.health_status,
        usedBy=tool.used_by or "All agents",
        input_schema=tool.input_schema,
        mcp_server_id=tool.mcp_server_id,
        created_at=tool.created_at,
        is_active=tool.is_active
    )

@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(tool_id: str, payload: ToolUpdateRequest, db: AsyncSession = Depends(get_db)):
    """
    Memperbarui konfigurasi atau metadata tool yang ada.
    """
    result = await db.execute(select(ToolModel).where(ToolModel.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool with ID '{tool_id}' not found.")

    update_data = payload.model_dump(exclude_unset=True)
    
    if "name" in update_data and update_data["name"] != tool.name:
        existing = await db.execute(select(ToolModel).where(ToolModel.name == update_data["name"]))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Tool with name '{update_data['name']}' already exists.")
            
    for key, value in update_data.items():
        setattr(tool, key, value)
        
    await db.commit()
    await db.refresh(tool)
    
    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        source=tool.source_type,
        auth=tool.auth_custody or "none",
        health=tool.health_status,
        usedBy=tool.used_by or "All agents",
        input_schema=tool.input_schema,
        mcp_server_id=tool.mcp_server_id,
        created_at=tool.created_at,
        is_active=tool.is_active
    )

@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(tool_id: str, db: AsyncSession = Depends(get_db)):
    """
    Menghapus tool dari registry allowlist.
    """
    result = await db.execute(select(ToolModel).where(ToolModel.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool with ID '{tool_id}' not found.")
        
    await db.delete(tool)
    await db.commit()
    return None
