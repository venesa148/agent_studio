from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class URLScrapeRequest(BaseModel):
    url: str = Field(..., description="Alamat URL yang ingin di-ingest ke Knowledge Base")
    title: Optional[str] = Field(None, description="Judul dokumen (opsional)")
    agent_id: Optional[str] = Field(None, description="ID Agent pemilik dokumen (opsional)")


class TextIngestRequest(BaseModel):
    title: str = Field(..., description="Judul dokumen teks")
    content: str = Field(..., description="Isi teks dokumen")
    agent_id: Optional[str] = Field(None, description="ID Agent pemilik dokumen (opsional)")


class KnowledgeQueryRequest(BaseModel):
    query: str = Field(..., description="Pertanyaan atau kueri pencarian semantik")
    agent_id: Optional[str] = Field(None, description="Filter kueri berdasarkan agent_id tertentu")
    top_k: int = Field(3, description="Jumlah potongan dokumen paling relevan yang ingin diambil")


class ChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    source_uri: Optional[str] = None
    chunk_index: int
    content: str
    similarity: float


class KnowledgeQueryResponse(BaseModel):
    query: str
    top_chunks: List[ChunkResponse]
    grounded_context: str


class KnowledgeDocumentResponse(BaseModel):
    id: str
    agent_id: Optional[str] = None
    title: str
    source_type: str
    source_uri: Optional[str] = None
    total_chunks: int
    created_at: datetime

    class Config:
        from_attributes = True
