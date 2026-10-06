from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class ToolCallDetail(BaseModel):
    name: str
    params: Dict[str, Any]
    result: Any
    duration_ms: int

class AgentChatRequest(BaseModel):
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    message: str
    stream: bool = False

class AgentChatResponse(BaseModel):
    id: str
    sender: str = "agent"
    text: str
    toolCall: Optional[ToolCallDetail] = None
    status: str = "ok" # ok, escalated, blocked
    run_id: str
    time: str = "Sekarang"

class ChatStreamChunk(BaseModel):
    event: str # content, tool_call, tool_result, status, done
    data: Dict[str, Any]
