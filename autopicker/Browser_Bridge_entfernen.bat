@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" install_browser.py --remove
pause