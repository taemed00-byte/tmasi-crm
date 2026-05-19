@echo off
cd /d "%~dp0"
echo.
echo  Pushing TMASI CRM to GitHub...
echo  ================================
echo.

REM ── Read token from gitignored file ──────────────────────
if not exist "deploy_token.txt" (
    echo  [ERROR] deploy_token.txt not found.
    echo  Create it with your GitHub PAT on the first line.
    pause & exit /b 1
)
set /p GH_TOKEN=<deploy_token.txt

REM ── Clear stale lock files ────────────────────────────────
for %%L in (".git\index.lock" ".git\config.lock" ".git\HEAD.lock") do (
    if exist "%%L" del /f /q "%%L" >nul 2>&1
)

REM ── Set git identity and remote ───────────────────────────
git config user.email "taemed00@gmail.com"
git config user.name "taemed00-byte"
git remote set-url origin https://oauth2:%GH_TOKEN%@github.com/taemed00-byte/tmasi-crm.git

REM ── Stage and commit ─────────────────────────────────────
git add -A
git diff --cached --quiet
if %errorlevel% neq 0 (
    git commit -m "Update TMASI CRM"
)

REM ── Push ─────────────────────────────────────────────────
set GIT_TERMINAL_PROMPT=0
git -c credential.helper= push origin main
if errorlevel 1 (
    echo  [ERROR] Push failed.
    pause & exit /b 1
)

echo.
echo  [OK] Pushed successfully!
echo.
pause
