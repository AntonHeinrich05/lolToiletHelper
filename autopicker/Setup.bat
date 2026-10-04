@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys; assert sys.version_info >= (3, 11); import tkinter" >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 oder neuer mit Tkinter von python.org installieren.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install .
if errorlevel 1 goto failed
echo.
echo Fertig. Start.bat startet den Autopicker.
echo Browser: Erweiterung laden, danach Browser_Bridge_installieren.bat.
echo Autostart ist freiwillig: Autostart_aktivieren.bat.
pause
exit /b 0
:failed
echo Einrichtung fehlgeschlagen. Die Fehlermeldung oben pruefen.
pause
exit /b 1