@echo off
setlocal
cd /d %~dp0
set "TASK_NAME=EMS Inbound Integration Drop"
set "SCRIPT=%~dp0RUN_INBOUND_WINDOWS.bat"
schtasks /Create /F /SC MINUTE /MO 1 /TN "%TASK_NAME%" /TR "\"%SCRIPT%\"" >nul
if errorlevel 1 (
  echo Could not create inbound integration scheduled task.
  exit /b 1
)
echo Created Windows scheduled task: %TASK_NAME%
echo Inbound drop cadence: every 1 minute
echo Configure EMS_INBOUND_ROOT as a machine/user environment variable before the task runs.
