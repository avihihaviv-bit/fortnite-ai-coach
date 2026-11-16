@echo off
REM Fortnite AI Coach - run from source on Windows.
REM First run creates a virtual environment and installs dependencies (needs internet, ~2-5 min).
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Install Python 3.12 from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation.
  pause
  exit /b 1
)
if not exist .venv (
  echo Creating virtual environment...
  py -3 -m venv .venv || goto :error
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt || goto :error
)
set PYTHONPATH=%~dp0src
.venv\Scripts\python -m fortnite_coach
exit /b 0
:error
echo Something failed. See the messages above.
pause
exit /b 1
