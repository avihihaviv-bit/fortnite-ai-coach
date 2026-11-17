@echo off
REM Build FortniteAICoach-Setup-<version>.exe on this Windows PC.
REM Needs: Python 3.12 (py launcher), internet, and Inno Setup 6 (https://jrsoftware.org/isdl.php) for the installer step.
setlocal
cd /d "%~dp0"

where py >nul 2>nul || (echo Python is not installed. Install Python 3.12 from https://www.python.org/downloads/ & goto :fail)
if not exist .venv-build (
  echo [1/6] Creating build environment...
  py -3.12 -m venv .venv-build || goto :fail
)
set PY=.venv-build\Scripts\python.exe
echo [2/6] Installing dependencies...
%PY% -m pip install --upgrade pip >nul || goto :fail
%PY% -m pip install -r requirements-dev.txt || goto :fail

echo [3/6] Downloading and verifying ffmpeg...
if not exist vendor\ffmpeg\ffmpeg.exe (
  powershell -NoProfile -ExecutionPolicy Bypass -File packaging\fetch_ffmpeg.ps1 || goto :fail
)

echo [4/6] Running tests...
set QT_QPA_PLATFORM=offscreen
set PATH=%~dp0vendor\ffmpeg;%PATH%
%PY% -m pytest -q || goto :fail
set QT_QPA_PLATFORM=

echo [5/6] Building the app with PyInstaller...
%PY% -m PyInstaller packaging\fortnite_coach.spec --noconfirm || goto :fail
dist\FortniteAICoach\FortniteAICoach.exe --self-test --out dist\selftest.json
if errorlevel 1 (echo Self-test FAILED, see dist\selftest.json & goto :fail)
echo Self-test passed.

echo [6/6] Building the installer...
for /f %%v in ('%PY% -c "import sys; sys.path.insert(0, 'src'); import fortnite_coach; print(fortnite_coach.__version__)"') do set APPVER=%%v
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup 6 not found. The app itself is ready in dist\FortniteAICoach\
  echo Install Inno Setup 6 to also build the Setup.exe installer.
  goto :done
)
%ISCC% /DAppVersion=%APPVER% packaging\installer.iss || goto :fail
echo.
echo Installer ready: dist\installer\FortniteAICoach-Setup-%APPVER%.exe
:done
pause
exit /b 0
:fail
echo BUILD FAILED. See the messages above.
pause
exit /b 1
