from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class EvaluationBase(BaseModel):
    agent: str
    input: str
    expected: str

class EvaluationCreate(EvaluationBase):
    pass

class EvaluationUpdate(BaseModel):
    actual: Optional[str] = None
    status: Optional[str] = None
    lastRun: Optional[str] = None

class EvaluationResponse(EvaluationBase):
    id: str
    actual: str
    status: str
    lastRun: str
    created_at: datetime

    class Config:
        from_attributes = True
