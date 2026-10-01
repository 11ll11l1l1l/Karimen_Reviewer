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
│  ├─ ems.sqlite              initial shared checkpoint
│  ├─ ems-checkpoint-*.sqlite immutable periodic checkpoints
│  ├─ Updates/*.delta         compressed changed SQLite blocks
│  ├─ manifest.json           revision, checkpoint, update hashes and publisher
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

1. EMS checks the small shared manifest at most once every two seconds per workstation by default (`EMS_SYNC_POLL_SECONDS`). After a failed share read, automatic checks back off for `EMS_SYNC_ERROR_BACKOFF_SECONDS` (default 15 seconds) while local reads continue; F5 forces an immediate check.
2. If the shared revision is newer, the SQLAlchemy pool is disposed.
3. EMS copies its local replica (or the latest checkpoint when it fell behind) and applies only missing update files.
4. Each update and reconstructed result are verified with SHA-256. Corrupt, missing or partial updates leave the previous local database intact and retry on the next refresh.
5. The new local file is atomically replaced only after the complete chain passes verification.
6. The user reads from the local SQLite replica.

The normal UI therefore reads from a fast local file rather than continuously querying a database across SMB.

Automatic manifest polling is also non-blocking for normal UI reads. A background worker probes only the small shared manifest without holding the local database/session lock. If there is no new revision, the foreground never waits on SMB. When a newer revision is detected, installation is serialized against local sessions before the local replica is atomically replaced. The Admin synchronization status uses the last verified local marker; the explicit Pull Latest action performs a synchronous live refresh.

## Write flow

1. The user works against the current local replica.
2. Before committing a transaction, EMS acquires the shared `.write-lock` by atomic directory creation.
3. EMS re-reads `manifest.json`.
4. If the shared revision changed since the local transaction began, the transaction is cancelled before commit and the caller receives a conflict/retry error.
5. If the revision still matches, the local SQLite transaction commits.
6. EMS disposes local database connections.
7. Changed 4 KiB blocks are compressed into one immutable update file at a speed-oriented compression level. The update includes its resulting database hash. If the update exceeds `EMS_SYNC_MAX_DELTA_RATIO` (default 0.5) or the checkpoint interval is reached, EMS publishes a new immutable checkpoint instead.
8. `manifest.json` is replaced **last** with the incremented revision, file hashes and checkpoint pointer. Readers require a complete consecutive revision chain before applying updates.
9. The write lease is released. Old immutable updates and checkpoints are retained for at least a day.

This deliberately serializes committed writes. Reads remain local.

## Concurrent-use behavior

This topology favors correctness over last-writer-wins behavior.

- Two users can browse and prepare work concurrently.
- The database commit and its small publication phase are globally serialized to prevent concurrent stale writes.
- Existing record-level optimistic `version` checks still protect equipment, tickets and other governed records.
- If another workstation publishes during a local transaction, the stale transaction is rejected instead of overwriting newer data.
- A busy shared write lease waits briefly and then returns a retryable error rather than hanging indefinitely.
- A live publisher heartbeats its lease so a slow transfer is not mistaken for a dead lock. Remote abandoned leases are reclaimed after the heartbeat exceeds the configured stale threshold.

Default synchronization controls:

```text
EMS_SYNC_LOCK_TIMEOUT_SECONDS=15
EMS_SYNC_STALE_LOCK_SECONDS=300
EMS_SYNC_MAX_DELTA_RATIO=0.5
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
Each attachment gets a unique filename, allowing different users to write
separate files concurrently. The small database transaction that records an
attachment still takes the shared write lease. Independent file writes do not
require copying or refreshing the database.

The database stores the shared path, size and SHA-256 as before.

## Availability policy

The no-server topology is **network-folder dependent for writes**. It does not currently accept unsynchronized offline writes, because automatic multi-master merging of the current relational EMS model would risk silent data loss.

A workstation may keep its most recent local replica, but the production UI should not claim a write succeeded unless the shared revision is published.

## Performance envelope

Normal writes publish changed compressed blocks; readers pull only missing revisions. Full checkpoints bound replay cost and handle large database changes. This is a file-level delta, not a SQL merge: a stale writer still must retry. Large binary evidence remains outside the database.

Tuning: `EMS_SYNC_POLL_SECONDS=2`, `EMS_SYNC_ERROR_BACKOFF_SECONDS=15`, `EMS_SYNC_CHECKPOINT_INTERVAL=16` and `EMS_SYNC_MAX_DELTA_RATIO=0.5`. A forced refresh bypasses polling/backoff. Transient failed share reads keep the last verified local copy available; bulk equipment edits/imports commit through one local transaction and one shared publish instead of one publish per row. Writes still require the shared lease and must be retried after reconnection.

Local response-time tuning now also includes a 64 MiB SQLite page cache, 128 MiB memory mapping, in-memory temporary tables, a local busy timeout, and no SQLite pool pre-ping. These are configurable with `EMS_SQLITE_CACHE_MB`, `EMS_SQLITE_MMAP_MB`, and `EMS_SQLITE_BUSY_TIMEOUT_MS`. Multi-query UI refreshes reuse one read-only SQLAlchemy session, common operational filters have composite indexes, ticket/control dashboard reads avoid per-ticket lookups, and escalation evaluation is throttled by `EMS_ESCALATION_CHECK_SECONDS` (default 30 seconds). Legacy lifecycle, hierarchy, and configuration repair remains available on every launch for correctness, but now uses set-based queries instead of per-record lookups.

## Backup

`BACKUP_WINDOWS.bat` resolves the synchronized local replica and writes verified SQLite backups to `EMS_BACKUP_ROOT` (default: `<EMS_SHARED_ROOT>\Backups`).

Backups still require restore drills before production sign-off.

## Current implementation status

RC4-G foundation implements:

- per-workstation local replica selection;
- shared manifest/revision tracking;
- cross-workstation write lease;
- stale-write conflict rejection;
- atomic verified delta and checkpoint publishing;
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

Local response-time tuning also includes a 64 MiB SQLite page cache, 128 MiB memory mapping, in-memory temporary tables, a local busy timeout, and no SQLite pool pre-ping. These are configurable with `EMS_SQLITE_CACHE_MB`, `EMS_SQLITE_MMAP_MB`, and `EMS_SQLITE_BUSY_TIMEOUT_MS`. Multi-query UI refreshes reuse one read-only SQLAlchemy session, common operational filters have composite indexes, ticket/control dashboard reads avoid per-ticket lookups, and escalation evaluation is throttled by `EMS_ESCALATION_CHECK_SECONDS` (default 30 seconds).

The dashboard counter card set is produced by one SQL statement rather than one count query per card. Layout/map reads filter equipment and storage locations inside SQLite with building/floor/area indexes. Large Qt tables calculate a display digest and skip unchanged redraws; changed tables suspend painting, sorting, and signals while updating and reuse existing cells. Saving a layout is also batched: all moved equipment/storage positions plus the audit record commit atomically through one shared publish instead of one publish per node.
