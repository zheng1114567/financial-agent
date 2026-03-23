@echo off
setlocal
REM MiniBot SSE backend -> http://127.0.0.1:8000 (ASCII only for cmd.exe)
cd /d "%~dp0"
if errorlevel 1 (
  echo ERROR: could not cd to script directory.
  exit /b 1
)

set PYTHONIOENCODING=utf-8
python -m pip install -r "%~dp0requirements.txt" -q
if errorlevel 1 (
  echo WARNING: pip install returned non-zero, continuing anyway...
)

echo.
echo Backend URL  http://127.0.0.1:8000
echo Health       http://127.0.0.1:8000/health
echo.

python "%~dp0src\lib\backend-sse-server.py"
set ERR=%ERRORLEVEL%
if not "%ERR%"=="0" echo ERROR: python exited with code %ERR%
exit /b %ERR%
