@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Bitte zuerst Setup.bat ausfuehren.
  pause
  exit /b 1
)
start "LoL Autopicker" ".venv\Scripts\pythonw.exe" "%~dp0Autopicker.py"