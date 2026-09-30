import json
import hashlib
import os
import sqlite3
import tempfile
import unittest
import zlib
from pathlib import Path

from network_workspace import SharedFolderConflict, SharedFolderUnavailable, SharedFolderWorkspace


def _write_value(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn=sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            "INSERT INTO probe(id,value) VALUES(1,?) "
            "ON CONFLICT(id) DO UPDATE SET value=excluded.value",
            (value,),
        )
        conn.commit()
    finally:
        conn.close()


def _read_value(path: Path) -> str:
    conn=sqlite3.connect(str(path))
    try:
        row=conn.execute("SELECT value FROM probe WHERE id=1").fetchone()
        return row[0] if row else ""
    finally:
        conn.close()


class SharedFolderWorkspaceTests(unittest.TestCase):
    def test_second_workstation_pulls_authoritative_snapshot_and_stale_write_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            shared=root/"share"
            a=SharedFolderWorkspace(shared,local_root=root/"pc-a",lock_timeout_seconds=1)
            b=SharedFolderWorkspace(shared,local_root=root/"pc-b",lock_timeout_seconds=1)

            a.prepare_local_database()
            _write_value(a.local_db,"initial")
            a.initialize_authoritative_if_missing()
            self.assertEqual(a.status()["shared_revision"],1)

            b.prepare_local_database()
            self.assertEqual(_read_value(b.local_db),"initial")
            self.assertEqual(b.local_revision(),1)

            with a.guarded_publish():
                _write_value(a.local_db,"from-a")
            self.assertEqual(a.status()["shared_revision"],2)

            with self.assertRaises(SharedFolderConflict):
                with b.guarded_publish():
                    _write_value(b.local_db,"stale-b")

            # The stale transaction helper itself does not roll back arbitrary
            # file edits made by this low-level test. A real Database session is
            # rejected before its SQLAlchemy commit and then refreshes on retry.
            b.refresh_local()
            self.assertEqual(_read_value(b.local_db),"from-a")
            self.assertEqual(b.local_revision(),2)

    def test_pending_publish_is_recovered_after_restart_when_shared_revision_did_not_advance(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            shared=root/"share"
            local=root/"pc-a"
            a=SharedFolderWorkspace(shared,local_root=local,lock_timeout_seconds=1)
            a.prepare_local_database()
            _write_value(a.local_db,"initial")
            a.initialize_authoritative_if_missing()

            _write_value(a.local_db,"committed-before-crash")
            a.pending_path.write_text(
                json.dumps(
                    {
                        "schema":a.MANIFEST_SCHEMA,
                        "base_revision":1,
                        "created_at":"2026-09-25T00:00:00+00:00",
                        "workstation":"pc-a",
                    }
                ),
                encoding="utf-8",
            )

            restarted=SharedFolderWorkspace(shared,local_root=local,lock_timeout_seconds=1)
            restarted.prepare_local_database()

            self.assertFalse(restarted.pending_path.exists())
            self.assertEqual(restarted.status()["shared_revision"],2)
            checkpoint = restarted.state_root / restarted._manifest()["checkpoint_file"]
            self.assertEqual(_read_value(checkpoint),"committed-before-crash")
            self.assertEqual(_read_value(restarted.local_db),"committed-before-crash")

    def test_large_replica_uses_small_update_files_and_incremental_pull(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            a=SharedFolderWorkspace(root/"share",local_root=root/"a")
            b=SharedFolderWorkspace(root/"share",local_root=root/"b")
            a.prepare_local_database()
            _write_value(a.local_db,"initial")
            with sqlite3.connect(a.local_db) as conn:
                conn.execute("CREATE TABLE padding (id INTEGER PRIMARY KEY, value BLOB)")
                conn.execute("INSERT INTO padding(value) VALUES (?)",(b"x"*1024*1024,))
            a.initialize_authoritative_if_missing()
            b.prepare_local_database()
            with a.guarded_publish():
                _write_value(a.local_db,"changed")
            manifest=a._manifest()
            self.assertEqual(len(manifest["deltas"]),1)
            self.assertTrue(a.base_path.is_file())
            self.assertEqual(a._publish_base_revision(),2)
            update=a.delta_root / manifest["deltas"][0]["file"]
            self.assertLess(update.stat().st_size, a.local_db.stat().st_size//10)
            self.assertTrue(b.refresh_local(force=True))
            self.assertEqual(_read_value(b.local_db),"changed")
            self.assertEqual(b.local_revision(),2)
            self.assertEqual(b._publish_base_revision(),2)

    def test_checkpoint_and_multiple_updates_restore_a_lagging_workstation(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            a=SharedFolderWorkspace(root/"share",local_root=root/"a")
            a.checkpoint_interval=2
            b=SharedFolderWorkspace(root/"share",local_root=root/"b")
            a.prepare_local_database()
            _write_value(a.local_db,"initial")
            with sqlite3.connect(a.local_db) as conn:
                conn.execute("CREATE TABLE padding (value BLOB)")
                conn.execute("INSERT INTO padding VALUES (?)",(b"x"*1024*1024,))
            a.initialize_authoritative_if_missing()
            b.prepare_local_database()
            for value in ("one","two","three","four"):
                with a.guarded_publish():
                    _write_value(a.local_db,value)
            self.assertGreater(a._manifest()["checkpoint_revision"],1)
            self.assertTrue(b.refresh_local(force=True))
            self.assertEqual(_read_value(b.local_db),"four")
            self.assertEqual(b.local_revision(),5)

    def test_restart_conflict_preserves_unsynchronized_database_before_pulling_new_shared_state(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            shared=root/"share"
            a=SharedFolderWorkspace(shared,local_root=root/"pc-a",lock_timeout_seconds=1)
            b=SharedFolderWorkspace(shared,local_root=root/"pc-b",lock_timeout_seconds=1)

            a.prepare_local_database()
            _write_value(a.local_db,"initial")
            a.initialize_authoritative_if_missing()
            b.prepare_local_database()

            _write_value(b.local_db,"pc-b-committed-locally")
            with sqlite3.connect(str(b.local_db)) as conn:
                conn.execute("INSERT INTO probe(id,value) VALUES(2,'unpublished-local-row')")
                conn.commit()
            b.pending_path.write_text(
                json.dumps(
                    {
                        "schema":b.MANIFEST_SCHEMA,
                        "base_revision":1,
                        "created_at":"2026-09-25T00:00:00+00:00",
                        "workstation":"pc-b",
                    }
                ),
                encoding="utf-8",
            )

            with a.guarded_publish():
                _write_value(a.local_db,"pc-a-newer-shared")
            self.assertEqual(a.status()["shared_revision"],2)

            restarted_b=SharedFolderWorkspace(shared,local_root=root/"pc-b",lock_timeout_seconds=1)
            restarted_b.prepare_local_database()

            conflicts=restarted_b.recovery_conflicts()
            self.assertEqual(len(conflicts),1)
            self.assertTrue(conflicts[0]["recovery_exists"])
            self.assertEqual(_read_value(Path(conflicts[0]["recovery_database"])),"pc-b-committed-locally")
            self.assertEqual(_read_value(restarted_b.local_db),"pc-a-newer-shared")
            with sqlite3.connect(str(restarted_b.local_db)) as conn:
                self.assertIsNone(conn.execute("SELECT id FROM probe WHERE id=2").fetchone())
            with sqlite3.connect(conflicts[0]["recovery_database"]) as conn:
                self.assertIsNotNone(conn.execute("SELECT id FROM probe WHERE id=2").fetchone())
            self.assertEqual(restarted_b.local_revision(),2)

    def test_status_exposes_recovery_count_and_paths(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            workspace=SharedFolderWorkspace(root/"share",local_root=root/"pc-a")
            workspace.recovery_root.mkdir(parents=True,exist_ok=True)
            recovery=workspace.recovery_root/"unsynced-test.sqlite"
            _write_value(recovery,"preserved")
            meta=workspace.recovery_root/"conflict-test.json"
            meta.write_text(
                json.dumps(
                    {
                        "detected_at":"2026-09-25T00:00:00+00:00",
                        "workstation":"pc-a",
                        "local_base_revision":3,
                        "shared_revision":4,
                        "recovery_database":str(recovery),
                    }
                ),
                encoding="utf-8",
            )

            status=workspace.status()
            self.assertEqual(status["recovery_conflicts"],1)
            self.assertEqual(Path(status["recovery_root"]),workspace.recovery_root)
            self.assertEqual(workspace.recovery_conflicts()[0]["shared_revision"],4)

    def test_corrupt_update_is_rejected_without_replacing_local_replica(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            a=SharedFolderWorkspace(root/"share",local_root=root/"a")
            b=SharedFolderWorkspace(root/"share",local_root=root/"b")
            a.prepare_local_database()
            _write_value(a.local_db,"initial")
            a.initialize_authoritative_if_missing()
            b.prepare_local_database()
            with a.guarded_publish():
                _write_value(a.local_db,"new-shared-value")
            manifest=a._manifest()
            (a.delta_root/manifest["deltas"][0]["file"]).write_bytes(b"truncated-network-write")

            self.assertFalse(b.refresh_local(force=True))
            self.assertIn("update file",b._last_refresh_error.lower())
            self.assertEqual(_read_value(b.local_db),"initial")
            self.assertEqual(b.local_revision(),1)

    def test_new_client_can_read_legacy_delta_from_an_older_workstation(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            a=SharedFolderWorkspace(root/"share",local_root=root/"a")
            b=SharedFolderWorkspace(root/"share",local_root=root/"b")
            a.prepare_local_database()
            _write_value(a.local_db,"initial")
            a.initialize_authoritative_if_missing()
            b.prepare_local_database()
            with a.guarded_publish():
                _write_value(a.local_db,"legacy-client-update")

            manifest=a._manifest()
            patch_path=a.delta_root/manifest["deltas"][0]["file"]
            payload=json.loads(zlib.decompress(patch_path.read_bytes()))
            payload.pop("format")
            payload.pop("block_size")
            payload.pop("sha256")
            patch_path.write_bytes(zlib.compress(json.dumps(payload,separators=(",",":")).encode(),6))
            manifest["deltas"][0]["sha256"]=hashlib.sha256(patch_path.read_bytes()).hexdigest()
            a.manifest_path.write_text(json.dumps(manifest),encoding="utf-8")

            self.assertTrue(b.refresh_local(force=True))
            self.assertEqual(_read_value(b.local_db),"legacy-client-update")
            self.assertEqual(b.local_revision(),2)

    def test_malformed_manifest_does_not_break_local_reads(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            workspace=SharedFolderWorkspace(root/"share",local_root=root/"pc")
            workspace.prepare_local_database()
            _write_value(workspace.local_db,"verified-local")
            workspace.initialize_authoritative_if_missing()
            manifest=workspace._manifest()
            manifest["deltas"]="not-a-list"
            workspace.manifest_path.write_text(json.dumps(manifest),encoding="utf-8")

            self.assertFalse(workspace.refresh_local(force=True))
            self.assertEqual(_read_value(workspace.local_db),"verified-local")

    def test_failed_manifest_poll_backs_off_automatic_reads(self):
        with tempfile.TemporaryDirectory() as root:
            workspace=SharedFolderWorkspace(Path(root)/"share",local_root=Path(root)/"pc")
            workspace.refresh_interval_seconds=0
            workspace.error_backoff_seconds=60
            calls={"count":0}

            def unavailable_manifest():
                calls["count"]+=1
                raise SharedFolderUnavailable("share offline")

            workspace._manifest=unavailable_manifest
            self.assertFalse(workspace.refresh_local())
            self.assertFalse(workspace.refresh_local())
            self.assertEqual(calls["count"],1)
            self.assertFalse(workspace.refresh_local(force=True))
            self.assertEqual(calls["count"],2)

    def test_manifest_read_failure_keeps_local_database_available(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            workspace=SharedFolderWorkspace(root/"share",local_root=root/"pc")
            workspace.prepare_local_database()
            _write_value(workspace.local_db,"local-copy")
            workspace.initialize_authoritative_if_missing()
            workspace.manifest_path.write_text("{truncated",encoding="utf-8")

            self.assertFalse(workspace.refresh_local(force=True))
            self.assertEqual(_read_value(workspace.local_db),"local-copy")
            self.assertIn("manifest",workspace._last_refresh_error.lower())

    def test_missing_delta_revision_does_not_publish_partial_replica(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            a=SharedFolderWorkspace(root/"share",local_root=root/"a")
            b=SharedFolderWorkspace(root/"share",local_root=root/"b")
            a.prepare_local_database()
            _write_value(a.local_db,"initial")
            a.initialize_authoritative_if_missing()
            b.prepare_local_database()
            for value in ("revision-two","revision-three"):
                with a.guarded_publish():
                    _write_value(a.local_db,value)
            manifest=a._manifest()
            removed=a.delta_root/manifest["deltas"][0]["file"]
            removed.unlink()

            self.assertFalse(b.refresh_local(force=True))
            self.assertIn("update file",b._last_refresh_error.lower())
            self.assertEqual(_read_value(b.local_db),"initial")
            self.assertEqual(b.local_revision(),1)

    def test_slow_live_writer_lock_is_not_reclaimed_while_owner_process_is_alive(self):
        with tempfile.TemporaryDirectory() as root:
            workspace=SharedFolderWorkspace(Path(root)/"share",local_root=Path(root)/"pc")
            workspace.state_root.mkdir(parents=True)
            workspace.lock_dir.mkdir()
            (workspace.lock_dir/"owner.json").write_text(
                json.dumps({
                    "workstation":workspace.workstation,
                    "pid":os.getpid(),
                    "created_at":"2020-01-01T00:00:00+00:00",
                    "heartbeat_at":"2020-01-01T00:00:00+00:00",
                }),
                encoding="utf-8",
            )
            self.assertFalse(workspace._lock_is_stale())


if __name__=="__main__":
    unittest.main()
