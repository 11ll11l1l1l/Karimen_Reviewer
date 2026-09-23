import tempfile
import unittest
from pathlib import Path

from backup import create_backup
from database import Database
from recovery import run_restore_drill


class RecoveryDrillTests(unittest.TestCase):
    def test_sqlite_restore_drill_validates_and_records_result(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/"source.db"
            backup=Path(root)/"backup.db"
            url=f"sqlite:///{source}"
            db=Database(url)
            db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="seed")
            create_backup(url,str(backup))
            ok,detail=run_restore_drill(url,str(backup),"qa")
            self.assertTrue(ok,detail)
            drills=Database(url).list_recovery_drills()
            self.assertEqual(len(drills),1)
            self.assertTrue(drills[0].success)
            self.assertEqual(drills[0].database_type,"SQLite")
            self.assertIn("Scratch restore",drills[0].detail)

    def test_missing_backup_records_failed_drill(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/"source.db"
            url=f"sqlite:///{source}"
            Database(url)
            missing=Path(root)/"missing.db"
            ok,detail=run_restore_drill(url,str(missing),"qa")
            self.assertFalse(ok)
            drills=Database(url).list_recovery_drills()
            self.assertFalse(drills[0].success)


if __name__=="__main__":
    unittest.main()
