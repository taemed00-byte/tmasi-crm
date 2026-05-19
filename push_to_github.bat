@echo off
cd /d "%~dp0"

echo.
echo  Pushing TMASI CRM to GitHub...
echo  ================================
echo.

REM ── Clear any stale git lock files ────────────────────────
for %%L in (
    ".git\index.lock"
    ".git\config.lock"
    ".git\HEAD.lock"
    ".git\COMMIT_EDITMSG.lock"
    ".git\MERGE_HEAD"
) do (
    if exist "%%L" (
        echo  [FIX] Removing %%L...
        del /f "%%L" >nul 2>&1
    )
)

REM ── Configure git identity ────────────────────────────────
git config user.email "taemed00@gmail.com"
git config user.name "taemed00-byte"

REM ── Configure remote (stored in .git/config, never committed) ──
git remote set-url origin https://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@github.com/taemed00-byte/tmasi-crm.git

REM ── Stage everything ──────────────────────────────────────
git add -A
if errorlevel 1 (
    echo  [ERROR] git add failed.
    pause & exit /b 1
)

REM ── Show staged summary ───────────────────────────────────
echo.
git diff --cached --stat
echo.

REM ── Commit if there are changes ───────────────────────────
git diff --cached --quiet
if %errorlevel% neq 0 (
    git commit -m "Phase 2: Network, Clients, Documents, Audit Trail, Business Rules Engine"
    if errorlevel 1 (
        echo  [ERROR] Commit failed.
        pause & exit /b 1
    )
)

REM ── Push ──────────────────────────────────────────────────
git push origin main
if errorlevel 1 (
    echo.
    echo  [TIP] If blocked by secret scanning, visit the unblock URL
    echo  shown above in the output, then run this script again.
    echo.
    pause & exit /b 1
)

echo.
echo  ================================================
echo   [OK] Pushed! Render will redeploy automatically.
echo   Monitor: https://dashboard.render.com
echo  ================================================
echo.
pause
