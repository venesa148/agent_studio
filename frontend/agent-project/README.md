# Agent Studio - Mini Engine (Python Prototype)

Modul mandiri untuk menjalankan siklus hidup AI Agent (Builder, Runtime, Harness, dan Automated Testing) berbasis YAML Declarative.

---

## 🚀 Panduan Menjalankan di Komputer Teman

### 1. Masuk ke Folder `agent-project`
```bash
cd agent-project
```

### 2. Buat Virtual Environment Baru
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Seluruh Dependensi
```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment Variable
Salin file `.env.example` menjadi `.env`:
```bash
# Windows (PowerShell / Command Prompt)
copy .env.example .env

# macOS / Linux
cp .env.example .env
```
Buka file `.env` dan masukkan API Key:
```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxx
```

### 5. Jalankan Aplikasi
```bash
python src/main.py
```
Pilih opsi:
- **Menu 1:** Merancang Agent baru dari teks kebutuhan (Builder Parent Agent $\rightarrow$ menghasilkan `.yaml`).
- **Menu 2:** Chat interaktif dengan Agent yang sudah dibuat.
- **Menu 3:** Menjalankan 4 Skenario Pengujian Otomatis sesuai PRD BPJS (Hospital Finder, Rujukan Normal, Eskalasi `RJ-9999`, dan Keamanan `blocked`).
