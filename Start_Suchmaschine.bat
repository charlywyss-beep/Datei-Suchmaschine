@echo off
chcp 65001 >nul
title Datei-Suchmaschine Pro
cls
echo ========================================================
echo    🚀 Datei-Suchmaschine Pro (v1.6.1)
echo ========================================================
echo.
cd /d "%~dp0"

REM Eventuelle alte Instanzen auf Port 5005 beenden (sprachunabhängig)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5005"') do (
    if not "%%a"=="0" taskkill /F /PID %%a >nul 2>&1
)

echo Starte Server...
python app.py
pause
