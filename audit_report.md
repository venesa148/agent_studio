# Agent Studio Audit Report

## 1. Executive Summary

Proyek **Agent Studio** memiliki fondasi yang sangat baik dalam mencapai tujuannya untuk memungkinkan orang awam membuat AI Agent. Implementasi *Conversational Co-pilot* (Builder Agent) berhasil menyembunyikan kompleksitas teknis (seperti pembuatan prompt yang panjang dan pemilihan tools) di balik antarmuka chat. Namun, masih terdapat celah keamanan kritis dan penggunaan istilah teknis yang dapat membingungkan pengguna awam.

**Rating:**
* Functionality: 8/10
* UX: 7/10
* Reliability: 8/10
* Backend: 8/10
* Database: 8/10
* Security: 3/10
* **Overall: 7/10**

---

## 2. Project Architecture

Arsitektur aplikasi terkonfirmasi berjalan sesuai struktur berikut:

`User → Next.js Frontend (Port 3000) → FastAPI Backend (Port 8080) → TiDB Cloud MySQL → OpenRouter (LLM: glm-5.3)`

Komponen yang ditemukan & divalidasi:
* **Frontend**: Next.js 14, Tailwind CSS, Lucide Icons. Menyediakan layout chat split-pane (Builder & Test).
* **Backend**: FastAPI dengan arsitektur services (`AgentService`, `BuilderService`, `ToolRegistryService`).
* **Database**: TiDB (MySQL) via `aiomysql` dan SQLAlchemy (Async).
* **AI/Agent Integration**: LLM digunakan di dua tempat: 1) Menyusun spesifikasi (Builder), 2) Menjalankan agen (Chat).

---

## 3. User Flow Audit

Flow aktual:
1. **Initial Load** - Masuk ke halaman utama (Builder Pane). [GOOD]
2. **Create Agent** - Pengguna mengetik kebutuhan. LLM mengenerate draf *System Prompt* dan memilih tools secara otomatis dari DB. [GOOD]
3. **Configure & Preview** - Draf ditampilkan di UI Card. [NEED IMPROVEMENT] (Banyak istilah teknis)
4. **Save Agent** - Pengguna klik "Terapkan & Simpan ke DB" atau meminta agen menyimpannya (should_commit=true). [GOOD]
5. **Test Agent** - Pengguna mencoba agent di panel kanan. History tersimpan di DB. [GOOD]
6. **Export YAML** - Pengguna bisa mengunduh file YAML agent. [GOOD]
7. **Deploy** - Fitur publish/deploy ke AWS server tersedia di UI. [IMPLEMENTED BUT MOCKED/EXTERNAL]

---

## 4. Test Matrix

| ID | Area | Test Case | Expected | Actual | Status | Severity | Evidence |
|---|---|---|---|---|---|---|---|
| TC-001 | Agent | Create agent via API | Status 200, Agent Draft created | Status 200, is_draft=True | PASSED | - | Log task-67 |
| TC-002 | Agent | Create agent (empty prompt) | Validasi menolak prompt kosong (400) | Status 400 | PASSED | - | Log task-67 |
| TC-003 | Database | Refresh & List Persistence | Data agent tetap ada | 14 agents ditemukan dari DB | PASSED | - | Log task-67 |
| TC-004 | UI Flow | Submit form kosong (Frontend) | Tombol terdisable | Button `disabled={!input.trim()}` | PASSED | - | Kode frontend |
| TC-005 | Chat | Send message to Agent | Menerima response LLM | Berhasil menerima respon & emoji | PASSED | - | Log task-113 |
| TC-006 | Security | Akses API tanpa Auth | Ditolak (401) jika REQUIRE_API_KEY=True | Lolos karena REQUIRE_API_KEY=False | FAILED | High | Kode backend |
| TC-007 | Agent | Update spesifikasi Agent | Data diubah & status 200 | Status 200 | PASSED | - | Log task-67 |

---

## 5. Bugs & Issues

### Critical
* **ID-01: Sensitive Data Exposure (`.env` in repo)**
  * **Masalah**: File `.env` dengan kredensial DB TiDB dan OpenRouter API Key tersimpan di dalam root folder backend.
  * **Dampak**: Siapa pun yang mengakses repository ini dapat mencuri API key dan mengakses database production/test.
  * **Rekomendasi**: Hapus `.env` dari repository, gunakan `.env.example`, dan rotasi (revoke) seluruh API key yang telah terekspos.

### High
* **ID-02: Missing Access Control / Multi-tenant isolation**
  * **Masalah**: Tidak ada fitur login, dan `REQUIRE_API_KEY` default ke `False`. 
  * **Dampak**: Siapapun yang mengakses frontend dapat mengubah, menghapus, atau menggunakan agent buatan orang lain karena semuanya berada dalam satu global scope (tanpa user ID).
  * **Rekomendasi**: Implementasikan user authentication (misal: NextAuth) dan kaitkan setiap agent dengan `user_id`.

