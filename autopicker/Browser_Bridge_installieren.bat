@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Zuerst Setup.bat ausfuehren.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" install_browser.py
pause