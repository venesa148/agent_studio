from sqlalchemy import Column, String, DateTime, Integer, Text, JSON
from datetime import datetime, timezone
import uuid
from app.core.db import Base

class EvaluationModel(Base):
    __tablename__ = "evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent = Column(String(100), nullable=False)
    input = Column(String(500), nullable=False)
    expected = Column(String(255), nullable=False)
    actual = Column(Text, default="-")
    status = Column(String(50), default="idle")
    score = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    lastRun = Column(String(100), default="Belum dijalankan")
    created_at = Column(DateTime, default=datetime.utcnow)
