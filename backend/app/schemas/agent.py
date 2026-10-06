from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class AgentSpec(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    instructions: Optional[str] = ""
    model: str = "gpt-4o-mini"
    tools: List[str] = []
    mcp_servers: List[str] = []
    harness: str = "default-safe-v1"
    status: str = "active"

class AgentSpecCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    instructions: Optional[str] = ""
    model: str = "gpt-4o-mini"
    tools: List[str] = []
    mcp_servers: List[str] = []
    harness: str = "default-safe-v1"
    status: str = "active"

class AgentSpecUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    tools: Optional[List[str]] = None
    mcp_servers: Optional[List[str]] = None
    harness: Optional[str] = None
    status: Optional[str] = None

class AgentSpecResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    instructions: Optional[str] = ""
    model: str = "gpt-4o-mini"
    tools: List[str] = []
    mcp_servers: List[str] = []
    harness: str = "default-safe-v1"
    status: str = "active"
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class BuilderChatRequest(BaseModel):
    prompt: str
    current_spec: Optional[AgentSpec] = None

class BuilderChatResponse(BaseModel):
    id: str
    message: str
    spec: AgentSpecResponse

class AgentTestRequest(BaseModel):
    agent_id: str
    message: str

class AgentTestResponse(BaseModel):
    agent_id: str
    agent_name: str
    response: str
    status: str = "ok"
    trace_steps: Optional[List[Dict[str, Any]]] = None
    timestamp: datetime
