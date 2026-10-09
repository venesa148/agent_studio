# Agent Studio - Live Endpoint Tester (Bubble Chat UI)

Aplikasi web mandiri berbasis UI **Bubble Chat** yang dirancang sebagai alternatif Postman yang interaktif dan ramah pengguna untuk menguji API Agent yang telah dipublish.

---

## 🚀 Fitur Utama

1. **Bubble Chat Modern & Responsif**:
   - Tampilan chat bubble mirip WhatsApp/ChatGPT dengan dukungan **Markdown** lengkap (tabel rumah sakit/dokter, list, teks tebal, link).
   - Indikator proses (*typing animation*) saat server sedang memproses balasan.
   - Deteksi eksekusi tool/API (*Tool Calls Badge*) yang dapat di-expand untuk melihat tool apa saja yang dipanggil oleh agent.
   - Informasi latensi respon (detik) dan status turn percakapan.

2. **Pengaturan Endpoint & Bearer Token Lengkap**:
   - **Endpoint URL**: Input alamat `POST` invoke agent (contoh: `http://13.250.191.160:8080/agents/pandu-bpjs-sehattt/invoke` atau `http://localhost:8080/agents/<slug>/invoke`).
   - Tombol shortcut **Localhost** dan **AWS EC2** untuk mengisi endpoint dengan 1 klik.
   - **Bearer Token / API Key**: Input token `agy_live_...` dengan tombol sembunyikan/tampilkan password.
   - **Session ID**: Input ID sesi untuk multi-turn conversation, lengkap dengan tombol `🔄` untuk generate session UUID baru.
   - Konfigurasi tersimpan otomatis di browser (`localStorage`).

3. **Raw JSON Inspector (Pengganti Postman)**:
   - Tombol **Raw JSON** di bagian atas menampilkan:
     - **Last Request**: Header HTTP dan JSON payload yang dikirim.
     - **Last Response**: Status kode HTTP dan JSON response lengkap dari server.
     - **cURL Command**: Perintah cURL yang sudah diformat rapi dan siap disalin untuk terminal atau Postman.

---

## 💻 Cara Menggunakan

1. **Buka Aplikasi**:
   - Cukup klik dua kali file **`run.bat`**, atau
   - Buka file **`index.html`** langsung menggunakan browser pilihan Anda (Chrome, Edge, Firefox, dll).

2. **Isi Konfigurasi**:
   - Masukkan **Endpoint URL** dari hasil Publish Agent Anda.
   - Masukkan **API Key / Bearer Token** (`agy_live_...`).
   - Tentukan **Session ID** (atau biarkan default).

3. **Mulai Chat**:
   - Ketik pertanyaan di kolom chat dan tekan **Enter** (atau gunakan contoh pertanyaan cepat).
   - Agent akan merespon secara langsung!
