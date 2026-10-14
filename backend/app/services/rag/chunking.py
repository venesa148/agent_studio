"""
Sub-Sistem Chunking:
Recursive Character Chunker untuk memecah teks panjang menjadi potongan-potongan
terukur dengan overlap semantik agar konteks tidak terputus.
"""

from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 600,
    chunk_overlap: int = 80,
) -> List[str]:
    """
    Memecah teks panjang secara rekursif:
    1. Coba pecah berdasarkan batas paragraf ('\\n\\n')
    2. Jika masih terlalu panjang, pecah berdasarkan kalimat ('. ', '\\n')
    3. Jika masih terlalu panjang, pecah berdasarkan spasi kata (' ')
    """
    if not text:
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size

        if end >= text_len:
            chunks.append(text[start:].strip())
            break

        # Cari titik pemisah alami terbaik sebelum batas 'end'
        segment = text[start:end]

        split_pos = -1
        # 1. Coba cari pemisah paragraf
        p_idx = segment.rfind("\n\n")
        if p_idx > chunk_size * 0.4:
            split_pos = p_idx + 2
        else:
            # 2. Coba cari pemisah kalimat (titik diikuti spasi atau newline)
            s_idx = max(segment.rfind(". "), segment.rfind(".\n"), segment.rfind("?\n"), segment.rfind("!\n"))
            if s_idx > chunk_size * 0.4:
                split_pos = s_idx + 2
            else:
                # 3. Coba cari spasi biasa
                w_idx = segment.rfind(" ")
                if w_idx > chunk_size * 0.3:
                    split_pos = w_idx + 1

        if split_pos == -1:
            split_pos = chunk_size

        chunk_content = text[start : start + split_pos].strip()
        if chunk_content:
            chunks.append(chunk_content)

        # Geser start dengan memperhitungkan overlap
        start = start + split_pos - chunk_overlap
        if start < 0 or start >= text_len:
            break

    return [c for c in chunks if c]
