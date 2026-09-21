@echo off
title The Civic Archive - save the LegiScan key
cd /d "%~dp0"
echo.
echo  This saves your LegiScan API key on this computer, in a file that is never uploaded.
echo  You need the key first: see the steps Claude gave you, or the LegiScan API page,
echo  https://legiscan.com/legiscan  (log in, fill in the short form, copy the key).
echo.
if not exist ".venv\Scripts\python.exe" (
  echo The private Python environment is not set up yet. Run a build first: python run_all.py check
  echo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m states.save_key
if errorlevel 1 (
  echo.
  pause
  exit /b 1
)
echo.
echo  Next: Minnesota's bills and recorded votes can be fetched now. It uses about two of your
echo  30,000 monthly queries and takes a minute or two.
echo.
choice /c YN /m "Fetch them now"
if errorlevel 2 (
  echo.
  echo  Fine. Tell Claude "the key is saved" and it will fetch them.
  echo.
  pause
  exit /b 0
)
echo.
".venv\Scripts\python.exe" run_states.py mn bills
echo.
echo  Done. Tell Claude "the key is saved and the bills are fetched" and it will take it from there.
echo.
pause
