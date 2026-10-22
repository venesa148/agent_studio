import sqlite3
import os
import datetime
import random

DB_PATH = os.path.join(os.path.dirname(__file__), "restaurant.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Tabel Info Restoran
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS restaurant_info (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        tagline TEXT,
        description TEXT,
        address TEXT NOT NULL,
        district TEXT,
        city TEXT,
        postal_code TEXT,
        phone TEXT,
        whatsapp TEXT,
        email TEXT,
        instagram TEXT,
        maps_url TEXT,
        maps_embed_url TEXT,
        open_time TEXT,
        close_time TEXT,
        total_tables INTEGER DEFAULT 20
    )
    """)

    # Tabel Jam Operasional Mingguan
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operating_hours (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_of_week INTEGER NOT NULL, -- 0: Senin, 1: Selasa, ..., 6: Minggu
        day_name TEXT NOT NULL,
        open_time TEXT NOT NULL,
        close_time TEXT NOT NULL,
        is_closed INTEGER DEFAULT 0
    )
    """)

    # Tabel Menu Makanan & Minuman
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price INTEGER NOT NULL,
        description TEXT,
        image_url TEXT,
        is_available INTEGER DEFAULT 1,
        is_favorite INTEGER DEFAULT 0,
        spicy_level INTEGER DEFAULT 0,
        tags TEXT
    )
    """)

    # Tabel Reservasi Meja
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_code TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        reservation_date TEXT NOT NULL,
        reservation_time TEXT NOT NULL,
        guest_count INTEGER NOT NULL,
        table_area TEXT NOT NULL,
        special_notes TEXT,
        status TEXT DEFAULT 'Confirmed', -- Pending, Confirmed, Completed, Cancelled
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()

    # Cek apakah data default sudah ada
    cursor.execute("SELECT COUNT(*) FROM restaurant_info")
    if cursor.fetchone()[0] == 0:
        seed_default_data(conn)

    conn.close()

def seed_default_data(conn):
    cursor = conn.cursor()

    # 1. Info Resto
    cursor.execute("""
    INSERT INTO restaurant_info (
        id, name, tagline, description, address, district, city, postal_code,
        phone, whatsapp, email, instagram, maps_url, maps_embed_url,
        open_time, close_time, total_tables
    ) VALUES (
        1,
        'Savoria Bistro & Nusantara Dining',
        'Harmoni Cita Rasa Autentik Nusantara & Suasana Modern Hangat',
        'Savoria Bistro menghadirkan perpaduan kuliner warisan Indonesia dengan sentuhan modern kontemporer. Menggunakan bahan lokal segar pilihan, kopi nusantara racikan barista, dan suasana nyaman untuk bersantap bersama keluarga, kolega bisnis, maupun kencan istimewa.',
        'Jl. Senopati Raya No. 88, Selong, Kebayoran Baru',
        'Kebayoran Baru',
        'Jakarta Selatan',
        '12110',
        '021-7258900',
        '6281289001234',
        'halo@savoriabistro.id',
        '@savoria.bistro',
        'https://maps.google.com/?q=Senopati+Jakarta+Selatan',
        'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3966.273646549234!2d106.80628297499039!3d-6.22760639376049!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x2e69f14d30075f07%3A0xb35a77b7891845bb!2sJl.%20Senopati%2C%20Kebayoran%20Baru%2C%20Jakarta%20Selatan!5e0!3m2!1sid!2sid!4v1710000000000!5m2!1sid!2sid',
        '10:00',
        '22:00',
        24
    )
    """)

    # 2. Jam Operasional (Senin s/d Minggu)
    days = [
        (0, "Senin", "10:00", "22:00", 0),
        (1, "Selasa", "10:00", "22:00", 0),
        (2, "Rabu", "10:00", "22:00", 0),
        (3, "Kamis", "10:00", "22:00", 0),
        (4, "Jumat", "10:00", "23:00", 0),
        (5, "Sabtu", "09:00", "23:00", 0),
        (6, "Minggu", "09:00", "22:00", 0),
    ]
    cursor.executemany("""
    INSERT INTO operating_hours (day_of_week, day_name, open_time, close_time, is_closed)
    VALUES (?, ?, ?, ?, ?)
    """, days)

    # 3. Menu Items
    menu = [
        # Makanan Utama
        (
            "Nasi Goreng Wagyu Kecombrang",
            "Makanan Utama",
            88000,
            "Nasi goreng aromatik dengan irisan bunga kecombrang segar, potongan daging Wagyu Meltique empuk, telur mata sapi, dan emping renyah.",
            "https://images.unsplash.com/photo-1603133872878-684f208fb84b?auto=format&fit=crop&w=600&q=80",
            1, 1, 1, "Best Seller, Rekomendasi Chef"
        ),
        (
            "Ayam Bakar Madu Jimbaran",
            "Makanan Utama",
            65000,
            "Paha ayam bakar bumbu rempah khas pesisir Jimbaran dengan olesan madu hutan alami, disajikan dengan lalapan dan sambal matah Bali segar.",
            "https://images.unsplash.com/photo-1598103442097-8b74394b95c6?auto=format&fit=crop&w=600&q=80",
            1, 1, 1, "Favorit Pelanggan"
        ),
        (
            "Rawon Iga Sapi Bakar Surabaya",
            "Makanan Utama",
            95000,
            "Kuah rawon hitam pekat dari kluwek istimewa disajikan terpisah dengan iga sapi bakar berkaramel gurih, tauge pendek, telur asin, dan sambal terasi.",
            "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=600&q=80",
            1, 1, 0, "Chef Signature"
        ),
        (
            "Sate Maranggi Sapi Purwakarta",
            "Makanan Utama",
            72000,
            "10 tusuk daging sapi maranggi empuk berbalut bumbu ketumbar gula aren, disajikan dengan sambal tomat segar uleg dan lontong daun pisang.",
            "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80",
            1, 0, 1, "Best Seller"
        ),
        (
            "Soto Betawi Daging & Paru Crispy",
            "Makanan Utama",
            68000,
            "Kuah santan susu gurih rempah pala kapulaga berisi daging sengkel empuk dan paru renyah, disajikan bersama nasi putih pulen dan emping melinjo.",
            "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=600&q=80",
            1, 0, 0, "Klasik Betawi"
        ),
        (
            "Salmon Bakar Sambal Dabu-Dabu",
            "Makanan Utama",
            125000,
            "Fillet Norwegian salmon segar dipanggang sempurna, dipadukan siraman sambal dabu-dabu khas Manado yang asam segar pedas dan sayur tumis pakis.",
            "https://images.unsplash.com/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=600&q=80",
            1, 1, 2, "Menu Sehat / Premium"
        ),
        (
            "Mie Goreng Jawa Seafood Spesial",
            "Makanan Utama",
            58000,
            "Mie telur kenyal dimasak dengan bumbu kemiri ebi harum, udang windu, cumi segar, kekian, kol, dan telur orak-arik dengan taburan bawang merah goreng.",
            "https://images.unsplash.com/photo-1612927601601-6638404737ce?auto=format&fit=crop&w=600&q=80",
            1, 0, 1, "Comfort Food"
        ),
        (
            "Bebek Crispy Ubud Sambal Ijo",
            "Makanan Utama",
            85000,
            "Bebek ungkep bumbu rempah 12 jam yang digoreng garing renyah di luar namun juicy di dalam, disajikan dengan plecing kangkung dan sambal ijo uleg.",
            "https://images.unsplash.com/photo-1514944298352-7b243469a473?auto=format&fit=crop&w=600&q=80",
            1, 0, 2, "Garing & Gurih"
        ),

        # Camilan & Appetizer
        (
            "Tahu Gejrot Cirebon Istimewa",
            "Camilan & Appetizer",
            32000,
            "Tahu pong renyah disiram kuah asam jawa kental pedas manis dengan ulegan bawang merah, cabai rawit hijau segar.",
            "https://images.unsplash.com/photo-1541518763669-27fef04b14ea?auto=format&fit=crop&w=600&q=80",
            1, 0, 2, "Pedas Gurih"
        ),
        (
            "Bakwan Jagung Renyah Sambal Roa",
            "Camilan & Appetizer",
            35000,
            "4 buah bakwan jagung manis pipil renyah keemasan, disajikan bersama cocolan sambal ikan roa khas Manado yang harum berasap.",
            "https://images.unsplash.com/photo-1563245372-f21724e3856d?auto=format&fit=crop&w=600&q=80",
            1, 1, 1, "Best Snack"
        ),
        (
            "Singkong Goreng Garlic Keju Salju",
            "Camilan & Appetizer",
            32000,
            "Singkong pilihan merekah lembut beraroma bawang putih gurih dengan taburan keju cheddar melimpah.",
            "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=600&q=80",
            1, 0, 0, "Teman Kopi"
        ),
        (
            "Chicken Wings Sambal Matah",
            "Camilan & Appetizer",
            45000,
            "Sayap ayam goreng renyah saus mentega yang diberi topping melimpah sambal matah serai segar khas Bali.",
            "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?auto=format&fit=crop&w=600&q=80",
            1, 0, 2, "Favorit"
        ),

        # Minuman & Kopi
        (
            "Es Kopi Susu Gula Aren Savoria",
            "Minuman & Kopi",
            28000,
            "Perpaduan espresso double shot arabika Flores Bajawa, susu segar creamy, dan gula aren organik murni.",
            "https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?auto=format&fit=crop&w=600&q=80",
            1, 1, 0, "Signature Drink"
        ),
        (
            "Teh Pandan Serai Madu Dingin",
            "Minuman & Kopi",
            25000,
            "Seduhan daun teh hitam artisan dengan rebusan daun pandan wangi, batang serai segar, dan perasan jeruk nipis serta madu alami.",
            "https://images.unsplash.com/photo-1556679343-c7306c1976bc?auto=format&fit=crop&w=600&q=80",
            1, 0, 0, "Menyegarkan"
        ),
        (
            "Jus Alpukat Kocok Kerok Cokelat",
            "Minuman & Kopi",
            35000,
            "Alpukat mentega matang dikerok berpadu susu kental cokelat premium dan es serut segar.",
            "https://images.unsplash.com/photo-1623065422902-30a2d299bbe4?auto=format&fit=crop&w=600&q=80",
            1, 0, 0, "Kental & Segar"
        ),
        (
            "Sparkling Lychee Mint Cooler",
            "Minuman & Kopi",
            32000,
            "Minuman soda buah leci asli dengan daun mint segar dan perasan jeruk lemon yang menyegarkan dahaga.",
            "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?auto=format&fit=crop&w=600&q=80",
            1, 0, 0, "Pelepas Dahaga"
        ),
        (
            "Wedang Uwuh Rempah Hangat",
            "Minuman & Kopi",
            24000,
            "Minuman herbal hangat khas Imogiri Yogyakarta dengan kayu secang, jahe bakar, cengkeh, kayu manis, dan gula batu.",
            "https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=600&q=80",
            1, 0, 0, "Hangat & Sehat"
        ),

        # Dessert
        (
            "Panna Cotta Klepon Gula Jawa",
            "Dessert",
            38000,
            "Panna cotta lembut rasa pandan wangi dengan saus kinca gula merah pekat dan taburan kelapa parut sangrai renyah.",
            "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=600&q=80",
            1, 1, 0, "Signature Dessert"
        ),
        (
            "Pisang Bakar Keju Karamel Aren",
            "Dessert",
            32000,
            "Pisang raja bakar beraroma arang dengan lelehan keju mozarella & cheddar, kental manis aren, dan taburan kacang sangrai.",
            "https://images.unsplash.com/photo-1587314168485-3236d6710814?auto=format&fit=crop&w=600&q=80",
            1, 0, 0, "Manis Legit"
        ),
        (
            "Es Cendol Durian Savoria",
            "Dessert",
            42000,
            "Cendol kenyal alami daun suji dengan santan murni gurih, gula aren cair, nangka manis, dan satu scoop daging buah durian Montong asli.",
            "https://images.unsplash.com/photo-1501443762994-82bd5dace89a?auto=format&fit=crop&w=600&q=80",
            1, 1, 0, "Paling Laris"
        )
    ]

    cursor.executemany("""
    INSERT INTO menu_items (name, category, price, description, image_url, is_available, is_favorite, spicy_level, tags)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, menu)

    # 4. Contoh Reservasi Awal
    today = datetime.date.today().strftime("%Y-%m-%d")
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    reservations = [
        (
            f"SB-{datetime.date.today().strftime('%Y%m%d')}-1042",
            "Budi Santoso",
            "081298765432",
            "budi.santoso@gmail.com",
            today,
            "19:00",
            4,
            "Indoor AC",
            "Dekat jendela, mohon siapkan baby chair 1 buah.",
            "Confirmed",
            datetime.datetime.now().isoformat()
        ),
        (
            f"SB-{datetime.date.today().strftime('%Y%m%d')}-2198",
            "Siti Rahmawati",
            "085712345678",
            "siti.rahma@perusahaan.co.id",
            today,
            "12:30",
            8,
            "VIP Private Room",
            "Lunch meeting direksi, butuh proyektor jika ada.",
            "Confirmed",
            datetime.datetime.now().isoformat()
        ),
        (
            f"SB-{(datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y%m%d')}-3341",
            "Michael Tanuwijaya",
            "081345678901",
            "michael.tan@yahoo.com",
            tomorrow,
            "18:30",
            2,
            "Outdoor Garden",
            "Anniversary dinner, mohon meja pojok yang tenang.",
            "Confirmed",
            datetime.datetime.now().isoformat()
        )
    ]

    cursor.executemany("""
    INSERT INTO reservations (
        booking_code, customer_name, phone, email, reservation_date,
        reservation_time, guest_count, table_area, special_notes, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, reservations)

    conn.commit()
    print("Database seeded successfully with default restaurant data!")
