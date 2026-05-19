@echo off
cd /d "%~dp0"
echo.
echo  TMASI CRM — Fix git config and push
echo  =====================================
echo.

REM ── Kill any background git processes ─────────────────────
taskkill /f /im git.exe >nul 2>&1
timeout /t 1 >nul

REM ── Remove ALL git lock files ─────────────────────────────
for %%L in (
    ".git\index.lock"
    ".git\config.lock"
    ".git\HEAD.lock"
    ".git\COMMIT_EDITMSG.lock"
    ".git\MERGE_HEAD"
    ".git\MERGE_MSG"
) do (
    if exist "%%L" (
        echo  [FIX] Removing %%L
        del /f /q "%%L" >nul 2>&1
    )
)

REM ── Rewrite .git\config from scratch ─────────────────────
echo  [FIX] Writing fresh .git\config...
(
echo [core]
echo     repositoryformatversion = 0
echo     filemode = false
echo     bare = false
echo     logallrefupdates = true
echo     symlinks = false
echo     ignorecase = true
echo [remote "origin"]
echo     url = https://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@github.com/taemed00-byte/tmasi-crm.git
echo     fetch = +refs/heads/*:refs/remotes/origin/*
echo [branch "main"]
echo     remote = origin
echo     merge = refs/heads/main
echo [user]
echo     name = taemed00-byte
echo     email = taemed00@gmail.com
) > ".git\config"

echo  [OK] git config written.
echo.

REM ── Verify git works now ──────────────────────────────────
git status >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] git still broken after config fix.
    pause & exit /b 1
)

REM ── Stage and commit everything ───────────────────────────
git add -A
if errorlevel 1 (
    echo  [ERROR] git add failed.
    pause & exit /b 1
)

echo  Staged files:
git diff --cached --stat
echo.

git diff --cached --quiet
if %errorlevel% neq 0 (
    git commit -m "Phase 2: Network, Clients, Documents, Audit, Business Rules + fix UserRole.clinic_admin"
    if errorlevel 1 (
        echo  [ERROR] Commit failed.
        pause & exit /b 1
    )
) else (
    echo  [INFO] No changes to commit, pushing existing commits...
)

REM ── Push ──────────────────────────────────────────────────
echo  Pushing to GitHub...
git push origin main
if errorlevel 1 (
    echo  [ERROR] Push failed. See above.
    pause & exit /b 1
)

echo.
echo  ================================================
echo   [OK] Pushed successfully!
echo   Render will redeploy automatically.
echo   Monitor: https://dashboard.render.com
echo  ================================================
echo.
pause
