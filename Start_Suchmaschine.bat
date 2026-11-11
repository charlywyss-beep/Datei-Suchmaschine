@echo off
chcp 65001 >nul
title Datei-Suchmaschine Pro
cls
echo ========================================================
echo    🚀 Starte Datei-Suchmaschine Pro (Lokale Suche)
echo ========================================================
echo.
echo Server wird initialisiert...
cd /d "%~dp0"
python app.py
pause
