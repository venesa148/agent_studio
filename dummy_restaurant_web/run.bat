@echo off
title Dummy Restaurant Web Server (Savoria Bistro)
echo ========================================================
echo   SAVORIA BISTRO & RESTO - DUMMY WEB & REST API
echo ========================================================
echo.
echo Menjalankan server lokal pada http://localhost:5000 ...
echo Database SQLite: restaurant.db
echo Swagger Docs: http://localhost:5000/docs
echo.
echo Tekan Ctrl+C untuk menghentikan server.
echo.

cd /d "%~dp0"
python -m uvicorn main:app --host 0.0.0.0 --port 5000 --reload

pause
