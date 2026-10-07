"""
src/statepoint.py
Modul Audit & Checkpoint (Statepoint & Trace Engine).
Sesuai PRD Halaman 5 (7.5 Trace dan Runs) & Halaman 8 (Model data traces):
- Menyimpan timeline per run dengan durasi tiap langkah (reasoning, tool_call, tool_result, escalate, final).
- Menyimpan snapshot sesi (Checkpoint) ke file JSON lokal yang siap dimigrasi ke PostgreSQL.
"""

import os
import json
import time
import uuid

class Statepoint:
    def __init__(self, agent_slug: str, user_message: str):
        self.run_id = f"run-{uuid.uuid4().hex[:6]}"
        self.agent_slug = agent_slug
        self.user_message = user_message
        self.final_answer = ""
        self.status = "ok"  # "ok" | "escalated" | "blocked" | "error"
        self.traces = []
        self.start_time = time.time()
        self.step_counter = 0

    def add_trace(self, step_type: str, title: str, detail: any, duration_ms: int = 0, status: str = "ok"):
        """
        Merekam satu langkah eksekusi ke dalam riwayat Trace.
        Type sesuai PRD: 'reasoning' | 'tool_call' | 'tool_result' | 'escalate' | 'final'
        """
        self.step_counter += 1
        trace_step = {
            "step_no": self.step_counter,
            "type": step_type,
            "title": title,
            "duration_ms": duration_ms,
            "detail": detail,
            "status": status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.traces.append(trace_step)
        return trace_step

    def finalize(self, final_answer: str, status: str = "ok"):
        """Menutup sesi run dan menghitung total durasi."""
        self.final_answer = final_answer
        self.status = status
        total_duration = int((time.time() - self.start_time) * 1000)
        return total_duration

    def to_dict(self) -> dict:
        """Mengonversi snapshot Statepoint ke format kamus Python."""
        return {
            "run_id": self.run_id,
            "agent_slug": self.agent_slug,
            "user_message": self.user_message,
            "final_answer": self.final_answer,
            "status": self.status,
            "trace_count": len(self.traces),
            "traces": self.traces
        }

    def save_checkpoint(self, output_dir: str = "checkpoints") -> str:
        """
        Menyimpan snapshot sesi saat ini ke berkas JSON (Checkpoint).
        Nantinya data inilah yang langsung di-INSERT ke tabel 'agent_runs' dan 'traces' PostgreSQL.
        """
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"statepoint_{self.run_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath
