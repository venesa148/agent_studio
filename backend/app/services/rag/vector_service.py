"""
Sub-Sistem Vector & Retrieval:
- Pembuatan embeddings (OpenAI / OpenRouter dengan fallback deterministik offline).
- Pencarian kemiripan kosinus (Cosine Similarity).
- Ingesti dokumen & potongan (chunks) ke database.
- Sintesis blok konteks sitasi terverifikasi (Cohere Groundedness Style).
"""

import hashlib
import json
import logging
import math
from typing import Any, Dict, List, Optional
import numpy as np
from openai import AsyncOpenAI
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.knowledge import KnowledgeDocumentModel, KnowledgeChunkModel
from app.services.rag.chunking import chunk_text

logger = logging.getLogger("rag_vector_service")
EMBEDDING_DIM = 1536


def _deterministic_mock_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Fallback embedding deterministik berbasis feature hashing & n-grams normal.
    Memungkinkan testing lokal dan offline tetap berjalan tanpa dependensi ke internet.
    """
    vec = np.zeros(dim, dtype=np.float32)
    tokens = text.lower().split()
    for token in tokens:
        # Hash token ke indeks vektor
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h % 2 == 0) else -1.0
        vec[idx] += sign

    # Normalisasi vektor menjadi unit vector (norm = 1.0)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    else:
        vec[0] = 1.0
    return vec.tolist()


class VectorService:
    @staticmethod
    async def get_embedding(text: str) -> List[float]:
        """
        Menghasilkan representasi vektor 1536-dimensi untuk teks.
        Menggunakan OpenAI / OpenRouter jika API Key tersedia, atau fallback deterministik.
        """
        api_key = settings.OPENAI_API_KEY or settings.LLM_API_KEY or settings.OPENROUTER_API_KEY
        if api_key and not api_key.startswith("mock_"):
            try:
                base_url = None
                if "openrouter.ai" in (settings.LLM_BASE_URL or ""):
                    base_url = settings.LLM_BASE_URL

                client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                resp = await client.embeddings.create(
                    input=text[:8000],
                    model="text-embedding-3-small"
                )
                return resp.data[0].embedding
            except Exception as exc:
                logger.warning(f"Gagal memanggil API embedding ({exc}). Beralih ke fallback deterministik.")

        return _deterministic_mock_embedding(text)

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Menghitung nilai kemiripan kosinus antara dua vektor."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    @classmethod
    async def ingest_document(
        cls,
        db: AsyncSession,
        title: str,
        source_type: str,
        text_content: str,
        source_uri: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> KnowledgeDocumentModel:
        """
        Memproses dokumen baru:
        1. Simpan header dokumen
        2. Pecah menjadi chunks
        3. Buat embedding tiap chunk
        4. Simpan ke database
        """
        cleaned_text = text_content.strip()
        if not cleaned_text:
            raise ValueError("Konten teks dokumen kosong.")

        # 1. Simpan entri dokumen utama
        doc = KnowledgeDocumentModel(
            title=title,
            source_type=source_type,
            source_uri=source_uri,
            raw_content=cleaned_text[:50000],  # simpan cuplikan dokumen
            agent_id=agent_id,
        )
        db.add(doc)
        await db.flush()

        # 2. Chunking teks
        chunks = chunk_text(cleaned_text, chunk_size=600, chunk_overlap=80)
        chunk_models = []

        # 3. Generate embedding & buat Chunk Models
        for idx, chunk_str in enumerate(chunks):
            embedding_vec = await cls.get_embedding(chunk_str)
            chunk_obj = KnowledgeChunkModel(
                document_id=doc.id,
                agent_id=agent_id,
                chunk_index=idx,
                content=chunk_str,
                embedding=embedding_vec,
                metadata_info={"source": title, "uri": source_uri, "index": idx},
            )
            db.add(chunk_obj)
            chunk_models.append(chunk_obj)

        doc.total_chunks = len(chunk_models)
        await db.commit()
        await db.refresh(doc)
        return doc

    @classmethod
    async def search_relevant_chunks(
        cls,
        db: AsyncSession,
        query: str,
        agent_id: Optional[str] = None,
        top_k: int = 3,
        min_similarity: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """
        Mencari potongan dokumen paling relevan dengan kueri pengguna
        menggunakan similarity kosinus terhadap seluruh chunk di database.
        """
        if not query or not query.strip():
            return []

        query_vec = await cls.get_embedding(query.strip())

        # Ambil chunks yang relevan untuk agent tertentu atau global
        stmt = select(KnowledgeChunkModel).options(selectinload(KnowledgeChunkModel.document))
        if agent_id:
            stmt = stmt.where((KnowledgeChunkModel.agent_id == agent_id) | (KnowledgeChunkModel.agent_id.is_(None)))

        res = await db.execute(stmt)
        all_chunks = res.scalars().all()

        if not all_chunks:
            return []

        scored_chunks = []
        for c in all_chunks:
            if not c.embedding:
                continue
            sim = cls.cosine_similarity(query_vec, c.embedding)
            if sim >= min_similarity:
                doc_title = c.document.title if c.document else "Dokumen"
                source_uri = c.document.source_uri if c.document else None
                scored_chunks.append({
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "document_title": doc_title,
                    "source_uri": source_uri,
                    "chunk_index": c.chunk_index,
                    "content": c.content,
                    "similarity": sim,
                })

        # Urutkan berdasarkan similarity tertinggi
        scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_chunks[:top_k]

    @staticmethod
    def build_grounded_context(chunks: List[Dict[str, Any]]) -> str:
        """
        Merangkai potongan informasi RAG menjadi blok konteks ber-sitasi (Cohere Style)
        untuk disuntikkan ke dalam prompt instruksi model.
        """
        if not chunks:
            return ""

        context_blocks = ["[KNOWLEDGE BASE / REFERENSI DOKUMEN RESMI]"]
        for idx, c in enumerate(chunks, 1):
            doc_name = c.get("document_title", "Dokumen")
            part_idx = c.get("chunk_index", 0) + 1
            content = c.get("content", "").strip()
            context_blocks.append(f"--- [Sumber {idx}]: {doc_name} (Bagian {part_idx}) ---\n{content}")

        context_blocks.append(
            "[ATURAN SITASI: Jawab pertanyaan pengguna berdasarkan referensi dokumen di atas. "
            "Sertakan nama dokumen referensi jika menyampaikan fakta atau informasi spesifik.]"
        )
        return "\n\n".join(context_blocks)
