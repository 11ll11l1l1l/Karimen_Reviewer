## Full-production program

The product/workflow transformation is tracked in:

- `FULL_PRODUCTION_ROADMAP.md` — milestone definitions, deliverables, dependencies and acceptance gates.
- `PRODUCTION_PROGRESS.md` — current milestone state, immediate execution order and standing development-report format.

A milestone is not complete merely because a backend method or button exists. The roadmap Definition of Done requires the user workflow, interconnectivity, evidence/Office behavior, testing and acceptance gate to be satisfied.

# Equipment Management System

Local Windows desktop equipment-management system isolated under `equipment_manager/` from the Karimen Reviewer application. The production-core refactor now separates governed domain rules into `domain.py` instead of keeping all behavior inside GUI/database CRUD code.

## Current build

### Release-candidate controls

- Formal equipment qualification protocols have controlled revisions; each run freezes the exact protocol/check set used for execution.
- Qualification requires completed passing checks, independent verification, and an independent final approver. Optional validity periods support qualification expiry.
- Equipment in Qualification state/disposition cannot pass final release approval without a current approved qualification run.
- Existing pre-governed equipment and tickets receive one idempotent baseline event on upgrade so reliability and lifecycle history start from a known state.
- `PREFLIGHT_WINDOWS.bat` validates database/schema access, file/attachment writeability, backup path readiness and PostgreSQL backup tooling before site rollout.
- `INSTALL_DAILY_BACKUP_WINDOWS.bat` can install an optional daily Windows backup task; the backup destination honors `EMS_BACKUP_ROOT`.
- See `PRODUCTION_DEPLOYMENT.md` for the deployment, upgrade, backup/restore and site-acceptance runbook.

### Final production hardening

- Authentication now records login attempts and applies timed lockout after repeated password failures. Successful login, administrator unlock, or password reset clears the lockout state.
- The Administration screen exposes recent login attempts and explicit account unlock.
- Controlled documents are separate from ordinary linked evidence. Controlled revisions are SHA-256 fingerprinted, require independent approval, support effective/expiry dates, and automatically supersede the previous effective revision.
- Effective controlled documents are integrity-checked before read-only opening; file changes after registration block approval/opening.
- Database backups are verified at creation: SQLite uses the native backup API plus `PRAGMA integrity_check`; PostgreSQL uses custom-format `pg_dump` plus `pg_restore --list` verification.
- Administrators can create and verify database backups from the desktop; `BACKUP_WINDOWS.bat` provides a simple Windows operator path.
- EMS CI includes PostgreSQL 16 transaction tests and a Windows runner that installs the full desktop dependencies and launches both PySide6 shells offscreen.

### Production completion Wave 2

- PM deferrals now use a controlled request → independent approve/reject workflow. The schedule is not changed until approval, and every request includes reason, risk assessment and mitigation.
- Equipment reliability is calculated from governed state history: availability, total/planned/unplanned downtime, failure count, MTTR and MTBF.
- Serialized equipment components/modules have parent-child hierarchy, part/serial identity, life-limit/usage fields and permanent install/remove history.
- Equipment usage meters support monotonic readings plus explicit counter resets with audit history.
- Usage/cycle PM triggers automatically create maintenance tasks at meter thresholds while preventing duplicate open work.
- Meter resets atomically rebase future usage-PM thresholds.
- Database startup now fails fast on schema drift instead of silently running against an incompatible existing schema.
- EMS CI now runs the complete regression suite against SQLite plus a real PostgreSQL 16 service.

### Production-core state governance

- Equipment operational state is no longer editable as ordinary master data.
- State changes follow an explicit transition graph with reason-code and evidence requirements.
- Downtime/waiting states require accountable ownership; failure/waiting states require linked issue tickets.
- Scheduled PM transitions require a related PM task; qualification and decommissioning use dedicated reasons.
- Production entry is blocked while the equipment disposition does not permit operation.
- Every state change is version-checked and written to the append-only `equipment_state_events` timeline plus the audit log in the same transaction.
- PostgreSQL state transitions acquire a row lock so two users cannot independently transition the same tool at the same time.
- Equipment creation now creates the initial state event; ordinary master-data edits cannot bypass status/disposition workflows.
- Dedicated EMS CI compiles the equipment module and runs state-machine unit + database integration tests.

### Governed incident lifecycle

- Ticket status is no longer editable as a free-form field in the issue editor.
- Tickets follow a controlled lifecycle: Open → assignment/investigation → waiting/monitoring → resolution → verification → closure.
- Resolution requires documented root cause and corrective action; closure additionally requires documented verification.
- Reopen, cancellation, and failed-verification transitions require explicit lifecycle notes.
- Ticket transitions are version-checked, PostgreSQL row-locked, evented in `ticket_state_events`, and audited in the same transaction.
- Troubleshooting history and lifecycle history are shown separately so engineering evidence is not confused with administrative state changes.

