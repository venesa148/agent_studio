"""
src/builder.py
Parent Agent / Builder Agent.
Sesuai PRD Halaman 3 (7.1 Build):
- Membaca Registry (daftar capability yang tersedia).
- Menerima kebutuhan pengguna dalam bahasa natural.
- Menghasilkan konfigurasi spec Agent lengkap secara dinamis (tanpa hardcode).
- Menyimpan hasil ke file YAML deklaratif: agents/<slug>.yaml.
"""

import os
import sys
import json
import re
import yaml
from dotenv import load_dotenv
from openai import OpenAI

# Pastikan folder src selalu ada di sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import registry

load_dotenv()

def get_ai_client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY belum diisi di file .env!")
    return OpenAI(
        base_url="https://litellm.pkc.pub/v1",
        api_key=api_key
    )

def generate_agent_spec(user_requirement: str, output_dir: str = "agents") -> tuple[dict, str]:
    """
    Builder Agent (Parent): Membaca Registry dan merakit Child Agent Spec
    berdasarkan prompt kebutuhan pengguna.
    """
    client = get_ai_client()
    
    # 1. Builder membaca semua kemampuan yang aktif di Registry
    available_capabilities = registry.list_capabilities()
    capabilities_text = json.dumps(available_capabilities, indent=2, ensure_ascii=False)

    # 2. Instruksi ketat untuk Builder Agent
    builder_system_prompt = (
        "Anda adalah Builder Agent di platform Agent Studio. "
        "Tugas Anda adalah merancang spesifikasi konfigurasi (Agent Spec) untuk sebuah AI Agent baru "
        "berdasarkan kebutuhan yang diberikan oleh pengguna dan daftar capabilities yang tersedia di Registry.\n\n"
        f"DAFTAR CAPABILITY DI REGISTRY:\n{capabilities_text}\n\n"
        "ATURAN PERANCANGAN:\n"
        "1. Hanya pilih tool yang BENAR-BENAR ADA di Registry di atas. Dilarang mengarang nama tool.\n"
        "2. Buat instruksi (System Prompt) yang jelas, sopan, dan berorientasi membantu pasien/pengguna.\n"
        "3. Keluaran HARUS berupa objek JSON MURNI tanpa markdown (```json), tanpa monolog batin, "
        "dan tanpa teks pembuka/penutup.\n\n"
        "SKEMA JSON YANG DIHARUSKAN:\n"
        "{\n"
        '  "name": "Nama lengkap agent (3-80 karakter)",\n'
        '  "slug": "nama-agent-kebab-case",\n'
        '  "description": "Deskripsi singkat fungsi agent",\n'
        '  "instructions": "System prompt lengkap untuk membimbing perilaku agen",\n'
        '  "model": "deepseek-chat",\n'
        '  "tools": ["nama_tool_1", "nama_tool_2"],\n'
        '  "harness": "default-safe-v1"\n'
        "}"
    )

    messages = [
        {"role": "system", "content": builder_system_prompt},
        {"role": "user", "content": f"Rancang agent untuk kebutuhan berikut: {user_requirement}"}
    ]

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.3
    )

    raw_output = response.choices[0].message.content.strip()

    # Ekstraksi blok JSON jika model membungkus dengan markdown atau reasoning
    json_match = re.search(r'\{[\s\S]*\}', raw_output)
    if json_match:
        clean_json_str = json_match.group(0)
    else:
        clean_json_str = raw_output

    try:
        spec = json.loads(clean_json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gagal mem-parsing spec dari Builder Agent: {e}\nRaw: {raw_output}")

    # Validasi: Pastikan tool yang dipilih ada di Registry
    valid_tools = [t for t in spec.get("tools", []) if t in registry.REGISTRY]
    spec["tools"] = valid_tools

    # 3. Simpan hasil spec ke berkas YAML deklaratif
    os.makedirs(output_dir, exist_ok=True)
    slug = spec.get("slug", "custom-agent")
    yaml_filepath = os.path.join(output_dir, f"{slug}.yaml")

    with open(yaml_filepath, "w", encoding="utf-8") as f:
        yaml.dump(spec, f, sort_keys=False, allow_unicode=True)

    return spec, yaml_filepath
