@echo off
chcp 65001 >nul
setlocal
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (
  echo [FEHLER] Windows .NET C#-Compiler csc.exe wurde nicht gefunden.
  pause
  exit /b 1
)

echo Kompiliere Suchmaschine-Helfer.exe ...
"%CSC%" /nologo /target:winexe /optimize+ ^
  /out:"%~dp0..\Suchmaschine-Helfer.exe" ^
  /reference:System.dll ^
  /reference:System.Drawing.dll ^
  /reference:System.Windows.Forms.dll ^
  /reference:System.Web.Extensions.dll ^
  /reference:Microsoft.VisualBasic.dll ^
  "%~dp0SuchmaschineHelfer.cs"

if errorlevel 1 (
  echo [FEHLER] Kompilierung fehlgeschlagen.
  pause
  exit /b 1
)

echo [OK] Fertig: %~dp0..\Suchmaschine-Helfer.exe
endlocal
