from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class DeploymentBase(BaseModel):
    agent: str
    environment: Optional[str] = "production"
    path: str
    status: Optional[str] = "Ready"

class DeploymentCreate(DeploymentBase):
    pass

class DeploymentResponse(DeploymentBase):
    id: str
    deployedAt: datetime

    class Config:
        from_attributes = True
