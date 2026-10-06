from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from typing import Optional, Dict, Any, Literal
from datetime import datetime

class ToolRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    description: Optional[str] = None
    source_type: Literal["mcp", "builtin", "openapi"] = "builtin"
    input_schema: Optional[Dict[str, Any]] = None


class OpenAPIImportRequest(BaseModel):
    spec_url: HttpUrl
    name_prefix: Optional[str] = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]*$")

class ToolUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_type: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    auth_custody: Optional[str] = None
    health_status: Optional[str] = None
    used_by: Optional[str] = None
    mcp_server_id: Optional[str] = None

class ToolResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    source: str  # maps from source_type in model
    auth: str    # maps from auth_custody
    health: str  # maps from health_status
    usedBy: str  # maps from used_by
    input_schema: Optional[Dict[str, Any]] = None
    mcp_server_id: Optional[str] = None
    created_at: datetime
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)
