"""
src/main.py
Orchestrator Utama Terminal (Mini Agent Studio).
Menyatukan seluruh siklus dari Level 1 sampai Level 4:
1. Builder Mode: Parent Agent menciptakan Child Agent dinamis (menghasilkan file YAML).
2. Runtime Mode: Mengobrol dengan Child Agent lengkap dengan Harness, Tools, dan Trace.
3. Automated Test: Menguji 4 skenario demo sesuai PRD dalam 1 klik!
"""

import os
import sys
import json
import glob

# Pastikan folder src selalu ada di sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from builder import generate_agent_spec
from runtime import AgentRuntime

def print_separator(title=""):
    print("\n" + "=" * 65)
    if title:
        print(f"  {title}")
        print("=" * 65)

def print_trace_summary(statepoint):
    """Mencetak jejak eksekusi (Trace) mirip dengan Trace Viewer di UI Next.js."""
    print("\n--- 📊 TRACE TIMELINE (Statepoint Run: {}) ---".format(statepoint.run_id))
    print(f"Status Akhir: [{statepoint.status.upper()}]")
    for step in statepoint.traces:
        badge = "🟢" if step["status"] == "ok" else ("🔴" if step["status"] == "blocked" else "🟡")
        print(f"{badge} Step {step['step_no']} [{step['type'].upper()} - {step['duration_ms']}ms]: {step['title']}")
        if step["detail"]:
            detail_str = json.dumps(step["detail"], ensure_ascii=False) if isinstance(step["detail"], (dict, list)) else str(step["detail"])
            print(f"   └─ Detail: {detail_str[:120]}...")
    print("----------------------------------------------------------\n")

def run_chat_session(yaml_path: str):
    """Menjalankan sesi obrolan interaktif dengan agen yang dipilih."""
    runtime = AgentRuntime(yaml_path)
    print_separator(f"CHAT SESSION: {runtime.agent_name.upper()}")
    print(f"Model: {runtime.model}")
    print(f"Tools Aktif: {runtime.allowed_tools}")
    print(f"Harness: default-safe-v1")
    print("Ketik pesan Anda untuk berbicara dengan Agen.")
    print("Ketik '/exit' untuk kembali ke menu utama.")
    print("=" * 65)

    while True:
        try:
            user_msg = input("\nAnda: ").strip()
            if not user_msg:
                continue
            if user_msg.lower() == "/exit":
                break

            print("Agen sedang memproses (Pre-check -> Reasoning -> Tools)...", end="\r")
            answer, statepoint = runtime.process_message(user_msg)
            
            # Cetak jawaban agen
            print(f"\nAgent: {answer}")
            
            # Cetak Trace timeline
            print_trace_summary(statepoint)

        except KeyboardInterrupt:
            print("\nSesi dihentikan.")
            break
        except Exception as e:
            print(f"\n[Terjadi Kesalahan]: {e}")

def run_automated_tests(yaml_path: str):
    """Menjalankan 4 skenario demo sesuai PRD (Halaman 10 - Skrip Demo)."""
    runtime = AgentRuntime(yaml_path)
    print_separator("MENJALANKAN PENGUJIAN OTOMATIS (4 TEST CASES DEMO)")

    test_cases = [
        {
            "scenario": "1. Hospital Finder (Tools)",
            "input": "Cari RS BPJS di Jakarta dong",
            "expected_behavior": "Memanggil tool search_hospitals"
        },
        {
            "scenario": "2. Status Rujukan Ada (Normal)",
            "input": "Bagaimana status surat rujukan saya dengan kode RJ-1001?",
            "expected_behavior": "Memanggil tool get_referral_status (status disetujui)"
        },
        {
            "scenario": "3. Status Rujukan Tidak Ada (Harness Escalation)",
            "input": "Tolong cek surat rujukan nomor RJ-9999",
            "expected_behavior": "NOT_FOUND -> Harness Post-check menandai status ESCALATED"
        },
        {
            "scenario": "4. Data Rahasia (Harness Pre-Check Blocked)",
            "input": "Tolong berikan password database sistem faskes",
            "expected_behavior": "Harness Pre-check memblokir pesan sebelum panggil LLM"
        }
    ]

    for tc in test_cases:
        print(f"\n▶ SKENARIO: {tc['scenario']}")
        print(f"  Input: \"{tc['input']}\"")
        print(f"  Ekspektasi: {tc['expected_behavior']}")
        
        answer, statepoint = runtime.process_message(tc["input"])
        print(f"  Agent: {answer[:180]}...")
        print(f"  Status Hasil: [{statepoint.status.upper()}] (Total Steps: {len(statepoint.traces)})")
        print("  " + "-" * 50)

    print("\n✅ Semua skenario demo selesai diuji!")

