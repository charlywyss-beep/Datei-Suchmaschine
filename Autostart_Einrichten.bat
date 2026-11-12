@echo off
REM Richtet Desktop-Verknuepfung + Autostart ein (Server startet unsichtbar bei jeder Windows-Anmeldung)
cd /d "%~dp0"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $dir = '%~dp0'; $vbs = Join-Path $dir 'Start_Hintergrund.vbs'; $desktop = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut((Join-Path $desktop 'Datei-Suchmaschine Pro.lnk')); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"' + $vbs + '\" open'; $s.WorkingDirectory = $dir; $s.IconLocation = 'shell32.dll,22'; $s.Save(); $startup = [Environment]::GetFolderPath('Startup'); $a = $ws.CreateShortcut((Join-Path $startup 'Datei-Suchmaschine Pro (Server).lnk')); $a.TargetPath = 'wscript.exe'; $a.Arguments = '\"' + $vbs + '\"'; $a.WorkingDirectory = $dir; $a.IconLocation = 'shell32.dll,22'; $a.Save()"

echo.
echo [OK] Desktop-Verknuepfung "Datei-Suchmaschine Pro" erstellt (Doppelklick = Browser oeffnet).
echo [OK] Autostart eingerichtet: Der Server startet ab jetzt unsichtbar mit Windows.
echo.
echo Rueckgaengig machen: Autostart_Entfernen.bat
pause
