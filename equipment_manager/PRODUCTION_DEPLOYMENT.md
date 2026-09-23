# Equipment Management System — Production Deployment Runbook

This runbook is for the Windows/PySide6 Equipment Management System under `equipment_manager/`.

## Production topology

Use PostgreSQL on an always-on LAN server for shared multi-user operation. SQLite is only for local/demo use. Store evidence, linked files, controlled documents, layout images and attachments on a normal Windows/SMB file server with operating-system permissions appropriate to the site.

Recommended environment variables on every EMS workstation:

```bat
set EMS_DATABASE_URL=postgresql+psycopg://ems_user:CHANGE_THIS@DATABASE-PC:5432/equipment_management
set EMS_FILE_ROOT=\\FILESERVER\EquipmentManagement
set EMS_BACKUP_ROOT=\\BACKUPSERVER\EquipmentManagementBackups
```

Do not place a SQLite database on an SMB share.

## First production deployment

1. Install PostgreSQL 16 or a currently supported PostgreSQL release on the designated database server.
2. Create a dedicated EMS database and least-privilege application login.
3. Create the file root and backup root. Confirm the EMS workstation accounts have the intended access.
4. Set `EMS_DATABASE_URL`, `EMS_FILE_ROOT` and `EMS_BACKUP_ROOT`.
5. Run `START_WINDOWS.bat` once to create the virtual environment and install the desktop dependencies.
6. Run `PREFLIGHT_WINDOWS.bat`. Production rollout should not proceed with a FAIL result. SQLite produces a WARN by design.
7. Launch the application and create the first administrator. No default administrator password is shipped.
8. Configure roles and permission overrides.
9. Run one verified manual backup from Administration.
10. Optionally run `INSTALL_DAILY_BACKUP_WINDOWS.bat` to create the 02:00 Windows scheduled backup task.
11. Perform a restore drill into a separate scratch database before declaring the deployment protected.

## Upgrade behavior

The current production-core and release-candidate upgrades add new controlled tables without removing existing operational tables. SQLAlchemy creates missing additive tables. Startup then checks that all required tables and columns are present; an incompatible schema fails fast instead of allowing partially working operation.

When upgrading a pre-governed database, EMS automatically creates exactly one baseline equipment-state event and one baseline ticket-lifecycle event for records that have no event history. Legacy ticket state `In Progress` is normalized to `Investigation` and `Completed` to `Closed`. This backfill is idempotent.

Before any application upgrade:

1. Create and verify a database backup.
2. Preserve the current application folder or Git commit used by the site.
3. Deploy the new EMS version.
4. Run `PREFLIGHT_WINDOWS.bat`.
5. Launch the app and verify Dashboard, Equipment, PM, Tickets, Qualification, Inventory and Documents.
6. If preflight reports schema incompatibility, stop. Do not operate against the database until a controlled migration is prepared.

## Backup and recovery

`BACKUP_WINDOWS.bat` creates a backup in `EMS_BACKUP_ROOT` when configured.

For SQLite, EMS uses the native SQLite backup API and verifies the result with `PRAGMA integrity_check`.

For PostgreSQL, EMS uses `pg_dump -Fc` and verifies the archive with `pg_restore --list`. PostgreSQL client tools must be available in PATH on the workstation/account that performs the backup.

A backup is not considered production-proven until a restore drill succeeds. Restore PostgreSQL backups into a separate scratch database using standard `pg_restore` procedures; never overwrite the live database while EMS clients are connected.

## Controlled files

The application normally opens linked files through temporary read-only copies. Controlled document revisions are SHA-256 fingerprinted. A controlled revision cannot be approved if the source file changed after registration, and effective controlled revisions are integrity-checked before opening.

Application read-only behavior does not replace SMB/NTFS permissions. Restrict direct write access to controlled-document folders at the file-server level.

## Release and qualification controls

Equipment operational status is a governed state machine. Master-data editing cannot directly change operational state or disposition.

Return-to-service release uses request, verification and independent approval. The approver cannot be the requester or verifier.

Equipment in `Qualification` state or disposition cannot be released without a current approved, non-expired qualification run. Qualification protocol revisions are frozen into each run. The executor cannot verify their own work and the verifier cannot perform final approval.

## Site acceptance

Before production sign-off, verify these workflows on the real site network:

- concurrent logins from at least two Windows workstations;
- equipment state transitions and conflict rejection;
- ticket investigation, resolution, independent verification and closure;
- PM execution with frozen specifications;
- PM deferral request and independent approval;
- meter/cycle-triggered PM creation;
- spare reservation and consumption;
- qualification execution through approval and release;
- controlled-document approval, supersession and integrity validation;
- backup creation and scratch restore;
- file-server evidence creation/opening;
- client restart and database-server restart recovery.

Automated CI already validates the core against SQLite, a real PostgreSQL service, and both PySide6 desktop shells on Windows. Site acceptance remains necessary because the actual LAN, SMB permissions, endpoint security and PostgreSQL deployment are environment-specific.
