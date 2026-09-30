@echo off
title The Civic Archive - save the FEC (api.data.gov) key
cd /d "%~dp0"
echo.
echo  This saves your free api.data.gov key on this computer, in a file that is never uploaded.
echo  On The Ballot uses it to look up each campaign's own website at the FEC, so candidates'
echo  photos can be found there. Sign up first at https://api.data.gov/signup/ (it is free);
echo  the key arrives by e-mail.
echo.
if not exist ".venv\Scripts\python.exe" (
  echo The private Python environment is not set up yet. Run a build first: python run_all.py check
  echo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m ballot.save_fec_key
if errorlevel 1 (
  echo.
  pause
  exit /b 1
)
echo.
echo  Done. Tell Claude "the FEC key is saved" and it will look up the campaigns' websites.
echo.
pause
