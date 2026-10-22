@echo off
title Savoria Bistro - Online Hosting via TryCloudflare
echo =====================================================================
echo    SAVORIA BISTRO - DUMMY WEB & DATABASE (TRYCLOUDFLARE HOSTING)
echo =====================================================================
echo.
echo 1. Menjalankan Server FastAPI Lokal (Port 5000)...
start "Savoria Bistro Server (Local: 5000)" cmd /k "cd /d "%~dp0" && python -m uvicorn main:app --host 0.0.0.0 --port 5000 --reload"

echo 2. Menghubungkan ke Cloudflare Quick Tunnel (Gratis, HTTPS Public)...
echo    Tunggu beberapa detik, Cloudflare akan menampilkan link publik:
echo    (Contoh: https://xxxx-xxxx-xxxx.trycloudflare.com)
echo.
echo =====================================================================
echo TIPS MELIHAT DATA MASUK KE DATABASE:
echo - Di web, klik menu "Admin Resto" -> tab "Live DB Inspector"
echo - Atau buka URL: https://[link-trycloudflare]/api/db-status
echo - Atau buka file restaurant.db di VS Code / DB Browser for SQLite
echo =====================================================================
echo.

cd /d "%~dp0"
.\cloudflared.exe tunnel --url http://localhost:5000

pause
