@echo off
setlocal enabledelayedexpansion
title TMASI CRM
cd /d "%~dp0"

echo.
echo  ===================================================
echo   TMASI CRM  -  Local Development Server
echo  ===================================================
echo.

REM ── 1. Find Python ────────────────────────────────────
set PYTHON=

py -3 --version >nul 2>&1
if not errorlevel 1 (set "PYTHON=py -3" & goto :found_python)

for /f "tokens=2*" %%A in ('reg query "HKCU\SOFTWARE\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr "REG_SZ"') do (
    if exist "%%B" (set "PYTHON=%%B" & goto :found_python)
)
for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr "REG_SZ"') do (
    if exist "%%B" (set "PYTHON=%%B" & goto :found_python)
)
for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr "REG_SZ"') do (
    if exist "%%B" (set "PYTHON=%%B" & goto :found_python)
)

for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python313"
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python310"
    "%LOCALAPPDATA%\Programs\Python\Python39"
    "C:\Python313" "C:\Python312" "C:\Python311" "C:\Python310" "C:\Python39"
    "%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3"
    "C:\miniconda3" "C:\anaconda3" "C:\ProgramData\miniconda3"
) do (
    if exist "%%~D\python.exe" (
        set "PYTHON=%%~D\python.exe"
        set "PATH=%%~D;%%~D\Scripts;%PATH%"
        goto :found_python
    )
)

echo  [ERROR] Python not found.
echo  Please install Python from https://www.python.org/downloads/
echo  Make sure to check "Add Python to PATH" during install.
pause & exit /b 1

:found_python
for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do echo  Found: %%v

REM ── 2. Create .env ────────────────────────────────────
if not exist ".env" (
    if exist ".env.example" (copy ".env.example" ".env" >nul)
    echo  [OK] .env created from template.
)

REM ── 3. Virtual environment ────────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo  [SETUP] Creating virtual environment...
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo  [ERROR] Could not create virtual environment.
        pause & exit /b 1
    )
    echo  [OK] Virtual environment created.
)

set "VPYTHON=%~dp0venv\Scripts\python.exe"
set "PATH=%~dp0venv\Scripts;%PATH%"

REM ── 4. Install / update packages ──────────────────────
echo  [SETUP] Upgrading pip...
"%VPYTHON%" -m pip install --upgrade pip setuptools wheel -q --disable-pip-version-check

echo  [SETUP] Installing packages (first run ~1 min)...
"%VPYTHON%" -m pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo  [RETRY] Retrying with pre-built wheels only...
    "%VPYTHON%" -m pip install -r requirements.txt --only-binary :all: -q --disable-pip-version-check
    if errorlevel 1 (
        echo  [ERROR] Package install failed. Deleting venv so next run starts fresh.
        rmdir /s /q venv
        pause & exit /b 1
    )
)
echo  [OK] Packages ready.

REM ── 5. Uploads directory ──────────────────────────────
if not exist "uploads" mkdir uploads

REM ── 6. Database setup ─────────────────────────────────
echo.
echo  [SETUP] Initialising database...
"%VPYTHON%" -c "from app.database import engine, Base; from app import models; Base.metadata.create_all(bind=engine); print('  [OK] Tables ready')"
if errorlevel 1 (
    echo  [ERROR] Database initialisation failed.
    pause & exit /b 1
)

"%VPYTHON%" -c "from app.startup import run_startup; run_startup(); print('  [OK] Startup done')"
if errorlevel 1 (
    echo  [ERROR] Application startup failed.
    pause & exit /b 1
)

REM ── 7. Launch ─────────────────────────────────────────
echo.
echo  ===================================================
echo   Running at: http://localhost:8000
echo   Login:      admin / admin123
echo   Stop:       Ctrl+C
echo  ===================================================
echo.
start "" cmd /c "timeout /t 2 >nul && start http://localhost:8000"
"%VPYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

echo.
echo  Server stopped.
pause
