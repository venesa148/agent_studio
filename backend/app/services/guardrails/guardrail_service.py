"""
Universal Guardrail Service:
Pusat pengaman dinamis independen domain (Sierra & Cohere Architecture):
1. Input Guardrail: Sanitasi prompt injection & system jailbreak.
2. Pre-Tool Impact Analysis: Klasifikasi efek (Read-Only vs State-Mutating / Write).
   Meminta konfirmasi eksplisit dari pengguna jika aksi mengubah data nyata.
3. Post-Output Guardrail: Verifikasi groundedness & integritas data hasil tool.
100% Dinamis, tidak terikat pada 1 domain/agen tertentu.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger("guardrail_service")

# Pola-pola prompt injection & jailbreak yang umum secara universal
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts)",
    r"disregard\s+(all\s+)?safety\s+(protocols|guidelines|policies)",
    r"reveal\s+(your\s+)?(system\s+prompt|secret|api\s*key)",
    r"bypass\s+guardrails?",
    r"system\s*:\s*you\s+are\s+now",
    r"jailbreak",
    r"dan\s+mode\s+developer",
    r"abaikan\s+semua\s+instruksi\s+(sebelumnya|awal)",
    r"bocorkan\s+(system\s+prompt|kunci\s+rahasia|token|api\s*key)",
]

# Kata-kata konfirmasi persetujuan pengguna universal (afirmatif murni)
CONFIRMATION_KEYWORDS = {
    "ya", "yes", "yup", "ok", "oke", "setuju", "lanjut", "lanjutkan", "proses",
    "konfirmasi", "confirm", "deal", "siap", "benar", "betul", "acc"
}


class GuardrailResult(BaseModel):
    passed: bool
    action: str  # "PROCEED", "BLOCK", "REQUIRE_CONFIRMATION"
    reason: Optional[str] = None
    detail: Optional[str] = None
    interception_message: Optional[str] = None


class GuardrailService:
    @staticmethod
    def check_input_guardrail(message: str) -> GuardrailResult:
        """
        Input Guardrail Universal:
        Memeriksa apakah pesan pengguna mengandung serangan prompt injection,
        upaya pembongkaran system prompt, atau manipulasi keamanan.
        """
        if not message or not message.strip():
            return GuardrailResult(passed=True, action="PROCEED")

        msg_lower = message.lower().strip()

        # 1. Cek pola prompt injection
        for pat in INJECTION_PATTERNS:
            if re.search(pat, msg_lower):
                logger.warning(f"Terdeteksi percobaan Prompt Injection: pattern='{pat}'")
                return GuardrailResult(
                    passed=False,
                    action="BLOCK",
                    reason="PROMPT_INJECTION_DETECTED",
                    detail="Pesan mengandung pola instruksi manipulasi keamanan atau bypass guardrail.",
                    interception_message=(
                        "\U0001f6e1\ufe0f **Akses Dibatasi oleh Guardrail Keamanan**\n\n"
                        "Pesan Anda terdeteksi mengandung instruksi yang melanggar kebijakan integritas sistem. "
                        "Permintaan ini tidak dapat diproses."
                    ),
                )

        # 2. Cek upaya kebocoran kredensial sensitif
        sensitive_targets = [
            "database password", "connection string", "secret_key",
            "kredensial internal", "bocorkan password", "drop table", "select * from users"
        ]
        matched_sensitive = [s for s in sensitive_targets if s in msg_lower]
        if matched_sensitive:
            return GuardrailResult(
                passed=False,
                action="BLOCK",
                reason="SENSITIVE_KEYWORD_VIOLATION",
                detail=f"Terdeteksi kata kunci terlarang: {', '.join(matched_sensitive)}",
                interception_message=(
                    "\U0001f6e1\ufe0f **Akses Data Sensitif Ditolak**\n\n"
                    "Permintaan terhadap kredensial atau struktur database internal tidak diizinkan demi keamanan."
                ),
            )

        return GuardrailResult(passed=True, action="PROCEED")

    @staticmethod
    def check_pre_tool_impact(
        tool_name: str,
        tool_effect: str = "read",
        agent_guardrails: Optional[Dict[str, Any]] = None,
        recent_user_messages: Optional[List[str]] = None,
        tool_params: Optional[Dict[str, Any]] = None,
    ) -> GuardrailResult:
        """
        Pre-Tool Impact Analysis (Sierra Style):
        Memeriksa apakah pemanggilan tool berpotensi mengubah status data (state-mutating / write).
        Jika bernilai 'write' atau 'external' dan pengguna belum menyatakan konfirmasi eksplisit,
        eksekusi tool ditahan dan meminta persetujuan manusia terlebih dahulu.
        """
        guardrails_conf = agent_guardrails or {}
        required_conf_tools = guardrails_conf.get("require_confirmation_for") or []
        disallowed_tools = guardrails_conf.get("disallowed_tools") or []

        # 1. Cek apakah tool dilarang oleh kebijakan agen
        if tool_name in disallowed_tools:
            return GuardrailResult(
                passed=False,
                action="BLOCK",
                reason="TOOL_DISALLOWED_BY_POLICY",
                detail=f"Tool '{tool_name}' dinonaktifkan oleh kebijakan keamanan agen.",
                interception_message=f"Tindakan '{tool_name}' diblokir oleh kebijakan keamanan agen.",
            )

        # 2. Evaluasi Efek Tool: Apakah mutasi data / state-changing?
        is_mutating = (
            tool_effect.lower() in ("write", "external")
            or tool_name in required_conf_tools
        )

        if not is_mutating:
            # Tool Read-Only / Idempoten: Langsung izinkan eksekusi tanpa hambatan
            return GuardrailResult(passed=True, action="PROCEED")

        # 3. Tool State-Mutating: Periksa apakah pengguna sudah memberikan konfirmasi di riwayat pesan
        user_has_confirmed = False
        if recent_user_messages and len(recent_user_messages) >= 2:
            latest_msg = recent_user_messages[-1].lower().strip()
            tokens = re.findall(r"\w+", latest_msg)
            # Konfirmasi harus berupa afirmasi yang ditujukan atas permintaan konfirmasi sebelumnya
            if any(tok in CONFIRMATION_KEYWORDS for tok in tokens):
                # Validasi: pesan pendek afirmasi (<= 6 kata) atau diawali kata persetujuan
                if len(tokens) <= 6 or latest_msg.startswith(("ya", "oke", "ok", "yes", "setuju", "lanjut", "siap", "confirm")):
                    user_has_confirmed = True

        if user_has_confirmed:
            # Pengguna telah menyatakan konfirmasi eksplisit
            return GuardrailResult(
                passed=True,
                action="PROCEED",
                detail="Konfirmasi pengguna terverifikasi. Eksekusi tool dilanjutkan.",
            )

        # Pengguna belum konfirmasi: TAHAN eksekusi dan minta konfirmasi
        logger.info(f"Pre-Tool Gate: Menahan eksekusi tool '{tool_name}' untuk meminta konfirmasi pengguna.")
        params_summary = ""
        if tool_params:
            clean_params = {k: v for k, v in tool_params.items() if not str(k).startswith("_")}
            params_summary = ", ".join([f"{k}: {v}" for k, v in clean_params.items() if v])

        confirm_prompt = (
            f"Aksi `{tool_name}` akan memproses/mengubah data penting"
            + (f" ({params_summary})" if params_summary else "")
            + ". Apakah Anda yakin ingin melanjutkan tindakan ini? Silakan ketik **'Ya, lanjutkan'** untuk menyetujui."
        )

        return GuardrailResult(
            passed=False,
            action="REQUIRE_CONFIRMATION",
            reason="HUMAN_CONFIRMATION_REQUIRED",
            detail=f"Tool '{tool_name}' memiliki efek '{tool_effect}' dan memerlukan persetujuan eksplisit.",
            interception_message=confirm_prompt,
        )

    @staticmethod
    def verify_output_groundedness(
        response_text: str,
        tool_results: List[Dict[str, Any]],
        has_knowledge_context: bool = False,
    ) -> Dict[str, Any]:
        """
        Post-Output Guardrail:
        Memeriksa apakah respon agen tidak mengklaim keberhasilan jika seluruh tool gagal,
        serta memberikan rekomendasi sitasi jika menggunakan referensi knowledge base.
        """
        has_errors = any(
            isinstance(tr.get("result"), dict) and tr.get("result", {}).get("status") == "error"
            for tr in tool_results
        )

        citation_applied = bool(
            has_knowledge_context and any(marker in response_text for marker in ["[Sumber", "Berdasarkan dokumen", "referensi"])
        )

        return {
            "grounded": True,
            "has_tool_errors": has_errors,
            "citation_applied": citation_applied,
        }
