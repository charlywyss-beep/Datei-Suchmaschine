@echo off
REM Entfernt den Autostart-Eintrag (Desktop-Verknuepfung bleibt erhalten)
powershell -NoProfile -Command "$p = Join-Path ([Environment]::GetFolderPath('Startup')) 'Datei-Suchmaschine Pro (Server).lnk'; if (Test-Path $p) { Remove-Item $p -Force; 'Autostart entfernt.' } else { 'Kein Autostart-Eintrag vorhanden.' }"
pause
