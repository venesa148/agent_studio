# Agent Studio Backend (FastAPI)

Backend layanan untuk **Agent Studio** yang dibangun menggunakan **FastAPI**, **PostgreSQL** (SQLAlchemy Async), **OpenAI SDK**, **MCP (Model Context Protocol) Client** over SSE, dan **Pydantic v2**.

---

## 📁 Struktur Direktori Backend

```
backend/
├── app/
│   ├── main.py                  # FastAPI Application Entry & CORS Setup
│   ├── core/                    # App Configuration, Async Database Setup, & Security
│   ├── models/                  # SQLAlchemy ORM Models (MCPServer, Tool, AgentSpec, TraceLog)
│   ├── schemas/                 # Pydantic Schemas (Data Validation & DTOs)
│   ├── services/                # Business Logic (MCPClientService, ToolRegistryService, OpenAIAgentService, BuilderService)
│   └── api/                     # REST & SSE Endpoint Controllers (/tools, /mcp, /builder, /agent)
├── tests/                       # Pytest Automated Test Suite
├── .env.example                 # Environment variables template
├── pyproject.toml               # Python project dependencies
├── run.py                       # Uvicorn runner script
└── README.md                    # Dokumentasi lengkap backend
```

---

## ⚙️ Instalasi & Konfigurasi Environment

1. Pastikan Anda menggunakan Python 3.10+ di sistem Anda.
2. Buat file `.env` di dalam folder `backend/` dari `.env.example`:
   ```bash
   cp .env.example .env
   ```
3. Sesuaikan variabel di `.env`:
   ```env
   APP_NAME=AgentStudioBackend
   PORT=8000
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_studio
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_DEFAULT_MODEL=gpt-4o-mini
   REQUIRE_API_KEY=false
   ```
4. Install dependensi Python:
   ```bash
   pip install -e .
   # atau
   pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy asyncpg openai httpx httpx-sse python-dotenv pytest pytest-asyncio aiosqlite
   ```

---

## 🚀 Cara Jalankan Server Backend FastAPI

Jalankan perintah berikut dari folder `backend/`:

```bash
python run.py
```
atau menggunakan uvicorn langsung:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Akses dokumentasi interaktif Swagger UI di:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## 📡 Daftar Endpoint API Utama

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/health` | Health check server status |
| `GET` | `/api/v1/tools` | Ambil seluruh daftar Tools yang terdaftar di catalog |
| `POST` | `/api/v1/tools` | Daftarkan custom / built-in tool baru |
| `GET` | `/api/v1/mcp` | Ambil daftar MCP Servers yang terdaftar |
| `POST` | `/api/v1/mcp` | Daftarkan MCP Server baru & temukan tools via SSE |
| `POST` | `/api/v1/builder/chat` | Buat Agent Specification dari prompt pengguna |
| `POST` | `/api/v1/agent/chat` | Eksekusi percakapan Agent (JSON response) |
| `POST` | `/api/v1/agent/chat/stream` | Eksekusi percakapan Agent (Real-time SSE stream) |
| `GET` | `/api/v1/agent/trace/{run_id}` | Ambil detail log trace & timeline eksekusi step |
| `GET` | `/api/v1/agent/simulations` | Ambil daftar test cases skenario pengujian |

---

## 🧪 Cara Jalankan Pengujian (Testing)

Jalankan suite tes otomatis menggunakan `pytest`:

```bash
pytest -v
```

Suite pengujian mencakup:
* Health check server
* Registrasi Tool catalog & MCP Server discovery
* Generator Agent Spec oleh Builder
* Eksekusi Agent runtime, safety harness blocking, escalation, & trace logs.
