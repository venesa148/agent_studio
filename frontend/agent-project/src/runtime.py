"""
src/runtime.py
Generic Runtime Engine (Mesin Penggerak Agnostik Tanpa Hardcode).
Sesuai PRD Halaman 4 (7.2 Agents dan Runtime) & Halaman 8 (Alur Runtime Loop):
- Menerima konfigurasi agent (Spec YAML) apapun secara dinamis.
- Mengintegrasikan Harness Pre-check dan Post-check.
- Menjalankan ReAct loop (LLM -> tool execution -> LLM, maks 6 iterasi).
- Merekam seluruh jejak langkah (Trace) dan menyimpan snapshot (Statepoint Checkpoint).
"""

import os
import sys
import json
import time
import re
import yaml
from dotenv import load_dotenv
from openai import OpenAI

# Pastikan folder src selalu ada di sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import registry
from harness import harness_pre_check, harness_post_check, MAX_AGENT_ITERATIONS
from statepoint import Statepoint

load_dotenv()

def get_ai_client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY belum diisi di file .env!")
    return OpenAI(
        base_url="https://litellm.pkc.pub/v1",
        api_key=api_key
    )

def clean_reasoning_text(text: str) -> str:
    """Membersihkan monolog batin bahasa Inggris (DeepSeek CoT) jika ada di awal teks."""
    if not text:
        return ""
    # Hapus tag <think>...</think> jika ada
    text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
    
    # Jika ada pola 'We need to... / User asks...' yang dipisah baris ganda
    paragraphs = text.split("\n\n")
    if len(paragraphs) > 1 and ("We need" in paragraphs[0] or "User asks" in paragraphs[0]):
        return "\n\n".join(paragraphs[1:]).strip()
    return text.strip()

class AgentRuntime:
    def __init__(self, spec_yaml_path: str):
        """Memuat DNA Agen secara dinamis dari file YAML (tanpa hardcode)."""
        if not os.path.exists(spec_yaml_path):
            raise FileNotFoundError(f"File spec tidak ditemukan: {spec_yaml_path}")
            
        with open(spec_yaml_path, "r", encoding="utf-8") as f:
            self.spec = yaml.safe_load(f)

        self.agent_name = self.spec.get("name", "Custom Agent")
        self.agent_slug = self.spec.get("slug", "custom-agent")
        self.model = self.spec.get("model", "deepseek-chat")
        self.instructions = self.spec.get("instructions", "Anda adalah asisten AI yang membantu.")
        self.allowed_tools = self.spec.get("tools", [])

        # Inisialisasi Working Memory
        self.messages = [
            {"role": "system", "content": self.instructions}
        ]
        self.client = get_ai_client()

    def process_message(self, user_input: str) -> tuple[str, Statepoint]:
        """
        Siklus Eksekusi Penuh (Pipa Level 2 - 4):
        Pre-check -> Memory -> Tool Calling Loop -> Post-check -> Statepoint
        """
        statepoint = Statepoint(agent_slug=self.agent_slug, user_message=user_input)
        
        # ======================================================================
        # LANGKAH 1: HARNESS PRE-CHECK (Level 3)
        # ======================================================================
        t0 = time.time()
        pre_check = harness_pre_check(user_input)
        pre_duration = int((time.time() - t0) * 1000)

        if not pre_check["passed"]:
            statepoint.add_trace(
                step_type="reasoning",
                title="Harness Pre-Check Terpicu (Pelanggaran Keamanan)",
                detail=pre_check["reason"],
                duration_ms=pre_duration,
                status="blocked"
            )
            statepoint.finalize(pre_check["message"], status="blocked")
            statepoint.save_checkpoint()
            return pre_check["message"], statepoint

        statepoint.add_trace(
            step_type="reasoning",
            title="Harness Pre-Check Lolos",
            detail="Pesan aman dari kebocoran kredensial rahasia.",
            duration_ms=pre_duration,
            status="ok"
        )

        # ======================================================================
        # LANGKAH 2: UPDATE MEMORI & DISCOVERY TOOLS (Level 1 & Level 4)
        # ======================================================================
        self.messages.append({"role": "user", "content": user_input})
        tool_schemas = registry.get_tool_schemas(self.allowed_tools)

        tool_executions = []
        final_text = ""
        iteration = 0

        # ======================================================================
        # LANGKAH 3: AGENT LOOP (Level 2: ReAct Loop, Maks 6 Iterasi)
        # ======================================================================
        while iteration < MAX_AGENT_ITERATIONS:
            iteration += 1
            t_llm_start = time.time()

            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=tool_schemas if tool_schemas else None,
                temperature=0.3
            )
            llm_duration = int((time.time() - t_llm_start) * 1000)

            msg = response.choices[0].message
            
            # KASUS A: Model meminta eksekusi tool (Function Calling)
            if msg.tool_calls:
                self.messages.append(msg) # Tambahkan perintah tool ke memory

                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    statepoint.add_trace(
                        step_type="tool_call",
                        title=f"Panggilan Tool: {fn_name}()",
                        detail=fn_args,
                        duration_ms=llm_duration,
                        status="ok"
                    )

                    # Eksekusi fungsi nyata di registry
                    t_exec = time.time()
                    try:
                        tool_result = registry.execute_tool(fn_name, fn_args)
                    except Exception as err:
                        tool_result = {"status": "ERROR", "error": str(err)}
                    exec_duration = int((time.time() - t_exec) * 1000)

                    statepoint.add_trace(
                        step_type="tool_result",
                        title=f"Hasil Tool: {fn_name}",
                        detail=tool_result,
                        duration_ms=exec_duration,
                        status="ok"
                    )

                    tool_executions.append({
                        "name": fn_name,
                        "args": fn_args,
                        "result": tool_result
                    })

                    # Masukkan hasil tool kembali ke memori agen
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                
                # Lanjutkan loop agar LLM merangkum hasil tool
                continue

            # KASUS B: Model sudah menghasilkan jawaban akhir
            else:
                raw_content = msg.content or ""
                final_text = clean_reasoning_text(raw_content)
                break

        # ======================================================================
        # LANGKAH 4: HARNESS POST-CHECK & ESKALASI (Level 3)
        # ======================================================================
        post_check = harness_post_check(tool_executions, final_text)
        final_answer = post_check["final_answer"]
        final_status = post_check["status"]

        if post_check["is_escalated"]:
            statepoint.add_trace(
                step_type="escalate",
                title="Harness Post-Check: Data Tidak Ditemukan",
                detail=post_check["details"],
                duration_ms=10,
                status="escalated"
            )

        statepoint.add_trace(
            step_type="final",
            title="Post-check Harness & Jawaban Akhir",
            detail="Jawaban tervalidasi dan siap dikirim ke antarmuka pengguna.",
            duration_ms=15,
            status=final_status
        )

        # Update memori dengan jawaban asisten
        self.messages.append({"role": "assistant", "content": final_answer})

        # ======================================================================
        # LANGKAH 5: SIMPAN CHECKPOINT (Level 3 & Persiapan Database)
        # ======================================================================
        statepoint.finalize(final_answer, status=final_status)
        checkpoint_path = statepoint.save_checkpoint()
        
        return final_answer, statepoint
