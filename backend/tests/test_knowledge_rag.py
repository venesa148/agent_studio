import io
import pytest
from httpx import AsyncClient, Response
from unittest.mock import patch, AsyncMock
from app.services.rag.ingestion import (
    validate_url_safety,
    clean_html_to_text,
    extract_pdf_text,
    SSRFValidationError,
)
from app.services.rag.chunking import chunk_text
from app.services.rag.vector_service import VectorService
from tests.conftest import TestingSessionLocal


def test_ssrf_safety_validation():
    """Menguji proteksi anti-SSRF terhadap berbagai serangan IP privat & loopback."""
    # 1. Tolak Loopback & Localhost
    with pytest.raises(SSRFValidationError):
        validate_url_safety("http://localhost:8000/admin")

    with pytest.raises(SSRFValidationError):
        validate_url_safety("http://127.0.0.1/etc/passwd")

    with pytest.raises(SSRFValidationError):
        validate_url_safety("http://0.0.0.0:5432")

    # 2. Tolak IP Privat RFC 1918 (10.x, 192.168.x, 172.16.x)
    with pytest.raises(SSRFValidationError):
        validate_url_safety("http://10.0.1.5/api")

    with pytest.raises(SSRFValidationError):
        validate_url_safety("http://192.168.1.1/router")

    # 3. Tolak AWS / Cloud Metadata IP (169.254.169.254)
    with pytest.raises(SSRFValidationError):
        validate_url_safety("http://169.254.169.254/latest/meta-data")

    # 4. Tolak Skema Non-HTTP (file, ftp, gopher)
    with pytest.raises(SSRFValidationError):
        validate_url_safety("ftp://files.example.com")


def test_html_cleaning():
    """Menguji konversi HTML kotor menjadi teks bersih."""
    raw_html = """
    <html>
        <head><script>alert('xss');</script><style>.body{color:red}</style></head>
        <body>
            <h1>Menu Kafe</h1>
            <p>Espresso: Rp 20.000<br/>Latte: Rp 25.000</p>
            <!-- Komentar internal -->
            <div>Buka: 08.00 - 22.00 WIB</div>
        </body>
    </html>
    """
    cleaned = clean_html_to_text(raw_html)
    assert "Menu Kafe" in cleaned
    assert "Espresso: Rp 20.000" in cleaned
    assert "Latte: Rp 25.000" in cleaned
    assert "Buka: 08.00 - 22.00 WIB" in cleaned
    assert "<script>" not in cleaned
    assert "alert" not in cleaned
    assert "Komentar internal" not in cleaned


def test_recursive_chunking():
    """Menguji pemecahan teks panjang menjadi chunks dengan overlap."""
    sample_text = (
        "Paragraf pertama menjelaskan tentang profil kafe dan visi misi didirikan sejak tahun 2020. "
        "Kami menyajikan biji kopi pilihan dari petani lokal Nusantara.\n\n"
        "Paragraf kedua merinci daftar menu makanan dan minuman spesial. "
        "Espresso Rp 20.000, Americano Rp 22.000, Cappuccino Rp 25.000, Croissant Rp 18.000.\n\n"
        "Paragraf ketiga menjelaskan jam operasional dan tata cara reservasi meja. "
        "Reservasi dapat dilakukan maksimal 2 jam sebelum kedatangan."
    )
    chunks = chunk_text(sample_text, chunk_size=120, chunk_overlap=20)
    assert len(chunks) >= 3
    # Verifikasi seluruh teks terwakili tanpa kata yang hilang
    full_joined = " ".join(chunks)
    assert "Espresso" in full_joined
    assert "Reservasi" in full_joined


def test_pdf_extraction_with_pypdf():
    """Menguji ekstraksi teks dari PDF in-memory."""
    import pypdf
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    # Simpan ke BytesIO
    stream = io.BytesIO()
    writer.write(stream)
    pdf_bytes = stream.getvalue()

    # Empty blank PDF should raise ValueError
    with pytest.raises(ValueError):
        extract_pdf_text(pdf_bytes)


@pytest.mark.asyncio
async def test_vector_service_ingest_and_search():
    """Menguji pipeline lengkap VectorService: Ingesti, Embedding, dan Semantic Search."""
    async with TestingSessionLocal() as session:
        doc = await VectorService.ingest_document(
            db=session,
            title="SOP Kafe Kopi Kamu",
            source_type="text",
            text_content=(
                "Jam buka kafe adalah pukul 08.00 pagi sampai 22.00 malam setiap hari. "
                "Harga menu kopi espresso adalah dua puluh ribu rupiah. "
                "Untuk reservasi meja pesta ulang tahun wajib membayar uang muka 50 persen."
            ),
            source_uri="sop_kafe.txt",
        )
        assert doc.id is not None
        assert doc.total_chunks >= 1

        # Uji pencarian semantik (query yang relevan)
        results = await VectorService.search_relevant_chunks(
            db=session,
            query="Berapa jam buka kafe dan harga kopi?",
            top_k=2
        )
        assert len(results) >= 1
        assert "08.00" in results[0]["content"]

        # Uji penyusunan grounded context
        grounded_context = VectorService.build_grounded_context(results)
        assert "[KNOWLEDGE BASE / REFERENSI DOKUMEN RESMI]" in grounded_context
        assert "SOP Kafe Kopi Kamu" in grounded_context


@pytest.mark.asyncio
async def test_knowledge_api_endpoints(async_client: AsyncClient):
    """Menguji endpoint REST API /api/v1/knowledge."""
    # 1. Ingest Text via POST /api/v1/knowledge/text
    res_text = await async_client.post(
        "/api/v1/knowledge/text",
        json={
            "title": "Ketentuan Garansi Elektronik",
            "content": "Garansi resmi berlaku selama 1 tahun untuk kerusakan pabrik. Garansi batal jika terkena air."
        }
    )
    assert res_text.status_code == 201
    doc_id = res_text.json()["id"]

    # 2. List Documents via GET /api/v1/knowledge/documents
    res_list = await async_client.get("/api/v1/knowledge/documents")
    assert res_list.status_code == 200
    docs = res_list.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Query Knowledge via POST /api/v1/knowledge/query
    res_query = await async_client.post(
        "/api/v1/knowledge/query",
        json={"query": "Apakah garansi berlaku kalau jatuh ke air?", "top_k": 1}
    )
    assert res_query.status_code == 200
    query_data = res_query.json()
    assert len(query_data["top_chunks"]) >= 1
    assert "garansi" in query_data["grounded_context"].lower()

    # 4. Delete Document via DELETE /api/v1/knowledge/documents/{id}
    res_del = await async_client.delete(f"/api/v1/knowledge/documents/{doc_id}")
    assert res_del.status_code == 200

    # 5. Uji Anti-SSRF pada POST /api/v1/knowledge/url-scrape
    res_ssrf = await async_client.post(
        "/api/v1/knowledge/url-scrape",
        json={"url": "http://127.0.0.1:8000/secret"}
    )
    assert res_ssrf.status_code == 400
    assert "Anti-SSRF" in res_ssrf.json()["detail"]
