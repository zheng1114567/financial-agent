@echo off
set PYTHONIOENCODING=utf-8

REM Start backend in new window
echo 🚀 Starting MiniBot backend...
start "MiniBot Backend" cmd /c "cd /d %~dp0 && call start-backend.bat"

REM Wait for backend to bind (naive 3s)
timeout /t 3 /nobreak >nul

REM Start frontend
echo 🌐 Starting MiniBot frontend...
python run.py
