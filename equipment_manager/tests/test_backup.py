import os
import tempfile
import unittest
from pathlib import Path

from backup import create_backup, verify_backup
from database import Database


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.source=str(Path(self.tmp.name)/"source.db")
        self.backup=str(Path(self.tmp.name)/"backup.db")
        self.url=f"sqlite:///{self.source}"
        self.db=Database(self.url)
        self.db.create_user("admin","Admin","very-strong-password","Administrator")
        self.db.save_equipment({"equipment_id":"ETCH-01","name":"Etcher"},user="admin")

    def tearDown(self):
        self.tmp.cleanup()

    def test_sqlite_backup_is_verified_and_readable(self):
        result=create_backup(self.url,self.backup)
        self.assertTrue(result["verified"])
        self.assertTrue(os.path.isfile(self.backup))
        self.assertGreater(result["size_bytes"],0)
        ok,detail=verify_backup(self.url,self.backup)
        self.assertTrue(ok,detail)
        restored=Database(f"sqlite:///{self.backup}")
        self.assertTrue(restored.has_users())
        self.assertEqual(restored.get_equipment("ETCH-01").name,"Etcher")

    def test_missing_backup_fails_verification(self):
        ok,detail=verify_backup(self.url,str(Path(self.tmp.name)/"missing.db"))
        self.assertFalse(ok)
        self.assertIn("not found",detail.lower())

    def test_in_memory_database_cannot_be_persistently_backed_up(self):
        db=Database("sqlite:///:memory:")
        with self.assertRaises(ValueError):
            create_backup(db.url,self.backup)


if __name__=="__main__":
    unittest.main()
