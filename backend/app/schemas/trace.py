from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class TraceStepResponse(BaseModel):
    step_no: int
    type: str # reasoning, tool_call, tool_result, final
    title: str
    duration_ms: int
    detail: Any
    status: str = "ok"

class TraceRunResponse(BaseModel):
    run_id: str
    status: str = "OK"
    total_duration_ms: int
    total_tokens: int
    steps: List[TraceStepResponse]

class SimulationCase(BaseModel):
    id: str
    scenario: str
    input: str
    expected: str
    actual: str
    status: str = "passed"
    duration: str
