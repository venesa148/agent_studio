from sqlalchemy import Column, String, DateTime
from datetime import datetime, timezone
import uuid
from app.core.db import Base

class DeploymentModel(Base):
    __tablename__ = "deployments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent = Column(String(100), nullable=False)
    environment = Column(String(50), default="production")
    path = Column(String(255), nullable=False)
    status = Column(String(50), default="Ready")
    deployedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
