from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any, Dict

class EvaluationBase(BaseModel):
    agent: str
    input: str
    expected: str

class EvaluationCreate(EvaluationBase):
    pass

class EvaluationUpdate(BaseModel):
    actual: Optional[str] = None
    status: Optional[str] = None
    score: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    lastRun: Optional[str] = None

class EvaluationResponse(EvaluationBase):
    id: str
    actual: str
    status: str
    score: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    lastRun: str
    created_at: datetime

    class Config:
        from_attributes = True
