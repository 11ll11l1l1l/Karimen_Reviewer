# Equipment Management System

Local Windows desktop equipment-management system. It is intentionally isolated from the Karimen Reviewer application even though it currently lives in the same repository.

## Current first build

- Login page and first-run administrator creation (no default password committed).
- PostgreSQL-ready multi-user database architecture. SQLite is used only as a local/demo fallback when `EMS_DATABASE_URL` is not set.
- Optimistic version checks for equipment, inventory, tickets, and storage records.
- Transactional inventory consumption with row locking on PostgreSQL so two users cannot consume the same last spare.
- Operational dashboard.
- Generic equipment master, hierarchy/location fields, status, disposition, map coordinates.
- PM backlog/schedule table and Excel/CSV backlog import preserving original due dates.
- PM checklist/control-specification Excel/CSV import, including automatic parsing of common ranges, `±`, min/max and pass/fail text.
- Distributed inventory with quantity per location, images, minimum stock, and consume transaction.
- Storage locations with building/floor/area/cabinet/shelf/bin and map coordinates.
- Equipment/floor layout showing equipment and storage locations; part/location search highlights distributed stock locations.
- Issue-ticket workflow.
- Linked documents and network files; opening from the application uses a temporary read-only copy by default.
- Audit log foundation.
- F5 refresh and 30-second dashboard refresh.

## Production database

Install PostgreSQL on a designated always-on LAN PC/server. Do **not** place SQLite on the SMB share.

On each client PC set:

```bat
set EMS_DATABASE_URL=postgresql+psycopg://ems_user:PASSWORD@DB-PC-IP:5432/equipment_management
python main.py
```

The application creates its tables automatically in this initial development build. A controlled migration process should replace auto-create before formal production release.

## First launch

If the database contains no users, the program asks you to create the first administrator account. Passwords are PBKDF2-SHA256 hashed with a random per-user salt.

## Excel PM backlog import

The importer auto-detects common headers such as Equipment ID, PM ID/Name, Due Date, Scheduled Date, Last PM, Status, Assigned To, Estimated Hours, Priority, SOP Path and Report Path. Original due dates are kept. Open/pending rows already past due are marked overdue during import.

## Excel PM step / specification import

The importer supports common columns such as PM ID, Step, Activity, Method, Specification, Unit, Target, Warning Low/High, Control Low/High, LSL/USL, Reaction Plan, SOP Path/Page/Section.

Common specification forms recognized in the initial parser include `10-20`, `10 ~ 20`, `10 to 20`, `10 ± 2`, `<=10`, `>=5`, `10 max`, `5 min`, `PASS`, `OK`, `No damage`, and `No leak`. Ambiguous text is preserved instead of being silently converted.

## Read-only network documents

The app opens linked files by copying them to a local temporary folder, marking the temporary copy read-only, then launching the normal Windows application. For controlled SOP folders, Windows/SMB permissions should also be read-only for ordinary users; application behavior alone cannot prevent editing files directly through Explorer.

## Run from source

```bat
cd equipment_manager
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

`START_WINDOWS.bat` performs this setup automatically for development PCs.

## Still planned

This is the first runnable build, not the completed production system. Next modules are the advanced flexible PM scheduler, PM execution with concurrent step claims, formal disposition/release approvals, endorsements, document revisions, clipboard image capture/annotation, richer dashboards/heatmaps, calibration, parts reservations/PM readiness, reliability analytics, import staging/rollback, granular role permissions, and EXE packaging.
