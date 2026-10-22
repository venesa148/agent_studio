# 🍽️ Savoria Bistro & Resto - Web Dummy & REST API

Aplikasi Web Dummy Restoran modern, mandiri, dan responsif yang dilengkapi dengan **Database SQLite lokal (persistent)**, antarmuka web interaktif (*Single Page Application*), dan **RESTful API** terintegrasi yang siap dihubungkan ke **AI Agent Studio**, Postman, maupun pengujian aplikasi.

---

## 🚀 Fitur Utama

1. **Database SQLite Lokal (`restaurant.db`)**:
   - Berisi tabel info restoran, jam operasional, menu makanan/minuman, dan tabel transaksi reservasi meja.
   - Tersedia script seeder otomatis dengan 18+ menu lezat, jadwal buka-tutup lengkap, dan contoh data reservasi.

2. **Daftar Menu & Harga Lengkap**:
   - Kategori menu: *Makanan Utama, Camilan & Appetizer, Minuman & Kopi, Dessert*.
   - Harga transparan dalam format Rupiah (IDR).
   - Fitur filter kategori, pencarian live (*live search*), dan pengurutan harga termurah/termahal/terpopuler.
   - Badge ketersediaan stok (*Tersedia / Stok Habis*) dan level kepedasan (🌶️).

3. **Informasi Lokasi & Kontak**:
   - Alamat lengkap dan patokan jalan di Senopati, Jakarta Selatan.
   - Integrasi Google Maps responsif (*embedded map*).
   - Kontak telepon dan tombol pintas WhatsApp Customer Care.

4. **Jam Buka - Tutup Dinamis**:
   - Status **Buka Sekarang / Sedang Tutup** dihitung secara *real-time* berdasarkan waktu sistem saat ini.
   - Tabel jadwal jam operasional dari Senin sampai Minggu dengan penanda otomatis untuk hari ini.
   - Informasi *last order* dan ketentuan kunjungan.

5. **Sistem Reservasi Meja (Booking)**:
   - Formulir reservasi: Nama, No. WhatsApp, Email, Tanggal (minimal hari ini), Jam Kedatangan, Jumlah Orang (1–20+ pax), Pilihan Area Meja (*Indoor AC, Semi-Outdoor Garden, VIP Room, Rooftop*), dan Catatan Khusus.
   - Menghasilkan **Kode Booking Unik** otomatis (contoh: `SB-20261015-4821`).
   - Pop-up **Tiket Reservasi Digital** yang dapat dicetak/disalin.

6. **Lacak / Cek Status Reservasi**:
   - Pelanggan dapat mengecek status booking menggunakan Kode Booking atau Nomor WhatsApp.
   - Opsi pembatalan reservasi (*Cancel*).

7. **Panel Admin / Manajemen Resto**:
   - Dashboard statistik: Total Reservasi, Reservasi Hari Ini, Status Konfirmasi, Total Menu.
   - Kelola reservasi: Ubah status (*Confirmed, Completed, Cancelled, Pending*).
   - Kelola menu: Tambah menu baru, ubah harga, toggle stok *Tersedia / Habis*, hapus menu.
   - Ubah profil resto: Ganti nama, alamat, dan jam buka-tutup langsung tersimpan ke database.

---

## 💻 Cara Menjalankan

### Cara 1: Menggunakan File Batch (Paling Cepat di Windows)
Cukup klik dua kali file **`run.bat`** di dalam folder `dummy_restaurant_web`.

### Cara 2: Melalui Terminal / Command Prompt
```bash
cd dummy_restaurant_web
python -m uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

Buka browser Anda di:
- **Tampilan Web Restoran**: [http://localhost:5000](http://localhost:5000)
- **Dokumentasi Swagger API (Interactive Docs)**: [http://localhost:5000/docs](http://localhost:5000/docs)
- **ReDoc Documentation**: [http://localhost:5000/redoc](http://localhost:5000/redoc)

---

## 📡 Daftar Endpoint REST API

Semua endpoint dapat langsung diuji via cURL, Postman, atau dipanggil oleh AI Agent:

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/api/info` | Profil restoran, lokasi, jam operasional, dan status Buka/Tutup saat ini |
| `PUT` | `/api/info` | Update profil resto dan jam operasional |
| `GET` | `/api/categories` | Mengambil daftar semua kategori menu |
| `GET` | `/api/menu` | Ambil semua menu (Filter: `?category=...&search=...&sort=...`) |
| `GET` | `/api/menu/{id}` | Detail satu item menu |
| `POST` | `/api/menu` | Tambah item menu baru ke database |
| `PUT` | `/api/menu/{id}` | Edit harga, ketersediaan, atau info menu |
| `DELETE` | `/api/menu/{id}` | Hapus item menu dari database |
| `POST` | `/api/reservations` | Buat reservasi meja baru (menghasilkan kode booking unik) |
| `GET` | `/api/reservations` | Ambil seluruh daftar reservasi (bisa difilter tanggal/status) |
| `GET` | `/api/reservations/{code_or_phone}` | Cari reservasi berdasarkan kode booking atau no. HP |
| `PATCH` | `/api/reservations/{id}/status` | Update status reservasi (`Confirmed`, `Completed`, `Cancelled`) |
| `DELETE` | `/api/reservations/{id}` | Hapus data reservasi |
| `GET` | `/api/stats` | Statistik ringkas total menu & reservasi |

---

## 🤖 Integrasi dengan AI Agent Studio

Jika Anda ingin AI Agent (misal di folder `agents/`) dapat melayani pelanggan, memesankan meja, atau mengecek menu, Anda cukup mendaftarkan tool HTTP dengan target endpoint di atas:

### Contoh Tool 1: `cek_menu_restoran`
```yaml
name: cek_menu_restoran
description: Mencari menu makanan atau minuman beserta harga di restoran
endpoint: GET http://localhost:5000/api/menu?category={category}&search={search}
```

### Contoh Tool 2: `buat_reservasi_meja`
```yaml
name: buat_reservasi_meja
description: Mendaftarkan reservasi meja untuk pelanggan
endpoint: POST http://localhost:5000/api/reservations
body:
  customer_name: "{customer_name}"
  phone: "{phone}"
  reservation_date: "{reservation_date}"
  reservation_time: "{reservation_time}"
  guest_count: {guest_count}
  table_area: "{table_area}"
  special_notes: "{special_notes}"
```

### Contoh Tool 3: `cek_status_reservasi`
```yaml
name: cek_status_reservasi
description: Mengecek status reservasi meja menggunakan kode booking atau nomor telepon
endpoint: GET http://localhost:5000/api/reservations/{query}
```

---

## 🔄 Reset Database
Jika Anda ingin menghapus semua data pengujian dan mengembalikan data dummy awal ke kondisi semula, jalankan:
```bash
python seed_data.py
```
