@echo off
setlocal
cd /d "%~dp0"
title JARVIS - Setup
color 0B
echo ========================================
echo       JARVIS ORGANIZED INSTALLER
echo ========================================
where py >nul 2>&1
if errorlevel 1 (
  where uv >nul 2>&1
  if errorlevel 1 (
    echo Python launcher or uv was not found. Install Python 3.11 or 3.12 and enable PATH.
    pause
    exit /b 1
  )
)
if not exist .venv\Scripts\python.exe call :create_venv
if errorlevel 1 goto fail
if not exist .venv\Scripts\python.exe goto fail
.venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 13) else 1)"
if errorlevel 1 (
  echo This virtual environment uses an unsupported Python version:
  .venv\Scripts\python.exe --version
  echo JARVIS requires Python 3.11 or 3.12.
  echo Rename the .venv folder and run SETUP.bat again.
  goto fail
)
echo Setup directory: %CD%
echo Virtual environment:
.venv\Scripts\python.exe -c "import sys, platform; print(sys.executable); print(sys.version); print(platform.machine())"
.venv\Scripts\python.exe -m pip --version
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
if not exist .env copy .env.example .env >nul

echo.
echo Installing voice, speech recognition, and wake-word support...
.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
if errorlevel 1 echo WARNING: Voice dependencies failed. Check the error above.

echo.
echo Installing Windows desktop-control support...
.venv\Scripts\python.exe -m pip install -r requirements-control.txt
if errorlevel 1 echo WARNING: Desktop-control dependencies failed. Check the error above.

echo.
echo Installing face-recognition and camera support...
.venv\Scripts\python.exe -m pip install -r requirements-face.txt
if errorlevel 1 echo WARNING: Face/camera dependencies failed. Face recognition may be unavailable.

echo.
echo Installing hand-gesture recognition support...
.venv\Scripts\python.exe -m pip install -r requirements-gestures.txt
if errorlevel 1 echo WARNING: Gesture dependencies failed. Gestures may be unavailable.

echo.
where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama was not found. Install it from https://ollama.com/download.
) else (
  echo Ollama detected.
  echo To install screen vision later, run: ollama pull qwen2.5vl:7b
)

echo.
echo Setup finished.
echo To enroll or reset the Owner face profile, use the face enrollment/reset options documented by this project.
echo Starting JARVIS...
call LAUNCH.bat
exit /b 0

:create_venv
set "PYTHON_EXE="
where py >nul 2>&1
if not errorlevel 1 (
  py -3.12 --version >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
  ) else (
    py -3.11 --version >nul 2>&1
    if not errorlevel 1 for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
  )
)
if not defined PYTHON_EXE (
  where uv >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%P in ('uv python find 3.12 2^>nul') do set "PYTHON_EXE=%%P"
    if not defined PYTHON_EXE for /f "delims=" %%P in ('uv python find 3.11 2^>nul') do set "PYTHON_EXE=%%P"
  )
)
if not defined PYTHON_EXE (
  echo Python 3.11 or 3.12 is required to create the virtual environment.
  exit /b 1
)
"%PYTHON_EXE%" -m venv .venv
exit /b %errorlevel%

:fail
echo Setup failed. See the error above.
pause
exit /b 1
