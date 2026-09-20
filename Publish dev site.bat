@echo off
title The Civic Archive - publish the draft
cd /d "%~dp0"
echo Publishing the DRAFT site so others can look at it.
echo Your live site is not affected.
echo.
if not exist "site\dev.html" (
  echo No draft built yet. Run "Preview dev site.bat" first.
  echo.
  pause
  exit /b 1
)
if not exist "docs\dev" mkdir "docs\dev"
copy /Y "site\dev.html" "docs\dev\index.html" >nul
if errorlevel 1 (
  echo Could not copy the draft. Is it open in a browser? Close it and retry.
  echo.
  pause
  exit /b 1
)
git add -A docs\dev
git diff --cached --quiet
if not errorlevel 1 (
  echo.
  echo The draft has not changed since last time. Nothing to publish.
  echo.
  pause
  exit /b 0
)
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "TODAY=%%a %%b %%c"
git commit -q -m "Draft site update %TODAY%"
echo Uploading ...
git push -q origin main
if errorlevel 1 (
  echo.
  echo Upload failed - check your internet connection and run this again.
  echo Your work is saved on this computer either way.
  echo.
  pause
  exit /b 1
)
echo.
echo Done. The draft is live in about a minute at:
echo   https://thecivicarchive.github.io/dev/
echo.
pause
