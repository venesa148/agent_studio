import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

class ToolModel(Base):
    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="mcp") # mcp, builtin, openapi
    mcp_server_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("mcp_servers.id"), nullable=True)
    input_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_custody: Mapped[Optional[str]] = mapped_column(String(100), default="none")
    health_status: Mapped[str] = mapped_column(String(50), default="healthy")
    used_by: Mapped[Optional[str]] = mapped_column(String(255), default="All agents")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    mcp_server: Mapped[Optional["MCPServerModel"]] = relationship("MCPServerModel", back_populates="tools")