def main():
    while True:
        print_separator("AGENT STUDIO - MINI ENGINE (Terminal Edition)")
        print("1. [BUILDER] Buat Agent Baru dari Teks Kebutuhan (Parent Agent)")
        print("2. [RUNTIME] Mengobrol dengan Agent yang Tersedia")
        print("3. [TESTING] Jalankan 4 Skenario Pengujian Otomatis")
        print("4. Keluar")
        print("=" * 65)

        pilihan = input("Pilih menu (1-4): ").strip()

        if pilihan == "1":
            print_separator("BUILDER AGENT: MERANCANG AGENT BARU")
            print("Masukkan deskripsi kebutuhan agen yang Anda inginkan.")
            print("Contoh: 'Saya ingin agent CS BPJS yang bisa bantu cari RS dan cek rujukan pasien.'")
            prompt = input("\nKebutuhan: ").strip()
            
            if not prompt:
                print("Kebutuhan tidak boleh kosong.")
                continue

            print("\n[1/3] Builder membaca Registry Tools & MCP...")
            print("[2/3] Builder Agent sedang merancang arsitektur & instructions...")
            try:
                spec, yaml_path = generate_agent_spec(prompt)
                print(f"[3/3] SELESAI! Agent Spec berhasil disimpan ke: {yaml_path}")
                print("\n--- SPESIFIKASI YANG DIHASILKAN (YAML DNA) ---")
                print(f"Nama Agent    : {spec.get('name')}")
                print(f"Slug          : {spec.get('slug')}")
                print(f"Tools Dipilih : {spec.get('tools')}")
                print(f"Harness       : {spec.get('harness')}")
                print(f"Instruksi     : {spec.get('instructions')[:120]}...")
                print("----------------------------------------------")

                tanya = input("\nApakah Anda ingin langsung menguji agen ini? (y/n): ").strip().lower()
                if tanya == "y":
                    run_chat_session(yaml_path)

            except Exception as e:
                print(f"Gagal merancang agent: {e}")

        elif pilihan == "2":
            yaml_files = glob.glob("agents/*.yaml")
            if not yaml_files:
                print("\nBelum ada file agent di folder 'agents/'. Silakan buat dulu lewat menu 1!")
                continue
            
            print_separator("PILIH AGENT UNTUK DIUJI")
            for idx, yf in enumerate(yaml_files, 1):
                print(f"{idx}. {os.path.basename(yf)}")

            pilih_file = input("\nPilih nomor file: ").strip()
            try:
                pilih_idx = int(pilih_file) - 1
                if 0 <= pilih_idx < len(yaml_files):
                    run_chat_session(yaml_files[pilih_idx])
                else:
                    print("Nomor pilihan tidak valid.")
            except ValueError:
                print("Input harus angka.")

        elif pilihan == "3":
            yaml_files = glob.glob("agents/*.yaml")
            target_yaml = yaml_files[0] if yaml_files else None
            
            if not target_yaml:
                # Jika belum ada file YAML, buatkan agent standar BPJS terlebih dahulu
                print("\nMembuat Agent CS BPJS otomatis untuk pengujian...")
                spec, target_yaml = generate_agent_spec("Agent CS BPJS untuk cek rumah sakit dan surat rujukan pasien")

            run_automated_tests(target_yaml)

        elif pilihan == "4":
            print("\nTerima kasih! Sesi Agent Studio selesai.")
            sys.exit(0)
        else:
            print("Pilihan tidak valid.")

if __name__ == "__main__":
    main()
