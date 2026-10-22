import os
import random
import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from database import init_db, get_db
from models import (
    ReservationCreate,
    ReservationStatusUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    RestaurantInfoUpdate
)

# Inisialisasi DB saat startup
init_db()

app = FastAPI(
    title="Savoria Bistro & Resto - API & Web Dummy",
    description="Backend API dan Web Dummy Restoran dengan Database SQLite: Menu, Harga, Lokasi, Jam Buka-Tutup, dan Reservasi Meja.",
    version="1.0.0"
)

# CORS Middleware agar bisa diakses dari frontend mana saja atau AI Agent
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Helper: Hitung status buka/tutup saat ini
def check_is_open(open_time_str: str, close_time_str: str, is_closed_day: bool = False):
    if is_closed_day:
        return False
    try:
        now = datetime.datetime.now()
        cur_time = now.time()
        open_time = datetime.datetime.strptime(open_time_str, "%H:%M").time()
        close_time = datetime.datetime.strptime(close_time_str, "%H:%M").time()
        
        if open_time <= close_time:
            return open_time <= cur_time <= close_time
        else:
            # Melewati tengah malam
            return cur_time >= open_time or cur_time <= close_time
    except Exception:
        return True

# ==================== PAGE ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Menampilkan antarmuka web dummy restoran"""
    return templates.TemplateResponse(request=request, name="index.html")

# ==================== REST API ENDPOINTS ====================

@app.get("/api/info", summary="Ambil informasi restoran, lokasi, dan status jam buka")
def get_restaurant_info():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM restaurant_info WHERE id = 1")
    info = cursor.fetchone()
    if not info:
        conn.close()
        raise HTTPException(status_code=404, detail="Info restoran tidak ditemukan")
    
    info_dict = dict(info)

    # Ambil jam operasional semua hari
    cursor.execute("SELECT * FROM operating_hours ORDER BY day_of_week ASC")
    hours_rows = cursor.fetchall()
    hours_list = [dict(r) for r in hours_rows]

    # Cek hari ini (0: Senin, ..., 6: Minggu)
    now = datetime.datetime.now()
    today_weekday = now.weekday()
    today_hour_row = next((h for h in hours_list if h["day_of_week"] == today_weekday), None)

    is_open_now = False
    today_open_str = info_dict.get("open_time", "10:00")
    today_close_str = info_dict.get("close_time", "22:00")
    today_day_name = "Hari Ini"

    if today_hour_row:
        today_open_str = today_hour_row["open_time"]
        today_close_str = today_hour_row["close_time"]
        today_day_name = today_hour_row["day_name"]
        is_open_now = check_is_open(today_open_str, today_close_str, bool(today_hour_row["is_closed"]))

    conn.close()

    return {
        "success": True,
        "data": info_dict,
        "operating_hours": hours_list,
        "status_now": {
            "is_open": is_open_now,
            "status_text": "BUKA SEKARANG" if is_open_now else "SEDANG TUTUP",
            "today_day": today_day_name,
            "today_hours": f"{today_open_str} - {today_close_str}",
            "current_time": now.strftime("%H:%M:%S")
        }
    }

@app.put("/api/info", summary="Update profil restoran & jam operasional")
def update_restaurant_info(payload: RestaurantInfoUpdate):
    conn = get_db()
    cursor = conn.cursor()

    fields = []
    values = []
    for k, v in payload.dict(exclude_unset=True).items():
        if v is not None:
            fields.append(f"{k} = ?")
            values.append(v)

    if not fields:
        conn.close()
        return {"success": True, "message": "Tidak ada perubahan data"}

    values.append(1)
    query = f"UPDATE restaurant_info SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    return {"success": True, "message": "Informasi restoran berhasil diperbarui"}

# ==================== MENU ENDPOINTS ====================

@app.get("/api/categories", summary="Daftar kategori menu")
def get_categories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM menu_items ORDER BY category ASC")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"success": True, "data": categories}

