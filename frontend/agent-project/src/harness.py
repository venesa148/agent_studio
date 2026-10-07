"""
src/harness.py
Modul Pengaman & Kebijakan (Harness Engine) - default-safe-v1.
Sesuai PRD Halaman 5 (7.4 Harness) & Halaman 10 (13. Harness v1):
1. Pre-check: Memblokir kata kunci rahasia sebelum LLM dipanggil.
2. Anti-Halusinasi: Jawaban berbasis data Tool resmi.
3. Eskalasi: Menandai status 'escalated' jika data tidak ditemukan (NOT_FOUND).
4. Iteration Guard: Maksimal 6 iterasi per run.
"""

import re

# Batas maksimal iterasi agent loop sesuai PRD F-A3
MAX_AGENT_ITERATIONS = 6

# Daftar kata kunci rahasia yang dilarang keras (Pre-check)
FORBIDDEN_KEYWORDS = [
    "password", "kata sandi", "secret", "api key", "apikey",
    "token", "kredensial", "credential", "database", "root password"
]

def harness_pre_check(user_message: str) -> dict:
    """
    Pre-check Harness: Memeriksa pesan pengguna sebelum diteruskan ke LLM.
    Jika mendeteksi permintaan informasi rahasia, langsung tolak (status: blocked).
    """
    msg_lower = user_message.lower()
    
    for kw in FORBIDDEN_KEYWORDS:
        # Deteksi kata utuh atau frasa
        if re.search(r'\b' + re.escape(kw) + r'\b', msg_lower) or kw in msg_lower:
            return {
                "passed": False,
                "status": "blocked",
                "reason": f"Permintaan mengandung kata terlarang '{kw}'",
                "message": (
                    "⛔ AKSES DITOLAK: Permintaan informasi rahasia, kredensial, atau "
                    "akses internal sistem diblokir secara otomatis oleh aturan keamanan "
                    "(Harness default-safe-v1)."
                )
            }
            
    return {
        "passed": True,
        "status": "ok",
        "reason": "Pesan lolos pemeriksaan keamanan pre-check.",
        "message": ""
    }

def harness_post_check(tool_executions: list[dict], agent_answer: str) -> dict:
    """
    Post-check Harness: Memeriksa hasil panggilan tool dan jawaban agen.
    Jika data penting (misal rujukan) menghasilkan NOT_FOUND,
    tandai sesi sebagai 'escalated' dan pastikan user diarahkan ke helpdesk BPJS.
    """
    has_not_found = False
    details = []

    for exec_info in tool_executions:
        result = exec_info.get("result", {})
        if isinstance(result, dict) and result.get("status") == "NOT_FOUND":
            has_not_found = True
            details.append(result.get("message", "Data tidak ditemukan."))

    if has_not_found:
        escalation_note = (
            "\n\n[Sistem BPJS]: Sesuai prosedur keamanan (Harness default-safe-v1), "
            "karena data tidak ditemukan dalam basis data resmi, laporan ini telah ditandai "
            "sebagai 'ESCALATED' untuk ditindaklanjuti oleh staf Customer Care BPJS."
        )
        return {
            "status": "escalated",
            "is_escalated": True,
            "final_answer": agent_answer + escalation_note,
            "details": details
        }

    return {
        "status": "ok",
        "is_escalated": False,
        "final_answer": agent_answer,
        "details": []
    }
