import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import verify_api_key
from app.models.knowledge import KnowledgeDocumentModel, KnowledgeChunkModel
from app.schemas.knowledge import (
    KnowledgeDocumentResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    TextIngestRequest,
    URLScrapeRequest,
)
from app.services.rag.ingestion import (
    SSRFValidationError,
    extract_pdf_text,
    fetch_url_content,
)
from app.services.rag.vector_service import VectorService

logger = logging.getLogger("api_knowledge")
router = APIRouter(prefix="/knowledge", tags=["Knowledge & RAG Engine"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=List[KnowledgeDocumentResponse])
@router.get("/documents", response_model=List[KnowledgeDocumentResponse])
async def list_documents(
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Mengambil daftar seluruh dokumen yang tersimpan di Knowledge Base (mendukung ?agent_id=...)."""
    stmt = select(KnowledgeDocumentModel).order_by(KnowledgeDocumentModel.created_at.desc())
    if agent_id:
        stmt = stmt.where((KnowledgeDocumentModel.agent_id == agent_id) | (KnowledgeDocumentModel.agent_id.is_(None)))

    res = await db.execute(stmt)
    docs = res.scalars().all()
    return docs


@router.post("/url-scrape", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def ingest_url(
    payload: URLScrapeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Mengambil isi URL publik secara aman (anti-SSRF), membersihkan HTML menjadi teks,
    lalu memotong dan menyimpannya ke database vektor.
    """
    try:
        scraped_text = await fetch_url_content(payload.url)
    except SSRFValidationError as s_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pelanggaran Keamanan Anti-SSRF: {str(s_err)}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gagal mengambil konten dari URL target: {str(exc)}",
        )

    doc_title = payload.title or f"Halaman Web: {payload.url[:40]}"
    doc = await VectorService.ingest_document(
        db=db,
        title=doc_title,
        source_type="url",
        source_uri=payload.url,
        text_content=scraped_text,
        agent_id=payload.agent_id,
    )
    return doc


@router.post("/upload", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    agent_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Mengunggah berkas PDF atau teks murni, mengekstraksi isinya,
    lalu menyimpannya ke dalam Knowledge Base.
    """
    filename = file.filename or "dokumen"
    content_bytes = await file.read()

    if not content_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Berkas yang diunggah kosong.")

    is_pdf = filename.lower().endswith(".pdf") or file.content_type == "application/pdf"
    if is_pdf:
        try:
            extracted_text = extract_pdf_text(content_bytes)
            source_type = "pdf"
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Gagal memproses file PDF: {str(exc)}",
            )
    else:
        # Asumsikan text/plain / markdown
        try:
            extracted_text = content_bytes.decode("utf-8", errors="replace")
            source_type = "text"
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Gagal membaca teks: {str(exc)}")

    doc_title = title or filename
    doc = await VectorService.ingest_document(
        db=db,
        title=doc_title,
        source_type=source_type,
        source_uri=filename,
        text_content=extracted_text,
        agent_id=agent_id,
    )
    return doc


@router.post("/text", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def ingest_raw_text(
    payload: TextIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Mendaftarkan teks langsung (misal: SOP, catatan) ke Knowledge Base."""
    doc = await VectorService.ingest_document(
        db=db,
        title=payload.title,
        source_type="text",
        source_uri="raw_input",
        text_content=payload.content,
        agent_id=payload.agent_id,
    )
    return doc


@router.delete("/documents/{doc_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Menghapus dokumen beserta seluruh chunks terkait dari Knowledge Base."""
    res = await db.execute(select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == doc_id))
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dokumen tidak ditemukan.")

    await db.delete(doc)
    await db.commit()
    return {"status": "ok", "message": f"Dokumen '{doc.title}' berhasil dihapus."}


@router.post("/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(
    payload: KnowledgeQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Melakukan pencarian kemiripan semantik terhadap kueri pengguna
    dan menyusun blok grounded context terstruktur.
    """
    chunks = await VectorService.search_relevant_chunks(
        db=db,
        query=payload.query,
        agent_id=payload.agent_id,
        top_k=payload.top_k,
    )
    grounded_context = VectorService.build_grounded_context(chunks)

    formatted_chunks = [
        {
            "chunk_id": c["chunk_id"],
            "document_id": c["document_id"],
            "document_title": c["document_title"],
            "source_uri": c["source_uri"],
            "chunk_index": c["chunk_index"],
            "content": c["content"],
            "similarity": round(c["similarity"], 4),
        }
        for c in chunks
    ]

    return {
        "query": payload.query,
        "top_chunks": formatted_chunks,
        "grounded_context": grounded_context,
    }