@app.get("/api/menu", summary="Daftar menu dengan filter kategori, pencarian, dan pengurutan harga")
def get_menu(
    category: Optional[str] = None,
    search: Optional[str] = None,
    available_only: bool = False,
    sort: Optional[str] = Query(None, description="'price_asc', 'price_desc', 'favorite', 'name'")
):
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM menu_items WHERE 1=1"
    params = []

    if category and category.lower() != "semua":
        query += " AND category = ?"
        params.append(category)

    if search:
        search_term = f"%{search}%"
        query += " AND (name LIKE ? OR description LIKE ? OR tags LIKE ?)"
        params.extend([search_term, search_term, search_term])

    if available_only:
        query += " AND is_available = 1"

    if sort == "price_asc":
        query += " ORDER BY price ASC"
    elif sort == "price_desc":
        query += " ORDER BY price DESC"
    elif sort == "favorite":
        query += " ORDER BY is_favorite DESC, price ASC"
    else:
        query += " ORDER BY category ASC, is_favorite DESC, id ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    menu_list = [dict(r) for r in rows]
    conn.close()

    return {
        "success": True,
        "count": len(menu_list),
        "data": menu_list
    }

@app.get("/api/menu/{item_id}", summary="Detail item menu")
def get_menu_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Item menu tidak ditemukan")
    return {"success": True, "data": dict(row)}

@app.post("/api/menu", summary="Tambah menu baru")
def create_menu_item(item: MenuItemCreate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO menu_items (name, category, price, description, image_url, is_available, is_favorite, spicy_level, tags)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item.name, item.category, item.price, item.description,
        item.image_url or "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80",
        item.is_available, item.is_favorite, item.spicy_level, item.tags
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"success": True, "message": "Menu berhasil ditambahkan", "id": new_id}

@app.put("/api/menu/{item_id}", summary="Update item menu")
def update_menu_item(item_id: int, payload: MenuItemUpdate):
    conn = get_db()
    cursor = conn.cursor()

    fields = []
    values = []
    for k, v in payload.dict(exclude_unset=True).items():
        if v is not None:
            fields.append(f"{k} = ?")
            values.append(v)

    if not fields:
        conn.close()
        return {"success": True, "message": "Tidak ada perubahan"}

    values.append(item_id)
    query = f"UPDATE menu_items SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    return {"success": True, "message": "Menu berhasil diperbarui"}

