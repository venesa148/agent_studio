"""
Sub-Sistem Ingestion & Security:
- Validasi keamanan Anti-SSRF (Server-Side Request Forgery).
- Ekstraksi konten halaman web bersih (HTML to Text).
- Ekstraksi dokumen PDF halaman per halaman menggunakan pypdf.
"""

import ipaddress
import logging
import re
import socket
from io import BytesIO
from typing import Optional
from urllib.parse import urlparse
import httpx

logger = logging.getLogger("rag_ingestion")

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private Network (RFC 1918)
    ipaddress.ip_network("172.16.0.0/12"),    # Private Network (RFC 1918)
    ipaddress.ip_network("192.168.0.0/16"),   # Private Network (RFC 1918)
    ipaddress.ip_network("169.254.0.0/16"),   # Link-Local / AWS Metadata
    ipaddress.ip_network("0.0.0.0/8"),        # Broadcast/Current network
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 Unique Local
]


class SSRFValidationError(ValueError):
    """Dilempar ketika URL melanggar kebijakan keamanan anti-SSRF."""
    pass


def validate_url_safety(url: str) -> None:
    """
    Memvalidasi apakah URL aman untuk diakses oleh server (Anti-SSRF Protection).
    Mencegah akses ke IP privat internal, AWS metadata, atau loopback.
    """
    if not url or not isinstance(url, str):
        raise SSRFValidationError("URL tidak boleh kosong.")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFValidationError(f"Skema URL '{parsed.scheme}' tidak diizinkan. Hanya 'http' dan 'https' yang didukung.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("Hostname tidak ditemukan dalam URL.")

    hostname_lower = hostname.lower()
    if hostname_lower in ("localhost", "127.0.0.1", "0.0.0.0", "internal", "local"):
        raise SSRFValidationError(f"Akses ke host '{hostname}' dilarang demi keamanan internal server.")

    # Resolusi DNS untuk memeriksa apakah domain memetakan ke IP privat
    try:
        resolved_ips = socket.getaddrinfo(hostname, None)
        for entry in resolved_ips:
            ip_str = entry[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            for blocked_net in BLOCKED_IP_NETWORKS:
                if ip_obj in blocked_net:
                    raise SSRFValidationError(
                        f"Domain '{hostname}' teresolusi ke IP privat/terlarang ({ip_str}) dan diblokir demi keamanan."
                    )
    except socket.gaierror as exc:
        raise SSRFValidationError(f"Gagal menyelesaikan DNS untuk domain '{hostname}': {exc}")


def clean_html_to_text(html_content: str) -> str:
    """Membersihkan raw HTML menjadi teks bersih bebas script, style, dan tag markup."""
    if not html_content:
        return ""

    # Hapus tag script, style, noscript, komentar
    text = re.sub(r"<(script|style|noscript|header|footer|nav).*?>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    # Ganti tag break/paragraf dengan newline
    text = re.sub(r"</?(p|br|div|h[1-6]|li|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Hapus tag HTML yang tersisa
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode entitas HTML umum
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    # Normalisasi spasi berlebih
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    cleaned = "\n".join([line for line in lines if line])
    return cleaned.strip()


async def fetch_url_content(url: str, timeout_sec: float = 10.0, max_bytes: int = 500_000) -> str:
    """
    Mengambil isi halaman web secara aman dengan proteksi SSRF dan konversi ke plain text.
    """
    validate_url_safety(url)

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AgentStudio-KnowledgeFetcher/1.0)",
        "Accept": "text/html,application/xhtml+xml,text/plain",
    }

    async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gagal mengambil URL '{url}': HTTP {resp.status_code}")

        content_bytes = resp.content[:max_bytes]
        raw_text = content_bytes.decode(resp.encoding or "utf-8", errors="replace")

        # Jika konten berupa HTML, bersihkan
        if "<html" in raw_text.lower() or "<body" in raw_text.lower() or "<div" in raw_text.lower():
            return clean_html_to_text(raw_text)
        return raw_text.strip()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """
    Mengekstraksi teks dari file PDF menggunakan pypdf.
    """
    import pypdf

    reader = pypdf.PdfReader(BytesIO(pdf_bytes))
    extracted_pages = []

    for idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        cleaned = re.sub(r"[ \t]+", " ", page_text).strip()
        if cleaned:
            extracted_pages.append(f"--- Halaman {idx + 1} ---\n{cleaned}")

    if not extracted_pages:
        raise ValueError("PDF tidak mengandung teks yang dapat dibaca (kemungkinan berupa scan gambar).")

    return "\n\n".join(extracted_pages).strip()
