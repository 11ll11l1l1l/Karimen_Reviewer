# Equipment Management System — Production Deployment Runbook

This runbook is for the Windows/PySide6 Equipment Management System under `equipment_manager/`.

## Production topology

The primary constrained deployment is **no-server / shared-network-folder mode**.

Every user runs EMS on their own Windows PC. Each workstation uses a private local SQLite replica; the shared SMB folder stores the authoritative synchronized snapshot, revision manifest, evidence/documents and backups. SQLite is never opened directly on SMB.

Configure every EMS workstation:

```bat
set EMS_DATA_MODE=network-folder
set EMS_SHARED_ROOT=\\FILESERVER\EquipmentManagement
```

Optional explicit roots:

```bat
set EMS_FILE_ROOT=\\FILESERVER\EquipmentManagement\Files
set EMS_BACKUP_ROOT=\\FILESERVER\EquipmentManagement\Backups
```

PostgreSQL is still supported when a future site has an always-on database host, but it is not required for this deployment.

See `NETWORK_FOLDER_ARCHITECTURE.md` for the exact read/write, locking, conflict and recovery flow.

## First production deployment

1. Create one normal Windows/SMB root such as `\\FILESERVER\EquipmentManagement`.
2. Grant the intended EMS users read/write/create/rename permissions on `SharedState`, `Files` and `Backups`; use tighter NTFS/SMB permissions for controlled-document folders as appropriate.
3. Set `EMS_DATA_MODE=network-folder` and `EMS_SHARED_ROOT` on every workstation.
4. Run `START_WINDOWS.bat` once on the first workstation to create the virtual environment and dependencies.
5. Run `PREFLIGHT_WINDOWS.bat`. Production rollout should not proceed with a FAIL result.
6. Launch EMS on the first workstation and create the first administrator. The first committed database becomes shared revision 1.
7. Launch a second workstation and confirm it pulls the same shared revision and users.
8. Configure roles and permission overrides.
9. Run one verified manual backup to the shared backup root.
10. Optionally run `INSTALL_DAILY_BACKUP_WINDOWS.bat` on the designated backup workstation.
11. Perform a restore drill into a separate scratch location before declaring the deployment protected.
12. Execute the M15 two-workstation concurrency/interruption scenarios before production sign-off.

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

In no-server mode, EMS first resolves the synchronized local replica and uses the native SQLite backup API. The backup is verified with `PRAGMA integrity_check` and defaults to `<EMS_SHARED_ROOT>\Backups`.

For optional PostgreSQL deployments, EMS uses `pg_dump -Fc` and verifies the archive with `pg_restore --list`.

A backup is not considered production-proven until a restore drill succeeds. Never replace the live shared snapshot manually while EMS clients are operating.

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
- client restart, temporary shared-folder interruption and reconnect recovery;

Automated CI validates the core against SQLite, optional PostgreSQL and both PySide6 desktop shells on Windows. Site acceptance remains necessary because the real SMB/LAN behavior, workstation endpoint controls and concurrent shared-folder timing are environment-specific.
