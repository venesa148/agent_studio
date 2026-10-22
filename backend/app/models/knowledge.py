import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, JSON, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class VectorType(TypeDecorator):
    """
    Universal Vector type:
    - On PostgreSQL with pgvector: maps to VECTOR(1536)
    - On SQLite/fallback: maps to JSON
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(1536))
        return dialect.type_descriptor(JSON())


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("agent_specs.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="text")  # 'pdf', 'url', 'text'
    source_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    chunks: Mapped[List["KnowledgeChunkModel"]] = relationship(
        "KnowledgeChunkModel", back_populates="document", cascade="all, delete-orphan"
    )
    agent: Mapped[Optional["AgentSpecModel"]] = relationship("AgentSpecModel", backref="documents")


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Stored as pgvector(1536) on PostgreSQL or JSON on SQLite
    embedding: Mapped[Optional[List[float]]] = mapped_column(VectorType, nullable=True)
    metadata_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["KnowledgeDocumentModel"] = relationship("KnowledgeDocumentModel", back_populates="chunks")
