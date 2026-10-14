import asyncio
import json
import sys
from app.core.db import AsyncSessionLocal
from app.core.config import settings
from openai import AsyncOpenAI
from sqlalchemy import select
from app.models.tool import ToolModel

# Force UTF-8 on Windows stdout
sys.stdout.reconfigure(encoding='utf-8')

async def run_and_capture():
    client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL, max_retries=0)
    model = settings.LLM_MODEL

    async with AsyncSessionLocal() as db:
        # Load tools
        db_tools_res = await db.execute(select(ToolModel).where(ToolModel.is_active == True))
        db_tools = db_tools_res.scalars().all()
        tools_info_list = []
        for t in db_tools:
            src_label = f"[{t.source_type.upper()}]" if t.source_type else "[TOOL]"
            tools_info_list.append(f"{t.name} ({src_label}: {t.description or 'No description'})")
        tools_info = "\n".join([f"- {item}" for item in tools_info_list]) if tools_info_list else "Belum ada tools aktif di database."

        # Turn 1
        turn1_user = "Halo, saya ingin membuat asisten toko online untuk mengecek resi pengiriman dan status paket pelanggan."
        
        system_msg_t1 = (
            "Anda adalah 'Builder Agent & Tool Architect' di Agent Studio, mengacu pada standar resmi SKILL.md (agent-builder-cek-12-poin).\n"
            "Tugas Anda: Mewawancarai pengguna non-teknis lewat percakapan interaktif, mengekstrak 12 Poin Kelengkapan secara DINAMIS (untuk industri/topik apa pun: toko online, helpdesk, HRD, klinik, akuntansi, dll), dan merancang spesifikasi agent serta draf tool.\n\n"
            "ATURAN KERAS (STANDAR SKILL.MD):\n"
            "1. PLATFORM UNIVERSAL (DINAMIS):\n"
            "   - Anda BUKAN bot khusus kesehatan/BPJS. Anda melayani pembuatan agent untuk domain apa pun yang diminta pengguna.\n"
            "   - Dilarang berasumsi atau memaksakan topik kesehatan/BPJS jika pengguna tidak memintanya.\n\n"
            "2. TEKNIK WAWANCARA (ECHO-BACK & MAKSIMAL 2 PERTANYAAN):\n"
            "   - Di awal respon 'message', lakukan echo-back singkat: rangkum poin yang sudah dipahami dari jawaban pengguna.\n"
            "   - Ajukan MAKSIMAL 1–2 pertanyaan per giliran untuk menggali poin yang masih kosong.\n"
            "   - Urutan prioritas pertanyaan (utamakan yang paling menentukan): C4 (Tindakan boleh/mutasi data) -> C3 (Sumber data/API) -> C5 (Larangan/batas topik) -> C1 (Tujuan utama) -> C6 (Jika data kosong/gagal) -> C12 (Dokumen acuan) -> C8 (Batas pemakaian) -> C9 (Data sensitif) -> C7 (Gaya jawaban) -> C10 (Serah ke manusia) -> C2 (Target pengguna) -> C11 (Contoh percakapan benar).\n"
            "   - Jika pengguna berkata 'langsung bangun saja' atau 'terserah', tolak dengan sopan dan jelaskan bahwa poin krusial (seperti izin aksi mutasi data atau sumber API) tetap membutuhkan konfirmasinya.\n\n"
            "3. PERANCANGAN TOOL (KATALOG VS TOOL FACTORY):\n"
            "   A. KATALOG TERSEDIA:\n"
            f"      Tool aktif saat ini:\n{tools_info}\n"
            "      Jika kebutuhan pengguna cocok dengan tool di atas, masukkan namanya ke 'spec.tools'.\n"
            "   B. TOOL FACTORY (JIKA PENGGUNA MEMBERIKAN API / ENDPOINT / SISTEM BARU):\n"
            "      Jika pengguna menyebutkan URL API, endpoint web (contoh: https://.../api/..., method GET/POST), rancang tool baru di array 'new_tools':\n"
            "      - name: nama tool (snake_case, contoh: check_order_status, book_slot)\n"
            "      - description: penjelasan kapan tool ini dipanggil oleh model AI (minimal 40 karakter)\n"
            "      - input_schema: format JSON Schema lengkap (properties, type, required)\n"
            "      - implementation: konfigurasi privat untuk Runner/Executor:\n"
            "        * type: \"http\"\n"
            "        * url: URL endpoint lengkap\n"
            "        * method: \"GET\" | \"POST\" | \"PUT\" | \"DELETE\"\n"
            "      - effect: \"read\" (hanya membaca data) atau \"write\" (mengubah/menambah data)\n"
            "      - status: \"draft\"\n"
            "      - source_ids: [\"L-001\"]\n\n"
            "4. ATURAN COMMIT ('should_commit'):\n"
            "   - Set 'should_commit': true HANYA jika pengguna menyatakan eksplisit setuju menyimpan ('simpan', 'terapkan', 'oke bangun sekarang', 'apply').\n"
            "   - Selama masih dalam proses tanya jawab atau klarifikasi, selalu set 'should_commit': false.\n\n"
            "FORMAT BALASAN (Wajib JSON valid di dalam blok ```json ... ```):\n"
            "{\n"
            '  "message": "Kalimat percakapan ramah (echo-back rangkuman singkat + maks 2 pertanyaan terarah berikutnya)",\n'
            '  "spec_updated": true,\n'
            '  "should_commit": false,\n'
            '  "spec": {\n'
            '    "name": "Nama Agent",\n'
            '    "description": "Tugas utama agent (C1)",\n'
            '    "instructions": "System prompt lengkap (Peran, SOP, Gaya Bahasa C7, Fallback C6, Batasan C5)",\n'
            '    "tools": ["nama_tool"]\n'
            '  },\n'
            '  "new_tools": [],\n'
            '  "coverage": {\n'
            '    "C1": "terisi",\n'
            '    "C2": "kosong",\n'
            '    "C3": "kosong",\n'
            '    "C4": "kosong",\n'
            '    "C5": "kosong",\n'
            '    "C6": "kosong",\n'
            '    "C7": "terisi",\n'
            '    "C8": "kosong",\n'
            '    "C9": "kosong",\n'
            '    "C10": "kosong",\n'
            '    "C11": "kosong",\n'
            '    "C12": "kosong"\n'
            '  }\n'
            "}\n\n"
            "Spesifikasi saat ini: Belum ada spesifikasi awal.\n"
        )

        messages_t1 = [
            {"role": "system", "content": system_msg_t1},
            {"role": "user", "content": turn1_user}
        ]

        print("=== [TURN 1] CALLING LLM ===")
        comp1 = await client.chat.completions.create(
            model=model,
            messages=messages_t1,
            temperature=0.2,
            max_tokens=2500,
            timeout=35.0
        )
        raw_res1 = comp1.choices[0].message.content or ""
        with open("scratch/raw_run_turn1.txt", "w", encoding="utf-8") as f:
            f.write(raw_res1)
        print("Turn 1 raw response written successfully.")
        print(raw_res1[:300] + "...")

        # Turn 2
        # Parse Turn 1 to get spec
        import re
        match1 = re.search(r"```json\s*(.*?)\s*```", raw_res1, re.DOTALL)
        if not match1:
            match1 = re.search(r"({.*})", raw_res1, re.DOTALL)
        parsed1 = json.loads(match1.group(1).strip() if match1 else "{}")
        t1_message = parsed1.get("message", "")
        t1_spec = parsed1.get("spec", {})

        turn2_user = (
            "Hanya boleh membaca status paket saja, jangan ubah apa-apa. "
            "Datanya ambil dari API toko saya di https://api.tokoonline.com/v1/tracking/{tracking_no} dengan method GET."
        )

        system_msg_t2 = system_msg_t1.replace("Spesifikasi saat ini: Belum ada spesifikasi awal.", f"Spesifikasi saat ini: {json.dumps(t1_spec)}")
        messages_t2 = [
            {"role": "system", "content": system_msg_t2},
            {"role": "user", "content": turn1_user},
            {"role": "assistant", "content": t1_message[:500]},
            {"role": "user", "content": turn2_user}
        ]

        print("\n=== [TURN 2] CALLING LLM ===")
        comp2 = await client.chat.completions.create(
            model=model,
            messages=messages_t2,
            temperature=0.2,
            max_tokens=2500,
            timeout=35.0
        )
        raw_res2 = comp2.choices[0].message.content or ""
        with open("scratch/raw_run_turn2.txt", "w", encoding="utf-8") as f:
            f.write(raw_res2)
        print("Turn 2 raw response written successfully.")
        print(raw_res2[:300] + "...")

        # Also write the full payload info for report
        payload_meta = {
            "model": model,
            "base_url": settings.LLM_BASE_URL,
            "temperature": 0.2,
            "max_tokens": 2500,
            "timeout": 35.0,
            "turn1_request_messages": messages_t1,
            "turn2_request_messages": messages_t2
        }
        with open("scratch/raw_run_meta.json", "w", encoding="utf-8") as f:
            json.dump(payload_meta, f, indent=2, ensure_ascii=False)
        print("Payload metadata written successfully.")

if __name__ == "__main__":
    asyncio.run(run_and_capture())
