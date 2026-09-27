@echo off
cd /d %~dp0

rem Isolated demo mode: never uses the production/shared-folder database.
set EMS_DEMO_MODE=1
set EMS_DATA_MODE=
set EMS_SHARED_ROOT=
set EMS_DATABASE_URL=sqlite:///equipment_manager_demo.db
set EMS_FILE_ROOT=%~dp0demo_files

if not exist .venv (
  py -m venv .venv
  call .venv\Scripts\activate
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)

python smart_app.py
