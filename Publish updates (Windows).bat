@echo off
title Plain Congress - publish updates
cd /d "%~dp0"
echo Plain Congress: publishing the current site to the web.
echo.

if not exist "site\index.html" (
  echo No site to publish yet.
  echo Run a build first: python run_all.py
  echo.
  pause
  exit /b 1
)

where git >nul 2>nul
if errorlevel 1 (
  echo Git is not installed or not on PATH.
  echo Open START_HERE.txt, or ask Claude Code to sort it out.
  echo.
  pause
  exit /b 1
)

git remote get-url origin >nul 2>nul
if errorlevel 1 (
  echo This folder is not connected to GitHub yet.
  echo Ask Claude Code to finish the GitHub Pages setup.
  echo.
  pause
  exit /b 1
)

echo Copying the freshly built site into docs\ ...
copy /Y "site\index.html" "docs\index.html" >nul
if errorlevel 1 (
  echo Could not copy site\index.html into docs\.
  echo Is the site file open in a browser or editor? Close it and try again.
  echo.
  pause
  exit /b 1
)

git add -A docs
git diff --cached --quiet
if not errorlevel 1 (
  echo.
  echo Nothing has changed since the last publish. Site is already up to date.
  echo.
  pause
  exit /b 0
)

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "TODAY=%%a %%b %%c"
echo Saving this version ...
git commit -q -m "Site update %TODAY%"
if errorlevel 1 (
  echo Could not save the update. The message above says why.
  echo.
  pause
  exit /b 1
)

echo Uploading to GitHub ...
git push -q origin main
if errorlevel 1 (
  echo.
  echo The upload failed. The most common causes:
  echo   - not signed in to GitHub yet ^(a sign-in window usually appears^)
  echo   - no internet connection
  echo The version is saved on this computer either way; run this file again to retry.
  echo.
  pause
  exit /b 1
)

echo.
echo Done. The new version is live in about a minute at:
git remote get-url origin
echo.
echo ^(GitHub needs a moment to publish. Refresh the page if you see the old one.^)
echo.
pause
