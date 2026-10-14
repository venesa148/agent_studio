"""
Native Python Executor: Eksekutor terisolasi untuk fungsi-fungsi deterministik
dan algoritma lokal Python murni (seperti kalkulator aman berbasis AST,
triase klinis, dan live web search).
"""

import ast
import operator
import re
from typing import Any, Callable, Dict, Optional


class NativePythonExecutor:
    """
    Eksekutor untuk tool berbasis algoritma lokal Python.
    Menggunakan dictionary dispatcher, bukan ratusan baris if-elif.
    """

    @classmethod
    def can_handle(cls, tool_name: str) -> bool:
        return tool_name in cls._HANDLERS

    @classmethod
    async def execute(cls, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        handler = cls._HANDLERS.get(tool_name)
        if not handler:
            return {
                "status": "error",
                "message": f"Handler native Python untuk tool '{tool_name}' tidak terdaftar.",
            }
        return await handler(params)

    # =========================================================================
    # HANDLER 1: CALCULATOR (Aman dari Arbitrary Code Execution via AST)
    # =========================================================================
    @staticmethod
    async def _execute_calculator(params: Dict[str, Any]) -> Dict[str, Any]:
        expr = str(params.get("expression") or params.get("expr") or "").strip()
        if not expr:
            return {"status": "error", "message": "Parameter 'expression' tidak boleh kosong."}

        allowed_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.Mod: operator.mod,
        }

        def _eval_node(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            elif isinstance(node, ast.BinOp) and type(node.op) in allowed_operators:
                return allowed_operators[type(node.op)](_eval_node(node.left), _eval_node(node.right))
            elif isinstance(node, ast.UnaryOp) and type(node.op) in allowed_operators:
                return allowed_operators[type(node.op)](_eval_node(node.operand))
            raise ValueError("Ekspresi matematika mengandung operator atau sintaks yang tidak diizinkan.")

        try:
            parsed = ast.parse(expr, mode="eval")
            calc_val = _eval_node(parsed.body)
            return {
                "status": "ok",
                "expression": expr,
                "result": calc_val,
                "_source": "Core Math Engine",
                "_endpoint": "internal://calculator",
            }
        except Exception as exc:
            return {
                "status": "error",
                "expression": expr,
                "message": f"Gagal mengevaluasi ekspresi matematika: {str(exc)}",
            }

    # =========================================================================
    # HANDLER 2: SEARCH WEB (DuckDuckGo Search)
    # =========================================================================
    @staticmethod
    async def _execute_search_web(params: Dict[str, Any]) -> Dict[str, Any]:
        query = str(params.get("query") or params.get("q") or "").strip()
        if not query:
            return {"status": "error", "message": "Parameter 'query' pencarian tidak boleh kosong."}

        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, region="id-id", max_results=4))
                if not raw_results:
                    raw_results = list(ddgs.text(query, region="wt-wt", max_results=4))
            if raw_results:
                formatted_results = [
                    {
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", ""),
                    }
                    for r in raw_results
                ]
                return {
                    "status": "ok",
                    "query": query,
                    "_source": "DuckDuckGo Live Web Search",
                    "_endpoint": "https://duckduckgo.com",
                    "count": len(formatted_results),
                    "results": formatted_results,
                }
        except Exception as exc:
            return {
                "status": "error",
                "error_type": "SEARCH_FAILED",
                "_source": "Web Search Provider",
                "query": query,
                "message": f"Layanan pencarian web sedang tidak dapat memuat hasil: {str(exc)}",
            }

        return {
            "status": "error",
            "error_type": "NO_RESULTS",
            "query": query,
            "message": f"Tidak ditemukan hasil pencarian untuk kueri '{query}'.",
        }

    # =========================================================================
    # HANDLER 3: CLASSIFY COMPLAINT (Clinical Triage Protocol)
    # =========================================================================
    @staticmethod
    async def _execute_classify_complaint(params: Dict[str, Any]) -> Dict[str, Any]:
        complaint = str(params.get("complaint") or params.get("keluhan") or "").strip()
        if not complaint:
            return {"status": "error", "message": "Parameter 'complaint' tidak boleh kosong."}

        complaint_lower = complaint.lower()
        red_flags = [
            "pingsan", "sesak nafas", "nyeri dada hebat", "darurat", "kejang",
            "tidak sadar", "pendarahan hebat", "stroke", "lumpuh", "koma"
        ]
        matched_red_flags = [rf for rf in red_flags if rf in complaint_lower]

        if matched_red_flags:
            return {
                "status": "ok",
                "triage_class": "EMERGENCY",
                "red_flag": True,
                "matched_red_flags": matched_red_flags,
                "candidate_service": ["IGD / Instalasi Gawat Darurat"],
                "action": "ESCALATE_TO_EMERGENCY",
                "_source": "Clinical Triage Protocol",
                "message": (
                    "Terdeteksi indikasi gawat darurat (Red Flag). Alur booking dokter reguler dihentikan. "
                    "Segera arahkan pasien ke IGD rumah sakit terdekat atau hubungi 119."
                ),
            }

        # Non-darurat: Mapping kandidat poliklinik
        poli_candidates = ["Poli Umum FKTP"]
        if any(w in complaint_lower for w in ["mata", "kabur", "minus", "silinder"]):
            poli_candidates = ["Poli Mata"]
        elif any(w in complaint_lower for w in ["gigi", "gusi", "cabut gigi"]):
            poli_candidates = ["Poli Gigi & Mulut"]
        elif any(w in complaint_lower for w in ["anak", "balita", "imunisasi"]):
            poli_candidates = ["Poli Anak (Sp.A)"]
        elif any(w in complaint_lower for w in ["jantung", "dada berdebar"]):
            poli_candidates = ["Poli Jantung (Sp.JP)"]
        elif any(w in complaint_lower for w in ["tulang", "patah", "sendi", "retak"]):
            poli_candidates = ["Poli Orthopaedi & Traumatologi"]
        elif any(w in complaint_lower for w in ["perut", "maag", "lambung", "mual", "pusing"]):
            poli_candidates = ["Poli Penyakit Dalam (Sp.PD)"]

        return {
            "status": "ok",
            "triage_class": "NEED_FURTHER_CARE",
            "red_flag": False,
            "candidate_service": poli_candidates,
            "action": "PROCEED_TO_CLINIC_REFERRAL",
            "_source": "Clinical Triage Protocol",
            "message": f"Keluhan stabil tanpa indikasi red flag. Direkomendasikan rujukan berjenjang ke {poli_candidates[0]}.",
        }

    # Registry Dispatcher
    _HANDLERS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
        "calculator": _execute_calculator,
        "math_eval": _execute_calculator,
        "search_web": _execute_search_web,
        "classify_complaint": _execute_classify_complaint,
    }
