@echo off
chcp 65001 >nul
title Datei-Suchmaschine Pro
cls
echo ========================================================
echo    🚀 Datei-Suchmaschine Pro (v1.5.2)
echo ========================================================
echo.
cd /d "%~dp0"

REM Eventuelle alte Instanzen auf Port 5005 beenden
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5005" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Starte Server...
python app.py
pause
