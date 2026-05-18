@echo off
setlocal enabledelayedexpansion
title Push TMASI CRM to GitHub
cd /d "%~dp0"

echo.
echo  ===================================================
echo   Push TMASI CRM to GitHub
echo  ===================================================
echo.

git --version >nul 2>&1
if errorlevel 1 (echo  [ERROR] Git not found & pause & exit /b 1)

git config --global user.email "taemed00@gmail.com"
git config --global user.name "Ahmed Farrag"

REM ── Read token from local file (gitignored) ──────────
set TOKEN=
for /f "tokens=*" %%t in (.gh_token) do set TOKEN=%%t
if "!TOKEN!"=="" (echo  [ERROR] .gh_token file not found & pause & exit /b 1)

set "REPO_URL=https://!TOKEN!@github.com/taemed00-byte/tmasi-crm.git"

if exist ".git" rmdir /s /q .git
git init
git branch -M main
git remote add origin !REPO_URL!

echo * text=auto> .gitattributes
echo *.bat text eol=crlf>> .gitattributes
echo *.sh text eol=lf>> .gitattributes

echo  [GIT] Staging and committing...
git add -A
git commit -m "TMASI CRM - update"
if errorlevel 1 (echo  [ERROR] Commit failed & pause & exit /b 1)

echo  [GIT] Pushing to GitHub...
git push -u origin main --force
if errorlevel 1 (echo  [ERROR] Push failed & pause & exit /b 1)

echo.
echo  ===================================================
echo   SUCCESS! GitHub repo updated.
echo  ===================================================
echo.
start "" "https://github.com/taemed00-byte/tmasi-crm"
pause
