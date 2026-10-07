@echo off
setlocal
cd /d "%~dp0"
set "PYEXE="
call :find_python
if defined PYEXE goto have_python

echo Kein passendes Python gefunden. Python 3.12 wird jetzt heruntergeladen und installiert ...
set "PYINST=%TEMP%\python-3.12.10-amd64.exe"
curl.exe -L --fail -o "%PYINST%" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
if errorlevel 1 goto try_winget
echo Installation laeuft (Fenster von Python abwarten) ...
"%PYINST%" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_tcltk=1 Include_test=0 Include_doc=0
if errorlevel 1 goto try_winget
goto refresh_path

:try_winget
echo Direkter Download fehlgeschlagen, Versuch ueber winget ...
winget install -e --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
if errorlevel 1 goto nopython

:refresh_path
set "PATH=%LOCALAPPDATA%\Programs\Python\Launcher;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
call :find_python
if not defined PYEXE goto nopython

:have_python
echo Verwende Python: %PYEXE%
if not exist ".venv\Scripts\python.exe" "%PYEXE%" -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install .
if errorlevel 1 goto failed
echo.
echo Fertig. Der Autopicker wird jetzt gestartet ...
start "LoL Autopicker" ".venv\Scripts\pythonw.exe" "%~dp0Autopicker.py"
echo.
echo Browser-Bridge: Die Erweiterung zuerst im Browser laden (README Abschnitt 3),
echo danach hier mit J die Verbindung einrichten. Spaeter geht das jederzeit mit Browser_Bridge_installieren.bat.
choice /C JN /N /M "Browser-Bridge jetzt einrichten? [J/N] "
if errorlevel 2 goto done
".venv\Scripts\python.exe" install_browser.py
:done
echo.
echo Naechster Start: Start.bat. Autostart ist freiwillig: Autostart_aktivieren.bat.
pause
exit /b 0

:find_python
for %%C in ("py -3.13" "py -3.12" "py -3.11" "py -3" "python") do (
  for /f "delims=" %%I in ('%%~C -c "import sys; assert sys.version_info >= (3, 11); import tkinter; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
  if defined PYEXE exit /b 0
)
for %%P in ("%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "%ProgramFiles%\Python313\python.exe" "%ProgramFiles%\Python312\python.exe" "%ProgramFiles%\Python311\python.exe") do (
  if exist %%P (
    %%P -c "import sys; assert sys.version_info >= (3, 11); import tkinter" >nul 2>&1 && set "PYEXE=%%~P"
  )
  if defined PYEXE exit /b 0
)
exit /b 1

:nopython
echo.
echo Python konnte nicht automatisch installiert werden.
echo Bitte Python 3.12 von https://www.python.org/downloads/windows/ installieren
echo ("Add python.exe to PATH" anhaken), danach Setup.bat erneut starten.
pause
exit /b 1

:failed
echo Einrichtung fehlgeschlagen. Die Fehlermeldung oben pruefen.
pause
exit /b 1
