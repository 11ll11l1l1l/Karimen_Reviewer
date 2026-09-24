@echo off
setlocal
cd /d %~dp0
if not exist .venv (
  echo EMS virtual environment not found. Run START_WINDOWS.bat once first.
  exit /b 1
)
call .venv\Scripts\activate
python ems_cli.py dispatch-integrations --limit 500
set "OUTBOUND_RC=%ERRORLEVEL%"
python ems_cli.py process-inbound --limit 200
set "INBOUND_RC=%ERRORLEVEL%"
if not "%OUTBOUND_RC%"=="0" exit /b %OUTBOUND_RC%
exit /b %INBOUND_RC%
