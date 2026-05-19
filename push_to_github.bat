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
    ".git\MERGE_HEAD"
    ".git\COMMIT_EDITMSG.lock"
) do (
    if exist "%%L" (
        echo  [FIX] Removing %%L...
        del /f "%%L" >nul 2>&1
    )
)

REM ── Configure git identity ────────────────────────────────
git config user.email "taemed00@gmail.com"
git config user.name "taemed00-byte"

REM ── Set PAT-authenticated remote ──────────────────────────
git remote set-url origin https://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@github.com/taemed00-byte/tmasi-crm.git

REM ── Stage everything ──────────────────────────────────────
git add -A
if errorlevel 1 (
    echo  [ERROR] git add failed.
    pause & exit /b 1
)

REM ── Show what's staged ────────────────────────────────────
echo.
echo  Staged changes:
git diff --cached --stat
echo.

REM ── Commit (skip if nothing changed) ──────────────────────
git diff --cached --quiet
if %errorlevel% == 0 (
    echo  [INFO] Nothing new to commit - pushing existing commits.
    goto :push
)
git commit -m "Phase 2: Network, Clients, Documents, Audit Trail, Business Rules Engine"
if errorlevel 1 (
    echo  [ERROR] git commit failed.
    pause & exit /b 1
)

:push
REM ── Push ──────────────────────────────────────────────────
git push origin main
if errorlevel 1 (
    echo  [ERROR] Push failed. Check output above.
    pause & exit /b 1
)

echo.
echo  ================================================
echo   [OK] Pushed! Render will redeploy automatically.
echo   Monitor: https://dashboard.render.com
echo  ================================================
echo.
pause
