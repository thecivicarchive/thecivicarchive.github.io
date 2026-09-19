@echo off
title Plain Congress kit
cd /d "%~dp0"
echo Plain Congress kit: %cd%
echo.
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where python >nul 2>nul
if errorlevel 1 where py >nul 2>nul
if errorlevel 1 (
  echo Python is not installed yet. Opening the download page...
  start https://www.python.org/downloads/
  echo Install Python. On the FIRST screen tick "Add python.exe to PATH", then Install Now.
  echo Then double-click this file again.
  pause
  exit /b 1
)
where claude >nul 2>nul
if errorlevel 1 (
  echo Installing Claude Code, one time, about a minute...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://claude.ai/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
where claude >nul 2>nul
if errorlevel 1 (
  echo Claude Code did not install. Open START_HERE.txt and follow Step 3 by hand.
  pause
  exit /b 1
)
echo Starting Claude Code.
echo   1. If it asks whether you trust this folder: press Enter for Yes.
echo   2. Paste everything from KICKOFF_PROMPT.txt and press Enter.
echo.
claude
pause