### Medium
* **ID-03: Console Unicode Error pada Backend di Windows**
  * **Masalah**: Saat LLM mengembalikan emoji, jika ada log yang mencetak respon di console Windows, server/script bisa crash karena encoding `cp1252`.
  * **Rekomendasi**: Paksakan encoding `utf-8` saat logging atau gunakan environment `PYTHONUTF8=1`.

### Low
* **ID-04: Inkonsistensi State (Draft vs DB)**
  * **Masalah**: Jika pengguna melakukan chat dengan builder namun belum menekan "Simpan" (atau tidak mengetik "simpan ini"), maka state agent hanya berupa draft di `localStorage`. Jika pengguna membuka di perangkat lain, draft hilang.

---

## 6. UX Problems (Bagi Orang Awam)

Khusus masalah yang dapat menyulitkan orang awam:
1. **Technical Jargon Overload (Impact: High)**: Dalam kartu preview spesifikasi, terdapat istilah "Harness: default-safe-v1", "Model: z-ai/glm-5.3", dan "MCP Servers". Orang awam tidak paham apa itu *Harness* atau spesifikasi *LLM Model*.
2. **"Tools dari Database" (Impact: Medium)**: Frasa ini terlalu teknis. Sebaiknya diganti dengan kata yang lebih ramah seperti "Kemampuan Tambahan" atau "Aplikasi Terhubung".
3. **Status "Draft" vs "Tersimpan" (Impact: Low)**: Penanda warna dan teks sudah cukup baik, tetapi user mungkin lupa menyimpan. Fitur auto-save (seperti di Google Docs) lebih disarankan daripada menuntut konfirmasi eksplisit.

---

## 7. Backend Problems

* Secara fungsional, backend FastAPI sudah sangat rapi, menggunakan arsitektur service layer dan Async SQLAlchemy. Validasi Pydantic berjalan dengan baik.
* Endpoint berjalan sesuai standard HTTP methods.

---

## 8. Database Problems

* Schema database telah didefinisikan dengan baik menggunakan SQLAlchemy ORM.
* Hubungan antara tool, agent, dan trace logs tampak konsisten.
* Persistence teruji aman (tidak bergantung pada state memory lokal, kecuali chat builder history).

---

## 9. Security Problems

* Lihat Bugs (ID-01 dan ID-02). Exposure API Key dan kurangnya Autentikasi / Rate Limiting adalah risiko besar untuk production.

---

## 10. Missing Features

Fitur yang dibutuhkan agar tujuan "orang awam" benar-benar tercapai dengan aman:
1. **User Authentication & Personal Workspace**: Agar agent orang awam tidak bercampur dengan orang lain.
2. **Simplified Mode Toggle**: Sebuah saklar UI (Simple / Advanced). Di mode Simple, sembunyikan System Prompt, Harness, dan Model. Hanya tampilkan: Nama, Deskripsi, dan Fitur Tambahan (Tools).
3. **One-Click Deploy**: Saat ini publish membutuhkan pemahaman domain/slug. Bisa dibuat 100% otomatis.

---

## 11. Recommended Flow

Flow yang direkomendasikan untuk user awam:
`Login → Buka "Agent Studio" → Ceritakan kebutuhan di Chat (Builder) → Agent Otomatis Tersimpan (Auto-save) → Test di Panel Kanan → Klik "Gunakan Agent Ini" (Deploy internal)`

---

## 12. Prioritized Fix List

1. **CRITICAL**: Hapus `.env` dari version control dan rotasi API Keys yang bocor (Database & OpenRouter).
2. **HIGH**: Implementasikan Authentication (Login) dan lindungi endpoint API dengan autentikasi / kepemilikan data (Ownership Validation).
3. **UX**: Sembunyikan field "Harness", "Model", dan "MCP Servers" ke dalam tab "Advanced Settings". Ganti "Tools dari Database" menjadi "Kemampuan / Integrasi".
4. **IMPROVEMENT**: Tambahkan auto-save (debounce) di frontend saat status builder chat mengeluarkan spec update agar meminimalisir data hilang.

---

## 13. Final Verdict

**READY WITH CONDITIONS**

Secara teknis (Functionality & Persistence), sistem ini sudah **bekerja dengan sangat baik** sesuai arsitektur yang dirancang (Frontend Next.js terhubung penuh dengan Backend FastAPI dan TiDB MySQL, mampu menggunakan LLM untuk mengenerate spesifikasi dan testing). Alur *Conversational Builder* sangat cerdas dalam mempermudah orang awam.

Namun, proyek ini **belum siap untuk dirilis ke publik (production)** sebelum **dua syarat mutlak (kondisi)** terpenuhi:
1. **Keamanan (Security)**: Kebocoran `.env` harus ditutup, kredensial dirotasi, dan sistem Autentikasi/Ownership ditambahkan agar pengguna awam tidak merusak atau melihat agen milik orang lain.
2. **Simplifikasi UI (UX)**: Istilah teknis (Model LLM, Harness, MCP, YAML) wajib disembunyikan dalam mode *Advanced* agar pengguna yang benar-benar awam (misal: pedagang kecil atau guru) tidak terintimidasi.
