@echo off
cd /d %~dp0
if not exist .venv (
  echo EMS virtual environment not found. Run START_WINDOWS.bat once first.
  exit /b 1
)
if "%EMS_INBOUND_ROOT%"=="" (
  echo EMS_INBOUND_ROOT is not configured.
  exit /b 2
)
call .venv\Scripts\activate
python inbound_drop.py
