import os
import tempfile
import unittest
from datetime import datetime, timedelta
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
    def test_equipment_pm_and_calendar_are_visible_on_second_workstation(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            shared=root/"share"
            a=_shared_database(shared,root/"a")
            a.create_user("planner","Planner","strong-password-123","Equipment Engineer")
            a.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="planner")
            due=datetime(2026,10,10,9)
            task=a.create_equipment_pm("ETCH-01",{
                "pm_id":"PM-ETCH","name":"Chamber PM","schedule_type":"Interval",
                "frequency_value":30,"frequency_unit":"days","anchor_mode":"Original Due",
                "early_window_days":2,"estimated_hours":2.0,"active":True,
            },due,"planner")
            b=_shared_database(shared,root/"b")
            self.assertEqual(b.get_equipment("ETCH-01").name,"Etcher")
            self.assertEqual(b.get_pm_task(task.id).pm_id,"PM-ETCH")
            self.assertEqual(b.get_pm_task_schedule(task.id).scheduled_end_at,due+timedelta(hours=2))
            b.schedule_pm_task(task.id,"planner",start_at=due-timedelta(days=1),
                expected_task_version=b.get_pm_task(task.id).version)
            a.refresh_shared_state()
            self.assertEqual(a.get_pm_task(task.id).scheduled_date,due-timedelta(days=1))

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

            # Explicit refresh bypasses the bounded background manifest poll.
            self.assertTrue(db_a.refresh_shared_state())
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
