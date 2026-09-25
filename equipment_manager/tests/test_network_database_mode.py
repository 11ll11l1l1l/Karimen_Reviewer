import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select

from database import Database, Equipment
from network_workspace import SharedFolderConflict


def _shared_database(shared_root: Path, local_root: Path) -> Database:
    env={
        "EMS_DATA_MODE":"network-folder",
        "EMS_SHARED_ROOT":str(shared_root),
        "EMS_LOCAL_STATE_ROOT":str(local_root),
    }
    with patch.dict(os.environ,env,clear=False):
        os.environ.pop("EMS_DATABASE_URL",None)
        return Database()


class SharedFolderDatabaseIntegrationTests(unittest.TestCase):
    def test_two_database_instances_exchange_committed_records_without_opening_sqlite_on_share(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            shared=root/"share"
            db_a=_shared_database(shared,root/"pc-a")
            db_a.create_user("admin","Admin","very-strong-password","Administrator")
            db_a.save_equipment({"equipment_id":"ETCH-01","name":"Etcher A"},user="admin")

            db_b=_shared_database(shared,root/"pc-b")
            self.assertTrue(db_b.has_users())
            self.assertEqual(db_b.get_equipment("ETCH-01").name,"Etcher A")
            self.assertNotEqual(Path(db_a.shared_workspace.local_db),Path(db_a.shared_workspace.canonical_db))
            self.assertNotEqual(Path(db_b.shared_workspace.local_db),Path(db_b.shared_workspace.canonical_db))

            row_b=db_b.get_equipment("ETCH-01")
            db_b.save_equipment(
                {"equipment_id":"ETCH-01","name":"Etcher B"},
                expected_version=row_b.version,
                user="admin",
            )

            # db_a refreshes from the manifest at the start of its next session.
            self.assertEqual(db_a.get_equipment("ETCH-01").name,"Etcher B")
            self.assertEqual(
                db_a.shared_sync_status()["local_revision"],
                db_a.shared_sync_status()["shared_revision"],
            )

    def test_transaction_opened_before_another_workstation_publish_is_rejected_and_auto_refreshed(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            shared=root/"share"
            db_a=_shared_database(shared,root/"pc-a")
            db_a.create_user("admin","Admin","very-strong-password","Administrator")
            db_a.save_equipment({"equipment_id":"ETCH-01","name":"Initial"},user="admin")
            db_b=_shared_database(shared,root/"pc-b")

            with self.assertRaises(SharedFolderConflict):
                with db_b.session() as session_b:
                    row_b=session_b.scalar(select(Equipment).where(Equipment.equipment_id=="ETCH-01"))
                    row_b.name="B stale change"

                    row_a=db_a.get_equipment("ETCH-01")
                    db_a.save_equipment(
                        {"equipment_id":"ETCH-01","name":"A winning change"},
                        expected_version=row_a.version,
                        user="admin",
                    )
                    # db_b's guarded publish runs only after the body exits. It
                    # must observe db_a's newer shared revision and reject B.

            # Conflict handling closes/rolls back B then pulls the winning
            # snapshot before the exception reaches the UI.
            self.assertEqual(db_b.get_equipment("ETCH-01").name,"A winning change")
            status=db_b.shared_sync_status()
            self.assertEqual(status["local_revision"],status["shared_revision"])
            self.assertFalse(status["pending_publish"])


if __name__=="__main__":
    unittest.main()
