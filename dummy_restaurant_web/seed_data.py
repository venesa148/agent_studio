"""
Script untuk mereset dan mengisi ulang database SQLite restaurant.db dengan data dummy default.
Jalankan: python seed_data.py
"""
import os
import sqlite3
from database import DB_PATH, init_db, seed_default_data

def reset_and_seed():
    print(f"Target Database: {DB_PATH}")
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("Database lama berhasil dihapus.")
        except Exception as e:
            print(f"Peringatan: Gagal menghapus database lama ({e}). Menimpa tabel...")

    print("Membuat skema tabel baru...")
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM menu_items")
    menu_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reservations")
    res_count = cursor.fetchone()[0]
    conn.close()

    print(f"Berhasil! Database baru siap digunakan.")
    print(f"- Total Menu: {menu_count} item")
    print(f"- Total Reservasi Awal: {res_count} booking")

if __name__ == "__main__":
    reset_and_seed()
