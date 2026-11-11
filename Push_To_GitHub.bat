@echo off
chcp 65001 >nul
title Datei-Suchmaschine Pro - GitHub Push
cls
echo ========================================================
echo    🚀 Datei-Suchmaschine Pro - Stand nach GitHub hochladen
echo ========================================================
echo.
cd /d "%~dp0"

echo [1/3] Aktueller Git Branch und Status:
git branch --show-current
git status --short

echo.
echo [2/3] Übertrage aktuellen Stand nach GitHub (git push -u origin main)...
git push -u origin main

echo.
echo [3/3] Abgeschlossen!
echo.
pause
