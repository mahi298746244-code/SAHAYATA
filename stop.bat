@echo off
rem Stops SAHAYATA backend (:8000) and frontend (:5173)
for %%P in (8000 5173) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%P .*LISTENING"') do taskkill /PID %%a /F >nul 2>&1
)
echo SAHAYATA stopped.
ping -n 3 127.0.0.1 >nul
