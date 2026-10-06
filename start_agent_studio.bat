@echo off
title Agent Studio Launcher
echo =========================================
echo       Starting Agent Studio...
echo =========================================

echo.
echo [1/3] Starting Backend (FastAPI)...
start "Agent Studio Backend" cmd /k "cd /d "%~dp0backend" && python run.py"

echo.
echo [2/3] Starting Frontend (Next.js)...
start "Agent Studio Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo [3/3] Waiting for services to initialize...
timeout /t 6 /nobreak > nul

echo.
echo Opening browser at http://localhost:3000...
start http://localhost:3000

echo.
echo Agent Studio has been launched successfully!
echo You can close this launcher window.