@app.delete("/api/menu/{item_id}", summary="Hapus item menu")
def delete_menu_item(item_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Menu berhasil dihapus"}

# ==================== RESERVASI MEJA ====================

@app.post("/api/reservations", summary="Buat reservasi meja baru")
def create_reservation(res: ReservationCreate):
    conn = get_db()
    cursor = conn.cursor()

    # Validasi tanggal minimal hari ini
    try:
        res_date = datetime.datetime.strptime(res.reservation_date, "%Y-%m-%d").date()
        today = datetime.date.today()
        if res_date < today:
            raise HTTPException(status_code=400, detail="Tanggal reservasi tidak boleh di masa lalu")
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD")

    # Generate Booking Code Unik: SB-YYYYMMDD-XXXX
    date_code = res_date.strftime("%Y%m%d")
    random_num = random.randint(1000, 9999)
    booking_code = f"SB-{date_code}-{random_num}"

    # Pastikan booking code unik
    while True:
        cursor.execute("SELECT id FROM reservations WHERE booking_code = ?", (booking_code,))
        if not cursor.fetchone():
            break
        booking_code = f"SB-{date_code}-{random.randint(1000, 9999)}"

    created_at = datetime.datetime.now().isoformat()
    status = "Confirmed" # Default langsung terkonfirmasi untuk kemudahan testing dummy

    cursor.execute("""
    INSERT INTO reservations (
        booking_code, customer_name, phone, email, reservation_date,
        reservation_time, guest_count, table_area, special_notes, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        booking_code, res.customer_name, res.phone, res.email,
        res.reservation_date, res.reservation_time, res.guest_count,
        res.table_area, res.special_notes, status, created_at
    ))

    conn.commit()
    res_id = cursor.lastrowid
    conn.close()

    print(f"\n🟢 [DATABASE INSERT] Reservasi Baru Berhasil Masuk ke SQLite (ID #{res_id})!")
    print(f"   ► Kode Booking : {booking_code}")
    print(f"   ► Nama Tamu    : {res.customer_name}")
    print(f"   ► Kontak       : {res.phone}")
    print(f"   ► Jadwal       : {res.reservation_date} pukul {res.reservation_time} WIB")
    print(f"   ► Meja & Tamu  : {res.table_area} ({res.guest_count} Orang)")
    print(f"   ► Waktu Simpan : {created_at}\n")

    return {
        "success": True,
        "message": "Reservasi meja berhasil dibuat!",
        "data": {
            "id": res_id,
            "booking_code": booking_code,
            "customer_name": res.customer_name,
            "phone": res.phone,
            "reservation_date": res.reservation_date,
            "reservation_time": res.reservation_time,
            "guest_count": res.guest_count,
            "table_area": res.table_area,
            "special_notes": res.special_notes,
            "status": status,
            "created_at": created_at
        }
    }

@app.get("/api/db-status", summary="Mengecek status file database SQLite & record terbaru")
def get_db_status():
    from database import DB_PATH
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(DB_PATH)).strftime("%Y-%m-%d %H:%M:%S") if os.path.exists(DB_PATH) else "-"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reservations")
    total_res = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM menu_items")
    total_menu = cursor.fetchone()[0]

    # Ambil 5 reservasi terbaru
    cursor.execute("SELECT * FROM reservations ORDER BY id DESC LIMIT 5")
    recent = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "success": True,
        "database": {
            "type": "SQLite 3",
            "file_name": os.path.basename(DB_PATH),
            "file_path": DB_PATH,
            "size_bytes": db_size,
            "size_readable": f"{db_size / 1024:.1f} KB",
            "last_modified": modified_time,
            "total_reservations": total_res,
            "total_menus": total_menu
        },
        "recent_records": recent
    }

@app.get("/api/reservations", summary="Daftar semua reservasi (untuk staff/admin/agent)")
def get_reservations(
    date: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM reservations WHERE 1=1"
    params = []

    if date:
        query += " AND reservation_date = ?"
        params.append(date)
    if status and status.lower() != "all":
        query += " AND status = ?"
        params.append(status)
    if search:
        search_term = f"%{search}%"
        query += " AND (customer_name LIKE ? OR phone LIKE ? OR booking_code LIKE ?)"
        params.extend([search_term, search_term, search_term])

    query += " ORDER BY reservation_date DESC, reservation_time DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    res_list = [dict(r) for r in rows]
    conn.close()

    return {
        "success": True,
        "count": len(res_list),
        "data": res_list
    }

@app.get("/api/reservations/{query_val}", summary="Cari reservasi berdasarkan kode booking atau nomor telepon")
def search_reservation(query_val: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM reservations 
    WHERE booking_code = ? OR phone = ? OR id = ?
    ORDER BY reservation_date DESC
    """, (query_val, query_val, query_val if query_val.isdigit() else -1))
    
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="Data reservasi tidak ditemukan dengan kode atau nomor tersebut")

    return {
        "success": True,
        "count": len(rows),
        "data": [dict(r) for r in rows]
    }

@app.patch("/api/reservations/{res_id}/status", summary="Update status reservasi (Confirmed/Completed/Cancelled)")
def update_reservation_status(res_id: int, payload: ReservationStatusUpdate):
    valid_statuses = ["Pending", "Confirmed", "Completed", "Cancelled"]
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status tidak valid. Pilihan: {', '.join(valid_statuses)}")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE reservations SET status = ? WHERE id = ?", (payload.status, res_id))
    conn.commit()
    conn.close()

    return {"success": True, "message": f"Status reservasi diubah menjadi {payload.status}"}

@app.delete("/api/reservations/{res_id}", summary="Hapus/Batalkan reservasi")
def delete_reservation(res_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservations WHERE id = ?", (res_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Reservasi berhasil dihapus"}

# ==================== STATISTIK SUMMARY ====================

@app.get("/api/stats", summary="Statistik ringkas restoran & reservasi")
def get_stats():
    conn = get_db()
    cursor = conn.cursor()

    today = datetime.date.today().strftime("%Y-%m-%d")

    cursor.execute("SELECT COUNT(*) FROM menu_items")
    total_menus = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM menu_items WHERE is_available = 1")
    available_menus = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reservations WHERE reservation_date = ?", (today,))
    reservations_today = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reservations WHERE status = 'Confirmed'")
    total_confirmed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reservations")
    total_reservations = cursor.fetchone()[0]

    conn.close()

    return {
        "success": True,
        "stats": {
            "total_menus": total_menus,
            "available_menus": available_menus,
            "reservations_today": reservations_today,
            "total_confirmed": total_confirmed,
            "total_reservations": total_reservations
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
