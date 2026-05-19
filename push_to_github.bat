@echo off
cd /d "%~dp0"

echo.
echo  Pushing TMASI CRM to GitHub...
echo  ================================
echo.

REM ── Clear any stale git lock files ────────────────────────
if exist ".git\index.lock" (
    echo  [FIX] Removing stale index.lock...
    del /f ".git\index.lock"
)
if exist ".git\MERGE_HEAD" (
    del /f ".git\MERGE_HEAD" >nul 2>&1
)

REM ── Stage everything ──────────────────────────────────────
git add -A

REM ── Commit (skip if nothing changed) ──────────────────────
git diff --cached --quiet
if %errorlevel% == 0 (
    echo  [INFO] Nothing new to commit - pushing existing commits.
) else (
    git commit -m "Phase 1: Case Management, Finance, Reports + extended models"
)

REM ── Push ──────────────────────────────────────────────────
git push origin main

echo.
if %errorlevel% == 0 (
    echo  [OK] Pushed to GitHub. Render will deploy automatically.
) else (
    echo  [ERROR] Push failed. Check output above.
)
echo.
pause
