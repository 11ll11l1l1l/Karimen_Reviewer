# EMS No-Server Network-Folder Architecture

## Decision

The primary constrained deployment is **serverless at the application/database layer**:

- every user runs the Windows EMS application on their own PC;
- there is no always-on PostgreSQL/database/application server requirement;
- one normal SMB/network folder is the shared coordination and file layer;
- SQLite is used only as a **private local workstation replica** and is never opened directly on SMB;
- Supplied PostgreSQL support remains available for a future site that gains an always-on database host, but it is not required for this topology.

Environment:

```bat
set EMS_DATA_MODE=network-folder
set EMS_SHARED_ROOT=\\FILESERVER\EquipmentManagement
```

Optional overrides:

```bat
set EMS_LOCAL_STATE_ROOT=C:\Users\%USERNAME%\AppData\Local\EquipmentManagement
set EMS_FILE_ROOT=\\FILESERVER\EquipmentManagement\Files
set EMS_BACKUP_ROOT=\\FILESERVER\EquipmentManagement\Backups
```

## Folder layout

```text
\\FILESERVER\EquipmentManagement
├─ SharedState
│  ├─ ems.sqlite              authoritative synchronized snapshot
│  ├─ manifest.json           revision, SHA-256, publisher and publish time
│  └─ .write-lock\            short-lived cross-workstation write lease
├─ Files
│  ├─ Attachments
│  ├─ ControlledDocuments
│  └─ ...                     reports, layouts and reference material
└─ Backups
   └─ EMS_YYYYMMDD_HHMMSS.db
```

Each workstation also has private state under `%LOCALAPPDATA%\EquipmentManagement`:

```text
ems.sqlite                    active local SQLite replica
replica.json                  synchronized shared revision
pending_publish.json          crash-recovery marker for a committed write
Recovery\                     preserved unsynchronized conflict copies
```

## Read flow

1. EMS checks the shared manifest before opening a database session.
2. If the shared revision is newer, the SQLAlchemy pool is disposed.
3. The authoritative shared snapshot is copied into a temporary local file.
4. SHA-256 is verified against the shared manifest.
5. The local file is atomically replaced.
6. The user reads from the local SQLite replica.

The normal UI therefore reads from a fast local file rather than continuously querying a database across SMB.

## Write flow

1. The user works against the current local replica.
2. Before committing a transaction, EMS acquires the shared `.write-lock` by atomic directory creation.
3. EMS re-reads `manifest.json`.
4. If the shared revision changed since the local transaction began, the transaction is cancelled before commit and the caller receives a conflict/retry error.
5. If the revision still matches, the local SQLite transaction commits.
6. EMS disposes local database connections.
7. The committed local database is copied to a temporary file in `SharedState`.
8. The temporary file is atomically renamed to `ems.sqlite`.
9. `manifest.json` is replaced **last** with the incremented revision and new SHA-256.
10. The write lease is released.

This deliberately serializes committed writes. Reads remain local.

## Concurrent-use behavior

This topology favors correctness over last-writer-wins behavior.

- Two users can browse and prepare work concurrently.
- Only the short publish phase is globally serialized.
- Existing record-level optimistic `version` checks still protect equipment, tickets and other governed records.
- If another workstation publishes during a local transaction, the stale transaction is rejected instead of overwriting newer data.
- A busy shared write lease waits briefly and then returns a retryable error rather than hanging indefinitely.
- A lock older than the configured stale threshold may be reclaimed.

Default synchronization controls:

```text
EMS_SYNC_LOCK_TIMEOUT_SECONDS=15
EMS_SYNC_STALE_LOCK_SECONDS=300
```

## Crash and interruption recovery

Before local commit, EMS writes `pending_publish.json`.

If the application or PC stops after local commit but before shared publication:

- on restart, if the shared revision has not advanced, EMS runs SQLite `PRAGMA integrity_check` and publishes the pending local replica;
- if another workstation already advanced the shared revision, EMS preserves the unsynchronized local database under `Recovery\`, records a conflict JSON file, and resumes from the authoritative shared snapshot.

This prevents an old workstation from silently replacing newer shared state after a crash.

## Shared files and screenshots

Attachments, clipboard screenshots and other evidence are stored under `Files`.

Writes use a temporary sibling file followed by `os.replace`, so other workstations do not see a half-written screenshot/document with its final name.

The database stores the shared path, size and SHA-256 as before.

## Availability policy

The no-server topology is **network-folder dependent for writes**. It does not currently accept unsynchronized offline writes, because automatic multi-master merging of the current relational EMS model would risk silent data loss.

A workstation may keep its most recent local replica, but the production UI should not claim a write succeeded unless the shared revision is published.

## Performance envelope

The current implementation publishes a complete SQLite snapshot per committed transaction. This is simple and auditable and is appropriate for the initial plant deployment while the database remains moderate in size.

Future optimization, only if measured site data requires it:

- batch low-value audit/activity writes;
- maintain periodic full snapshots plus an append-only delta journal;
- move large binary evidence out of database state (already true);
- compact/archive old operational history while retaining governed audit records.

Do not introduce delta replication until the snapshot model is measured on the real LAN; correctness is the priority.

## Backup

`BACKUP_WINDOWS.bat` resolves the synchronized local replica and writes verified SQLite backups to `EMS_BACKUP_ROOT` (default: `<EMS_SHARED_ROOT>\Backups`).

Backups still require restore drills before production sign-off.

## Current implementation status

RC4-G foundation implements:

- per-workstation local replica selection;
- shared manifest/revision tracking;
- cross-workstation write lease;
- stale-write conflict rejection;
- atomic full-snapshot publishing;
- SHA-256 validation;
- pending-publish crash recovery;
- preserved recovery copies for irreconcilable restart conflicts;
- shared-root defaults for evidence and backup locations;
- atomic attachment/screenshot file publication;
- preflight visibility for local/shared revision state.

Remaining before production certification:

- focused automated synchronization/concurrency fixtures;
- two-workstation SMB timing and interruption tests;
- UI treatment for retryable shared-state conflicts;
- Recovery-folder reconciliation/admin workflow;
- LAN performance measurement at representative database size;
- consolidated Windows/PySide6 regression and packaging certification.
