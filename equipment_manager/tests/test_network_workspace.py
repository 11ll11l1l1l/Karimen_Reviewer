import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from network_workspace import SharedFolderConflict, SharedFolderWorkspace


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
            self.assertEqual(_read_value(restarted.canonical_db),"committed-before-crash")
            self.assertEqual(_read_value(restarted.local_db),"committed-before-crash")

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


if __name__=="__main__":
    unittest.main()
