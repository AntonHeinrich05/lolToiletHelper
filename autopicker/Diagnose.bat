@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Zuerst Setup.bat ausfuehren.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" Autopicker.py
echo.
echo Falls schon eine Instanz laeuft, wird keine zweite gestartet.
echo Protokoll: %%LOCALAPPDATA%%\LoLAutopicker\autopicker.log
pause