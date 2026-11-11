@echo off
chcp 65001 >nul
title Datei-Suchmaschine Pro - GitHub Update
cls
echo ========================================================
echo    🐙 Datei-Suchmaschine Pro - GitHub Aktualisierung
echo ========================================================
echo.
cd /d "%~dp0"

echo [1/3] Prüfe Git-Status...
git status --short

echo.
echo [2/3] Hole neueste Änderungen von GitHub (git pull)...
git pull

echo.
echo [3/3] Aktualisierung abgeschlossen!
echo.
echo Drücken Sie eine beliebige Taste zum Beenden...
pause >nul
