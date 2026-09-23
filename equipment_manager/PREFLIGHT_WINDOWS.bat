@echo off
cd /d %~dp0
if not exist .venv (
  echo EMS virtual environment not found. Run START_WINDOWS.bat once first.
  exit /b 1
)
call .venv\Scripts\activate
python preflight.py
if errorlevel 1 (
  echo.
  echo EMS PRE-FLIGHT FAILED. Resolve all FAIL items before production use.
  pause
  exit /b 1
)
echo.
echo EMS PRE-FLIGHT PASSED.
pause
