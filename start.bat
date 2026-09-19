@echo off
rem ============================================================
rem  SAHAYATA - start backend (:8000) + frontend (:5173) + browser
rem  Double-click this file after restarting your PC.
rem ============================================================
setlocal
cd /d "%~dp0"

echo [1/3] Starting backend API...
start "SAHAYATA backend" /min cmd /c "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [2/3] Starting frontend dev server...
start "SAHAYATA frontend" /min cmd /c "cd frontend && npm run dev -- --port 5173 --strictPort"

echo [3/3] Waiting for servers...
ping -n 9 127.0.0.1 >nul

start "" http://localhost:5173

echo.
echo   SAHAYATA is running!
echo     App        : http://localhost:5173
echo     API docs   : http://127.0.0.1:8000/docs
echo.
echo   Demo logins (password: demo12345)
echo     Citizen    : aarti.demo@sahayata.in
echo     Officer    : officer.demo@sahayata.in
echo.
echo   To stop everything, run stop.bat or close the two
echo   minimized windows labeled "SAHAYATA".
echo.
ping -n 11 127.0.0.1 >nul
