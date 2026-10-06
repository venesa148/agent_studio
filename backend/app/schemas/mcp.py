from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class MCPServerRegisterRequest(BaseModel):
    name: str
    url: str

class MCPServerUpdateRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None

class MCPServerResponse(BaseModel):
    id: str
    name: str
    url: str
    status: str
    tools_count: Optional[int] = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
