# Equipment Management System

Local Windows desktop equipment-management system isolated under `equipment_manager/` from the Karimen Reviewer application.

## Current build

- Login page and first-run administrator creation; no default password is committed.
- PostgreSQL-ready multi-user architecture. SQLite remains local/demo fallback only.
- Optimistic version checks on shared records and transactional row locking on PostgreSQL for critical inventory/disposition operations.
- Equipment master, hierarchy/location fields, status, disposition and map coordinates.
- Operational dashboard with 30-second refresh.
- PM definitions with interval/one-time/event scheduling, frequency units, original-due vs last-completion anchoring, early/grace windows, workload hours, required people/skill/parts and SOP link.
- PM backlog import from Excel/CSV preserving original historical due dates.
- PM checklist/control-spec import from Excel/CSV with range, `±`, min/max and pass/fail parsing plus controlled revisions.
- PM execution screen with recorded measurements, automatic warning/control/spec result classification, completion validation, and clipboard-image evidence capture.
- PM workload forecast and next-PM generation from configured scheduling rules.
- Issue-ticket creation.
- Formal equipment disposition history with restrictions, release criteria, related ticket and approval field.
- Endorsement/handover records with acknowledgement.
- Distributed inventory with quantity per storage location, image paths, minimum stock and transactional consumption history.
- Equipment/storage layout with inventory location highlighting.
- Linked documents/network files opened through temporary read-only copies by default.
- Audit-log foundation.

## Internal verification performed before this build was pushed

The core was executed against a temporary SQLite database and passed tests covering login/password verification, stale-record conflict rejection, Excel backlog import, control-spec parsing/revision, PM scheduling calculations, PM execution/completion, distributed inventory consumption without negative stock, tickets, disposition, endorsement acknowledgement, read-only document copying, dashboard counts, and Python syntax compilation of all three source files.

The current execution environment does not contain PySide6, so the Qt desktop window itself was syntax-compiled but not rendered here. Runtime GUI verification must be done on a Windows PC after installing `requirements.txt`.

## Production database

Install PostgreSQL on a designated always-on LAN PC/server. Do **not** place SQLite on the SMB share.

Set on each client PC, for example:

```bat
set EMS_DATABASE_URL=postgresql+psycopg://ems_user:password@DATABASE-PC/equipment_management
set EMS_FILE_ROOT=\\FILESERVER\EquipmentManagement
python main.py
```

All normal linked-file opening is read-only by default. For controlled SOP/specification folders, also enforce read-only access with Windows/SMB permissions because application behavior alone cannot stop users editing files directly outside the app.
