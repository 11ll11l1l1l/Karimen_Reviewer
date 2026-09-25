from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import time
import uuid
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
        data = self._read_json(self.manifest_path)
        if not data:
            if self.canonical_db.is_file():
                return {
                    "schema": self.MANIFEST_SCHEMA,
                    "revision": 0,
                    "sha256": _sha256(self.canonical_db),
                    "published_at": "",
                    "publisher": "",
                }
            return {"schema": self.MANIFEST_SCHEMA, "revision": 0, "sha256": ""}
        if data.get("schema") != self.MANIFEST_SCHEMA:
            raise SharedFolderUnavailable(
                f"Unsupported EMS shared manifest schema: {data.get('schema')!r}"
            )
        return data

    def local_revision(self) -> int:
        return int(self._read_json(self.replica_path).get("revision") or 0)

    def prepare_local_database(self) -> Path:
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.local_root.mkdir(parents=True, exist_ok=True)
        self._recover_pending_publish_if_possible()
        manifest = self._manifest()
        if self.canonical_db.is_file():
            expected_hash = str(manifest.get("sha256") or "")
            needs_copy = not self.local_db.is_file() or self.local_revision() != int(manifest.get("revision") or 0)
            if not needs_copy and expected_hash:
                try:
                    needs_copy = _sha256(self.local_db) != expected_hash
                except Exception:
                    needs_copy = True
            if needs_copy:
                self._pull_snapshot(manifest)
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

    def refresh_local(self, engine=None) -> bool:
        if self.pending_path.exists():
            self._recover_pending_publish_if_possible(engine=engine)
        manifest = self._manifest()
        if not self.canonical_db.is_file():
            return False
        revision = int(manifest.get("revision") or 0)
        if revision <= self.local_revision() and self.local_db.is_file():
            return False
        self._pull_snapshot(manifest, engine=engine)
        return True

    def _pull_snapshot(self, manifest: dict, engine=None) -> None:
        if not self.canonical_db.is_file():
            return
        if engine is not None:
            engine.dispose()
        _atomic_copy(self.canonical_db, self.local_db)
        expected_hash = str(manifest.get("sha256") or "")
        actual_hash = _sha256(self.local_db)
        if expected_hash and actual_hash != expected_hash:
            raise SharedFolderUnavailable(
                "Shared EMS snapshot hash mismatch. The local replica was not accepted."
            )
        normalized = dict(manifest)
        normalized["sha256"] = actual_hash
        self._write_replica_marker(normalized)

    def _write_replica_marker(self, manifest: dict) -> None:
        _atomic_json(
            self.replica_path,
            {
                "schema": self.MANIFEST_SCHEMA,
                "revision": int(manifest.get("revision") or 0),
                "sha256": str(manifest.get("sha256") or ""),
                "synced_at": _utc_now(),
                "source": str(self.canonical_db),
            },
        )

    def _lock_metadata(self) -> dict:
        return self._read_json(self.lock_dir / "owner.json")

    def _lock_is_stale(self) -> bool:
        meta = self._lock_metadata()
        created = str(meta.get("created_at") or "")
        if created:
            try:
                stamp = datetime.fromisoformat(created)
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - stamp).total_seconds()
                return age >= self.stale_lock_seconds
            except Exception:
                pass
        try:
            age = time.time() - self.lock_dir.stat().st_mtime
            return age >= self.stale_lock_seconds
        except Exception:
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
        while True:
            try:
                os.mkdir(self.lock_dir)
                _atomic_json(
                    self.lock_dir / "owner.json",
                    {
                        "workstation": self.workstation,
                        "pid": os.getpid(),
                        "created_at": _utc_now(),
                    },
                )
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
                raise SharedFolderUnavailable(f"Cannot acquire EMS shared-folder write lease: {exc}") from exc
        try:
            yield
        finally:
            shutil.rmtree(self.lock_dir, ignore_errors=True)

    @contextmanager
    def guarded_publish(self, engine=None):
        with self.write_lease():
            manifest = self._manifest()
            remote_revision = int(manifest.get("revision") or 0)
            base_revision = self.local_revision()
            if self.canonical_db.is_file() and remote_revision != base_revision:
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
            try:
                yield
                if engine is not None:
                    engine.dispose()
                self._publish_locked(base_revision)
            except Exception:
                raise

    def _publish_locked(self, base_revision: int) -> dict:
        if not self.local_db.is_file():
            raise SharedFolderUnavailable("Local EMS replica does not exist.")
        manifest = self._manifest()
        remote_revision = int(manifest.get("revision") or 0)
        if self.canonical_db.is_file() and remote_revision != int(base_revision):
            raise SharedFolderConflict(
                f"Shared EMS revision advanced to {remote_revision} before publish."
            )
        digest = _sha256(self.local_db)
        _atomic_copy(self.local_db, self.canonical_db)
        next_manifest = {
            "schema": self.MANIFEST_SCHEMA,
            "revision": remote_revision + 1,
            "sha256": digest,
            "size_bytes": self.local_db.stat().st_size,
            "published_at": _utc_now(),
            "publisher": self.workstation,
        }
        _atomic_json(self.manifest_path, next_manifest)
        self._write_replica_marker(next_manifest)
        try:
            self.pending_path.unlink()
        except FileNotFoundError:
            pass
        return next_manifest

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
                self._publish_locked(base_revision)
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
                self._pull_snapshot(manifest, engine=engine)

    def status(self) -> dict:
        manifest = self._manifest()
        return {
            "mode": "network-folder",
            "shared_root": str(self.shared_root),
            "canonical_db": str(self.canonical_db),
            "local_db": str(self.local_db),
            "shared_revision": int(manifest.get("revision") or 0),
            "local_revision": self.local_revision(),
            "publisher": str(manifest.get("publisher") or ""),
            "published_at": str(manifest.get("published_at") or ""),
            "pending_publish": self.pending_path.exists(),
        }
