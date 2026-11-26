@echo off
chcp 65001 >nul
setlocal
set "SCRIPT_DIR=%~dp0"
set "HANDLER=%SCRIPT_DIR%open_in_explorer.pyw"

for /f "delims=" %%P in ('where pythonw 2^>nul') do (
    set "PYTHONW=%%P"
    goto :found
)

echo [FEHLER] pythonw.exe wurde nicht gefunden.
pause
exit /b 1

:found
reg add "HKCU\Software\Classes\suchmaschine-explorer" /ve /d "URL:Datei-Suchmaschine Explorer Protokoll" /f >nul
reg add "HKCU\Software\Classes\suchmaschine-explorer" /v "URL Protocol" /d "" /f >nul
reg add "HKCU\Software\Classes\suchmaschine-explorer\shell\open\command" /ve /d "\"%PYTHONW%\" \"%HANDLER%\" \"%%1\"" /f >nul

echo.
echo [OK] Explorer-Protokoll (suchmaschine-explorer://) wurde erfolgreich eingerichtet!
echo Handler: "%PYTHONW%" "%HANDLER%"
echo.
pause
