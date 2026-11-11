@echo off
chcp 65001 >nul
echo Erstelle Desktop-Verknüpfung für Datei-Suchmaschine Pro...

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $lnk = Join-Path $desktop 'Datei-Suchmaschine Pro.lnk'; $s = $ws.CreateShortcut($lnk); $s.TargetPath = (Join-Path '%~dp0' 'Start_Suchmaschine.bat'); $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,22'; $s.Save()"

echo.
echo [OK] Verknuepfung 'Datei-Suchmaschine Pro' wurde auf dem Desktop erstellt!
ping -n 3 127.0.0.1 >nul