### Controlled return-to-service

- Release request, verification and approval actions are individually audited with workstation attribution.
- Final release approval requires an independent approver who is neither the requester nor the verifier.
- Release approval remains blocked while P1/P2 equipment tickets are open.
- Release records and active equipment disposition are updated atomically.

### Frozen PM execution specifications

- Starting a PM creates an immutable execution snapshot of the active controlled checklist/spec revision.
- A PM already in progress continues against the specification revision it started with even if engineering publishes a newer revision.
- PM results are classified again in the database from the frozen limits; a client cannot force a PASS by submitting a forged result string.
- Results for steps that are not part of the frozen execution checklist are rejected.
- Completed PM executions are read-only and cannot accept later result edits.
- PM completion verifies that every frozen step has a result and blocks completion on specification/control failures or invalid steps.


- Login page and first-run administrator creation; no default password is committed.
- PostgreSQL-ready multi-user architecture. SQLite remains a local/demo fallback only and must not be placed on the shared drive.
- Role-based permissions plus per-user allow/deny overrides. Administrator UI supports user creation, enable/disable, role changes, password resets, and granular overrides.
- Optimistic version checks for shared records and transactional PostgreSQL row locking for critical stock/disposition/release operations.
- Generic equipment master, hierarchy/location fields, status, disposition and map coordinates.
- Operational dashboard with PM, issues, inventory, disposition, release, reservation and endorsement counts.
- Interactive facility layout editor: equipment and storage points can be dragged and saved; a per-building/floor background image can be linked; inventory part searches highlight storage locations.
- PM definitions with interval/one-time/event scheduling, frequency units, original-due vs last-completion anchoring, early/grace windows, workload hours, required people/skill/parts and SOP link.
- PM backlog import from Excel/CSV preserving original historical due dates.
- Bulk PM backlog copy/paste directly from Excel-compatible tabular clipboard data.
- PM checklist/control-spec import from Excel/CSV or clipboard with range, `±`, min/max and pass/fail parsing plus controlled revisions.
- PM execution screen with measurements, automatic warning/control/spec classification, clipboard-image evidence capture, completion validation, and blocking of failed/invalid controlled steps.
- PM workload forecast, next-PM generation, and required-parts readiness checks.
- Issue-ticket workflow with structured investigation history: observation → check → result → conclusion → action → evidence.
- Formal equipment disposition history with restrictions, release criteria and related tickets.
- Equipment release request, verification and approval workflow. Release requires all verification checks and is blocked while real P1/P2 tickets remain open.
- Endorsement/handover records with acknowledgement.
- Distributed inventory with quantity per storage location, storage images, minimum stock, transactional consumption history and reservations.
- Reservations calculate unreserved availability so planned PM work cannot double-book the same spare stock.
- Linked documents/network files opened through temporary read-only copies by default.
- Audit-log foundation and F5/manual refresh plus dashboard periodic refresh.

## Internal verification performed before push

The core was executed against temporary SQLite databases and passed tests covering:

- login/password verification;
- role permissions and per-user overrides;
- stale-record conflict rejection;
- equipment/map coordinate updates;
- layout background persistence;
- Excel/clipboard backlog migration preserving original due dates;
- control-spec parsing and PM result classification;
- PM scheduling calculations and month-end handling;
- PM execution/completion;
- prevention of PM closure with control/spec/Pass-Fail failures;
- distributed inventory consumption without negative stock;
- stock reservations and reservation release;
- PM parts-readiness calculations;
- ticket creation and structured investigation history;
- disposition and release verification/approval;
- prevention of equipment release with an open P1/P2 ticket;
- endorsement acknowledgement;
- read-only document copying;
- dashboard counters; and
- Python syntax compilation of all three source files.

The current execution environment does not contain PySide6, so the Qt desktop window itself is syntax-compiled but cannot be rendered here. Runtime GUI verification still needs to be done on a Windows PC after installing `requirements.txt`.

## Production database

Install PostgreSQL on a designated always-on LAN PC/server. Do **not** place SQLite on the SMB share.

On each client PC, configure the shared database and normal file-server root, for example:

```bat
set EMS_DATABASE_URL=postgresql+psycopg://ems_user:password@DATABASE-PC/equipment_management
set EMS_FILE_ROOT=\\FILESERVER\EquipmentManagement
python main.py
```

All normal linked-file opening is read-only by default. For controlled SOP/specification folders, also enforce read-only access with Windows/SMB permissions because application behavior alone cannot stop a user from editing files directly outside the app.
