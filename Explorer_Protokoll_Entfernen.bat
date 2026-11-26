@echo off
chcp 65001 >nul
reg delete "HKCU\Software\Classes\suchmaschine-explorer" /f >nul 2>&1
echo.
echo [OK] Explorer-Protokoll (suchmaschine-explorer://) wurde entfernt.
echo.
pause
