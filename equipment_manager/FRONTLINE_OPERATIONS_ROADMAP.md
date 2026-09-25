# EMS RC4 — Frontline Operations / Fab Reality

## Intent

RC4 converts the existing production-capable EMS backend into a low-friction manual fab operating tool.

The system remains **manual-entry first**. It does not require MES, SECS/GEM, FDC or automatic alarm ingestion for the core workflow.

Primary operator model:

1. FAB Overview — what is happening now.
2. Operational Calendar — what work is planned and when.
3. Equipment 360 — everything about one tool.
4. Issue / PM / Work Order — execute and record the work.
5. Troubleshooting History — reuse previous checks, results, actions and fixes.
6. Shift Report — copy current state and completed work directly into email.

## Branch ownership

Active implementation branch: `ems/rc4-frontline-a`

Base: `main@288f7b9ab1d1d425dad96297e9dd0b8f7e519caa`

This branch owns these files/surfaces while active:

- `equipment_manager/database.py`
- `equipment_manager/quick_create.py`
- `equipment_manager/incident_workspace.py`
- `equipment_manager/troubleshooting_library.py`
- `equipment_manager/workspaces.py`
- `equipment_manager/pm_template_io.py`
- `equipment_manager/instruction_resolver.py`
- `equipment_manager/pm_execution_workspace.py`
- `equipment_manager/maintenance_planner.py`
- `equipment_manager/equipment_health.py`
- `equipment_manager/smart_map.py`
- `equipment_manager/shift_report.py`
- `equipment_manager/table_productivity.py`
- `equipment_manager/smart_app.py`
- `equipment_manager/main.py`

Other chat instances should avoid editing those paths until this wave is integrated, or work from a separate branch and coordinate before merge.

## Milestones

### M16 — Manual issue capture / lot context — CODED

- Report Issue is the primary manual abnormality flow.
- Only equipment and problem/symptom are required.
- Optional impact, lots, alarm/error code, owner and details.
- Ticket is the human-facing canonical problem record.
- Optional alarm is created and linked inside the same transaction.
- First-class multi-lot links are stored separately while legacy affected-lots text remains populated.
- Issue-linked manual alarms auto-clear when the ticket resolves/closes.

### M17 — Clipboard evidence / troubleshooting knowledge — CODED

- Clipboard screenshot attach is zero-dialog in shared evidence.
- Quick Report Issue can accept a clipboard screenshot before record creation.
- Troubleshooting similarity uses tool, lot, alarm and symptom overlap.
- History exposes check, result, action, root cause, final fix and image evidence count.
- Standalone Troubleshooting History page supports symptom/alarm/lot/check/action/fix search.
- Global search includes lot context.

### M18 — PM Excel template / instructions — CODED

- EMS generates an editable PM Excel template.
- Template imports PM definition, steps/specs and execution requirements.
- Import applies an authoritative controlled revision and retires removed rows.
- Extra supporting sheets may remain in the workbook and are ignored rather than rejected.
- Step references may point to Excel, PowerPoint, PDF or other files.
- Open Instruction resolves embedded EMS instruction first, then effective controlled documents, then direct reference files.
- Per-step Screenshot Required and Comment Required completion rules are imported and enforced.

### M19 — Outlook-like operational scheduling — CODED

- Controlled PM due date is separated from movable calendar slot.
- Baseline, current start/end and planned slot hours are preserved.
- Every PM move/assignment writes schedule audit history.
- Outside-window calendar placement is allowed with a reason; formal due-date deferral remains separate.
- Month/day and Outlook-style week views exist.
- PM blocks can be dragged in 15-minute increments.
- PM/work blocks can be duration-resized.
- Work orders share the same operational calendar.
- Unscheduled engineering work orders appear beside the calendar and can be assigned a slot.
- PM bulk assignment/movement remains available.

### M20 — Connected work execution — CODED

- Calendar opens the real PM/work record rather than a duplicate event.
- PM supports Start / Resume / Pause / Carry Over / Complete.
- One PM execution can contain multiple labor sessions.
- Pause reasons include production request, waiting parts/engineer/vendor, shift end, safety hold and other.
- Focus Step mode supports Previous/Next guided execution.
- Evidence requirements block completion where configured.
- Existing checklist/requirements/parts/readiness/governance remain intact.

### M21 — FAB Overview command center — CODED

- One canonical equipment-health classifier drives FAB state.
- Health considers equipment state, manual tickets, active alarms and abnormal PM results.
- Batched FAB snapshot avoids per-tool query loops.
- Tool badges show active alarms, tickets, PM and work orders.
- Inspector shows lots, current issue/action, owner, alarms and next PM.
- KPI filters highlight critical, attention, planned, offline and normal tools.
- Map auto-refreshes and supports direct Equipment 360, issue, PM and Report Issue actions.

### M22 — Shift / email reporting — CODED

- Copy FAB Status places plain text + HTML on clipboard for Outlook/Teams.
- Copy Dashboard Image copies the complete FAB dashboard image.
- FAB export supports XLSX, CSV and PDF.
- Report includes current state plus completed/recovered issue, PM and work-order activity for the current shift/day.
- Generic engineering tables now support CSV and header-aware clipboard copy in addition to XLSX.

### M23 — Frontline roles / navigation — CODED, POLISH REMAINS

- Added Operator, Manufacturing Technician and Shift Leader role permissions.
- Role-specific navigation profiles reduce the legacy 29-screen menu.
- Operator / technician / manager landing pages prioritize FAB map or My Work.
- Troubleshooting History is exposed to operational roles.
- Legacy/admin/configuration surfaces remain available only to appropriate roles.

## Remaining coding before consolidated validation

1. UX polish for calendar overlap/readability and keyboard behavior.
2. Review all lifecycle deep links after role-based nav hiding.
3. Tighten report preview/print layout for narrow screens.
4. Add focused RC4 regression fixtures for new migrations and manual issue workflow.
5. Update version/release notes once the code-bearing head is frozen.

## Validation policy

The user explicitly deferred broad testing until coding is substantially complete.

Do not mark M15 complete. Real plant UAT/pilot, multi-workstation timing, hardware behavior and site signoff remain pending.

When RC4 coding is frozen, run one consolidated validation cycle:
- SQLite core/regression
- PostgreSQL schema/migration/concurrency
- RC4 manual issue / lot / clipboard flow
- PM template generate/import/revision
- PM completion-evidence rules
- operational calendar drag/resize/multi-entity scheduling
- PM pause/resume/work sessions
- FAB health precedence and reporting
- Windows PySide6 smoke/soak/package
