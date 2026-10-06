import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, DateTime, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class TraceLogModel(Base):
    __tablename__ = "trace_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    run_id: Mapped[str] = mapped_column(String(255), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False) # reasoning, tool_call, tool_result, final
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
