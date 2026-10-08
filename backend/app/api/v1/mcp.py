from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.db import get_db
from app.core.security import verify_api_key
from app.schemas.mcp import MCPServerResponse, MCPServerRegisterRequest
from app.models.mcp import MCPServerModel
from app.models.tool import ToolModel
from app.services.mcp_client import MCPClientService

router = APIRouter(prefix="/mcp", tags=["MCP Servers"], dependencies=[Depends(verify_api_key)])

@router.get("", response_model=List[MCPServerResponse])
async def list_mcp_servers(db: AsyncSession = Depends(get_db)):
    """
    Mengambil daftar seluruh MCP Servers yang terdaftar.
    """
    result = await db.execute(select(MCPServerModel).order_by(MCPServerModel.created_at.desc()))
    servers = result.scalars().all()
    
    response_list = []
    for s in servers:
        # Hitung jumlah tools untuk server ini
        tools_res = await db.execute(select(ToolModel).where(ToolModel.mcp_server_id == s.id))
        tools_count = len(tools_res.scalars().all())
        response_list.append(
            MCPServerResponse(
                id=s.id,
                name=s.name,
                url=s.url,
                status=s.status,
                tools_count=tools_count,
                created_at=s.created_at
            )
        )
    return response_list

@router.post("", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def register_mcp_server(payload: MCPServerRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Mendaftarkan MCP Server baru, menghubungkan MCP Client, dan otomatis mengimpor tools.
    """
    try:
        discovered_tools = await MCPClientService.discover_tools(payload.url)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    server = MCPServerModel(name=payload.name, url=payload.url, status="connected")
    db.add(server)
    await db.flush()
    
    for tool_data in discovered_tools:
        tool_name = tool_data.get("name")
        tool_desc = tool_data.get("description", f"Imported from {payload.name}")
        schema = tool_data.get("inputSchema", {})

        # Cek jika tool belum terdaftar
        existing_t = await db.execute(select(ToolModel).where(ToolModel.name == tool_name))
        if not existing_t.scalar_one_or_none():
            new_tool = ToolModel(
                name=tool_name,
                description=tool_desc,
                source_type="mcp",
                mcp_server_id=server.id,
                input_schema=schema,
                auth_custody="none",
                health_status="healthy",
                used_by="All agents"
            )
            db.add(new_tool)
    
    await db.commit()
    await db.refresh(server)

    return MCPServerResponse(
        id=server.id,
        name=server.name,
        url=server.url,
        status=server.status,
        tools_count=len(discovered_tools),
        created_at=server.created_at
    )

from app.schemas.mcp import MCPServerUpdateRequest

@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """
    Mengambil detail satu MCP Server berdasarkan ID.
    """
    result = await db.execute(select(MCPServerModel).where(MCPServerModel.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP Server with ID '{server_id}' not found.")
    
    tools_res = await db.execute(select(ToolModel).where(ToolModel.mcp_server_id == server.id))
    tools_count = len(tools_res.scalars().all())
    
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        url=server.url,
        status=server.status,
        tools_count=tools_count,
        created_at=server.created_at
    )

@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(server_id: str, payload: MCPServerUpdateRequest, db: AsyncSession = Depends(get_db)):
    """
    Memperbarui metadata atau konfigurasi MCP Server yang ada.
    """
    result = await db.execute(select(MCPServerModel).where(MCPServerModel.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP Server with ID '{server_id}' not found.")

    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(server, key, value)
        
    await db.commit()
    await db.refresh(server)
    
    tools_res = await db.execute(select(ToolModel).where(ToolModel.mcp_server_id == server.id))
    tools_count = len(tools_res.scalars().all())
    
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        url=server.url,
        status=server.status,
        tools_count=tools_count,
        created_at=server.created_at
    )

@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """
    Menghapus MCP Server dari registry. Tools yang terkait akan ikut terhapus secara cascade.
    """
    result = await db.execute(select(MCPServerModel).where(MCPServerModel.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP Server with ID '{server_id}' not found.")
        
    await db.delete(server)
    await db.commit()
    return None

@router.post("/local-server")
async def local_mcp_server_handler(request: Request):
    """
    Standar Model Context Protocol (MCP) JSON-RPC 2.0 Server Lokal.
    Menyediakan tools bawaan yang dapat langsung dihubungkan oleh MCP Client.
    """
    body = await request.json()
    req_id = body.get("id", 1)
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "system_time",
                        "description": "Mendapatkan waktu, tanggal, dan zona waktu server saat ini",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "timezone": {
                                    "type": "string",
                                    "description": "Zona waktu target (contoh: WIB, UTC, Asia/Jakarta)",
                                    "default": "Asia/Jakarta"
                                }
                            }
                        }
                    },
                    {
                        "name": "system_diagnostics",
                        "description": "Mendapatkan informasi status sistem, OS, Python version, dan platform runtime",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "currency_converter",
                        "description": "Konversi nilai mata uang asing (USD, EUR, SGD, JPY, MYR) ke Rupiah (IDR)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "amount": {
                                    "type": "number",
                                    "description": "Jumlah nominal uang yang ingin dikonversi"
                                },
                                "from_currency": {
                                    "type": "string",
                                    "description": "Kode mata uang asal (USD, EUR, SGD, JPY, MYR)",
                                    "default": "USD"
                                },
                                "to_currency": {
                                    "type": "string",
                                    "description": "Kode mata uang tujuan (default IDR)",
                                    "default": "IDR"
                                }
                            },
                            "required": ["amount", "from_currency"]
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name == "system_time":
            from datetime import datetime
            now = datetime.now()
            res_text = f"Waktu server saat ini: {now.strftime('%Y-%m-%d %H:%M:%S')} (WIB/Local Server Time)"
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": res_text}],
                    "data": {
                        "date": now.strftime("%Y-%m-%d"),
                        "time": now.strftime("%H:%M:%S"),
                        "timestamp": now.isoformat()
                    }
                }
            }

        elif tool_name == "system_diagnostics":
            import platform
            import sys
            diag = {
                "os": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_version": sys.version.split()[0],
                "status": "healthy"
            }
            res_text = f"Sistem Operasi: {diag['os']} {diag['release']} ({diag['machine']}), Python: {diag['python_version']}, Status: {diag['status']}"
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": res_text}],
                    "data": diag
                }
            }

        elif tool_name == "currency_converter":
            amount = float(tool_args.get("amount", 1))
            from_curr = str(tool_args.get("from_currency", "USD")).upper()
            to_curr = str(tool_args.get("to_currency", "IDR")).upper()

            rates_to_idr = {
                "USD": 15850.0,
                "EUR": 17200.0,
                "SGD": 11950.0,
                "JPY": 105.0,
                "MYR": 3550.0,
                "IDR": 1.0
            }
            rate_from = rates_to_idr.get(from_curr, 15850.0)
            rate_to = rates_to_idr.get(to_curr, 1.0)
            converted = (amount * rate_from) / rate_to
            formatted_res = f"{amount:,.2f} {from_curr} = {converted:,.2f} {to_curr} (Kurs estimasi pasar)"

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": formatted_res}],
                    "data": {
                        "amount": amount,
                        "from_currency": from_curr,
                        "to_currency": to_curr,
                        "result": converted,
                        "rate": rate_from / rate_to
                    }
                }
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method atau tool '{tool_name}' tidak ditemukan di MCP server."
                }
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32600,
            "message": f"Invalid JSON-RPC request method: '{method}'."
        }
    }
