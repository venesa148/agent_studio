import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# 1. Muat Environment Variables dari file .env
load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("ERROR: OPENROUTER_API_KEY belum diisi di file .env!")

client = OpenAI(
    base_url="https://litellm.pkc.pub/v1",
    api_key=api_key,
)

messages = [
    {
        "role": "system",
        "content": (
            "Anda adalah asisten AI resmi bernama AGENT TEST. "
            "ATURAN MUTLAK:\n"
            "1. Selalu berikan jawaban akhir LANGSUNG kepada pengguna dalam Bahasa Indonesia.\n"
            "2. JANGAN PERNAH menampilkan proses berpikir, monolog batin, atau teks bahasa Inggris.\n"
            "3. Bersikap ramah, ringkas, dan selalu ingat konteks percakapan sebelumnya."
        ),
    }
]


print("=" * 60)
print("AGENT TEST - LEVEL 1 RUNTIME (Terminal Edition)")
print("Ketik pesan Anda dan tekan Enter.")
print("Ketik '/debug' untuk melihat isi array memori saat ini.")
print("Ketik '/exit' untuk keluar.")
print("=" * 60)

while True:
    try:
        user_input = input("\nAnda: ").strip()

        # Validasi input kosong
        if not user_input:
            continue

        # Perintah keluar
        if user_input.lower() == "/exit":
            print("Keluar dari sesi.")
            break

        # Fitur Edukasi: Introspeksi Memori
        if user_input.lower() == "/debug":
            print("\n--- [DEBUG: ISI MEMORY SAAT INI] ---")
            print(json.dumps(messages, indent=2, ensure_ascii=False))
            print("------------------------------------\n")
            continue

        # ==========================================================
        # LANGKAH A: UPDATE MEMORI DENGAN INPUT PENGGUNA
        # ==========================================================
        messages.append({"role": "user", "content": user_input})

        print("Agen sedang berpikir...", end="\r")

        # ==========================================================
        # LANGKAH B: KIRIM SELURUH MEMORI KE MODEL (OpenRouter)
        # ==========================================================
        # Anda bisa mengganti model ke model gratis/murah seperti:
        # "openai/gpt-4o-mini" atau "meta-llama/llama-3.1-8b-instruct:free"
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
        )

        agent_reply = response.choices[0].message.content

        # ==========================================================
        # LANGKAH C: UPDATE MEMORI DENGAN JAWABAN AGEN
        # ==========================================================
        messages.append({"role": "assistant", "content": agent_reply})

        print(f"Agent: {agent_reply}")

    except KeyboardInterrupt:
        print("\nSesi dihentikan.")
        break
    except Exception as e:
        print(f"\n[Terjadi Kesalahan]: {e}")
