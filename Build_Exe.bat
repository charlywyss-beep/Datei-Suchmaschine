@echo off
chcp 65001 >nul
title Datei-Suchmaschine Pro - EXE Builder
cls
echo ========================================================
echo    📦 Datei-Suchmaschine Pro - Standalone EXE Builder
echo ========================================================
echo.
cd /d "%~dp0"

echo [1/3] Pruefe PyInstaller...
python -m pip install --quiet pyinstaller

echo [2/3] Erstelle Datei-Suchmaschine-Pro.exe...
python -m PyInstaller --name "Datei-Suchmaschine-Pro" --onefile --noconsole --add-data "templates;templates" --add-data "static;static" --hidden-import "send2trash" --hidden-import "jinja2" --hidden-import "werkzeug" app.py

if exist "dist\Datei-Suchmaschine-Pro.exe" (
    echo [3/3] Kopiere Datei-Suchmaschine-Pro.exe ins Hauptverzeichnis...
    copy /y "dist\Datei-Suchmaschine-Pro.exe" "Datei-Suchmaschine-Pro.exe" >nul
    echo.
    echo ========================================================
    echo  [OK] ERFOLGREICH ERSTELLT!
    echo  Datei: %~dp0Datei-Suchmaschine-Pro.exe
    echo.
    echo  Diese .exe laeuft auf JEDEM Windows-PC komplett ohne Python!
    echo  Einfach auf USB-Stick kopieren oder per Mail versenden.
    echo ========================================================
) else (
    echo.
    echo [FEHLER] Erstellung fehlgeschlagen.
)
echo.
pause
