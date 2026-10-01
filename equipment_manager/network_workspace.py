from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import threading
import time
import uuid
import base64
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class SharedFolderConflict(RuntimeError):
    """Raised when the shared authoritative revision changed during a local write."""


class SharedFolderUnavailable(RuntimeError):
    """Raised when the shared workspace cannot be reached or locked safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    shutil.copy2(source, temp)
    os.replace(temp, destination)


class SharedFolderWorkspace:
    """
    Serverless EMS synchronization over a normal SMB/network folder.

    SQLite never runs directly on the network share. Each workstation uses a
    private local replica. The shared folder stores an authoritative snapshot
    plus a small manifest. Writes are serialized with an atomic directory lease,
    then the committed local SQLite file is published by atomic rename.

    This is deliberately conservative: a workstation may reject a write if the
    authoritative revision changes while its local transaction is open. That is
    safer than allowing silent last-writer-wins data loss.
    """

    MANIFEST_SCHEMA = "ems-shared-folder-v1"
    BLOCK_SIZE = 4096
    IO_RETRIES = 3

    def __init__(
        self,
        shared_root: str | Path,
        *,
        local_root: str | Path | None = None,
        lock_timeout_seconds: float = 15.0,
        stale_lock_seconds: float = 300.0,
    ):
        self.shared_root = Path(shared_root)
        self.state_root = self.shared_root / "SharedState"
        self.canonical_db = self.state_root / "ems.sqlite"
        self.delta_root = self.state_root / "Updates"
        self.manifest_path = self.state_root / "manifest.json"
        self.lock_dir = self.state_root / ".write-lock"

        if local_root is None:
            base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
            if base:
                local_root = Path(base) / "EquipmentManagement"
            else:
                local_root = Path.home() / ".equipment_management"
        self.local_root = Path(local_root)
        self.local_db = self.local_root / "ems.sqlite"
        self.replica_path = self.local_root / "replica.json"
        self.pending_path = self.local_root / "pending_publish.json"
        self.recovery_root = self.local_root / "Recovery"
        self.base_path = self.local_root / "publish_base.sqlite"
        self.base_meta_path = self.local_root / "publish_base.json"
        self.refresh_interval_seconds = max(0.0, float(os.getenv("EMS_SYNC_POLL_SECONDS", "2")))
        self.error_backoff_seconds = max(
            self.refresh_interval_seconds,
            max(1.0, float(os.getenv("EMS_SYNC_ERROR_BACKOFF_SECONDS", "15"))),
        )
        self.checkpoint_interval = max(2, int(os.getenv("EMS_SYNC_CHECKPOINT_INTERVAL", "16")))
        self.max_delta_ratio = min(0.9, max(0.05, float(os.getenv("EMS_SYNC_MAX_DELTA_RATIO", "0.5"))))
        self._last_refresh_error = ""
        self._last_manifest_check = 0.0
        self._next_manifest_attempt = 0.0
        self._last_verified_manifest: dict = {}

        self.lock_timeout_seconds = max(1.0, float(lock_timeout_seconds))
        self.stale_lock_seconds = max(30.0, float(stale_lock_seconds))
        self.workstation = socket.gethostname() or "unknown-workstation"
        self.local_root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "SharedFolderWorkspace":
        root = os.getenv("EMS_SHARED_ROOT", "").strip()
        if not root:
            raise SharedFolderUnavailable("EMS_SHARED_ROOT is required for network-folder mode.")
        local_root = os.getenv("EMS_LOCAL_STATE_ROOT", "").strip() or None
        lock_timeout = float(os.getenv("EMS_SYNC_LOCK_TIMEOUT_SECONDS", "15"))
        stale_lock = float(os.getenv("EMS_SYNC_STALE_LOCK_SECONDS", "300"))
        return cls(
            root,
            local_root=local_root,
            lock_timeout_seconds=lock_timeout,
            stale_lock_seconds=stale_lock,
        )

    def database_url(self) -> str:
        return f"sqlite:///{self.local_db.resolve().as_posix()}"

    def _read_json(self, path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _manifest(self) -> dict:
        last_error = None
        for attempt in range(self.IO_RETRIES):
            try:
                data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("manifest root must be an object")
                if data.get("schema") != self.MANIFEST_SCHEMA:
                    raise SharedFolderUnavailable(
                        f"Unsupported EMS shared manifest schema: {data.get('schema')!r}"
                    )
                try:
                    revision = int(data.get("revision") or 0)
                    deltas = data.get("deltas") or []
                    if revision < 0 or not isinstance(deltas, list):
                        raise ValueError("invalid revision or update list")
                    for item in deltas:
                        if not isinstance(item, dict) or int(item.get("revision") or 0) < 1:
                            raise ValueError("invalid update entry")
                        name = str(item.get("file") or "")
                        digest = str(item.get("sha256") or "")
                        if Path(name).name != name or len(digest) != 64:
                            raise ValueError("invalid update file name or checksum")
                        int(digest, 16)
                    data["revision"] = revision
                    data["deltas"] = deltas
                except (TypeError, ValueError) as exc:
                    raise SharedFolderUnavailable(f"Invalid EMS shared manifest: {exc}") from exc
                return data
            except SharedFolderUnavailable:
                raise
            except FileNotFoundError as exc:
                last_error = exc
                if attempt + 1 < self.IO_RETRIES:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                if self.canonical_db.is_file():
                    raise SharedFolderUnavailable("EMS shared manifest is missing; keeping local replica.") from exc
                return {"schema": self.MANIFEST_SCHEMA, "revision": 0, "sha256": ""}
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < self.IO_RETRIES:
                    time.sleep(0.05 * (attempt + 1))
        raise SharedFolderUnavailable(f"Cannot read EMS shared manifest: {last_error}")

    def _delta(self, before: Path, after: Path) -> tuple[bytes, str]:
        # Fixed SQLite-sized blocks keep ordinary updates small, with each result hashed.
        changes = []
        after_hash = hashlib.sha256()
        with before.open("rb") as old, after.open("rb") as new:
            index = 0
            while (current := new.read(self.BLOCK_SIZE)):
                after_hash.update(current)
                if current != old.read(self.BLOCK_SIZE):
                    changes.append([index, base64.b64encode(current).decode("ascii")])
                index += 1
        payload = {
            "format": "ems-block-delta-v2",
            "block_size": self.BLOCK_SIZE,
            "size": after.stat().st_size,
            "sha256": after_hash.hexdigest(),
            "blocks": changes,
        }
        return zlib.compress(json.dumps(payload, separators=(",", ":")).encode(), 3), after_hash.hexdigest()

    def _apply_delta(self, db: Path, patch: Path, *, verify_result: bool = True) -> None:
        try:
            data = json.loads(zlib.decompress(patch.read_bytes()))
        except Exception as exc:
            raise SharedFolderUnavailable(f"EMS update file is incomplete or corrupt: {exc}") from exc
        if not isinstance(data, dict):
            raise SharedFolderUnavailable("Unsupported EMS update format; full checkpoint required.")
        format_version = data.get("format", "ems-block-delta-v1")
        try:
            block_size = int(data.get("block_size") or self.BLOCK_SIZE)
        except (TypeError, ValueError) as exc:
            raise SharedFolderUnavailable("Invalid EMS update block size.") from exc
        if format_version not in {"ems-block-delta-v1", "ems-block-delta-v2"} or block_size != self.BLOCK_SIZE:
            raise SharedFolderUnavailable("Unsupported EMS update format; full checkpoint required.")
        try:
            blocks = data["blocks"]
            size = int(data["size"])
            if size < 0 or not isinstance(blocks, list):
                raise ValueError("invalid update size or block list")
            with db.open("r+b") as handle:
                for index, content in blocks:
                    index = int(index)
                    block = base64.b64decode(content, validate=True)
                    if index < 0 or len(block) > self.BLOCK_SIZE:
                        raise ValueError("invalid update block")
                    handle.seek(index * self.BLOCK_SIZE)
                    handle.write(block)
                handle.truncate(size)
        except Exception as exc:
            raise SharedFolderUnavailable(f"EMS update file is incomplete or corrupt: {exc}") from exc
        if format_version == "ems-block-delta-v2" and verify_result and _sha256(db) != str(data.get("sha256") or ""):
            raise SharedFolderUnavailable("EMS update result hash mismatch; local replica was not accepted.")

    def local_revision(self) -> int:
        return int(self._read_json(self.replica_path).get("revision") or 0)

    def _publish_base_revision(self) -> int:
        meta = self._read_json(self.base_meta_path)
        try:
            return int(meta.get("revision"))
        except (TypeError, ValueError):
            return -1

    def _sync_publish_base(self, manifest: dict) -> None:
        """Keep an exact local baseline for the revision used to build deltas."""
        if not self.local_db.is_file():
            return
        _atomic_copy(self.local_db, self.base_path)
        _atomic_json(
            self.base_meta_path,
            {
                "schema": self.MANIFEST_SCHEMA,
                "revision": int(manifest.get("revision") or 0),
                "sha256": str(manifest.get("sha256") or ""),
                "synced_at": _utc_now(),
            },
        )

    def prepare_local_database(self) -> Path:
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.local_root.mkdir(parents=True, exist_ok=True)
        try:
            self._recover_pending_publish_if_possible()
            manifest = self._manifest()
        except SharedFolderUnavailable:
            if self.local_db.is_file():
                return self.local_db
            raise
        if self.canonical_db.is_file():
            expected_hash = str(manifest.get("sha256") or "")
            if not self.local_db.is_file() or self.local_revision() != int(manifest.get("revision") or 0) or (expected_hash and _sha256(self.local_db) != expected_hash):
                try:
                    self._pull_snapshot(manifest)
                except (SharedFolderUnavailable, OSError) as exc:
                    self._last_refresh_error = str(exc)
                    if not self.local_db.is_file():
                        raise SharedFolderUnavailable(f"Cannot initialize local EMS replica: {exc}") from exc
        if self.local_db.is_file() and self._publish_base_revision() != self.local_revision():
            try:
                self._sync_publish_base(manifest)
            except OSError:
                # A missing/stale local baseline only forces the next write to use
                # a full checkpoint; it must not make the local read replica unusable.
                pass
        return self.local_db
    def initialize_authoritative_if_missing(self, engine=None) -> None:
        if self.canonical_db.is_file() and self.manifest_path.is_file():
            return
        if not self.local_db.is_file():
            return
        with self.write_lease():
            if self.canonical_db.is_file() and self.manifest_path.is_file():
                self._pull_snapshot(self._manifest(), engine=engine)
                return
            if engine is not None:
                engine.dispose()
            digest = _sha256(self.local_db)
            _atomic_copy(self.local_db, self.canonical_db)
            manifest = {
                "schema": self.MANIFEST_SCHEMA,
                "revision": 1,
                "sha256": digest,
                "size_bytes": self.local_db.stat().st_size,
                "published_at": _utc_now(),
                "publisher": self.workstation,
            }
            _atomic_json(self.manifest_path, manifest)
            self._write_replica_marker(manifest)
            self._sync_publish_base(manifest)
    def publish_startup_changes(self, engine=None) -> bool:
        """Publish schema/bootstrap changes made locally during application startup."""
        if not self.local_db.is_file():
            return False
        if not self.canonical_db.is_file():
            self.initialize_authoritative_if_missing(engine=engine)
            return True
        manifest = self._manifest()
        expected = str(manifest.get("sha256") or "")
        actual = _sha256(self.local_db)
        if expected and actual == expected:
            return False
        with self.guarded_publish(engine=engine):
            pass
        return True

    def refresh_due(self) -> bool:
        """Return whether an automatic refresh is due without touching SMB."""
        if self.pending_path.exists():
            return True
        now=time.monotonic()
        if now<self._next_manifest_attempt:
            return False
        return now-self._last_manifest_check>=self.refresh_interval_seconds

    def probe_remote(self, *, force: bool = False) -> dict | None:
        """Read only the small shared manifest; never replace the local database."""
        now=time.monotonic()
        if not force:
            if now<self._next_manifest_attempt:
                return None
            if now-self._last_manifest_check<self.refresh_interval_seconds:
                return None
        self._last_manifest_check=now
        try:
            manifest=self._manifest()
        except SharedFolderUnavailable as exc:
            self._last_refresh_error=str(exc)
            self._next_manifest_attempt=now+self.error_backoff_seconds
            return None
        self._last_verified_manifest=dict(manifest)
        self._next_manifest_attempt=0.0
        self._last_refresh_error=""
        if int(manifest.get("revision") or 0)<=self.local_revision():
            return None
        return manifest

    def apply_remote_manifest(self, manifest: dict, engine=None) -> bool:
        """Install an already-verified newer manifest under the caller's DB lock."""
        if int(manifest.get("revision") or 0)<=self.local_revision():
            return False
        try:
            self._pull_snapshot(manifest,engine=engine)
            return True
        except (SharedFolderUnavailable,OSError) as exc:
            self._last_refresh_error=str(exc)
            self._next_manifest_attempt=time.monotonic()+self.error_backoff_seconds
            if self.local_db.is_file():
                return False
            raise SharedFolderUnavailable(f"Cannot initialize local EMS replica: {exc}") from exc

    def refresh_local(self, engine=None, *, force: bool = False) -> bool:
        if self.pending_path.exists():
            try:
                self._recover_pending_publish_if_possible(engine=engine)
            except SharedFolderUnavailable as exc:
                self._last_refresh_error = str(exc)
                if self.local_db.is_file():
                    return False
                raise
        manifest=self.probe_remote(force=force)
        if manifest is None:
            return False
        return self.apply_remote_manifest(manifest,engine=engine)
    def _pull_snapshot(self, manifest: dict, engine=None, *, force_checkpoint: bool = False) -> None:
        if engine is not None:
            engine.dispose()
        checkpoint_revision = int(manifest.get("checkpoint_revision") or manifest.get("revision") or 0)
        checkpoint_name = str(manifest.get("checkpoint_file") or "ems.sqlite")
        if Path(checkpoint_name).name != checkpoint_name:
            raise SharedFolderUnavailable("Invalid EMS checkpoint path.")
        local_revision = self.local_revision()
        temp = self.local_db.with_name(f".{self.local_db.name}.{uuid.uuid4().hex}.tmp")
        try:
            if (not force_checkpoint and self.local_db.is_file()
                    and checkpoint_revision <= local_revision < int(manifest.get("revision") or 0)):
                shutil.copy2(self.local_db, temp)
                start = local_revision
            else:
                shutil.copy2(self.state_root / checkpoint_name, temp)
                start = checkpoint_revision
            target_revision = int(manifest.get("revision") or 0)
            expected_revisions = list(range(start + 1, target_revision + 1))
            available = {int(item["revision"]): item for item in manifest.get("deltas", [])}
            if any(revision not in available for revision in expected_revisions):
                raise SharedFolderUnavailable("EMS update history is incomplete; retry after a checkpoint is published.")
            for revision in expected_revisions:
                item = available[revision]
                patch = self.delta_root / item["file"]
                try:
                    patch_hash = _sha256(patch)
                except OSError as exc:
                    raise SharedFolderUnavailable(f"EMS update file is unavailable: {item['file']}") from exc
                if patch_hash != item["sha256"]:
                    raise SharedFolderUnavailable("EMS update file hash mismatch.")
                self._apply_delta(temp, patch, verify_result=revision == target_revision)
            expected_hash = str(manifest.get("sha256") or "")
            actual_hash = _sha256(temp)
            if expected_hash and actual_hash != expected_hash:
                raise SharedFolderUnavailable("Shared EMS update chain hash mismatch.")
            os.replace(temp, self.local_db)
        finally:
            temp.unlink(missing_ok=True)
        normalized = dict(manifest)
        normalized["sha256"] = actual_hash
        self._write_replica_marker(normalized)
        self._sync_publish_base(normalized)
        self._last_refresh_error = ""
    def _write_replica_marker(self, manifest: dict) -> None:
        normalized=dict(manifest)
        self._last_verified_manifest=normalized
        _atomic_json(
            self.replica_path,
            {
                "schema": self.MANIFEST_SCHEMA,
                "revision": int(normalized.get("revision") or 0),
                "sha256": str(normalized.get("sha256") or ""),
                "synced_at": _utc_now(),
                "source": str(self.canonical_db),
                "publisher": str(normalized.get("publisher") or ""),
                "published_at": str(normalized.get("published_at") or ""),
                "checkpoint_file": str(normalized.get("checkpoint_file") or "ems.sqlite"),
            },
        )
    def _lock_metadata(self) -> dict:
        return self._read_json(self.lock_dir / "owner.json")

    def _lock_is_stale(self) -> bool:
        meta = self._lock_metadata()
        owner = str(meta.get("workstation") or "")
        try:
            owner_pid = int(meta.get("pid") or 0)
        except (TypeError, ValueError):
            owner_pid = 0
        # A remote owner cannot be probed safely, but its heartbeat distinguishes
        # an active slow transfer from a dead/stalled lock holder.
        heartbeat = str(meta.get("heartbeat_at") or meta.get("created_at") or "")
        created = str(meta.get("created_at") or "")
        if heartbeat:
            try:
                stamp = datetime.fromisoformat(heartbeat)
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - stamp).total_seconds()
                if owner == self.workstation and owner_pid:
                    if self._pid_is_alive(owner_pid):
                        return False
                    return True
                return age >= self.stale_lock_seconds
            except Exception:
                pass
        try:
            age = time.time() - self.lock_dir.stat().st_mtime
            return age >= self.stale_lock_seconds
        except Exception:
            return False

    @staticmethod
    def _pid_is_alive(pid: int) -> bool:
        if pid == os.getpid():
            return True
        if os.name == "nt":
            try:
                import ctypes
                process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                if not process:
                    return False
                ctypes.windll.kernel32.CloseHandle(process)
                return True
            except Exception:
                return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False

    def _break_stale_lock(self) -> bool:
        if not self.lock_dir.exists() or not self._lock_is_stale():
            return False
        stale = self.state_root / f".stale-write-lock-{uuid.uuid4().hex}"
        try:
            os.replace(self.lock_dir, stale)
        except Exception:
            return False
        shutil.rmtree(stale, ignore_errors=True)
        return True

    @contextmanager
    def write_lease(self):
        self.state_root.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.lock_timeout_seconds
        heartbeat_stop = threading.Event()
        heartbeat_thread = None
        while True:
            acquired = False
            try:
                os.mkdir(self.lock_dir)
                acquired = True
                _atomic_json(
                    self.lock_dir / "owner.json",
                    {
                        "workstation": self.workstation,
                        "pid": os.getpid(),
                        "created_at": _utc_now(),
                        "heartbeat_at": _utc_now(),
                    },
                )
                def heartbeat():
                    interval = max(2.0, min(15.0, self.stale_lock_seconds / 4))
                    owner_path = self.lock_dir / "owner.json"
                    while not heartbeat_stop.wait(interval):
                        current = self._lock_metadata()
                        if current.get("workstation") != self.workstation or int(current.get("pid") or 0) != os.getpid():
                            return
                        current["heartbeat_at"] = _utc_now()
                        try:
                            _atomic_json(owner_path, current)
                        except OSError:
                            # A brief SMB interruption must not abort the protected write.
                            continue
                heartbeat_thread = threading.Thread(target=heartbeat, name="ems-share-lock-heartbeat", daemon=True)
                heartbeat_thread.start()
                break
            except FileExistsError:
                if self._break_stale_lock():
                    continue
                if time.monotonic() >= deadline:
                    owner = self._lock_metadata()
                    raise SharedFolderUnavailable(
                        "EMS shared state is busy with another write"
                        + (f" from {owner.get('workstation')}" if owner.get("workstation") else "")
                        + ". Retry the operation."
                    )
                time.sleep(0.2)
            except OSError as exc:
                if acquired:
                    shutil.rmtree(self.lock_dir, ignore_errors=True)
                raise SharedFolderUnavailable(f"Cannot acquire EMS shared-folder write lease: {exc}") from exc
        try:
            yield
        finally:
            heartbeat_stop.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=1)
            owner = self._lock_metadata()
            if owner.get("workstation") == self.workstation and int(owner.get("pid") or 0) == os.getpid():
                shutil.rmtree(self.lock_dir, ignore_errors=True)

    @contextmanager
    def guarded_publish(self, engine=None):
        published_manifest = None
        with self.write_lease():
            manifest = self._manifest()
            remote_revision = int(manifest.get("revision") or 0)
            base_revision = self.local_revision()
            if remote_revision != base_revision:
                raise SharedFolderConflict(
                    f"Shared EMS data changed from revision {base_revision} to {remote_revision}. "
                    "The local transaction was cancelled; retry on the refreshed data."
                )
            _atomic_json(
                self.pending_path,
                {
                    "schema": self.MANIFEST_SCHEMA,
                    "base_revision": base_revision,
                    "created_at": _utc_now(),
                    "workstation": self.workstation,
                },
            )
            completed_local_commit = False
            try:
                yield
                completed_local_commit = True
                if engine is not None:
                    engine.dispose()
                published_manifest = self._publish_locked(base_revision)
            except Exception:
                if not completed_local_commit:
                    try:
                        self.pending_path.unlink()
                    except FileNotFoundError:
                        pass
                raise
        if published_manifest is not None:
            # Local-only baseline maintenance happens after releasing the shared
            # lease so large databases do not block other workstations needlessly.
            self._sync_publish_base(published_manifest)
    def _prepare_publish(self, base_revision: int) -> dict:
        """Compute local hashing/compression from an exact revision baseline."""
        if not self.local_db.is_file():
            raise SharedFolderUnavailable("Local EMS replica does not exist.")
        if self.base_path.is_file() and self._publish_base_revision() == int(base_revision):
            patch, digest = self._delta(self.base_path, self.local_db)
        else:
            # If the baseline was lost or is from another revision, publish a
            # checkpoint rather than risk constructing a delta from stale bytes.
            digest = _sha256(self.local_db)
            patch = b""
        return {"digest": digest, "patch": patch, "size_bytes": self.local_db.stat().st_size}
    def _publish_locked(self, base_revision: int, prepared: dict | None = None) -> dict:
        if prepared is None:
            prepared = self._prepare_publish(base_revision)
        manifest = self._manifest()
        remote_revision = int(manifest.get("revision") or 0)
        if remote_revision != int(base_revision):
            raise SharedFolderConflict(
                f"Shared EMS revision advanced to {remote_revision} before publish."
            )
        digest = prepared["digest"]
        deltas = list(manifest.get("deltas") or [])
        checkpoint_revision = int(manifest.get("checkpoint_revision") or remote_revision)
        patch = prepared["patch"]
        checkpoint = (not patch or len(deltas) >= self.checkpoint_interval
                      or len(patch) >= int(prepared["size_bytes"] * self.max_delta_ratio))
        if checkpoint:
            checkpoint_file = f"ems-checkpoint-{remote_revision + 1:012d}-{uuid.uuid4().hex}.sqlite"
            _atomic_copy(self.local_db, self.state_root / checkpoint_file)
            checkpoint_revision = remote_revision + 1
            deltas = []
        else:
            checkpoint_file = str(manifest.get("checkpoint_file") or "ems.sqlite")
        if not checkpoint:
            self.delta_root.mkdir(parents=True, exist_ok=True)
            name = f"{remote_revision + 1:012d}-{uuid.uuid4().hex}.delta"
            path = self.delta_root / name
            temp = path.with_suffix(".tmp")
            temp.write_bytes(patch)
            os.replace(temp, path)
            deltas.append({"revision": remote_revision + 1, "file": name, "sha256": _sha256(path)})
        next_manifest = {
            "schema": self.MANIFEST_SCHEMA,
            "revision": remote_revision + 1,
            "sha256": digest,
            "size_bytes": prepared["size_bytes"],
            "published_at": _utc_now(),
            "publisher": self.workstation,
            "checkpoint_revision": checkpoint_revision,
            "checkpoint_file": checkpoint_file,
            "deltas": deltas,
        }
        _atomic_json(self.manifest_path, next_manifest)
        self._write_replica_marker(next_manifest)
        try:
            self.pending_path.unlink()
        except FileNotFoundError:
            pass
        if checkpoint:
            try:
                self._prune_old_updates(next_manifest)
            except OSError:
                pass  # Cleanup must never turn a committed write into a failure.
        self._last_verified_manifest=dict(next_manifest)
        self._last_manifest_check=time.monotonic()
        self._next_manifest_attempt=0.0
        return next_manifest
    def _prune_old_updates(self, manifest: dict) -> None:
        # Keep old manifests' immutable files available for slow readers and
        # interrupted clients. Collect only files older than one day.
        cutoff = time.time() - 86400
        keep = {item["file"] for item in manifest.get("deltas", [])}
        if self.delta_root.is_dir():
            for path in self.delta_root.glob("*.delta"):
                if path.name not in keep and path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
        active = str(manifest.get("checkpoint_file") or "ems.sqlite")
        for path in self.state_root.glob("ems-checkpoint-*.sqlite"):
            if path.name != active and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)

    def _recover_pending_publish_if_possible(self, engine=None) -> None:
        pending = self._read_json(self.pending_path)
        if not pending:
            return
        if not self.local_db.is_file():
            try:
                self.pending_path.unlink()
            except FileNotFoundError:
                pass
            return

        with self.write_lease():
            manifest = self._manifest()
            remote_revision = int(manifest.get("revision") or 0)
            base_revision = int(pending.get("base_revision") or 0)
            if remote_revision == base_revision + 1 and manifest.get("sha256") == _sha256(self.local_db):
                self._write_replica_marker(manifest)
                self._sync_publish_base(manifest)
                self.pending_path.unlink(missing_ok=True)
                return
            if remote_revision == base_revision:
                if engine is not None:
                    engine.dispose()
                conn = sqlite3.connect(str(self.local_db))
                try:
                    result = conn.execute("PRAGMA integrity_check").fetchone()
                finally:
                    conn.close()
                if not result or result[0] != "ok":
                    raise SharedFolderUnavailable("Pending local EMS replica failed SQLite integrity_check.")
                prepared = self._prepare_publish(base_revision)
                recovered_manifest = self._publish_locked(base_revision, prepared)
                self._sync_publish_base(recovered_manifest)
                return

            self.recovery_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recovery = self.recovery_root / f"unsynced-{stamp}-{self.workstation}.sqlite"
            _atomic_copy(self.local_db, recovery)
            conflict = {
                "schema": self.MANIFEST_SCHEMA,
                "detected_at": _utc_now(),
                "workstation": self.workstation,
                "local_base_revision": base_revision,
                "shared_revision": remote_revision,
                "recovery_database": str(recovery),
            }
            _atomic_json(self.recovery_root / f"conflict-{stamp}.json", conflict)
            try:
                self.pending_path.unlink()
            except FileNotFoundError:
                pass
            if self.canonical_db.is_file():
                self._pull_snapshot(manifest, engine=engine, force_checkpoint=True)
    def recovery_conflicts(self) -> list[dict]:
        rows: list[dict] = []
        if not self.recovery_root.is_dir():
            return rows
        for meta_path in sorted(self.recovery_root.glob("conflict-*.json"), reverse=True):
            payload = self._read_json(meta_path)
            if not payload:
                continue
            recovery_path = Path(str(payload.get("recovery_database") or ""))
            rows.append(
                {
                    "detected_at": str(payload.get("detected_at") or ""),
                    "workstation": str(payload.get("workstation") or ""),
                    "local_base_revision": int(payload.get("local_base_revision") or 0),
                    "shared_revision": int(payload.get("shared_revision") or 0),
                    "recovery_database": str(recovery_path),
                    "recovery_exists": recovery_path.is_file(),
                    "metadata_path": str(meta_path),
                }
            )
        return rows

    def status(self, *, live: bool = True) -> dict:
        if live:
            manifest=self._manifest()
            self._last_verified_manifest=dict(manifest)
        else:
            manifest=dict(self._last_verified_manifest or self._read_json(self.replica_path))
            if not manifest:
                manifest={
                    "schema":self.MANIFEST_SCHEMA,
                    "revision":self.local_revision(),
                    "publisher":"",
                    "published_at":"",
                    "checkpoint_file":"ems.sqlite",
                }
        return {
            "mode": "network-folder",
            "shared_root": str(self.shared_root),
            "canonical_db": str(self.state_root / str(manifest.get("checkpoint_file") or "ems.sqlite")),
            "local_db": str(self.local_db),
            "shared_revision": int(manifest.get("revision") or 0),
            "local_revision": self.local_revision(),
            "publisher": str(manifest.get("publisher") or ""),
            "published_at": str(manifest.get("published_at") or ""),
            "pending_publish": self.pending_path.exists(),
            "recovery_root": str(self.recovery_root),
            "recovery_conflicts": len(self.recovery_conflicts()),
            "last_refresh_error": self._last_refresh_error,
            "status_source": "live" if live else "last-verified",
        }